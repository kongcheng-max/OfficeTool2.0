"""认证相关 API — 注册 / 登录（含暴力破解防护 BUG-047）"""

import time
from collections import defaultdict

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.exceptions import BadRequestError, UnauthorizedError
from core.response import APIResponse
from core.security import create_access_token, hash_password, verify_password
from models.models import User
from schemas.schemas import LoginRequest, RegisterRequest, TokenResponse, UserBrief

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])

# ── BUG-047: 登录/注册速率限制（内存级，每 IP 单独计数）──

_MAX_LOGIN_ATTEMPTS = 5     # 每 IP 每分钟最多 5 次登录尝试
_MAX_REGISTER_PER_HOUR = 3  # 每 IP 每小时最多 3 次注册
_LOGIN_WINDOW = 60           # 秒
_REGISTER_WINDOW = 3600      # 秒

_login_attempts: dict = defaultdict(list)     # ip → [timestamps]
_register_attempts: dict = defaultdict(list)  # ip → [timestamps]


def _check_rate_limit(store: dict, ip: str, max_attempts: int, window: int):
    """检查速率限制，超限抛出 429"""
    now = time.monotonic()
    store[ip] = [t for t in store[ip] if now - t < window]  # 清理过期记录
    if len(store[ip]) >= max_attempts:
        retry_after = int(window - (now - store[ip][0]))
        raise BadRequestError(
            f"操作过于频繁，请 {retry_after} 秒后重试"
        )
    store[ip].append(now)


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/register", response_model=APIResponse[TokenResponse])
async def register(req: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """用户注册 — 每 IP 每小时最多 3 次"""
    _check_rate_limit(_register_attempts, _get_client_ip(request),
                      _MAX_REGISTER_PER_HOUR, _REGISTER_WINDOW)

    result = await db.execute(select(User).where(User.username == req.username))
    if result.scalar_one_or_none():
        raise BadRequestError("用户名已存在")

    if req.email:
        result = await db.execute(select(User).where(User.email == req.email))
        if result.scalar_one_or_none():
            raise BadRequestError("邮箱已被注册")

    user = User(
        username=req.username,
        email=req.email or None,
        hashed_password=hash_password(req.password),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    token = create_access_token(user.id)
    return APIResponse.success(
        TokenResponse(access_token=token, user=UserBrief.model_validate(user)),
        message="注册成功",
    )


@router.post("/login", response_model=APIResponse[TokenResponse])
async def login(req: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """用户登录 — 每 IP 每分钟最多 5 次失败"""
    ip = _get_client_ip(request)

    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.hashed_password):
        _check_rate_limit(_login_attempts, ip, _MAX_LOGIN_ATTEMPTS, _LOGIN_WINDOW)
        raise UnauthorizedError("用户名或密码错误")

    if not user.is_active:
        raise UnauthorizedError("账号已被禁用")

    token = create_access_token(user.id)
    return APIResponse.success(
        TokenResponse(access_token=token, user=UserBrief.model_validate(user)),
        message="登录成功",
    )
