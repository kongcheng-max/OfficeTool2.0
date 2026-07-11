"""认证依赖注入"""

from typing import Optional

from fastapi import Depends, Header, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.exceptions import UnauthorizedError
from core.security import decode_access_token
from models.models import User


async def _resolve_user_from_token(token: str, db: AsyncSession) -> User:
    """从 JWT token 字符串解析用户"""
    user_id = decode_access_token(token)
    if user_id is None:
        raise UnauthorizedError("Token 无效或已过期")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError("用户不存在")

    if not user.is_active:
        raise UnauthorizedError("账号已被禁用")

    return user


async def get_current_user(
    authorization: str = Header(..., description="Bearer <JWT Token>"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT Token 中解析当前用户"""
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("认证格式错误，应为 Bearer <Token>")

    return await _resolve_user_from_token(authorization[7:], db)


async def get_current_user_from_query(
    db: AsyncSession = Depends(get_db),
    token: Optional[str] = Query(None, description="JWT Token（用于浏览器原生请求如 iframe/img/下载）"),
    authorization: Optional[str] = Header(None, description="Bearer <JWT Token>"),
) -> User:
    """从 URL Query 参数或 Authorization Header 中解析当前用户

    浏览器原生请求（iframe/img/window.open）不携带自定义 Header，
    此依赖允许通过 ?token=xxx 传递 JWT。Query 参数优先于 Header。
    """
    # 优先从 URL query param 获取 token
    if token:
        return await _resolve_user_from_token(token, db)

    # 回退到 Authorization Header
    if authorization and authorization.startswith("Bearer "):
        return await _resolve_user_from_token(authorization[7:], db)

    raise UnauthorizedError("缺少认证信息（请通过 Header 或 URL token 参数提供）")
