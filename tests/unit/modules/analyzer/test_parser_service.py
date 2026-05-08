"""Unit tests for parser_service.

VRL programs in these tests must end with ``\\n.`` so the final expression
resolves to the modified target event (otherwise ``remap()`` returns
just the assignment value).
"""

from app.modules.analyzer.services import parser_service


class TestWrapLines:
    """Tests for parser_service.wrap_lines()."""

    def test_drops_empty_lines(self):
        """Should drop empty / whitespace-only lines."""
        # Arrange / Act
        result = parser_service.wrap_lines(["a", "  ", "", "b"])

        # Assert
        assert result == ["a", "b"]

    def test_strips_whitespace(self):
        """Should trim each line."""
        # Arrange / Act
        result = parser_service.wrap_lines(["  a  ", "\tb\t"])

        # Assert
        assert result == ["a", "b"]


class TestParserRun:
    """Tests for parser_service.run() against the real PyO3 engine."""

    def test_empty_input_returns_empty_kind(self):
        """Should return kind=empty when no non-blank logs."""
        # Arrange / Act
        resp = parser_service.run(vrl=".x = 1\n.", logs=["", "  "], engine="0.32")

        # Assert
        assert resp.kind == "empty"
        assert resp.summary is not None
        assert resp.summary.total == 0

    def test_compile_error_returns_compile_error_kind(self):
        """Should return kind=compile_error when VRL is invalid."""
        # Arrange / Act
        resp = parser_service.run(vrl="this is not vrl", logs=["x"], engine="0.32")

        # Assert
        assert resp.kind == "compile_error"
        assert resp.compile_error is not None

    def test_happy_path(self):
        """Should run VRL and return per-line success."""
        # Arrange / Act
        resp = parser_service.run(
            vrl='.action = "allow"\n.',
            logs=["one", "two"],
            engine="0.32",
        )

        # Assert
        assert resp.kind == "ok"
        assert resp.summary is not None
        assert resp.summary.success == 2
        assert resp.summary.error == 0
        assert resp.results[0].output == {"vendorRaw": "one", "action": "allow"}
        assert resp.results[1].output == {"vendorRaw": "two", "action": "allow"}

    def test_runtime_error_per_line(self):
        """Should mark a single line as error without aborting the rest."""
        # Arrange — to_int!() raises on non-numeric strings
        vrl = ".n = to_int!(.vendorRaw)\n."

        # Act
        resp = parser_service.run(vrl=vrl, logs=["abc", "42"], engine="0.32")

        # Assert
        assert resp.kind == "ok"
        assert resp.results[0].status == "error"
        assert resp.results[1].status == "success"
        assert resp.results[1].output is not None
        assert resp.results[1].output["n"] == 42

    def test_engine_version_dispatch(self):
        """Should accept both 0.25 and 0.32 engines."""
        # Arrange / Act
        for engine in ("0.25", "0.32"):
            resp = parser_service.run(vrl=".x = 1\n.", logs=["a"], engine=engine)

            # Assert
            assert resp.kind == "ok"
            assert resp.engine == engine
