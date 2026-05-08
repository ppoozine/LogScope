from app.modules.auth.services.password_service import PasswordService


class TestPasswordService:
    """Tests for PasswordService."""

    def test_hash_then_verify_succeeds(self):
        """Should verify a correct password against its hash."""
        # Arrange
        svc = PasswordService()
        plain = "s3cret!"

        # Act
        hashed = svc.hash(plain)
        ok = svc.verify(plain, hashed)

        # Assert
        assert ok is True
        assert hashed != plain

    def test_verify_rejects_wrong_password(self):
        """Should return False when password does not match hash."""
        # Arrange
        svc = PasswordService()
        hashed = svc.hash("right")

        # Act
        ok = svc.verify("wrong", hashed)

        # Assert
        assert ok is False
