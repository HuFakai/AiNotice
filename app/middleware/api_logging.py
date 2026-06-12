# -*- coding: utf-8 -*-
"""
API调用记录中间件
记录所有API调用的详细信息，用于统计分析和监控
"""

import time
import json
from typing import Optional, Dict, Any
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from ipaddress import ip_address, AddressValueError

from app.database import AsyncSessionLocal
from app.models.api_call_log import ApiCallLog, ApiQuota
from app.dependencies import get_optional_user


class ApiLoggingMiddleware(BaseHTTPMiddleware):
    """API调用记录中间件"""

    def __init__(self, app, include_paths: Optional[list] = None):
        super().__init__(app)
        # 不记录任何路径，所有API调用记录由各自的service处理
        self.include_paths = include_paths or []

    async def dispatch(self, request: Request, call_next):
        """处理每个HTTP请求"""
        
        # 检查是否需要记录此路径
        if not self._should_include_path(request.url.path):
            return await call_next(request)

        # 记录开始时间
        start_time = time.time()
        
        # 获取请求信息（但不读取请求体，避免阻塞）
        request_data = await self._extract_request_data_without_body(request)
        
        # 处理请求
        response = await call_next(request)
        
        # 计算响应时间
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # 获取响应信息
        response_data = await self._extract_response_data(response)
        
        # 异步记录到数据库（不阻塞响应）
        try:
            import asyncio
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._log_api_call_async(
                    request=request,
                    response=response,
                    request_data=request_data,
                    response_data=response_data,
                    response_time_ms=response_time_ms,
                )
            )
        except Exception:
            # 如果记录失败，不影响主要业务逻辑
            pass
        
        return response

    def _should_include_path(self, path: str) -> bool:
        """判断是否应该记录此路径"""
        for include_path in self.include_paths:
            if path.startswith(include_path):
                return True
        return False

    async def _extract_request_data(self, request: Request) -> Dict[str, Any]:
        """提取请求数据"""
        try:
            # 获取请求体
            body = b""
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
            
            # 解析请求参数
            request_params = {}
            
            # 查询参数
            if request.query_params:
                request_params["query"] = dict(request.query_params)
            
            # 请求体参数（如果是JSON）
            if body and request.headers.get("content-type", "").startswith("application/json"):
                try:
                    request_params["body"] = json.loads(body.decode())
                    # 过滤敏感信息
                    request_params["body"] = self._filter_sensitive_data(request_params["body"])
                except (json.JSONDecodeError, UnicodeDecodeError):
                    request_params["body"] = "<binary_data>"
            
            # 路径参数
            if hasattr(request, "path_params") and request.path_params:
                request_params["path"] = dict(request.path_params)
            
            return {
                "endpoint": request.url.path,
                "method": request.method,
                "request_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent"),
                "request_size": len(body),
                "request_params": request_params if request_params else None,
            }
        except Exception as e:
            logger.error(f"提取请求数据失败: {e}")
            return {
                "endpoint": request.url.path,
                "method": request.method,
                "request_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent"),
                "request_size": 0,
                "request_params": None,
            }

    async def _extract_request_data_without_body(self, request: Request) -> Dict[str, Any]:
        """提取请求元数据但不读取请求体，避免消费流导致下游无法再次读取"""
        try:
            request_params: Dict[str, Any] = {}

            # 查询参数
            if request.query_params:
                request_params["query"] = dict(request.query_params)

            # 路径参数
            if hasattr(request, "path_params") and request.path_params:
                request_params["path"] = dict(request.path_params)

            # 从Content-Length推断大小（如果有）
            content_length_header = request.headers.get("content-length")
            try:
                request_size = int(content_length_header) if content_length_header is not None else 0
            except ValueError:
                request_size = 0

            return {
                "endpoint": request.url.path,
                "method": request.method,
                "request_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent"),
                "request_size": request_size,
                "request_params": request_params if request_params else None,
            }
        except Exception as e:
            logger.error(f"提取请求元数据失败: {e}")
            return {
                "endpoint": request.url.path,
                "method": request.method,
                "request_ip": self._get_client_ip(request),
                "user_agent": request.headers.get("user-agent"),
                "request_size": 0,
                "request_params": None,
            }

    async def _extract_response_data(self, response: Response) -> Dict[str, Any]:
        """提取响应数据"""
        try:
            response_size = 0
            response_content = None
            
            # 获取响应大小
            if hasattr(response, "body"):
                if isinstance(response.body, bytes):
                    response_size = len(response.body)
                    # 尝试解析JSON响应
                    try:
                        if response.headers.get("content-type", "").startswith("application/json"):
                            response_content = json.loads(response.body.decode())
                            # 过滤敏感信息
                            response_content = self._filter_sensitive_data(response_content)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        response_content = None
            elif isinstance(response, StreamingResponse):
                # 流式响应无法获取确切大小
                response_size = 0
            
            return {
                "status_code": response.status_code,
                "response_size": response_size,
                "response_data": response_content,
            }
        except Exception as e:
            logger.error(f"提取响应数据失败: {e}")
            return {
                "status_code": getattr(response, "status_code", 500),
                "response_size": 0,
                "response_data": None,
            }

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """获取客户端IP地址"""
        import socket
        import requests
        
        try:
            # 尝试从X-Forwarded-For头获取真实IP
            forwarded_for = request.headers.get("x-forwarded-for")
            if forwarded_for:
                # 取第一个IP地址
                ip = forwarded_for.split(",")[0].strip()
                try:
                    # 验证IP地址格式
                    ip_address(ip)
                    return ip
                except AddressValueError:
                    pass
            
            # 尝试从X-Real-IP头获取
            real_ip = request.headers.get("x-real-ip")
            if real_ip:
                try:
                    ip_address(real_ip)
                    return real_ip
                except AddressValueError:
                    pass
            
            # 获取直接连接的IP
            client_ip = request.client.host if request.client and request.client.host else None
            
            # 如果是本地IP（127.0.0.1或localhost），尝试获取真实的网络IP
            if client_ip in ["127.0.0.1", "localhost", "::1"] or not client_ip:
                try:
                    # 方法1: 通过连接外部服务获取本机公网IP
                    try:
                        response = requests.get("https://httpbin.org/ip", timeout=3)
                        if response.status_code == 200:
                            public_ip = response.json().get("origin")
                            if public_ip:
                                # 如果有多个IP，取第一个
                                public_ip = public_ip.split(",")[0].strip()
                                ip_address(public_ip)  # 验证IP格式
                                return public_ip
                    except:
                        pass
                    
                    # 方法2: 获取本机局域网IP
                    try:
                        # 创建一个UDP socket连接到外部地址（不会实际发送数据）
                        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                            s.connect(("8.8.8.8", 80))
                            local_ip = s.getsockname()[0]
                            if local_ip and local_ip != "127.0.0.1":
                                ip_address(local_ip)  # 验证IP格式
                                return local_ip
                    except:
                        pass
                        
                except Exception:
                    pass
            
            # 如果以上方法都失败，返回原始IP
            if client_ip:
                try:
                    ip_address(client_ip)
                    return client_ip
                except AddressValueError:
                    pass
            
            return None
        except (AddressValueError, AttributeError):
            return None

    def _filter_sensitive_data(self, data: Any) -> Any:
        """过滤敏感数据"""
        if isinstance(data, dict):
            filtered = {}
            for key, value in data.items():
                # 过滤敏感字段
                if isinstance(key, str) and any(sensitive in key.lower() for sensitive in 
                    ["password", "token", "secret", "key", "auth", "credential"]):
                    filtered[key] = "<filtered>"
                else:
                    filtered[key] = self._filter_sensitive_data(value)
            return filtered
        elif isinstance(data, list):
            return [self._filter_sensitive_data(item) for item in data]
        else:
            return data

    def _log_in_background(self, request, response, request_data, response_data, response_time_ms):
        """在后台线程中记录API调用"""
        try:
            import asyncio
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._log_api_call(
                    request=request,
                    response=response,
                    request_data=request_data,
                    response_data=response_data,
                    response_time_ms=response_time_ms
                ))
            finally:
                loop.close()
        except Exception as e:
            # 记录失败不影响主要业务逻辑
            print(f"API调用记录失败: {e}")

    async def _log_api_call_async(
        self,
        request: Request,
        response: Response,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any],
        response_time_ms: int
    ):
        """异步记录API调用，不阻塞主要业务逻辑"""
        try:
            await self._log_api_call(
                request=request,
                response=response,
                request_data=request_data,
                response_data=response_data,
                response_time_ms=response_time_ms
            )
        except Exception as e:
            logger.error(f"记录API调用失败: {e}")

    async def _log_api_call(
        self,
        request: Request,
        response: Response,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any],
        response_time_ms: int
    ):
        """记录API调用到数据库"""
        try:
            # 获取用户信息
            user_id = None
            api_key_id = None
            
            # 尝试从请求中获取用户信息
            try:
                # 这里需要手动解析认证信息，因为中间件在依赖注入之前执行
                user_info = await self._get_user_from_request(request)
                if user_info:
                    user_id = user_info.get("user_id")
                    api_key_id = user_info.get("api_key_id")
            except Exception as e:
                logger.debug(f"获取用户信息失败: {e}")
            
            # 如果没有用户信息，跳过记录（可能是公开接口）
            if not user_id:
                return
            
            # 创建数据库会话
            session = AsyncSessionLocal()
            try:
                # 创建API调用记录
                api_log = ApiCallLog(
                    user_id=user_id,
                    api_key_id=api_key_id,
                    endpoint=request_data["endpoint"],
                    method=request_data["method"],
                    request_ip=request_data["request_ip"],
                    user_agent=request_data["user_agent"],
                    request_size=request_data["request_size"],
                    response_size=response_data["response_size"],
                    status_code=response_data["status_code"],
                    response_time_ms=response_time_ms,
                    error_message=self._extract_error_message(response_data),
                    request_params=request_data["request_params"],
                    response_data=response_data["response_data"],
                )
                
                session.add(api_log)
                await session.commit()
                
                # 更新配额使用情况
                await self._update_quota_usage(session, user_id, request_data["endpoint"])
                
            except Exception as e:
                logger.error(f"记录API调用日志失败: {e}")
                await session.rollback()
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"记录API调用到数据库失败: {e}")

    async def _get_user_from_request(self, request: Request) -> Optional[Dict[str, Any]]:
        """从请求中获取用户信息"""
        try:
            # 优先检查Authorization头
            auth_header = request.headers.get("authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:]

                # 如果是API密钥格式（与依赖保持一致：xai_sk_ 前缀），优先走API Key认证
                if isinstance(token, str) and token.startswith("xai_sk_"):
                    try:
                        from app.services.api_key_service import ApiKeyService
                        session = AsyncSessionLocal()
                        try:
                            api_key_service = ApiKeyService(session)
                            is_valid, user, key_info = await api_key_service.verify_api_key(token)
                            if is_valid and key_info:
                                return {"user_id": key_info.user_id, "api_key_id": key_info.id}
                        finally:
                            await session.close()
                    except Exception as e:
                        logger.debug(f"Authorization中API密钥认证失败: {e}")
                
                # 否则尝试JWT认证
                try:
                    from app.services.auth_service import AuthService
                    session = AsyncSessionLocal()
                    try:
                        auth_service = AuthService(session)
                        is_valid, user = await auth_service.verify_token(token)
                        if is_valid and user:
                            return {"user_id": user.id, "api_key_id": None}
                    finally:
                        await session.close()
                except Exception as e:
                    logger.debug(f"JWT认证失败: {e}")
                
                # Authorization头存在但认证失败，直接返回None，不再检查x-api-key头
                return None
            
            # 只有当Authorization头不存在时，才检查API Key（x-api-key 头）
            api_key = request.headers.get("x-api-key")
            if api_key:
                logger.info(f"中间件检测到API密钥: {api_key[:20]}...")
                # 验证API Key
                from app.services.api_key_service import ApiKeyService
                session = AsyncSessionLocal()
                try:
                    api_key_service = ApiKeyService(session)
                    is_valid, user, key_info = await api_key_service.verify_api_key(api_key)
                    logger.info(f"API密钥验证结果: is_valid={is_valid}, user={user}, key_info={key_info}")
                    if is_valid and key_info:
                        logger.info(f"API密钥验证成功: user_id={key_info.user_id}, api_key_id={key_info.id}")
                        return {"user_id": key_info.user_id, "api_key_id": key_info.id}
                    else:
                        logger.warning(f"API密钥验证失败: {api_key[:20]}...")
                finally:
                    await session.close()
            else:
                logger.debug("未检测到API密钥头")
            
            return None
        except Exception as e:
            logger.debug(f"解析用户信息失败: {e}")
            return None

    def _extract_error_message(self, response_data: Dict[str, Any]) -> Optional[str]:
        """提取错误信息"""
        if response_data["status_code"] >= 400:
            response_content = response_data.get("response_data")
            if isinstance(response_content, dict):
                return response_content.get("message") or response_content.get("detail")
        return None

    async def _update_quota_usage(self, session: AsyncSession, user_id: int, endpoint: str):
        """更新配额使用情况"""
        try:
            from sqlalchemy import select, update
            from datetime import date
            
            # 更新每日配额
            stmt = (
                update(ApiQuota)
                .where(
                    ApiQuota.user_id == user_id,
                    ApiQuota.endpoint == endpoint,
                    ApiQuota.quota_type == "daily"
                )
                .values(quota_used=ApiQuota.quota_used + 1)
            )
            await session.execute(stmt)
            
            # 更新月度配额
            stmt = (
                update(ApiQuota)
                .where(
                    ApiQuota.user_id == user_id,
                    ApiQuota.endpoint == endpoint,
                    ApiQuota.quota_type == "monthly"
                )
                .values(quota_used=ApiQuota.quota_used + 1)
            )
            await session.execute(stmt)
            
            await session.commit()
            
        except Exception as e:
            logger.error(f"更新配额使用情况失败: {e}")