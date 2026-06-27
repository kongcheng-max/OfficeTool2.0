"""认证依赖注入"""

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.exceptions import UnauthorizedError
from core.security import decode_access_token
from models.models import User


async def get_current_user(
    authorization: str = Header(..., description="Bearer <JWT Token>"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT Token 中解析当前用户"""
    if not authorization.startswith("Bearer "):
        raise UnauthorizedError("认证格式错误，应为 Bearer <Token>")

    token = authorization[7:]
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
