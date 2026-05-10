"""Copilot chat service — orchestrates Anthropic streaming and yields SSE bytes."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from app.modules.copilot.constants import (
    ERROR_ANTHROPIC_FAILED,
    ERROR_NO_API_KEY,
    SSE_EVENT_DONE,
    SSE_EVENT_ERROR,
    SSE_EVENT_TEXT_DELTA,
)
from app.modules.copilot.schemas import ChatRequest, InlineVrlRequest
from app.modules.copilot.services.prompt_builder import (
    build_inline_system_blocks,
    build_system_blocks,
)

logger = logging.getLogger(__name__)


class ChatService:
    """Stream Anthropic responses as SSE bytes for the copilot chat endpoint."""

    def __init__(
        self,
        *,
        anthropic_client,
        anthropic_api_key: str | None,
        default_model: str,
        skill_models: dict[str, str] | None = None,
        max_history: int,
        max_log_lines_in_context: int,
        max_vrl_chars_in_context: int,
        max_library_products_in_context: int,
    ) -> None:
        self._client = anthropic_client
        self._api_key = anthropic_api_key
        self._default_model = default_model
        self._skill_models = skill_models or {}
        self._max_history = max_history
        self._max_log_lines = max_log_lines_in_context
        self._max_vrl_chars = max_vrl_chars_in_context
        self._max_library_products = max_library_products_in_context

    def _model_for(self, skill: str | None) -> str:
        if skill and skill in self._skill_models:
            return self._skill_models[skill]
        return self._default_model

    async def stream(self, *, request: ChatRequest) -> AsyncIterator[bytes]:
        if not self._api_key:
            yield self._sse(
                SSE_EVENT_ERROR,
                {
                    "code": ERROR_NO_API_KEY,
                    "message": "Copilot 未啟用：尚未設定 ANTHROPIC_API_KEY",
                },
            )
            yield self._sse(SSE_EVENT_DONE, {})
            return

        system_blocks = build_system_blocks(
            skill=request.skill,
            page_context=request.page_context,
            max_log_lines=self._max_log_lines,
            max_vrl_chars=self._max_vrl_chars,
            max_library_products=self._max_library_products,
        )
        anthropic_messages = [
            {"role": m.role, "content": m.content}
            for m in request.messages[-self._max_history :]
        ]

        try:
            async with self._client.messages.stream(
                model=self._model_for(request.skill),
                max_tokens=2048,
                system=system_blocks,
                messages=anthropic_messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield self._sse(SSE_EVENT_TEXT_DELTA, {"text": text})
        except Exception:
            logger.exception("anthropic_stream_failed")
            yield self._sse(
                SSE_EVENT_ERROR,
                {
                    "code": ERROR_ANTHROPIC_FAILED,
                    "message": "Copilot 暫時無法回應，請稍後再試",
                },
            )
        finally:
            yield self._sse(SSE_EVENT_DONE, {})

    async def stream_inline(
        self, *, request: InlineVrlRequest
    ) -> AsyncIterator[bytes]:
        """Stream Anthropic completion for inline VRL editor (⌘K)."""
        if not self._api_key:
            yield self._sse(
                SSE_EVENT_ERROR,
                {
                    "code": ERROR_NO_API_KEY,
                    "message": "Copilot 未啟用：尚未設定 ANTHROPIC_API_KEY",
                },
            )
            yield self._sse(SSE_EVENT_DONE, {})
            return

        system_blocks = build_inline_system_blocks(
            request,
            max_log_lines=self._max_log_lines,
            max_vrl_chars=self._max_vrl_chars,
        )
        anthropic_messages = [{"role": "user", "content": request.instruction}]

        try:
            async with self._client.messages.stream(
                model=self._model_for(request.skill),
                max_tokens=1024,
                system=system_blocks,
                messages=anthropic_messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield self._sse(SSE_EVENT_TEXT_DELTA, {"text": text})
        except Exception:
            logger.exception("anthropic_inline_failed")
            yield self._sse(
                SSE_EVENT_ERROR,
                {
                    "code": ERROR_ANTHROPIC_FAILED,
                    "message": "Copilot 暫時無法回應，請稍後再試",
                },
            )
        finally:
            yield self._sse(SSE_EVENT_DONE, {})

    @staticmethod
    def _sse(event: str, data: dict) -> bytes:
        body = json.dumps(data, ensure_ascii=False)
        return f"event: {event}\ndata: {body}\n\n".encode()
