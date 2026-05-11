"""extend log_types: status/source CHECKs include llm_draft/llm_generated; add source_job_id

Revision ID: 0008_extend_log_types_for_llm
Revises: 0007_add_llm_generation_jobs_table
Create Date: 2026-05-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_extend_log_types_for_llm"
down_revision: str | None = "0007_add_llm_generation_jobs_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop existing CHECKs if any (init migration didn't add them; defensive)
    op.execute(
        "ALTER TABLE log_types DROP CONSTRAINT IF EXISTS log_types_status_check"
    )
    op.execute(
        "ALTER TABLE log_types DROP CONSTRAINT IF EXISTS log_types_source_check"
    )

    op.create_check_constraint(
        "log_types_status_check",
        "log_types",
        "status IN ('draft', 'llm_draft', 'published')",
    )
    op.create_check_constraint(
        "log_types_source_check",
        "log_types",
        "source IN ('manual', 'llm_generated')",
    )

    # source_job_id — FK constraint added in 0010
    op.add_column(
        "log_types",
        sa.Column("source_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("log_types", "source_job_id")
    op.execute(
        "ALTER TABLE log_types DROP CONSTRAINT IF EXISTS log_types_status_check"
    )
    op.execute(
        "ALTER TABLE log_types DROP CONSTRAINT IF EXISTS log_types_source_check"
    )
    # Restore narrower CHECKs
    op.create_check_constraint(
        "log_types_status_check",
        "log_types",
        "status IN ('draft', 'published')",
    )
    op.create_check_constraint(
        "log_types_source_check",
        "log_types",
        "source IN ('manual')",
    )
