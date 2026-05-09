"""Unit tests for ChatService.stream() (mocked Anthropic SDK)."""

import json
from unittest.mock import MagicMock

from app.modules.copilot.schemas import ChatRequest
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
        model="claude-haiku-4-5-20251001",
        max_history=20,
        max_log_lines_in_context=20,
        max_vrl_chars_in_context=4000,
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
            model="m",
            max_history=20,
            max_log_lines_in_context=20,
            max_vrl_chars_in_context=4000,
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
