# -*- coding: utf-8 -*-
"""
通知服务业务逻辑
实现通道管理及多通道消息分发
"""

import json
import time
import ssl
import hmac
import hashlib
import base64
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from typing import List, Optional, Tuple, Dict, Any
import httpx
from loguru import logger
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification_channel import NotificationChannel
from app.models.notification_log import NotificationLog
from app.schemas.notification import NotificationSendRequest, NotificationSendResponse
from app.utils.encryption import encrypt_password, decrypt_password


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
        """更新通知通道"""
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
            config_str = json.dumps(config, ensure_ascii=False)
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
        """解密通道配置"""
        try:
            decrypted = decrypt_password(channel.config_json)
            return json.loads(decrypted)
        except Exception as e:
            logger.error(f"解密通道配置失败 (ID={channel.id}): {e}")
            return {}

    # ==================== 发送逻辑 ====================

    async def send_notification(
        self, db: AsyncSession, user_id: int, req: NotificationSendRequest
    ) -> NotificationSendResponse:
        """统一发送通知主接口"""
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
            config = self.decrypt_channel_config(channel)
        elif not channel_type:
            return NotificationSendResponse(success=False, message="必须指定 channel_id 或 channel_type")

        # 2. 确定接收人
        recipient = req.recipient
        if not recipient:
            # 根据通道配置中寻找默认接收者
            if channel_type == "email":
                recipient = config.get("to_addresses") or config.get("email_to") or config.get("smtp_user")
            elif channel_type == "speak":
                recipient = config.get("device_id")
            elif channel_type in ("dingtalk", "feishu", "wechat", "webhook"):
                recipient = config.get("webhook_url") or config.get("url")

        # 3. 创建持久化日志
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
        await db.commit()
        await db.refresh(log)

        # 4. 异步执行发送任务，避免阻塞 HTTP 请求返回
        # 传递会话生成器创建独立 Session，或者异步执行后自己创建
        asyncio.create_task(
            self._execute_send_task(log.id, channel_type, config, req.title, req.content, recipient, req.extra or {})
        )

        return NotificationSendResponse(
            success=True,
            message=f"已成功调度发送任务到通道: {channel_name} ({channel_type})",
            log_id=log.id,
        )

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
        """异步执行的具体发送协程"""
        from app.database import AsyncSessionLocal

        # 创建一个独立的数据库会话以防冲突
        async with AsyncSessionLocal() as session:
            try:
                success, error_msg, detail = False, None, None

                if channel_type == "email":
                    success, error_msg = await self._send_email(config, title, content, recipient)
                elif channel_type == "dingtalk":
                    success, error_msg, detail = await self._send_dingtalk(config, title, content, recipient)
                elif channel_type == "feishu":
                    success, error_msg, detail = await self._send_feishu(config, title, content, recipient)
                elif channel_type == "wechat":
                    success, error_msg, detail = await self._send_wechat(config, title, content, recipient)
                elif channel_type == "webhook":
                    success, error_msg, detail = await self._send_webhook(config, title, content, recipient, extra)
                elif channel_type == "speak":
                    success, error_msg, detail = await self._send_speak(log_id, config, content, recipient, extra)
                else:
                    error_msg = f"未支持的通道类型: {channel_type}"

                # 更新日志状态
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
                logger.info(f"通知日志更新成功 (ID={log_id}), 发送结果: {'成功' if success else f'失败({error_msg})'}")

            except Exception as e:
                logger.error(f"异步发送任务中发生未知异常: {e}")
                try:
                    stmt = (
                        update(NotificationLog)
                        .where(NotificationLog.id == log_id)
                        .values(status="failed", error_message=str(e))
                    )
                    await session.execute(stmt)
                    await session.commit()
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

        # 定义同步邮件发送阻塞任务
        def sync_send():
            msg = MIMEText(content, "html", "utf-8")
            msg["From"] = Header(f"Notification Center <{from_address}>", "utf-8")
            msg["To"] = Header(to_address, "utf-8")
            msg["Subject"] = Header(title or "爱通知系统通知", "utf-8")

            use_ssl = (smtp_port == 465)
            if use_ssl:
                server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
                if smtp_port == 587:
                    server.starttls()

            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)

            server.sendmail(from_address, [to_address], msg.as_string())
            server.quit()

        try:
            logger.info(f"正在向 {to_address} 发送邮件，使用主机 {smtp_host}:{smtp_port}...")
            # 在异步线程中执行同步阻塞操作
            await asyncio.to_thread(sync_send)
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
            params["sign"] = sign

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
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.post(webhook_url, params=params, json=payload)
                data = res.json()
                if data.get("errcode") == 0:
                    return True, None, data
                else:
                    return False, data.get("errmsg", "钉钉接口返回失败"), data
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
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.post(webhook_url, json=payload)
                data = res.json()
                if data.get("code") == 0 or data.get("StatusCode") == 0:
                    return True, None, data
                else:
                    return False, data.get("msg", "飞书接口返回失败"), data
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
            async with httpx.AsyncClient(timeout=10) as client:
                res = await client.post(webhook_url, json=payload)
                data = res.json()
                if data.get("errcode") == 0:
                    return True, None, data
                else:
                    return False, data.get("errmsg", "企业微信接口返回失败"), data
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
            async with httpx.AsyncClient(timeout=15) as client:
                if method == "GET":
                    res = await client.get(url, headers=headers, params=payload)
                else:
                    res = await client.post(url, headers=headers, json=payload)

                if res.status_code in (200, 201, 202, 204):
                    return True, None, {"status_code": res.status_code, "body": res.text[:200]}
                else:
                    return False, f"HTTP 回调失败，状态码: {res.status_code}", {"body": res.text[:200]}
        except Exception as e:
            logger.error(f"Webhook 回调异常: {e}")
            return False, str(e), None

    async def _send_speak(
        self, log_id: int, config: Dict[str, Any], content: str, recipient: Optional[str], extra: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], Optional[dict]]:
        """转发至小爱音箱语音播放"""
        from app.services.speak_service import speak_service
        from app.models.speak import SpeakRequest

        device_id = recipient or config.get("device_id")
        if not device_id:
            return False, "未指定有效的小爱设备ID", None

        # 构造 SpeakRequest
        speak_req = SpeakRequest(
            text=content,
            device_id=device_id,
            volume=extra.get("volume") or config.get("volume"),
            endvolume=extra.get("endvolume") or config.get("endvolume"),
            speed=extra.get("speed") or config.get("speed") or 1.0,
            voice_type=extra.get("voice_type") or config.get("voice_type") or "female",
        )

        try:
            # speak_service 不需要 user_id 时可为 None。为了模拟或真实认证，我们直接使用该账户的所有者
            # 获取通道所有者 ID，以便加载对应的 MiService 实例
            from sqlalchemy import select
            from app.database import AsyncSessionLocal
            
            user_id = None
            async with AsyncSessionLocal() as session:
                # 从 NotificationLog 反查所有者
                stmt = select(NotificationLog.user_id).where(NotificationLog.id == log_id)
                result = await session.execute(stmt)
                user_id = result.scalar()

            # 调用已存在的 speak_text
            res = await speak_service.speak_text(
                request=speak_req,
                user_id=user_id,
                db=None,  # 传入 None，让其创建独立 session 并异步后台播放
            )
            
            if res.success:
                return True, None, {"task_id": res.task_id}
            else:
                return False, res.message, None
        except Exception as e:
            logger.error(f"小爱播报服务转发异常: {e}")
            return False, str(e), None


# 全局通知服务实例
notification_service = NotificationService()
