"""seed admin user

Revision ID: 0002_seed_admin_user
Revises: 0001_init_users
Create Date: 2026-05-08
"""
import os
import uuid
from collections.abc import Sequence

import bcrypt
import sqlalchemy as sa
from alembic import op

revision: str = "0002_seed_admin_user"
down_revision: str | None = "0001_init_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _get_admin_credentials() -> tuple[str, str]:
    """從環境變數或 pydantic Settings 取得 admin 帳密。"""
    email = os.environ.get("LOGSCOPE_ADMIN_EMAIL")
    password = os.environ.get("LOGSCOPE_ADMIN_PASSWORD")
    if email and password:
        return email, password

    # fallback：透過 pydantic_settings（會讀 .env 檔）
    try:
        from app.core.config import get_settings

        settings = get_settings()
        return settings.admin_email, settings.admin_password
    except Exception:
        pass

    raise RuntimeError(
        "LOGSCOPE_ADMIN_EMAIL and LOGSCOPE_ADMIN_PASSWORD must be set to run 0002 migration"
    )


def upgrade() -> None:
    email, password = _get_admin_credentials()

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    op.execute(
        sa.text(
            "INSERT INTO users (id, email, password_hash, display_name, is_active) "
            "VALUES (:id, :email, :hash, :name, true)"
        ).bindparams(
            id=uuid.uuid4(),
            email=email,
            hash=password_hash,
            name="Admin",
        )
    )


def downgrade() -> None:
    email = os.environ.get("LOGSCOPE_ADMIN_EMAIL")
    if not email:
        try:
            from app.core.config import get_settings

            email = get_settings().admin_email
        except Exception:
            return
    op.execute(sa.text("DELETE FROM users WHERE email = :email").bindparams(email=email))
