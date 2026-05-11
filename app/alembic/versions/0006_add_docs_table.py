"""add docs table

Revision ID: 0006_add_docs_table
Revises: 0005_parse_rule_archived_status
Create Date: 2026-05-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.helpers import add_updated_at_trigger, drop_updated_at_trigger

revision: str = "0006_add_docs_table"
down_revision: str | None = "0005_parse_rule_archived_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "docs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "vendor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("url", sa.Text, nullable=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column(
            "content_format",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'markdown'"),
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "fetched_by",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'manual'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_check_constraint(
        "docs_content_format_check",
        "docs",
        "content_format IN ('markdown')",
    )
    op.create_check_constraint(
        "docs_fetched_by_check",
        "docs",
        "fetched_by IN ('manual', 'crawler')",
    )
    op.create_index("ix_docs_vendor_id_created_at", "docs", ["vendor_id", sa.text("created_at DESC")])
    op.create_index(
        "uq_docs_vendor_url",
        "docs",
        ["vendor_id", "url"],
        unique=True,
        postgresql_where=sa.text("url IS NOT NULL"),
    )
    add_updated_at_trigger("docs")


def downgrade() -> None:
    drop_updated_at_trigger("docs")
    op.drop_index("uq_docs_vendor_url", table_name="docs")
    op.drop_index("ix_docs_vendor_id_created_at", table_name="docs")
    op.drop_table("docs")
