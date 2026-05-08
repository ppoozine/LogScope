"""Read-only loader for bundled VRL+logs fixtures.

Each fixture is a sub-directory under ``fixtures/<id>/`` containing:

- ``parser.vrl`` — VRL source
- ``logs.txt`` — one raw log per line
- ``meta.json`` (optional) — ``{name, description, engine}``

The bundle ships in the repo, so reads happen from local disk on every
list call. Fixtures are small (a few KB) so a fresh read each time is
fine and keeps changes hot-reloadable in dev.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from app.modules.analyzer.schemas import EngineVersion, FixtureItem

# Repo layout: this file lives at app/modules/analyzer/services/fixtures_service.py
# fixtures/ is at the repo root, three "parents" up + one back down.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURES_DIR = _REPO_ROOT / "fixtures"


def list_fixtures() -> list[FixtureItem]:
    """Return all bundled fixtures, sorted by id."""
    if not _FIXTURES_DIR.is_dir():
        return []
    out: list[FixtureItem] = []
    for entry in sorted(_FIXTURES_DIR.iterdir()):
        if not entry.is_dir():
            continue
        parser = entry / "parser.vrl"
        logs = entry / "logs.txt"
        if not parser.is_file() or not logs.is_file():
            continue
        meta: dict = {}
        meta_path = entry / "meta.json"
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text())
            except json.JSONDecodeError:
                meta = {}
        engine_raw = meta.get("engine", "0.32")
        engine: EngineVersion = cast(EngineVersion, engine_raw if engine_raw in ("0.25", "0.32") else "0.32")
        out.append(
            FixtureItem(
                id=entry.name,
                name=meta.get("name", entry.name),
                description=meta.get("description", ""),
                vrl=parser.read_text(),
                logs=logs.read_text(),
                engine=engine,
            )
        )
    return out
