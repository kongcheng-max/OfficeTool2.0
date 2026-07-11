"""操作审计日志模型 — W11.3

记录所有关键操作：用户、操作、时间、IP、结果。
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    """审计日志表"""
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
    )  # kb:create / doc:upload / user:delete / ...
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True,
    )  # kb / doc / user / tag
    resource_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 详情
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    success: Mapped[bool] = mapped_column(default=True)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True,
    )

    __table_args__ = (
        Index("ix_audit_user_action", "user_id", "action"),
        Index("ix_audit_created", "created_at"),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, user={self.username}, action={self.action})>"
