"""VRL engine dispatch.

Imports both engine wheels at module load and exposes a single
`compile_program()` entry point that returns a thin wrapper exposing
`remap()`. Mirrors the POC's interface.
"""

from __future__ import annotations

from typing import Any

import pyvrl_playground_v25
import pyvrl_playground_v32

from app.modules.analyzer.schemas import EngineVersion

_ENGINES = {
    "0.25": pyvrl_playground_v25,
    "0.32": pyvrl_playground_v32,
}


class CompileError(Exception):
    """Raised when VRL source fails to compile."""


class Program:
    """Wraps a compiled engine `Transform` so callers don't import pyvrl directly."""

    def __init__(self, transform: Any) -> None:
        self._transform = transform

    def remap(self, event: dict) -> Any:
        return self._transform.remap(event)


def compile_program(source: str, engine: EngineVersion) -> Program:
    if engine not in _ENGINES:
        raise ValueError(f"unknown engine: {engine!r}")
    module = _ENGINES[engine]
    try:
        transform = module.Transform(source)
    except ValueError as e:
        raise CompileError(str(e)) from e
    return Program(transform)
