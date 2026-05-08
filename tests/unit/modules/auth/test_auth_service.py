import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.common.exceptions import UnauthorizedError
from app.modules.auth.models.user import User
from app.modules.auth.services.auth_service import AuthService


def _make_user(email: str = "a@b.c", active: bool = True) -> User:
    u = User()
    u.id = uuid.uuid4()
    u.email = email
    u.password_hash = "stored-hash"
    u.is_active = active
    return u


def _make_service(
    *,
    user_lookup: User | None = None,
    password_ok: bool = True,
):
    repo = MagicMock()
    repo.get_by_email = AsyncMock(return_value=user_lookup)
    repo.get_by_id = AsyncMock(return_value=user_lookup)

    pwd = MagicMock()
    pwd.verify = MagicMock(return_value=password_ok)

    redis = MagicMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=str(user_lookup.id) if user_lookup else None)
    redis.delete = AsyncMock(return_value=1)

    service = AuthService(
        user_repo=repo,
        password_service=pwd,
        redis_client=redis,
        session_ttl_seconds=3600,
    )
    return service, repo, pwd, redis


class TestAuthServiceLogin:
    """Tests for AuthService.login()."""

    async def test_login_success_returns_session_id(self):
        """Should return a session_id and store user_id in redis."""
        # Arrange
        user = _make_user()
        service, _repo, _pwd, redis = _make_service(user_lookup=user)

        # Act
        session_id = await service.login(email=user.email, password="anything")

        # Assert
        assert isinstance(session_id, str) and len(session_id) > 0
        redis.set.assert_awaited_once()
        args, kwargs = redis.set.call_args
        assert args[0] == f"session:{session_id}"
        assert args[1] == str(user.id)
        assert kwargs.get("ex") == 3600

    async def test_login_unknown_email_raises_unauthorized(self):
        """Should raise UnauthorizedError when email not found."""
        # Arrange
        service, *_ = _make_service(user_lookup=None)

        # Act / Assert
        with pytest.raises(UnauthorizedError):
            await service.login(email="x@y.z", password="p")

    async def test_login_wrong_password_raises_unauthorized(self):
        """Should raise UnauthorizedError when password.verify returns False."""
        # Arrange
        user = _make_user()
        service, *_ = _make_service(user_lookup=user, password_ok=False)

        # Act / Assert
        with pytest.raises(UnauthorizedError):
            await service.login(email=user.email, password="wrong")

    async def test_login_inactive_user_raises_unauthorized(self):
        """Should reject inactive users."""
        # Arrange
        user = _make_user(active=False)
        service, *_ = _make_service(user_lookup=user)

        # Act / Assert
        with pytest.raises(UnauthorizedError):
            await service.login(email=user.email, password="ok")


class TestAuthServiceLogout:
    """Tests for AuthService.logout()."""

    async def test_logout_deletes_session(self):
        """Should DEL session:{id} in redis."""
        # Arrange
        service, *_, redis = _make_service(user_lookup=_make_user())

        # Act
        await service.logout("abc-123")

        # Assert
        redis.delete.assert_awaited_once_with("session:abc-123")


class TestAuthServiceCurrentUser:
    """Tests for AuthService.get_current_user_from_session()."""

    async def test_returns_user_when_session_valid(self):
        """Should look up redis and return User."""
        # Arrange
        user = _make_user()
        service, repo, _pwd, _redis = _make_service(user_lookup=user)

        # Act
        result = await service.get_current_user_from_session("sid")

        # Assert
        assert result is user
        repo.get_by_id.assert_awaited_once()

    async def test_raises_when_no_session_id(self):
        """Should raise when session_id is None."""
        # Arrange
        service, *_ = _make_service(user_lookup=_make_user())

        # Act / Assert
        with pytest.raises(UnauthorizedError):
            await service.get_current_user_from_session(None)
