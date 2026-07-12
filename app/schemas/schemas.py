"""Pydantic Schema — 请求/响应数据模型"""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# BUG-050: 常见弱密码黑名单
_WEAK_PASSWORDS = {
    "123456", "12345678", "123456789", "password", "Password",
    "admin123", "Admin123", "qwerty", "abc123", "111111",
    "123123", "000000", "iloveyou", "welcome", "monkey",
}


# ==================== 认证 ====================

class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    email: Optional[EmailStr] = None
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if v.lower() in _WEAK_PASSWORDS:
            raise ValueError("密码过于常见，请使用更复杂的密码")
        if not re.search(r'[A-Z]', v):
            raise ValueError("密码必须包含至少一个大写字母")
        if not re.search(r'[a-z]', v):
            raise ValueError("密码必须包含至少一个小写字母")
        if not re.search(r'[0-9]', v):
            raise ValueError("密码必须包含至少一个数字")
        return v


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
    qa_count: int = 0  # BUG-080: 问答计数
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
    tags: list["TagResponse"] = []

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    document_id: str
    status: str
    message: str = "文档已提交解析"


# ==================== 问答 ====================

class QARequest(BaseModel):
    question: str = Field(min_length=1, max_length=4096)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4096)
    conversation_id: Optional[str] = None


class QAResponse(BaseModel):
    answer: str
    conversation_id: Optional[str] = None
    sources: list["SourceInfo"] = []
    confidence: float = 0.0


class ChatResponse(QAResponse):
    context_rounds: int = 0  # 多轮对话已有的轮数


class SourceInfo(BaseModel):
    document_id: str = ""
    document_name: str = ""
    chunk_text: str = ""
    page: Optional[int] = None
    section: Optional[str] = None
    score: float = 0.0
    sources: list[str] = []  # 命中通路 ["vector","bm25","kg"]
    chunk_index: Optional[int] = None


# ==================== 标签 ====================

class TagCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    color: str = Field(default="#1890ff", max_length=16)


class TagResponse(BaseModel):
    id: str
    name: str
    color: str
    kb_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class TagAssignRequest(BaseModel):
    tag_ids: list[str]
    document_ids: list[str]


# ==================== 文档详情 ====================

class DocumentDetailResponse(DocumentResponse):
    pass


# ==================== 文档替换 ====================

class DocumentReplaceRequest(BaseModel):
    change_note: str = ""


# ==================== 批量上传 ====================

class BatchItemResult(BaseModel):
    filename: str
    document_id: str = ""
    status: str = "success"  # success | failed
    message: str = ""


class BatchUploadResponse(BaseModel):
    success_count: int
    failed_count: int
    skipped_count: int = 0
    results: list[BatchItemResult] = []


# ==================== 标签统计 ====================

class TagStatResponse(BaseModel):
    id: str
    name: str
    color: str
    document_count: int


# ==================== 文档版本 ====================

class DocumentVersionResponse(BaseModel):
    id: str
    document_id: str
    version: int
    file_size: int
    file_md5: str
    chunk_count: int
    change_note: str
    created_at: datetime

    class Config:
        from_attributes = True
