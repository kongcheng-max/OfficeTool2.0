"""安全模块 — JWT 认证 + bcrypt 密码哈希 + RBAC 权限 (W11.1)"""

from enum import StrEnum
from functools import wraps
from typing import Callable, Optional

import bcrypt
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt

from core.config import settings
from core.exceptions import ForbiddenError


# ── W11.1: RBAC 角色定义 ──────────────────────────────────────

class Role(StrEnum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"

# 角色能力矩阵
_ROLE_PERMISSIONS = {
    Role.ADMIN: {
        "kb:create", "kb:delete", "kb:update", "kb:read",
        "doc:upload", "doc:delete", "doc:update", "doc:read",
        "tag:manage",
        "user:manage",  # admin 独有
        "audit:read",   # admin 独有
        "qa:ask",
    },
    Role.EDITOR: {
        "kb:create", "kb:delete", "kb:update", "kb:read",
        "doc:upload", "doc:delete", "doc:update", "doc:read",
        "tag:manage",
        "qa:ask",
    },
    Role.VIEWER: {
        "kb:read", "doc:read", "qa:ask",
    },
}


def has_permission(user_role: str, action: str) -> bool:
    """检查角色是否拥有某个操作权限"""
    perms = _ROLE_PERMISSIONS.get(Role(user_role), set())
    return action in perms


def require_role(*roles: str):
    """路由装饰器 — 限制访问角色

    Usage:
        @router.post("/admin/users")
        @require_role("admin")
        async def manage_users(...): ...

    Raises:
        ForbiddenError: 角色不满足要求
    """
    allowed = set(roles)

    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            # 从 kwargs 找 current_user
            user = kwargs.get("current_user")
            if user is None:
                raise ForbiddenError("未认证")
            if user.role not in allowed:
                raise ForbiddenError(
                    f"权限不足：需要 {','.join(roles)} 角色，当前为 {user.role}"
                )
            return await fn(*args, **kwargs)
        return wrapper
    return decorator


def is_admin(user) -> bool:
    return getattr(user, "role", "") == Role.ADMIN


def is_editor_or_admin(user) -> bool:
    return getattr(user, "role", "") in (Role.EDITOR, Role.ADMIN)


def hash_password(password: str) -> str:
    """bcrypt 哈希密码"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """生成 JWT 访问令牌"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """解码 JWT 令牌，返回 user_id 或 None"""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload.get("sub")
    except JWTError:
        return None
