"""Run a VRL program against a batch of raw log lines."""

from __future__ import annotations

from app.modules.analyzer.schemas import (
    EngineVersion,
    ParseResponse,
    ParseResultItem,
    ParseSummary,
)
from app.modules.analyzer.services.vrl_runtime import CompileError, compile_program


def wrap_lines(logs: list[str]) -> list[str]:
    """Trim and drop empty lines."""
    return [stripped for line in logs if (stripped := line.strip())]


def run(vrl: str, logs: list[str], engine: EngineVersion) -> ParseResponse:
    """Compile VRL once, run it against each non-empty log line."""
    raw_lines = wrap_lines(logs)

    if not raw_lines:
        return ParseResponse(
            kind="empty",
            engine=engine,
            summary=ParseSummary(total=0, success=0, error=0),
        )

    try:
        program = compile_program(vrl, engine)
    except CompileError as err:
        return ParseResponse(
            kind="compile_error",
            engine=engine,
            compile_error=str(err),
        )

    results: list[ParseResultItem] = []
    success = 0
    error = 0
    for i, line in enumerate(raw_lines):
        event = {"vendorRaw": line}
        try:
            output = program.remap(event)
            results.append(ParseResultItem(index=i, input=line, status="success", output=output))
            success += 1
        except Exception as e:  # engine raises generic errors
            results.append(ParseResultItem(index=i, input=line, status="error", error=str(e)))
            error += 1

    return ParseResponse(
        kind="ok",
        engine=engine,
        summary=ParseSummary(total=len(raw_lines), success=success, error=error),
        results=results,
    )
