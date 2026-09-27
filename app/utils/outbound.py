# -*- coding: utf-8 -*-
"""
出站请求安全校验

通知发送（webhook/钉钉/飞书/企业微信）与 SMTP 的目标地址全部来自用户配置，
必须经过这里的校验，防止把服务端当作 SSRF 跳板访问内网、云元数据等。

注意：这里做的是"解析后校验"，对 DNS rebinding 只能缓解而非彻底杜绝
（解析与真正建连之间存在 TOCTOU 窗口）。如需彻底防护，应在出站代理层实现。
"""

import ipaddress
import socket
from urllib.parse import urlparse
from typing import Optional, Iterable

from loguru import logger

ALLOWED_SCHEMES = {"http", "https"}

# 钉钉 / 飞书 / 企业微信官方机器人域名白名单
OFFICIAL_WEBHOOK_HOSTS = {
    "oapi.dingtalk.com",
    "open.feishu.cn",
    "qyapi.weixin.qq.com",
}


def is_blocked_ip(ip: str) -> bool:
    """判断 IP 是否属于禁止出站访问的范围（回环/私网/链路本地/保留段等）。"""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    if addr.is_unspecified or addr.is_loopback or addr.is_link_local:
        return True
    if addr.is_private or addr.is_reserved or addr.is_multicast:
        return True
    # IPv4-mapped IPv6 地址按 IPv4 语义判断
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        return is_blocked_ip(str(addr.ipv4_mapped))
    return False


def resolve_host_ips(hostname: str) -> list[str]:
    """解析主机名的全部 IP；解析失败返回空列表。"""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        logger.warning(f"域名解析失败: {hostname} ({e})")
        return []
    ips = []
    for info in infos:
        ip = info[4][0]
        if ip not in ips:
            ips.append(ip)
    return ips


def validate_outbound_url(
    url: str,
    *,
    allowed_hosts: Optional[Iterable[str]] = None,
    allow_private: bool = False,
) -> str:
    """
    校验一个用户提供的出站 URL。

    Args:
        url: 目标 URL
        allowed_hosts: 域名白名单（精确匹配主机名），传入则只允许访问这些主机
        allow_private: 是否允许私网地址（自托管场景通过配置放开）

    Returns:
        原始 URL（校验通过）

    Raises:
        ValueError: URL 不合法或目标被禁止
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL 不能为空")

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValueError("仅支持 http/https 协议")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL 缺少主机名")

    # 纯 IP 字面量（含奇怪写法如 0x7f000001、十进制整数）先归一化再判断
    try:
        if ipaddress.ip_address(hostname) and not allow_private:
            raise ValueError("禁止访问 IP 字面量地址，请使用域名")
    except ValueError as e:
        if "禁止" in str(e):
            raise
        # 不是合法 IP，按域名处理
    else:
        return url.strip()

    if allowed_hosts is not None:
        allowed = {h.lower() for h in allowed_hosts}
        if hostname.lower() not in allowed:
            raise ValueError(f"目标主机不在允许的域名白名单内")

    if not allow_private:
        for ip in resolve_host_ips(hostname):
            if is_blocked_ip(ip):
                raise ValueError(f"目标地址解析到内网/保留 IP（{ip}），已禁止访问")

    return url.strip()


def validate_outbound_host(host: str, *, allow_private: bool = False) -> str:
    """校验出站主机名（用于 SMTP 等非 URL 目标）。"""
    if not host or not isinstance(host, str):
        raise ValueError("主机名不能为空")
    host = host.strip().rstrip(".")
    if "/" in host or "@" in host or ":" in host:
        raise ValueError("主机名格式不合法")
    if not allow_private:
        for ip in resolve_host_ips(host):
            if is_blocked_ip(ip):
                raise ValueError(f"目标主机解析到内网/保留 IP（{ip}），已禁止访问")
    return host


def get_allow_private() -> bool:
    """是否允许出站访问私网（自托管 SMTP/webhook 场景由配置放开）。"""
    from app.config import settings

    return bool(getattr(settings, "outbound_allow_private", False))
