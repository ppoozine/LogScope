"""extend parse_rules: status CHECK includes llm_draft; add source + source_job_id

Revision ID: 0009_extend_parse_rules_for_llm
Revises: 0008_extend_log_types_for_llm
Create Date: 2026-05-10
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_extend_parse_rules_for_llm"
down_revision: str | None = "0008_extend_log_types_for_llm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE parse_rules DROP CONSTRAINT IF EXISTS parse_rules_status_check"
    )
    op.create_check_constraint(
        "parse_rules_status_check",
        "parse_rules",
        "status IN ('draft', 'llm_draft', 'published', 'archived')",
    )

    op.add_column(
        "parse_rules",
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'manual'"),
        ),
    )
    op.create_check_constraint(
        "parse_rules_source_check",
        "parse_rules",
        "source IN ('manual', 'llm_generated')",
    )
    op.add_column(
        "parse_rules",
        sa.Column("source_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("parse_rules", "source_job_id")
    op.drop_constraint("parse_rules_source_check", "parse_rules", type_="check")
    op.drop_column("parse_rules", "source")
    op.execute(
        "ALTER TABLE parse_rules DROP CONSTRAINT IF EXISTS parse_rules_status_check"
    )
    op.create_check_constraint(
        "parse_rules_status_check",
        "parse_rules",
        "status IN ('draft', 'published', 'archived')",
    )
