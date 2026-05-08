"""init users

Revision ID: 0001_init_users
Revises:
Create Date: 2026-05-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.helpers import (
    add_updated_at_trigger,
    create_set_updated_at_function,
    drop_set_updated_at_function,
    drop_updated_at_trigger,
)

revision: str = "0001_init_users"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    create_set_updated_at_function()

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_users_email", "users", ["email"])
    add_updated_at_trigger("users")


def downgrade() -> None:
    drop_updated_at_trigger("users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    drop_set_updated_at_function()
