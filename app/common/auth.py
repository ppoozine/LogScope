from typing import Annotated

from fastapi import Cookie, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_redis
from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.modules.auth.models.user import User
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.services.auth_service import AuthService
from app.modules.auth.services.password_service import PasswordService

# Cookie name 固定，不從 Settings 取，避免 Cookie(alias=...) 與 Settings 失聯
SESSION_COOKIE_NAME = "session"


async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(
        user_repo=UserRepository(session),
        password_service=PasswordService(),
        redis_client=redis,  # type: ignore[arg-type]
        session_ttl_seconds=settings.session_ttl_seconds,
    )


async def current_user(
    auth: Annotated[AuthService, Depends(get_auth_service)],
    session_cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> User:
    return await auth.get_current_user_from_session(session_cookie)
