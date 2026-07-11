"""审计日志中间件 — W11.3/11.4

自动记录所有 API 请求的用户、操作、IP、状态码。
"""

import time
import uuid
from typing import Optional

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.security import decode_access_token


# 日志记录的操作类型映射（path pattern → action）
_PATH_ACTION_MAP = [
    # 知识库
    (("POST", "/api/v1/knowledge-bases"), "kb:create"),
    (("DELETE", "/api/v1/knowledge-bases/"), "kb:delete"),
    # 文档
    (("POST", "/api/v1/kb/{kb_id}/documents"), "doc:upload"),
    (("DELETE", "/api/v1/kb/{kb_id}/documents/"), "doc:delete"),
    (("POST", "/api/v1/kb/{kb_id}/documents/{doc_id}/replace"), "doc:update"),
    # 标签
    (("POST", "/api/v1/kb/{kb_id}/tags"), "tag:create"),
    (("DELETE", "/api/v1/kb/{kb_id}/tags/"), "tag:delete"),
    # 用户管理
    (("DELETE", "/api/v1/admin/users/"), "user:delete"),
    (("PUT", "/api/v1/admin/users/"), "user:update"),
    # 问答
    (("POST", "/api/v1/kb/{kb_id}/qa"), "qa:ask"),
    (("POST", "/api/v1/kb/{kb_id}/chat/stream"), "qa:chat"),
]


def _resolve_action(method: str, path: str) -> str:
    """根据 HTTP 方法和路径推断操作类型"""
    for (m, pattern), action in _PATH_ACTION_MAP:
        if method.upper() == m and pattern in path:
            return action
    # 通用匹配
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        return f"{method.lower()}:{path.split('/')[-1] if '/' in path else path}"
    return ""


async def _log_audit(
    request: Request,
    response: Response,
    user_id: str,
    username: str,
    latency_ms: float,
):
    """写入审计日志到 DB"""
    try:
        from core.database import async_session_factory
        from models.audit_log import AuditLog

        action = _resolve_action(request.method, request.url.path)
        if not action:
            return  # 不记录纯查询操作

        detail_parts = []
        if request.query_params:
            detail_parts.append(f"query={request.query_params}")
        detail = "; ".join(detail_parts) if detail_parts else None

        async with async_session_factory() as session:
            async with session.begin():
                log = AuditLog(
                    user_id=user_id,
                    username=username,
                    action=action,
                    resource_type=action.split(":")[0] if ":" in action else None,
                    resource_id=None,  # 从 path 提取太复杂，省略
                    detail=detail,
                    ip_address=request.client.host if request.client else None,
                    user_agent=request.headers.get("user-agent", "")[:256],
                    success=200 <= response.status_code < 300,
                    status_code=response.status_code,
                )
                session.add(log)
    except Exception as e:
        logger.debug(f"审计日志写入失败（非关键）: {e}")


class AuditMiddleware(BaseHTTPMiddleware):
    """审计日志中间件 — 记录所有 API 请求"""

    async def dispatch(self, request: Request, call_next):
        t0 = time.monotonic()

        # 跳过非 API 路径
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        response = await call_next(request)
        latency_ms = (time.monotonic() - t0) * 1000

        # 提取用户
        user_id = ""
        username = ""
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            uid = decode_access_token(token)
            if uid:
                user_id = uid
                username = uid  # 简化：用 user_id 代替（真实实现应查 DB）

        # 仅记录非 GET 操作
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            try:
                await _log_audit(request, response, user_id, username, latency_ms)
            except Exception:
                pass  # 审计不可用时不影响业务

        return response
