"""initial_schema

Revision ID: 001
Revises:
Create Date: 2026-06-28 15:26:31

All core tables: users, knowledge_bases, documents, tags,
document_tags (association), document_versions.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("email", sa.String(128), nullable=True),
        sa.Column("hashed_password", sa.String(256), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="editor"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            # Python ORM handles default via _utcnow(); no DB-level default needed,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            # Python ORM handles default via _utcnow(); no DB-level default needed,
        ),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    # --- knowledge_bases ---
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            # Python ORM handles default via _utcnow(); no DB-level default needed,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            # Python ORM handles default via _utcnow(); no DB-level default needed,
        ),
    )
    op.create_index(
        op.f("ix_knowledge_bases_owner_id"), "knowledge_bases", ["owner_id"]
    )

    # --- documents ---
    op.create_table(
        "documents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "kb_id",
            sa.String(32),
            sa.ForeignKey("knowledge_bases.id"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(256), nullable=False),
        sa.Column("original_filename", sa.String(256), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mime_type", sa.String(128), nullable=False, server_default=""),
        sa.Column("file_path", sa.String(512), nullable=False, server_default=""),
        sa.Column("file_md5", sa.String(64), nullable=False, server_default=""),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            # Python ORM handles default via _utcnow(); no DB-level default needed,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            # Python ORM handles default via _utcnow(); no DB-level default needed,
        ),
    )
    op.create_index(op.f("ix_documents_kb_id"), "documents", ["kb_id"])
    op.create_index(op.f("ix_documents_status"), "documents", ["status"])

    # --- tags ---
    op.create_table(
        "tags",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("color", sa.String(16), nullable=False, server_default="#1890ff"),
        sa.Column(
            "kb_id",
            sa.String(32),
            sa.ForeignKey("knowledge_bases.id"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            # Python ORM handles default via _utcnow(); no DB-level default needed,
        ),
    )
    op.create_index(op.f("ix_tags_kb_id"), "tags", ["kb_id"])

    # --- document_tags (many-to-many association) ---
    op.create_table(
        "document_tags",
        sa.Column(
            "document_id",
            sa.String(32),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "tag_id",
            sa.String(32),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # --- document_versions ---
    op.create_table(
        "document_versions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(32),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("file_path", sa.String(512), nullable=False, server_default=""),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("file_md5", sa.String(64), nullable=False, server_default=""),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("change_note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            # Python ORM handles default via _utcnow(); no DB-level default needed,
        ),
    )
    op.create_index(
        op.f("ix_document_versions_document_id"),
        "document_versions",
        ["document_id"],
    )


def downgrade() -> None:
    op.drop_table("document_versions")
    op.drop_table("document_tags")
    op.drop_table("tags")
    op.drop_table("documents")
    op.drop_table("knowledge_bases")
    op.drop_table("users")
