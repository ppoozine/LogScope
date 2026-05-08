import uuid
from typing import Protocol

from app.common.exceptions import UnauthorizedError
from app.modules.auth.models.user import User
from app.modules.auth.repositories.user_repository import UserRepository
from app.modules.auth.services.password_service import PasswordService


class _RedisLike(Protocol):
    async def set(self, key: str, value: str, *, ex: int | None = None) -> bool: ...
    async def get(self, key: str) -> str | None: ...
    async def delete(self, key: str) -> int: ...


class AuthService:
    def __init__(
        self,
        *,
        user_repo: UserRepository,
        password_service: PasswordService,
        redis_client: _RedisLike,
        session_ttl_seconds: int,
    ) -> None:
        self._users = user_repo
        self._pwd = password_service
        self._redis = redis_client
        self._ttl = session_ttl_seconds

    async def login(self, *, email: str, password: str) -> str:
        user = await self._users.get_by_email(email)
        if user is None or not user.is_active:
            raise UnauthorizedError("invalid credentials")
        if not self._pwd.verify(password, user.password_hash):
            raise UnauthorizedError("invalid credentials")

        session_id = uuid.uuid4().hex
        await self._redis.set(f"session:{session_id}", str(user.id), ex=self._ttl)
        return session_id

    async def logout(self, session_id: str) -> None:
        await self._redis.delete(f"session:{session_id}")

    async def get_current_user_from_session(self, session_id: str | None) -> User:
        if not session_id:
            raise UnauthorizedError("missing session")
        user_id_str = await self._redis.get(f"session:{session_id}")
        if user_id_str is None:
            raise UnauthorizedError("invalid session")
        try:
            user_id = uuid.UUID(user_id_str)
        except ValueError as e:
            raise UnauthorizedError("invalid session") from e
        user = await self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("invalid session")
        return user
