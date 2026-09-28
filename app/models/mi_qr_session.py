# -*- coding: utf-8 -*-
"""
小米扫码登录会话模型

扫码会话必须持久化到数据库而不是进程内存：
- uvicorn reload（API_DEBUG=True）、多 worker 部署、进程崩溃重启
  都会导致内存会话丢失，表现为"二维码能显示但轮询报会话不存在"
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Integer, String, Text, DateTime, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base, BJDateTime


class MiQrSession(Base):
    """小米扫码登录会话"""

    __tablename__ = "mi_qr_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="扫码会话ID")
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="所属平台用户ID"
    )

    # 小米返回的会话信息
    qr_url: Mapped[str] = mapped_column(Text, comment="二维码图片地址")
    login_url: Mapped[Optional[str]] = mapped_column(Text, comment="备用登录链接")
    lp_url: Mapped[str] = mapped_column(Text, comment="长轮询地址")
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300, comment="会话有效期（秒）")
    display_name: Mapped[Optional[str]] = mapped_column(String(100), comment="账户备注名")

    # loginUrl 阶段设置的会话 Cookie（参考实现三步骤共享同一 Session，
    # lp 长轮询必须携带这些 Cookie 才能收到扫码确认事件）
    cookies_json: Mapped[Optional[Dict[str, str]]] = mapped_column(JSON, comment="loginUrl 会话Cookie")

    # 状态机: waiting -> confirmed -> consumed；waiting -> expired/error
    status: Mapped[str] = mapped_column(String(20), default="waiting", comment="状态")
    result_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, comment="扫码成功后的凭据（消费后清除）")

    # 时间字段
    created_at: Mapped[datetime] = mapped_column(BJDateTime(), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        BJDateTime(), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )

    # 索引
    __table_args__ = (
        Index("idx_mi_qr_sessions_user_id", "user_id"),
        Index("idx_mi_qr_sessions_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<MiQrSession(id={self.session_id}, user_id={self.user_id}, status={self.status})>"
