"""add llm_generation_jobs table (FK constraints to log_types/parse_rules added in 0010)

Revision ID: 0007_add_llm_generation_jobs_table
Revises: 0006_add_docs_table
Create Date: 2026-05-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.helpers import add_updated_at_trigger, drop_updated_at_trigger

revision: str = "0007_add_llm_generation_jobs_table"
down_revision: str | None = "0006_add_docs_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Widen alembic_version.version_num to accommodate longer revision IDs
    # (default is varchar(32); revision IDs from this migration onward exceed that)
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")

    op.create_table(
        "llm_generation_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "doc_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("docs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("error_code", sa.String(40), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("raw_response", sa.Text, nullable=True),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("cache_read_tokens", sa.Integer, nullable=True),
        # FK constraints added in 0010 to break circular dep
        sa.Column("log_type_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parse_rule_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
        "llm_generation_jobs_status_check",
        "llm_generation_jobs",
        "status IN ('pending', 'succeeded', 'failed')",
    )
    op.create_index(
        "ix_llm_generation_jobs_product_status_started",
        "llm_generation_jobs",
        ["product_id", "status", sa.text("started_at DESC")],
    )
    add_updated_at_trigger("llm_generation_jobs")


def downgrade() -> None:
    drop_updated_at_trigger("llm_generation_jobs")
    op.drop_index(
        "ix_llm_generation_jobs_product_status_started",
        table_name="llm_generation_jobs",
    )
    op.drop_table("llm_generation_jobs")
