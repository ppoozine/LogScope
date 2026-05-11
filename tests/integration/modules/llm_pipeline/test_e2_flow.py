"""End-to-end happy + failure flows for the E2 LLM pipeline.

Real Postgres + Redis + alembic-migrated schema. Anthropic is mocked at
the dep-override boundary (``get_anthropic_client``) so no real network
calls happen, but auth / throttle / router / service / repo / DB are all
exercised end-to-end.
"""
import uuid
from types import SimpleNamespace

import pytest

# Import all FK target models so SQLAlchemy can resolve relationships.
from app.modules.auth.models.user import User  # noqa: F401

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


def _good_response(field_name: str = "src_ip") -> SimpleNamespace:
    """Canned Anthropic response that passes parse + self-consistency + compile."""
    return SimpleNamespace(
        content=[
            SimpleNamespace(
                type="tool_use",
                name="submit_draft",
                id="t1",
                input={
                    "log_type": {
                        "name": "PAN-OS TRAFFIC",
                        "format": "syslog",
                        "transport": "syslog_udp",
                        "description": None,
                    },
                    "fields": [
                        {
                            "field_name": field_name,
                            "field_type": "ip",
                            "is_required": True,
                            "is_identifier": False,
                            "description": None,
                            "example_value": None,
                        },
                    ],
                    "vrl_code": (
                        ". = parse_syslog!(.message)\n"
                        f".{field_name} = .hostname"
                    ),
                    "engine_version": "0.32",
                    "notes": "ok",
                },
            ),
        ],
        stop_reason="tool_use",
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=50,
            cache_read_input_tokens=10,
        ),
        model_dump=lambda: {"id": "x"},
    )


class TestE2HappyFlow:
    async def test_upload_doc_then_generate_writes_three_tables(
        self,
        authenticated_client,
        override_anthropic,
        seed_vendor_product,
        db_session_factory,
    ):
        vendor, product = seed_vendor_product

        # 1. upload doc
        r = await authenticated_client.post(
            "/api/v1/llm-pipeline/docs",
            json={
                "vendor_id": str(vendor.id),
                "url": f"https://x/{uuid.uuid4().hex[:8]}",
                "content": "# example PAN-OS doc",
            },
        )
        assert r.status_code == 201, r.text
        doc_id = r.json()["data"]["id"]

        # 2. install canned anthropic response
        override_anthropic(_good_response())

        # 3. trigger generate
        r = await authenticated_client.post(
            "/api/v1/llm-pipeline/drafts/generate",
            json={"doc_id": doc_id, "product_id": str(product.id)},
        )
        assert r.status_code == 200, r.text
        body = r.json()["data"]
        assert "log_type_id" in body
        assert "parse_rule_id" in body
        assert "job_id" in body

        # 4. assert DB state via fresh session
        from sqlalchemy import select

        from app.modules.library.models.field_schema import FieldSchema
        from app.modules.library.models.log_type import LogType
        from app.modules.library.models.parse_rule import ParseRule
        from app.modules.llm_pipeline.models import LlmGenerationJob

        async with db_session_factory() as s:
            lt = await s.get(LogType, uuid.UUID(body["log_type_id"]))
            pr = await s.get(ParseRule, uuid.UUID(body["parse_rule_id"]))
            job = await s.get(LlmGenerationJob, uuid.UUID(body["job_id"]))
            assert lt is not None
            assert lt.status == "llm_draft"
            assert lt.source == "llm_generated"
            assert pr is not None
            assert pr.status == "llm_draft"
            assert pr.source == "llm_generated"
            assert lt.source_job_id == job.id
            assert pr.source_job_id == job.id
            assert job is not None
            assert job.status == "succeeded"
            assert job.input_tokens == 100
            res = await s.execute(
                select(FieldSchema).where(FieldSchema.log_type_id == lt.id)
            )
            assert len(res.scalars().all()) == 1


class TestE2FailureFlows:
    async def test_schema_mismatch_no_library_writes(
        self,
        authenticated_client,
        override_anthropic,
        seed_vendor_product,
        db_session_factory,
    ):
        """Anthropic returns text-only (no tool_use) -> 422 schema_mismatch.

        Library tables must remain empty for this product.
        """
        vendor, product = seed_vendor_product

        r = await authenticated_client.post(
            "/api/v1/llm-pipeline/docs",
            json={
                "vendor_id": str(vendor.id),
                "url": f"https://x/{uuid.uuid4().hex[:8]}",
                "content": "# x",
            },
        )
        assert r.status_code == 201, r.text
        doc_id = r.json()["data"]["id"]

        # response with text only, no tool_use block
        bad_resp = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hi")],
            stop_reason="end_turn",
            model_dump=lambda: {"id": "x"},
        )
        override_anthropic(bad_resp)

        r = await authenticated_client.post(
            "/api/v1/llm-pipeline/drafts/generate",
            json={"doc_id": doc_id, "product_id": str(product.id)},
        )
        assert r.status_code == 422
        body = r.json()["detail"]
        assert body["error_code"] == "schema_mismatch"

        # confirm no library leakage for this product
        from sqlalchemy import select

        from app.modules.library.models.log_type import LogType

        async with db_session_factory() as s:
            res = await s.execute(
                select(LogType).where(LogType.product_id == product.id)
            )
            assert res.scalars().all() == []

    async def test_vrl_compile_failed_no_library_writes(
        self,
        authenticated_client,
        override_anthropic,
        seed_vendor_product,
        db_session_factory,
    ):
        """VRL passes self-consistency (splat-assign present) but fails compile.

        Library tables must remain empty.
        """
        vendor, product = seed_vendor_product

        r = await authenticated_client.post(
            "/api/v1/llm-pipeline/docs",
            json={
                "vendor_id": str(vendor.id),
                "url": f"https://x/{uuid.uuid4().hex[:8]}",
                "content": "# x",
            },
        )
        assert r.status_code == 201, r.text
        doc_id = r.json()["data"]["id"]

        # tool_use with intentionally invalid VRL — passes parse + self-consistency
        # (splat-assign satisfies fields-disjoint check), fails compile validation.
        bad_vrl_resp = SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="tool_use",
                    name="submit_draft",
                    id="t1",
                    input={
                        "log_type": {
                            "name": "X",
                            "format": "json",
                            "transport": None,
                            "description": None,
                        },
                        "fields": [
                            {
                                "field_name": "x",
                                "field_type": "string",
                                "is_required": False,
                                "is_identifier": False,
                                "description": None,
                                "example_value": None,
                            },
                        ],
                        # splat-assign satisfies self-consistency, then nonsense
                        # after to make compile fail.
                        "vrl_code": (
                            ". = parse_json!(.message)\n"
                            "this is not vrl !!!"
                        ),
                        "engine_version": "0.32",
                        "notes": "",
                    },
                ),
            ],
            stop_reason="tool_use",
            usage=SimpleNamespace(
                input_tokens=1, output_tokens=1, cache_read_input_tokens=0,
            ),
            model_dump=lambda: {"id": "x"},
        )
        override_anthropic(bad_vrl_resp)

        r = await authenticated_client.post(
            "/api/v1/llm-pipeline/drafts/generate",
            json={"doc_id": doc_id, "product_id": str(product.id)},
        )
        assert r.status_code == 422
        assert r.json()["detail"]["error_code"] == "vrl_compile_failed"

        from sqlalchemy import select

        from app.modules.library.models.log_type import LogType

        async with db_session_factory() as s:
            res = await s.execute(
                select(LogType).where(LogType.product_id == product.id)
            )
            assert res.scalars().all() == []

    async def test_anthropic_failure_returns_502(
        self,
        authenticated_client,
        override_anthropic,
        seed_vendor_product,
    ):
        """Anthropic raises mid-call -> 502 anthropic_failed."""
        vendor, product = seed_vendor_product

        r = await authenticated_client.post(
            "/api/v1/llm-pipeline/docs",
            json={
                "vendor_id": str(vendor.id),
                "url": f"https://x/{uuid.uuid4().hex[:8]}",
                "content": "# x",
            },
        )
        assert r.status_code == 201, r.text
        doc_id = r.json()["data"]["id"]

        override_anthropic(RuntimeError("API 500"))

        r = await authenticated_client.post(
            "/api/v1/llm-pipeline/drafts/generate",
            json={"doc_id": doc_id, "product_id": str(product.id)},
        )
        assert r.status_code == 502
        assert r.json()["detail"]["error_code"] == "anthropic_failed"
