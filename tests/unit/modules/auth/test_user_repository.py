import uuid
from unittest.mock import AsyncMock, MagicMock

from app.modules.auth.models.user import User
from app.modules.auth.repositories.user_repository import UserRepository


def _make_user(email: str = "a@b.c") -> User:
    user = User()
    user.id = uuid.uuid4()
    user.email = email
    user.password_hash = "hashed"
    user.is_active = True
    return user


class TestUserRepositoryGetByEmail:
    """Tests for UserRepository.get_by_email()."""

    async def test_returns_user_when_found(self):
        """Should return User when email exists."""
        # Arrange
        target = _make_user("found@x.y")
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = target
        mock_session.execute = AsyncMock(return_value=mock_result)
        repo = UserRepository(mock_session)

        # Act
        result = await repo.get_by_email("found@x.y")

        # Assert
        assert result is target
        mock_session.execute.assert_awaited_once()

    async def test_returns_none_when_not_found(self):
        """Should return None when no row matches."""
        # Arrange
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        repo = UserRepository(mock_session)

        # Act
        result = await repo.get_by_email("missing@x.y")

        # Assert
        assert result is None
