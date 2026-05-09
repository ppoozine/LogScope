"""parse_rule archived status + partial unique on published

Revision ID: 0005_parse_rule_archived_status
Revises: 0004_drop_product_category
Create Date: 2026-05-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_parse_rule_archived_status"
down_revision: str | None = "0004_drop_product_category"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. drop existing status check (if any)
    op.execute(
        "ALTER TABLE parse_rules DROP CONSTRAINT IF EXISTS parse_rules_status_check"
    )

    # 2. archive duplicate published rules — keep latest (highest version) per log_type
    op.execute(
        """
        WITH ranked AS (
          SELECT id,
                 ROW_NUMBER() OVER (
                   PARTITION BY log_type_id ORDER BY version DESC
                 ) AS rn
          FROM parse_rules
          WHERE status = 'published'
        )
        UPDATE parse_rules SET status = 'archived'
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
        """
    )

    # 3. add new status check including 'archived'
    op.create_check_constraint(
        "parse_rules_status_check",
        "parse_rules",
        "status IN ('draft', 'published', 'archived')",
    )

    # 4. partial unique: each log_type may have at most one published rule
    op.create_index(
        "uq_parse_rules_one_published_per_log_type",
        "parse_rules",
        ["log_type_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )


def downgrade() -> None:
    op.drop_index("uq_parse_rules_one_published_per_log_type", table_name="parse_rules")
    op.execute(
        "ALTER TABLE parse_rules DROP CONSTRAINT IF EXISTS parse_rules_status_check"
    )
    # Restore archived rows back to published (note: this may still leave duplicates,
    # but downgrade is best-effort; the partial unique index is already dropped above)
    op.execute("UPDATE parse_rules SET status = 'published' WHERE status = 'archived'")
    op.create_check_constraint(
        "parse_rules_status_check",
        "parse_rules",
        "status IN ('draft', 'published')",
    )
