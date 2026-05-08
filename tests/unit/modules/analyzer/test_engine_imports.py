"""Sanity checks that both VRL engine wheels build and load.

If these fail, run `make build-engines` (or `uv sync`).
"""

import pyvrl_playground_v25
import pyvrl_playground_v32


class TestEngineImports:
    """Tests that both engine modules expose a working Transform class.

    VRL programs must end with a trailing ``.`` so the final expression
    resolves to the modified target event (otherwise ``remap()`` returns
    only the value of the last assignment).
    """

    def test_v25_compile_and_remap(self):
        """v0.25 engine should compile a trivial VRL and remap input."""
        # Arrange
        program = pyvrl_playground_v25.Transform('.action = "allow"\n.')

        # Act
        result = program.remap({"vendorRaw": "ignored"})

        # Assert
        assert result == {"vendorRaw": "ignored", "action": "allow"}

    def test_v32_compile_and_remap(self):
        """v0.32 engine should compile a trivial VRL and remap input."""
        # Arrange
        program = pyvrl_playground_v32.Transform('.action = "allow"\n.')

        # Act
        result = program.remap({"vendorRaw": "ignored"})

        # Assert
        assert result == {"vendorRaw": "ignored", "action": "allow"}
