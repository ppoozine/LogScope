from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.common.exceptions import (
    AppException,
    ConflictError,
    NotFoundError,
    UnauthorizedError,
)
from app.core.exception_handlers import register_exception_handlers


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


class TestIntegrityErrorHandler:
    """Tests for IntegrityError → 409 mapping."""

    def test_integrity_error_returns_409(self):
        """Should map sqlalchemy IntegrityError to 409 with 'conflict' code."""
        # Arrange
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/boom")
        async def boom():
            raise IntegrityError("INSERT FAILED", params=None, orig=Exception("FK violation"))

        client = TestClient(app)

        # Act
        r = client.get("/boom")

        # Assert
        assert r.status_code == 409
        body = r.json()
        assert body["error"]["code"] == "conflict"
        assert "constraint" in body["error"]["detail"].lower() or "integrity" in body["error"]["detail"].lower()
