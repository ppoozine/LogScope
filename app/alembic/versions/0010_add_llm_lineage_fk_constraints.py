"""add 4 FK constraints to break circular dep between llm_generation_jobs and library tables

Revision ID: 0010_add_llm_lineage_fk_constraints
Revises: 0009_extend_parse_rules_for_llm
Create Date: 2026-05-10
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0010_add_llm_lineage_fk_constraints"
down_revision: str | None = "0009_extend_parse_rules_for_llm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_log_types_source_job",
        "log_types",
        "llm_generation_jobs",
        ["source_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_parse_rules_source_job",
        "parse_rules",
        "llm_generation_jobs",
        ["source_job_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_llm_jobs_log_type",
        "llm_generation_jobs",
        "log_types",
        ["log_type_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_llm_jobs_parse_rule",
        "llm_generation_jobs",
        "parse_rules",
        ["parse_rule_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_llm_jobs_parse_rule", "llm_generation_jobs", type_="foreignkey")
    op.drop_constraint("fk_llm_jobs_log_type", "llm_generation_jobs", type_="foreignkey")
    op.drop_constraint("fk_parse_rules_source_job", "parse_rules", type_="foreignkey")
    op.drop_constraint("fk_log_types_source_job", "log_types", type_="foreignkey")
