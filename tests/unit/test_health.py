class TestHealth:
    """Tests for /healthz endpoint."""

    async def test_healthz_returns_200(self, client):
        """Should return 200 with status=ok."""
        # Arrange / Act
        response = await client.get("/healthz")

        # Assert
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
