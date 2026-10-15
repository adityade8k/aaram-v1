import json
import asyncio
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from openai import AsyncOpenAI

import reachy_mini_conversation_app.background_reasoning as reasoning_mod
from reachy_mini_conversation_app.config import config, refresh_runtime_config_from_env
from reachy_mini_conversation_app.background_reasoning import (
    ReasoningAdvice,
    BackgroundReasoner,
    create_background_reasoner,
)


def _advice(snippet: str = "Ask which material was used.") -> ReasoningAdvice:
    return ReasoningAdvice(
        snippets=[snippet], next_question="What material did you use?", uncertainty="No settings known."
    )


@pytest.mark.parametrize("effort", ["medium", "high", "max"])
@pytest.mark.asyncio
async def test_real_sdk_sends_grounded_snapshot_and_parses_advice(effort: str) -> None:
    """Exercise actual SDK serialization and parsing without calling OpenAI."""
    requests = []
    advice = _advice()

    async def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 0,
                "model": "gpt-6-astra",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "id": "msg_test",
                        "role": "assistant",
                        "status": "completed",
                        "content": [{"type": "output_text", "text": advice.model_dump_json(), "annotations": []}],
                    }
                ],
            },
        )

    client = AsyncOpenAI(api_key="test-only", http_client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    published = asyncio.Event()
    contexts = []

    async def publish() -> None:
        contexts.append(worker.conversation_context)
        published.set()

    worker = BackgroundReasoner(
        client,
        "Tutor and shop grounding",
        "gpt-6-astra",
        publish,
        reasoning_effort=effort,
        debounce_seconds=0,
        min_interval_seconds=0,
    )
    try:
        worker.observe("assistant", "Welcome!")
        await asyncio.sleep(0)
        assert not requests
        worker.observe("user", "My cut failed.")
        await asyncio.wait_for(published.wait(), 1)
        payload = json.loads(requests[0].content)
        assert payload["instructions"] == "Tutor and shop grounding"
        assert "My cut failed." in payload["input"]
        assert "Welcome!" in payload["input"]
        assert payload["store"] is False
        assert payload["reasoning"] == {"effort": effort}
        assert payload["model"] == "gpt-6-astra"
        assert payload["text"]["format"]["type"] == "json_schema"
        assert payload["max_output_tokens"] == 3000
        assert "Ask which material was used." in contexts[0]
    finally:
        await worker.close()
    assert client.is_closed()


@pytest.mark.asyncio
async def test_slow_inference_coalesces_context_and_discards_outdated_result() -> None:
    """New conversation can proceed during inference, with only one current result delivered."""
    started = asyncio.Event()
    release_first = asyncio.Event()
    published = asyncio.Event()
    snapshots = []
    contexts = []
    client = MagicMock()
    client.close = AsyncMock()

    async def infer(**kwargs):
        snapshots.append(kwargs["input"])
        if len(snapshots) == 1:
            started.set()
            await release_first.wait()
            return SimpleNamespace(status="completed", output_parsed=_advice("OLD ADVICE"))
        return SimpleNamespace(status="completed", output_parsed=_advice("CURRENT ADVICE"))

    client.responses.parse = AsyncMock(side_effect=infer)

    async def publish() -> None:
        contexts.append(worker.conversation_context)
        published.set()

    worker = BackgroundReasoner(client, "grounding", "model", publish, debounce_seconds=0, min_interval_seconds=0)
    try:
        worker.observe("user", "First question")
        await asyncio.wait_for(started.wait(), 1)
        worker.observe("assistant", "Tell me more")
        worker.observe("user", "Actually, a new question")
        worker.observe("assistant", "A fresh follow-up")
        await asyncio.sleep(0)
        assert len(snapshots) == 1
        release_first.set()
        await asyncio.wait_for(published.wait(), 1)
        assert len(snapshots) == 2
        assert "A fresh follow-up" in snapshots[1]
        assert "Actually, a new question" in snapshots[1]
        assert all("OLD ADVICE" not in context for context in contexts)
        assert "CURRENT ADVICE" in contexts[-1]

        published.clear()
        worker.observe("user", "A follow-up")
        assert "CURRENT ADVICE" in worker.conversation_context
        assert "Actually, a new question" in worker.conversation_context
        worker.observe("user", "Another topic")
        assert "CURRENT ADVICE" not in worker.conversation_context
        await asyncio.wait_for(published.wait(), 1)
        assert "CURRENT ADVICE" not in contexts[1]
    finally:
        await worker.close()


@pytest.mark.asyncio
async def test_close_cancels_active_inference_and_pending_updates() -> None:
    """Disconnecting closes the client without publishing a late answer or leaking tasks."""
    started = asyncio.Event()
    cancelled = asyncio.Event()
    client = MagicMock()
    client.close = AsyncMock()

    async def infer(**kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    client.responses.parse = AsyncMock(side_effect=infer)
    publish = AsyncMock()
    worker = BackgroundReasoner(client, "grounding", "model", publish, debounce_seconds=0)
    worker.observe("user", "Question")
    await asyncio.wait_for(started.wait(), 1)
    worker.observe("assistant", "Follow-up")
    await worker.close()
    await worker.close()
    worker.observe("user", "Too late")
    assert cancelled.is_set()
    assert client.responses.parse.await_count == 1
    publish.assert_not_awaited()
    client.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_timeout_preserves_conversation_and_throttles_pending_retry(caplog) -> None:
    """A slow API call times out without starting a retry loop or publishing partial advice."""
    started = asyncio.Event()
    cancelled = asyncio.Event()
    client = MagicMock()
    client.close = AsyncMock()

    async def infer(**kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    client.responses.parse = AsyncMock(side_effect=infer)
    publish = AsyncMock()
    worker = BackgroundReasoner(client, "grounding", "model", publish, debounce_seconds=0, timeout_seconds=0.01)
    try:
        worker.observe("user", "Question")
        await asyncio.wait_for(started.wait(), 1)
        worker.observe("assistant", "Conversation continues")
        await asyncio.wait_for(cancelled.wait(), 1)
        await asyncio.sleep(0.01)
        assert "Background reasoning unavailable: TimeoutError" in caplog.text
        assert client.responses.parse.await_count == 1
        publish.assert_not_awaited()
    finally:
        await worker.close()


@pytest.mark.parametrize("status,advice", [("incomplete", _advice()), ("completed", None)])
@pytest.mark.asyncio
async def test_incomplete_or_refused_response_is_not_published(status, advice, caplog) -> None:
    """Refusals and token-truncated results cannot reach the voice model as guidance."""
    client = MagicMock()
    client.close = AsyncMock()
    client.responses.parse = AsyncMock(return_value=SimpleNamespace(status=status, output_parsed=advice))
    publish = AsyncMock()
    worker = BackgroundReasoner(client, "grounding", "model", publish, debounce_seconds=0)
    try:
        worker.observe("user", "Question")
        await asyncio.sleep(0.01)
        publish.assert_not_awaited()
        assert "no complete advisory note" in caplog.text
    finally:
        await worker.close()


@pytest.mark.asyncio
async def test_factory_uses_both_documents_and_dedicated_openai_client(tmp_path: Path, monkeypatch) -> None:
    """Tutor and shop files go to OpenAI through a separate, explicitly addressed client."""
    tutor = tmp_path / "tutor.md"
    tutor.write_text("Ask one question at a time.")
    shop = tmp_path / "shop.md"
    shop.write_text("Staff must approve materials.")
    monkeypatch.setattr(config, "REASONING_ENABLED", True)
    monkeypatch.setattr(config, "REASONING_GROUNDING_FILE", str(tutor))
    monkeypatch.setattr(config, "GROUNDING_FILE", str(shop))
    monkeypatch.setattr(config, "REASONING_MODEL", "custom-reasoner")
    monkeypatch.setattr(config, "REASONING_EFFORT", "high")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://wrong.example/v1")
    client = MagicMock()
    client.responses.parse = AsyncMock(return_value=SimpleNamespace(status="completed", output_parsed=_advice()))
    client.close = AsyncMock()
    constructor = MagicMock(return_value=client)
    monkeypatch.setattr(reasoning_mod, "AsyncOpenAI", constructor)
    published = asyncio.Event()

    async def publish() -> None:
        published.set()

    worker = create_background_reasoner(publish)
    assert worker is not None
    try:
        worker.observe("user", "How do I start?")
        await asyncio.wait_for(published.wait(), 2)
        request = client.responses.parse.call_args.kwargs
        assert request["model"] == "custom-reasoner"
        assert request["extra_body"]["reasoning"] == {"effort": "high"}
        instructions = request["instructions"]
        assert tutor.read_text() in instructions
        assert shop.read_text() in instructions
        assert constructor.call_args.kwargs["base_url"] == "https://api.openai.com/v1"
        assert constructor.call_args.kwargs["api_key"] == "test-key"
        assert constructor.call_args.kwargs["max_retries"] == 0
    finally:
        await worker.close()


def test_missing_key_or_grounding_disables_only_reasoner(tmp_path: Path, monkeypatch, caplog) -> None:
    """Incomplete setup warns without creating a network client or stopping conversation."""
    monkeypatch.setattr(config, "REASONING_ENABLED", True)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert create_background_reasoner(AsyncMock()) is None
    assert "set OPENAI_API_KEY" in caplog.text
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "REASONING_GROUNDING_FILE", str(tmp_path / "missing.md"))
    assert create_background_reasoner(AsyncMock()) is None
    assert "Cannot read REACHY_MINI_REASONING_GROUNDING_FILE" in caplog.text


def test_reasoning_config_reloads_from_environment(monkeypatch) -> None:
    """Instance .env loading updates the reasoner configuration along with other settings."""
    for name in ("REASONING_ENABLED", "REASONING_MODEL", "REASONING_EFFORT", "REASONING_GROUNDING_FILE"):
        monkeypatch.setattr(config, name, getattr(config, name))
    monkeypatch.setenv("REACHY_MINI_REASONING_ENABLED", "true")
    monkeypatch.setenv("REACHY_MINI_REASONING_MODEL", "custom-reasoner")
    monkeypatch.setenv("REACHY_MINI_REASONING_EFFORT", " High ")
    monkeypatch.setenv("REACHY_MINI_REASONING_GROUNDING_FILE", "tutor.md")
    refresh_runtime_config_from_env()
    assert config.REASONING_ENABLED is True
    assert config.REASONING_MODEL == "custom-reasoner"
    assert config.REASONING_EFFORT == "high"
    assert config.REASONING_GROUNDING_FILE == "tutor.md"
