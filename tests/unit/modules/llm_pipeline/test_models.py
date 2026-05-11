from app.modules.llm_pipeline.models import Doc, LlmGenerationJob


def test_doc_table_name():
    assert Doc.__tablename__ == "docs"


def test_doc_columns_exist():
    cols = {c.name for c in Doc.__table__.columns}
    expected = {
        "id", "vendor_id", "url", "title", "content",
        "content_format", "fetched_at", "fetched_by",
        "created_at", "updated_at",
    }
    assert expected.issubset(cols)


def test_llm_generation_job_table_name():
    assert LlmGenerationJob.__tablename__ == "llm_generation_jobs"


def test_llm_generation_job_columns_exist():
    cols = {c.name for c in LlmGenerationJob.__table__.columns}
    expected = {
        "id", "doc_id", "product_id", "requested_by", "status", "model",
        "error_code", "error_message", "raw_response",
        "input_tokens", "output_tokens", "cache_read_tokens",
        "log_type_id", "parse_rule_id",
        "started_at", "finished_at", "created_at", "updated_at",
    }
    assert expected.issubset(cols)
