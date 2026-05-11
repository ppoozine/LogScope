"""enforce unique vendor names; rename existing duplicates with rn suffix

Revision ID: 0011_vendor_name_unique
Revises: 0010_add_llm_lineage_fk_constraints
Create Date: 2026-05-11
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0011_vendor_name_unique"
down_revision: str | None = "0010_add_llm_lineage_fk_constraints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Rename duplicates: keep oldest (lowest created_at, then id as tiebreaker)
    # unchanged; suffix the rest with "-<rn>" so the unique constraint passes
    # without dropping rows or breaking FK references.
    op.execute(
        """
        WITH ranked AS (
          SELECT id,
                 ROW_NUMBER() OVER (
                   PARTITION BY name ORDER BY created_at, id
                 ) AS rn
          FROM vendors
        )
        UPDATE vendors
        SET name = vendors.name || '-' || ranked.rn::text
        FROM ranked
        WHERE vendors.id = ranked.id AND ranked.rn > 1
        """
    )

    op.create_unique_constraint("uq_vendors_name", "vendors", ["name"])


def downgrade() -> None:
    op.drop_constraint("uq_vendors_name", "vendors", type_="unique")
    # Renamed duplicates are not auto-reverted: regex stripping the "-<int>"
    # suffix would risk collapsing legitimate names like "PAN-OS-1". Leave
    # renamed rows in place; operator can manually clean if desired.
