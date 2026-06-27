"""Pydantic Schema — 请求/响应数据模型"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ==================== 认证 ====================

class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    email: Optional[EmailStr] = None
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserBrief"


# ==================== 用户 ====================

class UserBrief(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserDetail(UserBrief):
    pass


# ==================== 知识库 ====================

class KBCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="")


class KBUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    description: Optional[str] = None


class KBResponse(BaseModel):
    id: str
    name: str
    description: str
    owner_id: str
    chunk_count: int
    doc_count: int = 0  # 从 relations 补充
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== 文档 ====================

class DocumentResponse(BaseModel):
    id: str
    kb_id: str
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    status: str
    error_message: str = ""
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    document_id: str
    status: str
    message: str = "文档已提交解析"


# ==================== 问答 ====================

class QARequest(BaseModel):
    question: str = Field(min_length=1, max_length=4096)

class QAResponse(BaseModel):
    answer: str
    conversation_id: Optional[str] = None
    sources: list["SourceInfo"] = []
    confidence: float = 0.0


class SourceInfo(BaseModel):
    document_id: str = ""
    document_name: str = ""
    chunk_text: str = ""
    page: Optional[int] = None
    score: float = 0.0
