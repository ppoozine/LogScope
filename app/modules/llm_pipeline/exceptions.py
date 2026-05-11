"""Exception classes used by llm_pipeline. Each carries a stable error_code
that is forwarded to the audit job row and the HTTP error response body."""


class LlmDraftError(Exception):
    """Base for errors raised during draft generation. Subclasses set error_code."""

    error_code: str = "llm_draft_error"


class SchemaMismatchError(LlmDraftError):
    error_code = "schema_mismatch"


class VrlFieldsDisjointError(LlmDraftError):
    error_code = "vrl_fields_disjoint"


class VrlCompileError(LlmDraftError):
    error_code = "vrl_compile_failed"


class AnthropicCallError(LlmDraftError):
    error_code = "anthropic_failed"


class DbWriteError(LlmDraftError):
    error_code = "db_write_failed"
