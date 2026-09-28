# -*- coding: utf-8 -*-
"""
通知服务业务逻辑
实现通道管理及多通道消息分发

安全说明：
- 所有出站目标（webhook/钉钉/飞书/企业微信/SMTP 主机）在发送前都会经过
  app.utils.outbound 的 SSRF 校验；校验失败会记录到 NotificationLog.error_message，
  不会向调用方抛出 500。
- 渠道配置以 Fernet 加密存储；更新配置时支持 "******"/null/空字符串回填旧值，
  "__DELETE__" 显式删除字段。
"""

import json
import time
import ssl
import hmac
import hashlib
import base64
import asyncio
import smtplib
from concurrent.futures import ThreadPoolExecutor
from email.mime.text import MIMEText
from email.header import Header
from typing import List, Optional, Tuple, Dict, Any, Set
from urllib.parse import quote_plus

import httpx
from loguru import logger
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_channel import NotificationChannel
from app.models.notification_log import NotificationLog
from app.schemas.notification import NotificationSendRequest, NotificationSendResponse
from app.utils.encryption import encrypt_password, decrypt_password
from app.utils.outbound import (
    OFFICIAL_WEBHOOK_HOSTS,
    validate_outbound_host,
    validate_outbound_url,
)


# 后台发送任务集合：持有 task 强引用，防止被 GC 回收；完成时自动移除
_bg_tasks: Set[asyncio.Task] = set()

# SMTP 专用线程池（同步阻塞发送不占用默认 executor）
_smtp_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="smtp")

# 配置更新时的删除标记
CONFIG_DELETE_MARKER = "__DELETE__"
# 前端回显的掩码占位符：更新时代表“保持原值”
CONFIG_MASK_PLACEHOLDER = "******"


def get_pending_task_count() -> int:
    """当前仍在执行/待执行的后台发送任务数（供测试与监控使用）"""
    return len(_bg_tasks)


def encode_dingtalk_sign(sign: str) -> str:
    """
    钉钉签名 URL 编码。

    签名是 base64 字符串，包含 '+'、'/'、'=' 等字符；'+' 必须编码为 %2B，
    否则在部分网关/客户端会被解析成空格，导致偶发 310000 签名错误。
    """
    return quote_plus(sign)


class NotificationService:
    """通知管理及发送逻辑"""

    # ==================== 通道管理 (CRUD) ====================

    async def get_user_channels(self, db: AsyncSession, user_id: int) -> List[NotificationChannel]:
        """获取用户的所有通知通道"""
        stmt = select(NotificationChannel).where(NotificationChannel.user_id == user_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_channel_by_id(self, db: AsyncSession, user_id: int, channel_id: int) -> Optional[NotificationChannel]:
        """根据通道ID获取特定通道"""
        stmt = select(NotificationChannel).where(
            NotificationChannel.id == channel_id, NotificationChannel.user_id == user_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_channel(
        self, db: AsyncSession, user_id: int, name: str, channel_type: str, config: Dict[str, Any], is_active: bool = True
    ) -> NotificationChannel:
        """创建通知通道"""
        # 加密序列化配置
        config_str = json.dumps(config, ensure_ascii=False)
        encrypted_config = encrypt_password(config_str)

        channel = NotificationChannel(
            user_id=user_id,
            name=name,
            channel_type=channel_type,
            config_json=encrypted_config,
            is_active=is_active,
        )
        db.add(channel)
        await db.commit()
        await db.refresh(channel)
        return channel

    @staticmethod
    def _merge_config_update(old_config: Dict[str, Any], new_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并渠道配置更新。

        规则（前端被重写后以此为准）：
        - 值为 None / 空字符串 / "******" 的字段：保留 old_config 中旧值（未出现过则忽略）；
        - 值为 "__DELETE__" 的字段：从结果中移除；
        - 其余值照写；嵌套 dict（如 webhook headers）递归应用同样规则。
        """
        merged: Dict[str, Any] = dict(old_config or {})
        for key, value in (new_config or {}).items():
            if isinstance(value, str) and value == CONFIG_DELETE_MARKER:
                merged.pop(key, None)
                continue
            if isinstance(value, dict):
                old_value = merged.get(key)
                base = old_value if isinstance(old_value, dict) else {}
                merged[key] = NotificationService._merge_config_update(base, value)
                continue
            if value is None or (isinstance(value, str) and value in ("", CONFIG_MASK_PLACEHOLDER)):
                # 回填旧值（merged 中已有旧值则保留）；若旧配置本就没有该字段则不写入
                continue
            merged[key] = value
        return merged

    async def update_channel(
        self,
        db: AsyncSession,
        user_id: int,
        channel_id: int,
        name: Optional[str] = None,
        channel_type: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[NotificationChannel]:
        """
        更新通知通道。

        config 采用“增量合并”语义：null/""/"******" 保持旧值，"__DELETE__" 删除字段。
        旧配置解密失败时抛出 ValueError，由路由层返回明确错误。
        """
        channel = await self.get_channel_by_id(db, user_id, channel_id)
        if not channel:
            return None

        if name is not None:
            channel.name = name
        if channel_type is not None:
            channel.channel_type = channel_type
        if is_active is not None:
            channel.is_active = is_active
        if config is not None:
            # 解密失败会抛 ValueError，避免用不完整的新配置覆盖旧密钥
            old_config = self.decrypt_channel_config(channel)
            merged_config = self._merge_config_update(old_config, config)
            config_str = json.dumps(merged_config, ensure_ascii=False)
            channel.config_json = encrypt_password(config_str)

        await db.commit()
        await db.refresh(channel)
        return channel

    async def delete_channel(self, db: AsyncSession, user_id: int, channel_id: int) -> bool:
        """删除通知通道"""
        channel = await self.get_channel_by_id(db, user_id, channel_id)
        if not channel:
            return False

        await db.delete(channel)
        await db.commit()
        return True

    def decrypt_channel_config(self, channel: NotificationChannel) -> Dict[str, Any]:
        """
        解密通道配置。

        Raises:
            ValueError: 配置无法解密/解析（例如加密密钥变更或数据损坏）
        """
        try:
            decrypted = decrypt_password(channel.config_json)
            config = json.loads(decrypted)
            if not isinstance(config, dict):
                raise ValueError("配置内容不是 JSON 对象")
            return config
        except Exception as e:
            logger.error(f"解密通道配置失败 (ID={channel.id}): {e}")
            raise ValueError("渠道配置解密失败，请重新保存该渠道")

    # ==================== 发送逻辑 ====================

    async def send_notification(
        self,
        db: AsyncSession,
        user_id: int,
        req: NotificationSendRequest,
        wait: bool = False,
        bound_channel_ids: Optional[List[int]] = None,
    ) -> NotificationSendResponse:
        """
        统一发送通知主接口。

        Args:
            wait: False（默认）异步调度，立即返回并携带 log_id；
                  True 同步执行真实发送，返回真实成败结果（测试通道场景使用）。
            bound_channel_ids: API Key 绑定的通知渠道ID列表。请求未显式指定
                  channel_id/channel_type 时，向这些启用渠道逐个推送（多渠道）。
        """
        # 0. API Key 免传参模式：向绑定的全部启用渠道推送
        #    bound_channel_ids is None → JWT 调用（保持显式要求）；[] → 密钥未绑定任何渠道
        if not req.channel_id and not req.channel_type and bound_channel_ids is not None:
            if not bound_channel_ids:
                return NotificationSendResponse(
                    success=False,
                    message="该 API 密钥尚未绑定通知渠道：请到「API 密钥」页为密钥绑定渠道，或显式指定 channel_id",
                )
            return await self._send_to_bound_channels(db, user_id, req, bound_channel_ids, wait=wait)

        channel_name = "临时发送"
        channel_type = req.channel_type
        channel_id = req.channel_id
        config = req.config or {}

        # 1. 寻找通道
        if channel_id:
            channel = await self.get_channel_by_id(db, user_id, channel_id)
            if not channel:
                return NotificationSendResponse(success=False, message="指定的通知渠道不存在")
            if not channel.is_active:
                return NotificationSendResponse(success=False, message="指定的通知渠道已被禁用")
            channel_name = channel.name
            channel_type = channel.channel_type
            try:
                config = self.decrypt_channel_config(channel)
            except ValueError as e:
                return NotificationSendResponse(success=False, message=str(e))
        elif not channel_type:
            return NotificationSendResponse(success=False, message="必须指定 channel_id 或 channel_type")

        # 2. 确定接收人（recipient 会覆盖渠道自身的 URL/邮箱等目标，白名单校验仍然生效）
        recipient = req.recipient
        if not recipient:
            # 根据通道配置中寻找默认接收者
            if channel_type == "email":
                recipient = config.get("to_addresses") or config.get("email_to") or config.get("smtp_user")
            elif channel_type == "speak":
                recipient = config.get("device_id")
            elif channel_type in ("dingtalk", "feishu", "wechat", "webhook"):
                recipient = config.get("webhook_url") or config.get("url")
        elif channel_id and channel_type in ("dingtalk", "feishu", "wechat", "webhook"):
            logger.warning(
                f"调用方在指定通道(ID={channel_id})的同时传入了 recipient，将覆盖渠道默认目标；"
                f"请确认该行为符合预期 (user_id={user_id}, channel_type={channel_type})"
            )

        # 3. 创建持久化日志（先 flush 拿到 ID 再提交，保证返回值带 log_id）
        log = NotificationLog(
            user_id=user_id,
            channel_id=channel_id,
            channel_type=channel_type,
            channel_name=channel_name,
            title=req.title,
            content=req.content,
            recipient=str(recipient) if recipient else "未指定",
            status="pending",
        )
        db.add(log)
        await db.flush()
        log_id = log.id
        await db.commit()

        # 4a. 同步模式：直接执行发送并回写日志，返回真实结果
        if wait:
            try:
                success, error_msg, detail = await self._dispatch_send(
                    log_id, channel_type, config, req.title, req.content, recipient, req.extra or {}
                )
            except Exception as e:
                logger.exception(f"同步发送通知异常 (log_id={log_id}): {e}")
                success, error_msg, detail = False, "发送过程发生异常，请查看服务端日志", None

            await self._update_log_status(db, log_id, success, error_msg)
            if success:
                message = f"发送成功: {channel_name} ({channel_type})"
            else:
                message = error_msg or "发送失败"
            return NotificationSendResponse(success=success, message=message, log_id=log_id, detail=detail)

        # 4b. 异步模式：后台任务执行发送，立即返回（持有 task 引用防止被 GC）
        task = asyncio.create_task(
            self._execute_send_task(log_id, channel_type, config, req.title, req.content, recipient, req.extra or {})
        )
        _bg_tasks.add(task)
        task.add_done_callback(_bg_tasks.discard)

        return NotificationSendResponse(
            success=True,
            message=f"已成功调度发送任务到通道: {channel_name} ({channel_type})",
            log_id=log_id,
        )

    async def _send_to_bound_channels(
        self,
        db: AsyncSession,
        user_id: int,
        req: NotificationSendRequest,
        bound_channel_ids: List[int],
        wait: bool = False,
    ) -> NotificationSendResponse:
        """API Key 免传参模式：向密钥绑定的全部启用渠道逐个推送（每个渠道一条日志）。"""
        from sqlalchemy import select

        from app.models.notification_channel import NotificationChannel

        try:
            stmt = select(NotificationChannel).where(
                NotificationChannel.user_id == user_id,
                NotificationChannel.is_active == True,  # noqa: E712
                NotificationChannel.id.in_(list(set(bound_channel_ids))),
            )
            result = await db.execute(stmt)
            channels = result.scalars().all()
        except Exception as e:
            logger.error(f"解析密钥绑定渠道失败: {e}")
            return NotificationSendResponse(success=False, message="解析绑定渠道失败")

        if not channels:
            return NotificationSendResponse(
                success=False,
                message="密钥未绑定任何可用的通知渠道（或绑定的渠道均已被禁用/删除）",
            )

        # 保持绑定顺序发送
        order = {cid: i for i, cid in enumerate(bound_channel_ids)}
        channels = sorted(channels, key=lambda c: order.get(c.id, 999))

        results: List[Dict[str, Any]] = []
        scheduled = 0
        for channel in channels:
            item: Dict[str, Any] = {
                "channel_id": channel.id,
                "channel_name": channel.name,
                "channel_type": channel.channel_type,
                "success": False,
                "log_id": None,
                "message": "",
            }
            try:
                config = self.decrypt_channel_config(channel)
            except ValueError as e:
                item["message"] = str(e)
                results.append(item)
                continue

            # 构造单渠道请求（显式 channel_id 语义；recipient/extra 透传）
            single_req = NotificationSendRequest(
                channel_id=channel.id,
                title=req.title,
                content=req.content,
                recipient=req.recipient,
                extra=req.extra,
            )
            resp = await self.send_notification(db, user_id, single_req, wait=wait)
            item["success"] = resp.success
            item["log_id"] = resp.log_id
            item["message"] = resp.message
            if resp.success:
                scheduled += 1
            results.append(item)

        success = scheduled > 0
        resp = NotificationSendResponse(
            success=success,
            message=f"已向 {scheduled}/{len(results)} 个绑定渠道调度发送",
        )
        resp.results = results
        resp.log_id = next((r["log_id"] for r in results if r["log_id"]), None)
        return resp

    async def _dispatch_send(
        self,
        log_id: int,
        channel_type: str,
        config: Dict[str, Any],
        title: Optional[str],
        content: str,
        recipient: Optional[str],
        extra: Dict[str, Any],
    ) -> Tuple[bool, Optional[str], Optional[dict]]:
        """按通道类型分发到具体发送实现，返回 (success, error_msg, detail)"""
        if channel_type == "email":
            success, error_msg = await self._send_email(config, title, content, recipient)
            return success, error_msg, None
        if channel_type == "dingtalk":
            return await self._send_dingtalk(config, title, content, recipient)
        if channel_type == "feishu":
            return await self._send_feishu(config, title, content, recipient)
        if channel_type == "wechat":
            return await self._send_wechat(config, title, content, recipient)
        if channel_type == "webhook":
            return await self._send_webhook(config, title, content, recipient, extra)
        if channel_type == "speak":
            return await self._send_speak(log_id, config, content, recipient, extra)
        return False, f"未支持的通道类型: {channel_type}", None

    async def _update_log_status(
        self, session: AsyncSession, log_id: int, success: bool, error_msg: Optional[str]
    ) -> None:
        """回写 NotificationLog 的发送结果"""
        stmt = (
            update(NotificationLog)
            .where(NotificationLog.id == log_id)
            .values(
                status="success" if success else "failed",
                error_message=error_msg,
            )
        )
        await session.execute(stmt)
        await session.commit()

    async def _execute_send_task(
        self,
        log_id: int,
        channel_type: str,
        config: Dict[str, Any],
        title: Optional[str],
        content: str,
        recipient: Optional[str],
        extra: Dict[str, Any],
    ):
        """异步执行的具体发送协程（自建独立会话）"""
        from app.database import AsyncSessionLocal

        # 创建一个独立的数据库会话以防冲突
        async with AsyncSessionLocal() as session:
            try:
                success, error_msg, detail = await self._dispatch_send(
                    log_id, channel_type, config, title, content, recipient, extra
                )

                # 更新日志状态
                await self._update_log_status(session, log_id, success, error_msg)
                logger.info(f"通知日志更新成功 (ID={log_id}), 发送结果: {'成功' if success else f'失败({error_msg})'}")

            except Exception as e:
                logger.exception(f"异步发送任务中发生未知异常 (log_id={log_id}): {e}")
                try:
                    await self._update_log_status(session, log_id, False, "发送过程发生异常，请查看服务端日志")
                except Exception as e2:
                    logger.error(f"尝试更新失败状态时出错: {e2}")

    # ==================== 各通道底层发送逻辑 ====================

    async def _send_email(
        self, config: Dict[str, Any], title: Optional[str], content: str, recipient: Optional[str]
    ) -> Tuple[bool, Optional[str]]:
        """发送 SMTP 邮件"""
        smtp_host = config.get("smtp_host")
        smtp_port = int(config.get("smtp_port") or 465)
        smtp_user = config.get("smtp_user")
        smtp_password = config.get("smtp_password")
        from_address = config.get("from_address") or smtp_user
        to_address = recipient

        if not all([smtp_host, smtp_user, smtp_password, to_address]):
            return False, "邮件发送配置缺失: 需要主机、账号、密码及接收人"

        # SSRF 校验：SMTP 主机来自用户配置
        try:
            validate_outbound_host(smtp_host)
        except ValueError as e:
            return False, f"SMTP 主机安全校验失败: {e}"

        # 定义同步邮件发送阻塞任务（在专用线程池中执行）
        def sync_send():
            msg = MIMEText(content, "html", "utf-8")
            msg["From"] = Header(f"Notification Center <{from_address}>", "utf-8")
            msg["To"] = Header(to_address, "utf-8")
            msg["Subject"] = Header(title or "爱通知系统通知", "utf-8")

            context = ssl.create_default_context()
            use_ssl = (smtp_port == 465)
            if use_ssl:
                server_cm = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10, context=context)
            else:
                server_cm = smtplib.SMTP(smtp_host, smtp_port, timeout=10)

            with server_cm as server:
                if not use_ssl:
                    # 非 465 端口必须升级 TLS；失败直接报错，绝不回退明文
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(from_address, [to_address], msg.as_string())

        try:
            logger.info(f"正在向 {to_address} 发送邮件，使用主机 {smtp_host}:{smtp_port}...")
            # 在专用线程池中执行同步阻塞操作，避免污染默认 executor
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(_smtp_executor, sync_send)
            return True, None
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False, str(e)

    async def _send_dingtalk(
        self, config: Dict[str, Any], title: Optional[str], content: str, recipient: Optional[str]
    ) -> Tuple[bool, Optional[str], Optional[dict]]:
        """发送钉钉机器人消息"""
        webhook_url = recipient or config.get("webhook_url")
        secret = config.get("secret")

        if not webhook_url:
            return False, "缺少钉钉 Webhook 链接", None

        # SSRF 校验：只允许钉钉官方域名
        try:
            validate_outbound_url(webhook_url, allowed_hosts=OFFICIAL_WEBHOOK_HOSTS)
        except ValueError as e:
            return False, f"钉钉 Webhook 安全校验失败: {e}", None

        # 组装签名
        params = {}
        if secret:
            timestamp = int(round(time.time() * 1000))
            secret_enc = secret.encode("utf-8")
            string_to_sign = f"{timestamp}\n{secret}"
            string_to_sign_enc = string_to_sign.encode("utf-8")
            hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
            sign = base64.b64encode(hmac_code).decode("utf-8")
            params["timestamp"] = timestamp
            # '+' 必须编码为 %2B，否则会被当成空格导致 310000 签名错误
            params["sign"] = encode_dingtalk_sign(sign)

        # 支持 markdown 或 text
        msg_type = config.get("msg_type", "text")
        if msg_type == "markdown":
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title or "系统通知",
                    "text": content,
                },
            }
        else:
            payload = {
                "msgtype": "text",
                "text": {
                    "content": f"{title + ': ' if title else ''}{content}",
                },
            }

        try:
            async with httpx.AsyncClient(follow_redirects=False, timeout=10) as client:
                res = await client.post(webhook_url, params=params, json=payload)
                raw_snippet = res.text[:200]
                if not (200 <= res.status_code < 300):
                    return False, f"钉钉接口 HTTP {res.status_code}: {raw_snippet}", None
                try:
                    data = res.json()
                except Exception:
                    return False, f"钉钉接口响应解析失败 (HTTP {res.status_code}): {raw_snippet}", {"raw": raw_snippet}
                if data.get("errcode") == 0:
                    return True, None, data
                return False, data.get("errmsg") or f"钉钉接口返回失败: {raw_snippet}", data
        except Exception as e:
            logger.error(f"钉钉推送异常: {e}")
            return False, str(e), None

    async def _send_feishu(
        self, config: Dict[str, Any], title: Optional[str], content: str, recipient: Optional[str]
    ) -> Tuple[bool, Optional[str], Optional[dict]]:
        """发送飞书机器人消息"""
        webhook_url = recipient or config.get("webhook_url")
        secret = config.get("secret")

        if not webhook_url:
            return False, "缺少飞书 Webhook 链接", None

        # SSRF 校验：只允许飞书官方域名
        try:
            validate_outbound_url(webhook_url, allowed_hosts=OFFICIAL_WEBHOOK_HOSTS)
        except ValueError as e:
            return False, f"飞书 Webhook 安全校验失败: {e}", None

        payload: Dict[str, Any] = {}

        # 飞书签名算法
        if secret:
            timestamp = int(time.time())
            string_to_sign = f"{timestamp}\n{secret}"
            hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
            sign = base64.b64encode(hmac_code).decode("utf-8")
            payload["timestamp"] = str(timestamp)
            payload["sign"] = sign

        msg_type = config.get("msg_type", "text")
        if msg_type == "post":
            payload.update({
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": title or "通知消息",
                            "content": [
                                [
                                    {"tag": "text", "text": content}
                                ]
                            ]
                        }
                    }
                }
            })
        else:
            msg_content = f"{title}\n{content}" if title else content
            payload.update({
                "msg_type": "text",
                "content": {
                    "text": msg_content
                }
            })

        try:
            async with httpx.AsyncClient(follow_redirects=False, timeout=10) as client:
                res = await client.post(webhook_url, json=payload)
                raw_snippet = res.text[:200]
                if not (200 <= res.status_code < 300):
                    return False, f"飞书接口 HTTP {res.status_code}: {raw_snippet}", None
                try:
                    data = res.json()
                except Exception:
                    return False, f"飞书接口响应解析失败 (HTTP {res.status_code}): {raw_snippet}", {"raw": raw_snippet}
                if data.get("code") == 0 or data.get("StatusCode") == 0:
                    return True, None, data
                # 失败时优先取 msg（飞书业务错误）
                return False, data.get("msg") or data.get("errmsg") or f"飞书接口返回失败: {raw_snippet}", data
        except Exception as e:
            logger.error(f"飞书推送异常: {e}")
            return False, str(e), None

    async def _send_wechat(
        self, config: Dict[str, Any], title: Optional[str], content: str, recipient: Optional[str]
    ) -> Tuple[bool, Optional[str], Optional[dict]]:
        """发送企业微信机器人消息"""
        webhook_url = recipient or config.get("webhook_url")

        if not webhook_url:
            return False, "缺少企业微信 Webhook 链接", None

        # SSRF 校验：只允许企业微信官方域名
        try:
            validate_outbound_url(webhook_url, allowed_hosts={"qyapi.weixin.qq.com"})
        except ValueError as e:
            return False, f"企业微信 Webhook 安全校验失败: {e}", None

        msg_type = config.get("msg_type", "text")
        if msg_type == "markdown":
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"### {title or '系统通知'}\n{content}"
                }
            }
        else:
            msg_content = f"{title}\n{content}" if title else content
            payload = {
                "msgtype": "text",
                "text": {
                    "content": msg_content
                }
            }

        try:
            async with httpx.AsyncClient(follow_redirects=False, timeout=10) as client:
                res = await client.post(webhook_url, json=payload)
                raw_snippet = res.text[:200]
                if not (200 <= res.status_code < 300):
                    return False, f"企业微信接口 HTTP {res.status_code}: {raw_snippet}", None
                try:
                    data = res.json()
                except Exception:
                    return False, f"企业微信接口响应解析失败 (HTTP {res.status_code}): {raw_snippet}", {"raw": raw_snippet}
                if data.get("errcode") == 0:
                    return True, None, data
                return False, data.get("errmsg") or f"企业微信接口返回失败: {raw_snippet}", data
        except Exception as e:
            logger.error(f"企业微信推送异常: {e}")
            return False, str(e), None

    async def _send_webhook(
        self,
        config: Dict[str, Any],
        title: Optional[str],
        content: str,
        recipient: Optional[str],
        extra: Dict[str, Any],
    ) -> Tuple[bool, Optional[str], Optional[dict]]:
        """触发自定义通用 Webhook"""
        url = recipient or config.get("url")
        if not url:
            return False, "缺少 Webhook 回调 URL", None

        # SSRF 校验：不允许内网/保留地址（可通过 settings.outbound_allow_private 放开）
        try:
            validate_outbound_url(url)
        except ValueError as e:
            return False, f"Webhook URL 安全校验失败: {e}", None

        method = config.get("method", "POST").upper()
        headers = config.get("headers") or {}

        payload = {
            "event": "notification",
            "title": title,
            "content": content,
            "timestamp": int(time.time()),
            "extra": extra,
        }

        try:
            async with httpx.AsyncClient(follow_redirects=False, timeout=10) as client:
                if method == "GET":
                    res = await client.get(url, headers=headers, params=payload)
                else:
                    res = await client.post(url, headers=headers, json=payload)

                if res.status_code in (200, 201, 202, 204):
                    return True, None, {"status_code": res.status_code, "body": res.text[:200]}
                else:
                    return False, f"HTTP 回调失败，状态码: {res.status_code}: {res.text[:200]}", {"body": res.text[:200]}
        except Exception as e:
            logger.error(f"Webhook 回调异常: {e}")
            return False, str(e), None

    async def _send_speak(
        self, log_id: int, config: Dict[str, Any], content: str, recipient: Optional[str], extra: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[dict]]:
        """转发至小爱音箱语音播放"""
        from app.database import AsyncSessionLocal
        from app.services.speak_service import speak_service
        from app.schemas.speak import SpeakRequest

        # 多设备优先（config.device_ids 列表），兼容旧单值 device_id；recipient 仍可覆盖
        device_ids: Optional[List[str]] = None
        if isinstance(config.get("device_ids"), list) and config["device_ids"]:
            device_ids = [str(d) for d in config["device_ids"] if d]
        single_device = recipient or config.get("device_id")
        if not device_ids and not single_device:
            return False, "未指定有效的小爱设备ID，请在渠道配置中选择音箱设备", None

        # 播报模式：text=文本TTS（默认）/ url=在线音频；兼容仅填了 audio_url 的旧配置
        audio_url = str(config.get("audio_url") or "").strip()
        mode = config.get("speak_mode") or ("url" if audio_url else "text")
        volume = extra.get("volume") if extra.get("volume") is not None else config.get("volume")
        endvolume = extra.get("endvolume") if extra.get("endvolume") is not None else config.get("endvolume")
        repeat = config.get("repeat") or 1
        interval = config.get("interval") or 0
        end_volume_delay = config.get("end_volume_delay")
        devices = device_ids if device_ids else [single_device]

        try:
            # 必须传入真实数据库会话：speak_text 依赖 (user_id, db) 查询该用户的设备列表，
            # 传 db=None 会导致 get_devices 返回空列表而 100% 失败。
            async with AsyncSessionLocal() as session:
                user_id = await session.scalar(
                    select(NotificationLog.user_id).where(NotificationLog.id == log_id)
                )
                if not user_id:
                    return False, "无法确定通知所属用户，语音播报已取消", None

                if mode == "url":
                    if not audio_url:
                        return False, "音频播报模式需要在渠道配置中填写在线音频 URL", None

                    # 次数/间隔循环在服务层内完成；音量语义：首播前设开始音量，全部播完后设结束音量
                    res_msg = await speak_service.notify_play_url(
                        user_id=user_id,
                        device_ids=[str(d) for d in devices],
                        url=audio_url,
                        volume=volume,
                        endvolume=endvolume,
                        repeat=repeat,
                        interval=interval,
                        end_volume_delay=end_volume_delay,
                    )
                    return True, None, {"message": res_msg}

                # 文本播报：repeat 循环调用（每次生成独立任务记录）
                repeats = max(1, min(int(repeat or 1), 10))
                last_error = None
                for i in range(repeats):
                    speak_req = SpeakRequest(
                        text=content,
                        device_id=(device_ids if device_ids else single_device),
                        volume=volume if i == 0 else None,          # 仅首播设置开始音量
                        endvolume=endvolume if i == repeats - 1 else None,  # 仅末次恢复结束音量
                        end_volume_delay=end_volume_delay,
                        speed=extra.get("speed") or config.get("speed") or 1.0,
                        voice_type=extra.get("voice_type") or config.get("voice_type") or "female",
                    )
                    res = await speak_service.speak_text(request=speak_req, user_id=user_id, db=session)
                    if not res.success:
                        last_error = res.message
                        break
                    if i < repeats - 1 and interval:
                        await asyncio.sleep(max(0.0, float(interval)))

                if last_error:
                    return False, last_error, None
                return True, None, None
        except Exception as e:
            logger.error(f"小爱播报服务转发异常: {e}")
            return False, str(e), None


# 全局通知服务实例
notification_service = NotificationService()

# 模块级便捷入口（等价于 notification_service.send_notification，供直接 import 使用）
send_notification = notification_service.send_notification