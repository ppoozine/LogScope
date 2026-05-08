from app.common.exceptions import (
    AppException,
    ConflictError,
    NotFoundError,
    UnauthorizedError,
)


class TestAppException:
    """Tests for AppException hierarchy."""

    def test_not_found_default_status(self):
        """Should set status_code=404 and code='not_found'."""
        # Arrange / Act
        exc = NotFoundError("vendor not found")

        # Assert
        assert exc.status_code == 404
        assert exc.code == "not_found"
        assert exc.detail == "vendor not found"

    def test_conflict_default_status(self):
        """Should set status_code=409."""
        # Arrange / Act
        exc = ConflictError()

        # Assert
        assert exc.status_code == 409
        assert exc.code == "conflict"

    def test_unauthorized_default_status(self):
        """Should set status_code=401."""
        # Arrange / Act
        exc = UnauthorizedError()

        # Assert
        assert exc.status_code == 401
        assert isinstance(exc, AppException)
