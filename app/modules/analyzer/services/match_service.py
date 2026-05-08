"""LLM-based vendor/product match service."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Protocol

from app.modules.analyzer.schemas import MatchCandidate, MatchResponse
from app.modules.analyzer.services.prompt_builder import (
    CatalogEntry,
    build_match_messages,
    build_match_system_prompt,
)

logger = logging.getLogger(__name__)


@dataclass
class _CatalogRow:
    """Internal repo row shape."""

    log_type_id: uuid.UUID
    vendor_slug: str
    product_slug: str
    log_type_name: str
    format: str
    sample: str | None


class _CatalogRepoLike(Protocol):
    async def fetch_all(self) -> list[_CatalogRow]: ...


class _AnthropicLike(Protocol):
    messages: object  # has async .create(...)


class MatchService:
    """Match raw log against Library candidates using an LLM."""

    def __init__(
        self,
        *,
        catalog_repo: _CatalogRepoLike,
        anthropic_client: _AnthropicLike,
        anthropic_api_key: str | None,
        model: str,
    ) -> None:
        self._catalog = catalog_repo
        self._client = anthropic_client
        self._api_key = anthropic_api_key
        self._model = model

    async def match(self, *, raw_log: str, top_k: int) -> MatchResponse:
        if not self._api_key:
            return MatchResponse(candidates=[])

        rows = await self._catalog.fetch_all()
        if not rows:
            return MatchResponse(candidates=[])

        catalog_entries = [
            CatalogEntry(
                log_type_id=str(r.log_type_id),
                vendor_slug=r.vendor_slug,
                product_slug=r.product_slug,
                log_type_name=r.log_type_name,
                format=r.format,
                sample=r.sample,
            )
            for r in rows
        ]
        system_prompt = build_match_system_prompt(catalog_entries, top_k=top_k)
        messages = build_match_messages(raw_log)

        try:
            response = await self._client.messages.create(  # type: ignore[attr-defined]
                model=self._model,
                max_tokens=1024,
                system=[
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=messages,
            )
            text = response.content[0].text
        except Exception:
            logger.exception("anthropic_call_failed")
            return MatchResponse(candidates=[])

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("llm_returned_non_json", extra={"text": text[:200]})
            return MatchResponse(candidates=[])

        raw_candidates = parsed.get("candidates") or []
        row_by_id = {str(r.log_type_id): r for r in rows}

        result_candidates: list[MatchCandidate] = []
        for cand in raw_candidates:
            lt_id = cand.get("log_type_id")
            row = row_by_id.get(str(lt_id))
            if row is None:
                continue
            try:
                result_candidates.append(
                    MatchCandidate(
                        vendor_slug=row.vendor_slug,
                        product_slug=row.product_slug,
                        log_type_id=row.log_type_id,
                        log_type_name=row.log_type_name,
                        confidence=float(cand.get("confidence", 0.0)),
                        reason=str(cand.get("reason", "")),
                    )
                )
            except (ValueError, TypeError):
                continue

        result_candidates.sort(key=lambda c: c.confidence, reverse=True)
        return MatchResponse(candidates=result_candidates[:top_k])
