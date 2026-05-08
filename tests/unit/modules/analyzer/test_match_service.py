"""Unit tests for MatchService (mocked Anthropic + repo)."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.analyzer.services.match_service import (
    MatchService,
    _CatalogRow,
)


def _row(log_type_id=None, vendor="palo-alto", product="pan-os", name="Traffic"):
    return _CatalogRow(
        log_type_id=log_type_id or uuid.uuid4(),
        vendor_slug=vendor,
        product_slug=product,
        log_type_name=name,
        format="csv",
        sample=None,
    )


def _make_anthropic_response(json_text: str):
    """Build a fake Anthropic SDK response that yields .content[0].text."""
    block = MagicMock()
    block.text = json_text
    msg = MagicMock()
    msg.content = [block]
    return msg


def _make_service(*, catalog_rows: list[_CatalogRow], anthropic_response, api_key: str | None = "key"):
    catalog_repo = MagicMock()
    catalog_repo.fetch_all = AsyncMock(return_value=catalog_rows)

    anthropic_client = MagicMock()
    anthropic_client.messages.create = AsyncMock(return_value=anthropic_response)

    return MatchService(
        catalog_repo=catalog_repo,
        anthropic_client=anthropic_client,
        anthropic_api_key=api_key,
        model="claude-haiku-4-5-20251001",
    )


class TestMatchServiceMatch:
    """Tests for MatchService.match()."""

    async def test_returns_candidates_from_llm(self):
        """LLM returns valid JSON → service returns parsed candidates."""
        # Arrange
        row = _row()
        llm_json = json.dumps(
            {
                "candidates": [
                    {
                        "log_type_id": str(row.log_type_id),
                        "confidence": 0.9,
                        "reason": "格式像 PAN-OS Traffic CSV",
                    }
                ]
            }
        )
        service = _make_service(
            catalog_rows=[row],
            anthropic_response=_make_anthropic_response(llm_json),
        )

        # Act
        result = await service.match(raw_log="1,2,3", top_k=3)

        # Assert
        assert len(result.candidates) == 1
        cand = result.candidates[0]
        assert cand.log_type_id == row.log_type_id
        assert cand.confidence == pytest.approx(0.9)
        assert cand.vendor_slug == row.vendor_slug

    async def test_filters_unknown_log_type_ids(self):
        """LLM hallucinates a log_type_id not in catalog → drop it."""
        # Arrange
        row = _row()
        unknown_id = str(uuid.uuid4())
        llm_json = json.dumps(
            {
                "candidates": [
                    {"log_type_id": unknown_id, "confidence": 0.95, "reason": "x"},
                    {"log_type_id": str(row.log_type_id), "confidence": 0.5, "reason": "y"},
                ]
            }
        )
        service = _make_service(
            catalog_rows=[row],
            anthropic_response=_make_anthropic_response(llm_json),
        )

        # Act
        result = await service.match(raw_log="x", top_k=3)

        # Assert
        assert len(result.candidates) == 1
        assert result.candidates[0].log_type_id == row.log_type_id

    async def test_returns_empty_when_no_api_key(self):
        """Service should short-circuit and return empty when key absent."""
        # Arrange
        service = _make_service(
            catalog_rows=[_row()],
            anthropic_response=_make_anthropic_response("{}"),
            api_key=None,
        )

        # Act
        result = await service.match(raw_log="x", top_k=3)

        # Assert
        assert result.candidates == []

    async def test_returns_empty_when_llm_returns_invalid_json(self):
        """Should swallow JSON parse errors and return empty."""
        # Arrange
        service = _make_service(
            catalog_rows=[_row()],
            anthropic_response=_make_anthropic_response("not json"),
        )

        # Act
        result = await service.match(raw_log="x", top_k=3)

        # Assert
        assert result.candidates == []

    async def test_empty_catalog_skips_llm_call(self):
        """When DB has zero LogTypes, do not call LLM at all."""
        # Arrange
        anthropic_client = MagicMock()
        anthropic_client.messages.create = AsyncMock()

        catalog_repo = MagicMock()
        catalog_repo.fetch_all = AsyncMock(return_value=[])

        service = MatchService(
            catalog_repo=catalog_repo,
            anthropic_client=anthropic_client,
            anthropic_api_key="key",
            model="m",
        )

        # Act
        result = await service.match(raw_log="x", top_k=3)

        # Assert
        assert result.candidates == []
        anthropic_client.messages.create.assert_not_called()

    async def test_sorts_by_confidence_descending(self):
        """Candidates returned should be sorted high → low."""
        # Arrange
        row1 = _row()
        row2 = _row(vendor="fortinet", product="fortigate")
        llm_json = json.dumps(
            {
                "candidates": [
                    {"log_type_id": str(row1.log_type_id), "confidence": 0.4, "reason": "a"},
                    {"log_type_id": str(row2.log_type_id), "confidence": 0.8, "reason": "b"},
                ]
            }
        )
        service = _make_service(
            catalog_rows=[row1, row2],
            anthropic_response=_make_anthropic_response(llm_json),
        )

        # Act
        result = await service.match(raw_log="x", top_k=3)

        # Assert
        assert [c.confidence for c in result.candidates] == [0.8, 0.4]
