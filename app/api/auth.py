"""认证相关 API — 注册 / 登录"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.exceptions import BadRequestError, UnauthorizedError
from core.response import APIResponse
from core.security import create_access_token, hash_password, verify_password
from models.models import User
from schemas.schemas import LoginRequest, RegisterRequest, TokenResponse, UserBrief

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


@router.post("/register", response_model=APIResponse[TokenResponse])
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == req.username))
    if result.scalar_one_or_none():
        raise BadRequestError("用户名已存在")

    # 检查邮箱是否已存在（仅当提供了邮箱时）
    if req.email:
        result = await db.execute(select(User).where(User.email == req.email))
        if result.scalar_one_or_none():
            raise BadRequestError("邮箱已被注册")

    # 创建用户
    user = User(
        username=req.username,
        email=req.email or None,
        hashed_password=hash_password(req.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # 生成 Token
    token = create_access_token(user.id)

    return APIResponse.success(
        TokenResponse(
            access_token=token,
            user=UserBrief.model_validate(user),
        ),
        message="注册成功",
    )


@router.post("/login", response_model=APIResponse[TokenResponse])
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    # 查找用户
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedError("用户名或密码错误")

    if not verify_password(req.password, user.hashed_password):
        raise UnauthorizedError("用户名或密码错误")

    if not user.is_active:
        raise UnauthorizedError("账号已被禁用")

    # 生成 Token
    token = create_access_token(user.id)

    return APIResponse.success(
        TokenResponse(
            access_token=token,
            user=UserBrief.model_validate(user),
        ),
        message="登录成功",
    )
