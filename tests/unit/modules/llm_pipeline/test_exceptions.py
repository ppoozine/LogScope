from app.modules.llm_pipeline.exceptions import (
    AnthropicCallError,
    DbWriteError,
    LlmDraftError,
    SchemaMismatchError,
    VrlCompileError,
    VrlFieldsDisjointError,
)


def test_all_subclass_base():
    for cls in (
        SchemaMismatchError, VrlFieldsDisjointError,
        VrlCompileError, AnthropicCallError, DbWriteError,
    ):
        assert issubclass(cls, LlmDraftError)


def test_each_has_unique_error_code():
    codes = {
        SchemaMismatchError("x").error_code,
        VrlFieldsDisjointError("x").error_code,
        VrlCompileError("x").error_code,
        AnthropicCallError("x").error_code,
        DbWriteError("x").error_code,
    }
    assert codes == {
        "schema_mismatch", "vrl_fields_disjoint",
        "vrl_compile_failed", "anthropic_failed", "db_write_failed",
    }


def test_str_message_preserved():
    e = VrlCompileError("bad syntax at line 3")
    assert str(e) == "bad syntax at line 3"
    assert e.error_code == "vrl_compile_failed"
