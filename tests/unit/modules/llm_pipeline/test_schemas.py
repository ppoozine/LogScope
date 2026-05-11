import uuid

import pytest
from pydantic import ValidationError

from app.modules.llm_pipeline.schemas import (
    DocCreate,
    GenerateDraftRequest,
)

VENDOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DOC_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PRODUCT_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


class TestDocCreate:
    def test_minimal(self):
        d = DocCreate(
            vendor_id=VENDOR_ID,
            content="# hello\nworld",
        )
        assert d.content_format == "markdown"

    def test_rejects_unknown_format(self):
        with pytest.raises(ValidationError):
            DocCreate(
                vendor_id=VENDOR_ID,
                content="x",
                content_format="pdf",  # type: ignore[arg-type]
            )

    def test_content_max_length(self):
        with pytest.raises(ValidationError):
            DocCreate(
                vendor_id=VENDOR_ID,
                content="x" * 200001,
            )


class TestGenerateDraftRequest:
    def test_minimal(self):
        r = GenerateDraftRequest(
            doc_id=DOC_ID,
            product_id=PRODUCT_ID,
        )
        assert r.hint is None

    def test_hint_max_length(self):
        with pytest.raises(ValidationError):
            GenerateDraftRequest(
                doc_id=DOC_ID,
                product_id=PRODUCT_ID,
                hint="x" * 1001,
            )
