"""Compile-validate a VRL program against a target engine version.

Thin wrapper over analyzer.vrl_runtime.compile_program. Translates the
analyzer's CompileError (and any unexpected exception class from PyO3)
into our own VrlCompileError so service-layer callers depend only on
llm_pipeline.exceptions."""
from app.modules.analyzer.schemas import EngineVersion
from app.modules.analyzer.services import vrl_runtime
from app.modules.llm_pipeline.exceptions import VrlCompileError


def validate_vrl(vrl_code: str, *, engine_version: EngineVersion) -> None:
    """Raise VrlCompileError if vrl_code does not compile under engine_version.

    Returns None on success.
    """
    try:
        vrl_runtime.compile_program(vrl_code, engine_version)
    except vrl_runtime.CompileError as e:
        raise VrlCompileError(str(e)) from e
