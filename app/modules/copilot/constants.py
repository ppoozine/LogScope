"""Copilot module constants — SSE event names, skill ids, XML tag names."""

# SSE event names
SSE_EVENT_TEXT_DELTA = "text_delta"
SSE_EVENT_ERROR = "error"
SSE_EVENT_DONE = "done"

# Skill ids
SKILL_LOG_EXPLAIN = "log_explain"
SKILL_VRL_GENERATE = "vrl_generate"
SKILL_VRL_OPTIMIZE = "vrl_optimize"
SKILL_ANOMALY = "anomaly"
SKILL_VRL_INLINE = "vrl_inline"
SKILL_VRL_FIX = "vrl_fix"
SKILL_VRL_RUNTIME_FIX = "vrl_runtime_fix"

# Error codes (machine-readable, frontend may switch on these)
ERROR_NO_API_KEY = "no_api_key"
ERROR_ANTHROPIC_FAILED = "anthropic_failed"
ERROR_INTERNAL = "internal_error"
