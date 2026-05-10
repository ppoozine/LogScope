"""Unit tests for ChatService.stream() (mocked Anthropic SDK)."""

import json
from unittest.mock import MagicMock

from app.modules.copilot.schemas import ChatRequest, InlineVrlRequest
from app.modules.copilot.services.chat_service import ChatService


def _request(*, messages=None, skill=None, page_context=None) -> ChatRequest:
    return ChatRequest.model_validate(
        {
            "messages": messages or [{"role": "user", "content": "hi"}],
            "skill": skill,
            "page_context": page_context,
        }
    )


def _fake_anthropic_stream(text_chunks: list[str], *, raise_exc: Exception | None = None):
    """Build a fake Anthropic SDK stream context manager.

    Mimics `async with client.messages.stream(...) as stream:
                async for text in stream.text_stream: ...`
    """
    class _FakeStream:
        async def __aenter__(self_inner):
            return self_inner

        async def __aexit__(self_inner, *args):
            return False

        @property
        def text_stream(self_inner):
            async def _iter():
                if raise_exc is not None:
                    raise raise_exc
                for c in text_chunks:
                    yield c
            return _iter()

    client = MagicMock()
    client.messages.stream = MagicMock(return_value=_FakeStream())
    return client


def _make_service(*, client=None, api_key: str | None = "sk-test"):
    client = client or _fake_anthropic_stream([])
    return ChatService(
        anthropic_client=client,
        anthropic_api_key=api_key,
        default_model="claude-haiku-4-5-20251001",
        skill_models={},
        max_history=20,
        max_log_lines_in_context=20,
        max_vrl_chars_in_context=4000,
        max_library_products_in_context=20,
    )


async def _collect(gen) -> list[bytes]:
    out: list[bytes] = []
    async for chunk in gen:
        out.append(chunk)
    return out


def _decode_events(chunks: list[bytes]) -> list[tuple[str, dict]]:
    """Parse SSE bytes into (event, data) tuples."""
    text = b"".join(chunks).decode()
    events: list[tuple[str, dict]] = []
    for frame in text.split("\n\n"):
        if not frame.strip():
            continue
        ev = ""
        data = ""
        for line in frame.split("\n"):
            if line.startswith("event:"):
                ev = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data += line[len("data:"):].strip()
        events.append((ev, json.loads(data) if data else {}))
    return events


class TestChatServiceStream:
    async def test_no_api_key_yields_error_then_done(self):
        # Arrange
        service = _make_service(api_key=None)

        # Act
        chunks = await _collect(service.stream(request=_request()))
        events = _decode_events(chunks)

        # Assert
        assert [e[0] for e in events] == ["error", "done"]
        assert events[0][1]["code"] == "no_api_key"
        assert "ANTHROPIC_API_KEY" in events[0][1]["message"]

    async def test_happy_path_yields_text_deltas_then_done(self):
        # Arrange
        client = _fake_anthropic_stream(["hello ", "world", "!"])
        service = _make_service(client=client)

        # Act
        events = _decode_events(await _collect(service.stream(request=_request())))

        # Assert
        kinds = [e[0] for e in events]
        assert kinds == ["text_delta", "text_delta", "text_delta", "done"]
        assert [e[1].get("text") for e in events[:3]] == ["hello ", "world", "!"]

    async def test_anthropic_failure_yields_error_then_done(self):
        # Arrange
        client = _fake_anthropic_stream([], raise_exc=RuntimeError("boom"))
        service = _make_service(client=client)

        # Act
        events = _decode_events(await _collect(service.stream(request=_request())))

        # Assert
        assert events[-1][0] == "done"
        # error event present somewhere before done
        error_events = [e for e in events if e[0] == "error"]
        assert len(error_events) == 1
        assert error_events[0][1]["code"] == "anthropic_failed"

    async def test_truncates_messages_to_max_history(self):
        # Arrange: send 30 messages, expect only last 20 to reach SDK
        captured = {}

        class _StreamCapture:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            @property
            def text_stream(self):
                async def _iter():
                    yield "ok"
                return _iter()

        client = MagicMock()
        client.messages.stream = MagicMock(side_effect=lambda **kw: _StreamCapture(**kw))

        service = ChatService(
            anthropic_client=client,
            anthropic_api_key="sk",
            default_model="m",
            skill_models={},
            max_history=20,
            max_log_lines_in_context=20,
            max_vrl_chars_in_context=4000,
            max_library_products_in_context=20,
        )

        # 30 alternating user/assistant — must end with user
        msgs = []
        for i in range(15):
            msgs.append({"role": "user", "content": f"u{i}"})
            msgs.append({"role": "assistant", "content": f"a{i}"})
        # ensure last is user
        msgs.append({"role": "user", "content": "final"})

        # Act
        await _collect(service.stream(request=_request(messages=msgs)))

        # Assert
        sent = captured["messages"]
        assert len(sent) == 20
        assert sent[-1]["content"] == "final"

    async def test_passes_system_blocks_with_cache_control(self):
        # Arrange
        captured = {}

        class _Cap:
            def __init__(self, **kw):
                captured.update(kw)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            @property
            def text_stream(self):
                async def _iter():
                    if False:
                        yield ""
                return _iter()

        client = MagicMock()
        client.messages.stream = MagicMock(side_effect=lambda **kw: _Cap(**kw))
        service = _make_service(client=client)

        # Act
        await _collect(
            service.stream(request=_request(skill="log_explain"))
        )

        # Assert
        system = captured["system"]
        assert isinstance(system, list)
        assert system[0]["cache_control"] == {"type": "ephemeral"}
        assert "log_explain" in system[0]["text"]


class TestModelDispatch:
    def _make_service(self, skill_models, default_model="claude-haiku-4-5"):
        from app.modules.copilot.services.chat_service import ChatService
        return ChatService(
            anthropic_client=object(),
            anthropic_api_key="test",
            default_model=default_model,
            skill_models=skill_models,
            max_history=20,
            max_log_lines_in_context=10,
            max_vrl_chars_in_context=4000,
            max_library_products_in_context=20,
        )

    def test_no_override_uses_default(self):
        s = self._make_service(skill_models={})
        assert s._model_for("log_explain") == "claude-haiku-4-5"
        assert s._model_for(None) == "claude-haiku-4-5"

    def test_vrl_generate_override_used(self):
        s = self._make_service(skill_models={"vrl_generate": "claude-sonnet-4-6"})
        assert s._model_for("vrl_generate") == "claude-sonnet-4-6"
        # Other skills 仍走 default
        assert s._model_for("log_explain") == "claude-haiku-4-5"

    def test_vrl_optimize_shares_vrl_model_override(self):
        """vrl_optimize routes to LLM_COPILOT_VRL_MODEL when set, same as vrl_generate."""
        s = self._make_service(skill_models={
            "vrl_generate": "claude-sonnet-4-6",
            "vrl_optimize": "claude-sonnet-4-6",
        })
        assert s._model_for("vrl_optimize") == "claude-sonnet-4-6"
        assert s._model_for("vrl_generate") == "claude-sonnet-4-6"
        # anomaly stays on default
        assert s._model_for("anomaly") == "claude-haiku-4-5"
        # log_explain stays on default
        assert s._model_for("log_explain") == "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# TestStreamInline — stream_inline() for ⌘K inline VRL editor
# ---------------------------------------------------------------------------


def _service(skill_models=None, api_key="key"):
    return ChatService(
        anthropic_client=MagicMock(),
        anthropic_api_key=api_key,
        default_model="default-model",
        skill_models=skill_models or {},
        max_history=20,
        max_log_lines_in_context=20,
        max_vrl_chars_in_context=4000,
        max_library_products_in_context=20,
    )


def _req():
    return InlineVrlRequest(
        instruction="x",
        mode="insert",
        current_vrl="",
        cursor_offset=0,
    )


class _FakeStream:
    def __init__(self, items):
        self._items = items

    async def __aenter__(self):
        async def gen():
            for it in self._items:
                yield it
        self.text_stream = gen()
        return self

    async def __aexit__(self, *exc):
        return False


class _FailStream:
    async def __aenter__(self):
        raise RuntimeError("boom")

    async def __aexit__(self, *exc):
        return False


class TestStreamInline:
    async def test_no_api_key_yields_error_done(self):
        svc = _service(api_key=None)
        events = [b async for b in svc.stream_inline(request=_req())]
        assert len(events) == 2
        assert b"no_api_key" in events[0]
        assert b"event: done" in events[1]

    async def test_uses_vrl_inline_model_override(self):
        svc = _service(skill_models={"vrl_inline": "override-model"})
        captured = {}

        def stream_fn(**kw):
            captured.update(kw)
            return _FakeStream(["hello"])

        svc._client = MagicMock()
        svc._client.messages.stream = stream_fn

        events = [b async for b in svc.stream_inline(request=_req())]
        assert captured["model"] == "override-model"
        assert captured["max_tokens"] == 1024
        assert any(b"text_delta" in e for e in events)
        assert b"event: done" in events[-1]

    async def test_falls_back_to_default_model(self):
        svc = _service()
        captured = {}

        def stream_fn(**kw):
            captured.update(kw)
            return _FakeStream([])

        svc._client = MagicMock()
        svc._client.messages.stream = stream_fn

        _events = [b async for b in svc.stream_inline(request=_req())]
        assert captured["model"] == "default-model"

    async def test_anthropic_failure_yields_error_done(self):
        svc = _service()
        svc._client = MagicMock()
        svc._client.messages.stream = lambda **kw: _FailStream()

        events = [b async for b in svc.stream_inline(request=_req())]
        assert any(b"anthropic_failed" in e for e in events)
        assert b"event: done" in events[-1]

    async def test_user_message_carries_instruction(self):
        svc = _service()
        captured = {}

        def stream_fn(**kw):
            captured.update(kw)
            return _FakeStream([])

        svc._client = MagicMock()
        svc._client.messages.stream = stream_fn

        req = InlineVrlRequest(
            instruction="加 dst_ip",
            mode="insert",
            current_vrl="",
            cursor_offset=0,
        )
        _events = [b async for b in svc.stream_inline(request=req)]
        assert captured["messages"] == [{"role": "user", "content": "加 dst_ip"}]

    async def test_uses_vrl_fix_model_override(self):
        svc = _service(skill_models={"vrl_fix": "fix-model", "vrl_inline": "inline-model"})
        captured = {}

        def stream_fn(**kw):
            captured.update(kw)
            return _FakeStream([])

        svc._client = MagicMock()
        svc._client.messages.stream = stream_fn

        req = InlineVrlRequest(
            instruction="x",
            skill="vrl_fix",
            mode="replace",
            current_vrl="abcdefghij",
            selection_start=2,
            selection_end=5,
            compile_error="error[E110]: ...",
        )
        _events = [b async for b in svc.stream_inline(request=req)]
        assert captured["model"] == "fix-model"

    async def test_vrl_inline_default_still_uses_inline_model(self):
        svc = _service(skill_models={"vrl_inline": "inline-model", "vrl_fix": "fix-model"})
        captured = {}

        def stream_fn(**kw):
            captured.update(kw)
            return _FakeStream([])

        svc._client = MagicMock()
        svc._client.messages.stream = stream_fn

        # default skill (no skill specified -> vrl_inline)
        _events = [b async for b in svc.stream_inline(request=_req())]
        assert captured["model"] == "inline-model"
