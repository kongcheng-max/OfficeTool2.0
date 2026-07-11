"""add_audit_logs

Revision ID: 002
Revises: 001
Create Date: 2026-07-11

W11.3: 审计日志表 + W10.7 复合索引。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── audit_logs (W11.3) ──
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(32), nullable=False, index=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False, index=True),
        sa.Column("resource_type", sa.String(32), nullable=True),
        sa.Column("resource_id", sa.String(64), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(256), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            # Python ORM handles default via _utcnow()
        ),
    )
    op.create_index("ix_audit_user_action", "audit_logs", ["user_id", "action"])
    op.create_index("ix_audit_created", "audit_logs", ["created_at"])

    # ── W10.7 复合索引 ──
    op.create_index("ix_documents_kb_status", "documents", ["kb_id", "status"])
    op.create_index("ix_documents_kb_md5", "documents", ["kb_id", "file_md5"])
    op.create_index("ix_documents_kb_created", "documents", ["kb_id", "created_at"])
    op.create_index("ix_tags_kb_name", "tags", ["kb_id", "name"])


def downgrade() -> None:
    op.drop_index("ix_tags_kb_name", table_name="tags")
    op.drop_index("ix_documents_kb_created", table_name="documents")
    op.drop_index("ix_documents_kb_md5", table_name="documents")
    op.drop_index("ix_documents_kb_status", table_name="documents")
    op.drop_index("ix_audit_created", table_name="audit_logs")
    op.drop_index("ix_audit_user_action", table_name="audit_logs")
    op.drop_table("audit_logs")
