"""API 限流中间件 — W11.7

基于 Token Bucket 算法，每用户 100 req/min。
"""

import time
from collections import defaultdict
from typing import Dict, Tuple

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from core.config import settings

# ── 配置 ──
RATE_LIMIT = 100       # 每分钟请求数
WINDOW_SECONDS = 60    # 时间窗口
BURST_MULTIPLIER = 1.5  # 突发倍数（首窗口允许 150）


class TokenBucket:
    """令牌桶 — 每个用户的限流状态"""

    def __init__(self, rate: int, burst: float):
        self.rate = rate
        self.burst = burst
        self.tokens = burst        # 初始令牌数
        self.last_refill = time.monotonic()

    def consume(self) -> bool:
        """尝试消费 1 个令牌，成功返回 True"""
        now = time.monotonic()
        elapsed = now - self.last_refill

        # 补充令牌（时间比例）
        self.tokens = min(
            self.burst,
            self.tokens + elapsed * (self.rate / WINDOW_SECONDS),
        )
        self.last_refill = now

        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token Bucket 限流中间件"""

    def __init__(self, app):
        super().__init__(app)
        self._buckets: Dict[str, TokenBucket] = {}

    async def dispatch(self, request: Request, call_next):
        # 仅 API 路径限流
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # 提取用户标识（优先 token → IP）
        key = self._get_user_key(request)

        # 检查/创建桶
        if key not in self._buckets:
            self._buckets[key] = TokenBucket(
                rate=RATE_LIMIT, burst=RATE_LIMIT * BURST_MULTIPLIER
            )

        bucket = self._buckets[key]
        if not bucket.consume():
            return JSONResponse(
                status_code=429,
                content={
                    "code": 429,
                    "message": f"请求过于频繁，限流 {RATE_LIMIT} req/min",
                    "data": None,
                },
                headers={"Retry-After": "30"},
            )

        return await call_next(request)

    @staticmethod
    def _get_user_key(request: Request) -> str:
        """提取用户标识：JWT token → user_id，否则用 IP"""
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            from core.security import decode_access_token
            uid = decode_access_token(auth[7:])
            if uid:
                return f"user:{uid}"

        client = request.client
        return f"ip:{client.host}" if client else "unknown"

    async def cleanup(self):
        """定期清理过期的桶（可被后台任务调用）"""
        # 简化实现：每 10 分钟清空所有桶
        self._buckets.clear()
