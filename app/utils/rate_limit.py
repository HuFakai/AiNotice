# -*- coding: utf-8 -*-
"""
进程内滑动窗口限流器

用于登录/注册/可用性检查等敏感端点的暴力破解防护。
单实例部署直接使用内存实现即可；如未来横向扩展，可替换为 Redis 实现。
"""

import time
import threading
from typing import Dict, List, Tuple


class RateLimiter:
    """滑动窗口限流器：窗口内失败次数达到上限后锁定一段时间。"""

    def __init__(self, max_attempts: int, window_seconds: int, lockout_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._failures: Dict[str, List[float]] = {}
        self._locked_until: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._last_prune = time.monotonic()

    def _prune(self, now: float) -> None:
        """清理过期数据，避免长期运行下内存无限增长。"""
        if now - self._last_prune < 300:
            return
        self._last_prune = now
        self._failures = {
            k: [t for t in v if now - t < self.window_seconds]
            for k, v in self._failures.items()
            if v
        }
        self._locked_until = {k: t for k, t in self._locked_until.items() if t > now}

    def check(self, key: str) -> Tuple[bool, int]:
        """
        检查是否被锁定。

        Returns:
            (是否被锁定, 剩余锁定秒数)
        """
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            until = self._locked_until.get(key, 0)
            if until > now:
                return True, int(until - now) + 1
            return False, 0

    def record_failure(self, key: str) -> None:
        """记录一次失败，达到阈值后自动锁定。"""
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            self._failures.setdefault(key, []).append(now)
            recent = [t for t in self._failures[key] if now - t < self.window_seconds]
            self._failures[key] = recent
            if len(recent) >= self.max_attempts:
                self._locked_until[key] = now + self.lockout_seconds
                self._failures.pop(key, None)

    def reset(self, key: str) -> None:
        """成功后清除失败记录。"""
        with self._lock:
            self._failures.pop(key, None)


# 全局实例：登录按 IP + 账号双维度限制，注册与可用性检查按 IP 限制
login_limiter = RateLimiter(max_attempts=5, window_seconds=300, lockout_seconds=900)
register_limiter = RateLimiter(max_attempts=10, window_seconds=3600, lockout_seconds=3600)
availability_limiter = RateLimiter(max_attempts=30, window_seconds=300, lockout_seconds=600)
