from app.common.utils.slug import slugify


class TestSlugify:
    """Tests for slugify utility."""

    def test_lowercases_and_replaces_spaces(self) -> None:
        """Should lowercase and replace spaces with hyphens."""
        # Arrange / Act
        result = slugify("Palo Alto Networks")

        # Assert
        assert result == "palo-alto-networks"

    def test_strips_special_chars(self) -> None:
        """Should remove non-alphanumeric chars except hyphens."""
        # Arrange / Act
        result = slugify("Acme, Inc.")

        # Assert
        assert result == "acme-inc"

    def test_collapses_multiple_hyphens(self) -> None:
        """Should collapse runs of hyphens into one."""
        # Arrange / Act
        result = slugify("foo  --  bar")

        # Assert
        assert result == "foo-bar"

    def test_strips_leading_trailing_hyphens(self) -> None:
        """Should not start or end with a hyphen."""
        # Arrange / Act
        result = slugify("--hello--")

        # Assert
        assert result == "hello"
