"""Unit tests for prompt_builder."""

from app.modules.analyzer.services.prompt_builder import (
    CatalogEntry,
    build_match_messages,
    build_match_system_prompt,
)


class TestBuildSystemPrompt:
    """Tests for build_match_system_prompt()."""

    def test_includes_top_k_and_catalog_lines(self):
        """Should embed top_k and one catalog line per entry."""
        # Arrange
        catalog = [
            CatalogEntry(
                log_type_id="aaa",
                vendor_slug="palo-alto",
                product_slug="pan-os",
                log_type_name="Traffic",
                format="csv",
                sample="1,2,allow",
            )
        ]

        # Act
        sys_prompt = build_match_system_prompt(catalog, top_k=3)

        # Assert
        assert "top 3" in sys_prompt.lower() or "at most 3" in sys_prompt.lower()
        assert "palo-alto" in sys_prompt
        assert "Traffic" in sys_prompt
        assert "1,2,allow" in sys_prompt

    def test_handles_no_sample(self):
        """Catalog entry without sample should not crash."""
        # Arrange
        catalog = [
            CatalogEntry(
                log_type_id="aaa",
                vendor_slug="x",
                product_slug="y",
                log_type_name="z",
                format="json",
                sample=None,
            )
        ]

        # Act
        sys_prompt = build_match_system_prompt(catalog, top_k=3)

        # Assert
        assert "y" in sys_prompt


class TestBuildMessages:
    """Tests for build_match_messages()."""

    def test_user_message_contains_truncated_log(self):
        """User message should embed at most first 500 chars of raw_log."""
        # Arrange
        long_log = "x" * 600

        # Act
        messages = build_match_messages(long_log)

        # Assert
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        text = messages[0]["content"]
        assert isinstance(text, str)
        assert len(text) < 700  # has wrapper text + truncated log
        assert "x" * 500 in text
        assert "x" * 501 not in text
