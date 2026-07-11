"""管理后台 API — W11.4: 审计日志查询 + 用户管理 (admin only)"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from core.database import get_db
from core.exceptions import ForbiddenError, NotFoundError
from core.response import APIResponse
from core.security import Role, require_role
from models.models import User

router = APIRouter(prefix="/api/v1/admin", tags=["管理后台"])


def _verify_admin(user: User) -> User:
    """确保当前用户是 admin"""
    if user.role != Role.ADMIN:
        raise ForbiddenError(f"权限不足：需要 admin 角色，当前为 {user.role}")
    return user


# ── 用户管理 ──────────────────────────────────────────────────

@router.get("/users", response_model=APIResponse[dict])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户列表（admin only）"""
    _verify_admin(current_user)

    count_q = select(func.count(User.id))
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(page_size)
    )
    users = result.scalars().all()

    items = [{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    } for u in users]

    return APIResponse.success({
        "items": items, "total": total, "page": page, "page_size": page_size,
    })


@router.put("/users/{user_id}/role", response_model=APIResponse)
async def update_user_role(
    user_id: str,
    role: str = Query(..., description="新角色: admin/editor/viewer"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改用户角色（admin only）"""
    _verify_admin(current_user)

    if role not in ("admin", "editor", "viewer"):
        from core.exceptions import BadRequestError
        raise BadRequestError(f"无效角色: {role}")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("用户")

    user.role = role
    await db.flush()

    return APIResponse.success(message=f"用户 {user.username} 角色已更新为 {role}")


@router.delete("/users/{user_id}", response_model=APIResponse)
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除用户（admin only，不可删除自己）"""
    _verify_admin(current_user)

    if user_id == current_user.id:
        from core.exceptions import BadRequestError
        raise BadRequestError("不可删除自己的账号")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise NotFoundError("用户")

    username = user.username
    await db.delete(user)
    await db.flush()

    return APIResponse.success(message=f"用户 {username} 已删除")


# ── 审计日志查询 ──────────────────────────────────────────────

@router.get("/audit-logs", response_model=APIResponse[dict])
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: Optional[str] = Query(None, description="按用户筛选"),
    action: Optional[str] = Query(None, description="按操作筛选"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """审计日志查询（admin only）"""
    _verify_admin(current_user)

    from models.audit_log import AuditLog

    q = select(AuditLog)
    count_q = select(func.count(AuditLog.id))

    if user_id:
        q = q.where(AuditLog.user_id == user_id)
        count_q = count_q.where(AuditLog.user_id == user_id)
    if action:
        q = q.where(AuditLog.action == action)
        count_q = count_q.where(AuditLog.action == action)

    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        q.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)
    )
    logs = result.scalars().all()

    items = [{
        "id": log.id,
        "user_id": log.user_id,
        "username": log.username,
        "action": log.action,
        "resource_type": log.resource_type,
        "resource_id": log.resource_id,
        "detail": log.detail,
        "ip_address": log.ip_address,
        "success": log.success,
        "status_code": log.status_code,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    } for log in logs]

    return APIResponse.success({
        "items": items, "total": total, "page": page, "page_size": page_size,
    })
