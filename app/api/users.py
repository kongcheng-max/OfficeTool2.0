"""用户相关 API"""

from fastapi import APIRouter, Depends

from api.deps import get_current_user
from core.response import APIResponse
from models.models import User
from schemas.schemas import UserDetail

router = APIRouter(prefix="/api/v1/users", tags=["用户"])


@router.get("/me", response_model=APIResponse[UserDetail])
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return APIResponse.success(UserDetail.model_validate(current_user))
