"""init library

Revision ID: 0003_init_library
Revises: 0002_seed_admin_user
Create Date: 2026-05-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.helpers import (
    add_updated_at_trigger,
    drop_updated_at_trigger,
)

revision: str = "0003_init_library"
down_revision: str | None = "0002_seed_admin_user"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # vendors
    op.create_table(
        "vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("website_url", sa.Text, nullable=True),
        sa.Column("logo_url", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_vendors_slug", "vendors", ["slug"])

    # products
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "vendor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vendors.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("deploy_type", sa.String(50), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("doc_url", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("vendor_id", "slug", name="uq_products_vendor_slug"),
    )
    op.create_index("ix_products_vendor_id", "products", ["vendor_id"])
    op.create_index("ix_products_category", "products", ["category"])

    # log_types — 不含 current_parse_rule_id FK constraint（先建，下面 ALTER 加）
    op.create_table(
        "log_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("transport", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("source", sa.String(20), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("current_parse_rule_id", postgresql.UUID(as_uuid=True), nullable=True),  # FK 之後 ALTER
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("product_id", "slug", name="uq_log_types_product_slug"),
    )
    op.create_index("ix_log_types_product_id", "log_types", ["product_id"])
    op.create_index("ix_log_types_status", "log_types", ["status"])

    # parse_rules
    op.create_table(
        "parse_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "log_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("log_types.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("vrl_code", sa.Text, nullable=False),
        sa.Column("engine_version", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("log_type_id", "version", name="uq_parse_rules_log_type_version"),
    )
    op.create_index("ix_parse_rules_log_type_id", "parse_rules", ["log_type_id"])
    op.create_index("ix_parse_rules_status", "parse_rules", ["status"])

    # 解循環：現在 ALTER log_types 加 FK 到 parse_rules
    op.create_foreign_key(
        "fk_log_types_current_parse_rule",
        "log_types",
        "parse_rules",
        ["current_parse_rule_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # field_schemas
    op.create_table(
        "field_schemas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "log_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("log_types.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("field_type", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_identifier", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("example_value", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("log_type_id", "field_name", name="uq_field_schemas_log_type_name"),
    )
    op.create_index("ix_field_schemas_log_type_id", "field_schemas", ["log_type_id"])
    op.create_index("ix_field_schemas_log_type_sort_order", "field_schemas", ["log_type_id", "sort_order"])

    # sample_logs
    op.create_table(
        "sample_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "log_type_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("log_types.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("raw_log", sa.Text, nullable=False),
        sa.Column("label", sa.String(20), nullable=False, server_default=sa.text("'normal'")),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("added_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_sample_logs_log_type_id", "sample_logs", ["log_type_id"])

    # 為每張表加 updated_at trigger
    for table in ("vendors", "products", "log_types", "parse_rules", "field_schemas", "sample_logs"):
        add_updated_at_trigger(table)


def downgrade() -> None:
    for table in ("sample_logs", "field_schemas", "parse_rules", "log_types", "products", "vendors"):
        drop_updated_at_trigger(table)
    op.drop_table("sample_logs")
    op.drop_table("field_schemas")
    op.drop_constraint("fk_log_types_current_parse_rule", "log_types", type_="foreignkey")
    op.drop_table("parse_rules")
    op.drop_table("log_types")
    op.drop_table("products")
    op.drop_table("vendors")
