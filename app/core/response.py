"""统一响应格式"""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """统一 API 响应结构: {code, message, data}"""
    code: int = 0
    message: str = "ok"
    data: Optional[T] = None

    @classmethod
    def success(cls, data: Any = None, message: str = "ok") -> "APIResponse":
        return cls(code=0, message=message, data=data)

    @classmethod
    def error(cls, code: int, message: str, data: Any = None) -> "APIResponse":
        return cls(code=code, message=message, data=data)


class PaginatedData(BaseModel, Generic[T]):
    """分页响应"""
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
