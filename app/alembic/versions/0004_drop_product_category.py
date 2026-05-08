"""drop product category

Revision ID: 0004_drop_product_category
Revises: 0003_init_library
Create Date: 2026-05-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_drop_product_category"
down_revision: str | None = "0003_init_library"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_products_category", table_name="products")
    op.drop_column("products", "category")


def downgrade() -> None:
    op.add_column("products", sa.Column("category", sa.String(50), nullable=True))
    op.create_index("ix_products_category", "products", ["category"])
