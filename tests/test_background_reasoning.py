import gzip
import json
import asyncio
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx2
import pytest
from anthropic import AsyncAnthropic, BadRequestError

import reachy_mini_conversation_app.background_reasoning as reasoning_mod
from reachy_mini_conversation_app.config import config, refresh_runtime_config_from_env
from reachy_mini_conversation_app.experiment_log import ExperimentLog
from reachy_mini_conversation_app.background_reasoning import (
    ReasoningAdvice,
    BackgroundReasoner,
    create_background_reasoner,
)


def _advice(snippet: str = "Ask which material was used.") -> ReasoningAdvice:
    return ReasoningAdvice(snippets=[snippet], next_question="Which material?", uncertainty="No settings known.")


def _message(advice=None, stop_reason="end_turn", extra=(), text=None):
    """Build the subset of an Anthropic message that the reasoner reads."""
    body = text if text is not None else (advice or _advice()).model_dump_json()
    return SimpleNamespace(
        stop_reason=stop_reason, content=[*extra, SimpleNamespace(type="text", text=body, citations=None)]
    )


def _prompt(call_kwargs):
    return call_kwargs["messages"][0]["content"]


def _client(advice=None):
    client = MagicMock()
    client.close = AsyncMock()
    client.messages.create = AsyncMock(return_value=_message(advice))
    return client


async def _wait_status(worker, status):
    async with asyncio.timeout(2):
        while worker.research_status["status"] != status:
            await asyncio.sleep(0.001)


@pytest.mark.parametrize(
    "effort,expected_effort,web_search,search_required",
    [("medium", "medium", True, True), ("high", "high", False, False), ("none", "low", True, False)],
)
@pytest.mark.asyncio
async def test_sdk_sends_explicit_research_with_optional_search_and_preserves_citations(
    effort, expected_effort, web_search, search_required
):
    """Research uses the real SDK wire format and retains attributable source links."""
    requests = []
    advice = _advice()

    async def respond(request):
        requests.append(json.loads(request.content))
        return httpx2.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "test-model",
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "content": [
                    {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search", "input": {"query": "x"}},
                    {
                        "type": "text",
                        "text": advice.model_dump_json(),
                        "citations": [
                            {
                                "type": "web_search_result_location",
                                "url": "https://www.epiloglaser.com/",
                                "title": "Manufacturer documentation",
                                "cited_text": "Laser settings",
                                "encrypted_index": "abc",
                            },
                        ],
                    },
                ],
            },
        )

    client = AsyncAnthropic(
        api_key="test-only", http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond))
    )
    publish = AsyncMock(return_value=True)
    worker = BackgroundReasoner(
        client,
        "Tutor and shop grounding",
        "test-model",
        publish,
        reasoning_effort=effort,
        web_search=web_search,
        debounce_seconds=0,
        min_interval_seconds=0,
    )
    try:
        worker.observe("assistant", "Welcome!")
        worker.observe("user", "My cut failed.")
        await asyncio.sleep(0.01)
        assert not requests
        reply = worker.request("Explain uneven cuts in the supplied material", search_required)
        assert reply["status"] == "researching"
        await _wait_status(worker, "ready")
        payload = requests[0]
        prompt = payload["messages"][0]["content"]
        assert payload["system"] == "Tutor and shop grounding"
        assert "My cut failed." in prompt
        assert "Welcome!" in prompt
        assert "Explain uneven cuts" in prompt
        assert ("must use web search" in prompt) is search_required
        assert payload["output_config"] == {"effort": expected_effort}
        assert payload["tools"] == ([{"type": "web_search_20260209", "name": "web_search"}] if web_search else [])
        assert "tool_choice" not in payload
        assert payload["max_tokens"] == 8000
        assert "Ask which material" in worker.conversation_context
        assert worker.research_status["web_search_calls"] == 1
        assert worker.research_status["sources"] == [
            {"url": "https://www.epiloglaser.com/", "title": "Manufacturer documentation"}
        ]
        worker.consume(worker.advice_id)
        assert "Advisory note (JSON data)" not in worker.conversation_context
        assert worker.research_status["sources"]
        assert worker.research_status["snippets"]
    finally:
        await worker.close()
    assert client.is_closed()


@pytest.mark.asyncio
async def test_late_advice_carries_age_without_research_on_every_turn():
    """Follow-up conversation continues without causing unsolicited API requests."""
    started = asyncio.Event()
    release = asyncio.Event()
    client = _client()

    async def infer(**kwargs):
        started.set()
        await release.wait()
        return _message(_advice("LATE ADVICE"))

    client.messages.create.side_effect = infer
    worker = BackgroundReasoner(client, "grounding", "model", AsyncMock(return_value=True), debounce_seconds=0)
    try:
        worker.observe("user", "Why is my cut uneven?")
        worker.request("Explain uneven cuts")
        await asyncio.wait_for(started.wait(), 1)
        worker.observe("assistant", "Was that everywhere?")
        worker.observe("user", "Only in the middle")
        release.set()
        await _wait_status(worker, "ready")
        assert '"user_turns_since_request": 1' in worker.conversation_context
        assert '"based_on_user_request": "Explain uneven cuts"' in worker.conversation_context
        worker.observe("user", "The material is flat")
        await asyncio.sleep(0.01)
        assert client.messages.create.await_count == 1
        assert '"user_turns_since_request": 2' in worker.conversation_context
        worker.consume(worker.advice_id)
        assert worker.advice_id == 0
    finally:
        await worker.close()


@pytest.mark.asyncio
async def test_new_question_cancels_inflight_research_and_never_delivers_old_result():
    """A changed question replaces slow research instead of publishing obsolete findings."""
    started = asyncio.Event()
    cancelled = asyncio.Event()
    client = _client()

    async def infer(**kwargs):
        if "FIRST QUESTION" in _prompt(kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        return _message(_advice("NEW ANSWER"))

    client.messages.create.side_effect = infer
    worker = BackgroundReasoner(
        client, "grounding", "model", AsyncMock(return_value=True), debounce_seconds=0, min_interval_seconds=0
    )
    try:
        worker.request("FIRST QUESTION")
        await asyncio.wait_for(started.wait(), 1)
        worker.request("SECOND QUESTION")
        await asyncio.wait_for(cancelled.wait(), 1)
        await _wait_status(worker, "ready")
        assert "NEW ANSWER" in worker.conversation_context
        assert "FIRST QUESTION" not in worker.conversation_context
        assert worker.advice_id == 2
        worker.request("SECOND QUESTION")
        await asyncio.sleep(0.01)
        assert client.messages.create.await_count == 2
    finally:
        await worker.close()


@pytest.mark.asyncio
async def test_advice_expires_after_four_followup_turns():
    """Unconsumed notes leave the prompt after the allowed conversation window."""
    client = _client()
    worker = BackgroundReasoner(client, "grounding", "model", AsyncMock(return_value=True), debounce_seconds=0)
    try:
        worker.observe("user", "Question")
        worker.request("Question")
        await _wait_status(worker, "ready")
        for n in range(4):
            worker.observe("user", f"Turn {n}")
            assert worker.advice_id
        worker.observe("user", "One too many")
        assert worker.advice_id == 0
        assert worker.research_status["status"] == "expired"
        assert client.messages.create.await_count == 1
    finally:
        await worker.close()


@pytest.mark.asyncio
async def test_timeout_reports_unavailable_without_automatic_retry(caplog):
    """A timeout produces honest availability context while conversation remains usable."""
    client = _client()
    cancelled = asyncio.Event()

    async def infer(**kwargs):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    client.messages.create.side_effect = infer
    worker = BackgroundReasoner(
        client, "grounding", "model", AsyncMock(return_value=True), debounce_seconds=0, timeout_seconds=0.01
    )
    try:
        worker.request("Question")
        await _wait_status(worker, "unavailable")
        worker.observe("user", "We can still talk")
        await asyncio.sleep(0.01)
        assert cancelled.is_set()
        assert "Background reasoning unavailable: TimeoutError" in caplog.text
        assert "Research status: unavailable" in worker.conversation_context
        assert client.messages.create.await_count == 1
    finally:
        await worker.close()


@pytest.mark.asyncio
async def test_close_cancels_research_and_publication():
    """Closing a session cancels network work and rejects later requests."""
    started = asyncio.Event()
    cancelled = asyncio.Event()
    client = _client()

    async def infer(**kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    client.messages.create.side_effect = infer
    worker = BackgroundReasoner(client, "grounding", "model", AsyncMock(return_value=True), debounce_seconds=0)
    worker.request("Question")
    await asyncio.wait_for(started.wait(), 1)
    await worker.close()
    await worker.close()
    assert cancelled.is_set()
    assert "error" in worker.request("Too late")
    client.close.assert_awaited_once()


@pytest.mark.parametrize(
    "stop_reason,advice,text",
    [
        ("max_tokens", _advice(), None),
        ("refusal", _advice(), None),
        ("end_turn", None, "I could not produce JSON."),
    ],
)
@pytest.mark.asyncio
async def test_incomplete_refused_and_oversized_results_are_unavailable(stop_reason, advice, text):
    """Invalid model results cannot become spoken research findings."""
    client = _client()
    client.messages.create.return_value = _message(advice, stop_reason, text=text)
    worker = BackgroundReasoner(client, "grounding", "model", AsyncMock(return_value=True), debounce_seconds=0)
    try:
        worker.request("Question")
        await _wait_status(worker, "unavailable")
        assert worker.advice_id == 0
    finally:
        await worker.close()


@pytest.mark.asyncio
async def test_oversized_result_is_clipped_not_discarded():
    """A long snippet is shortened to the limit so a good answer still reaches Ari."""
    client = _client()
    client.messages.create.return_value = _message(_advice("Processing was made by Fry and Reas. " * 40), "end_turn")
    worker = BackgroundReasoner(client, "grounding", "model", AsyncMock(return_value=True), debounce_seconds=0)
    try:
        worker.request("Question")
        await _wait_status(worker, "ready")
        snippets = worker.research_status["snippets"]
        assert snippets and all(len(s) <= 600 for s in snippets)
        assert snippets[0].startswith("Processing was made by Fry and Reas.")
    finally:
        await worker.close()


@pytest.mark.asyncio
async def test_publication_does_not_report_a_disconnected_update_as_sent(caplog):
    """A disconnected session is never logged as receiving the note."""
    worker = BackgroundReasoner(_client(), "grounding", "model", AsyncMock(return_value=False), debounce_seconds=0)
    try:
        worker.request("Question")
        await _wait_status(worker, "ready")
        await asyncio.sleep(0.01)
        assert "Research context not sent" in caplog.text
        assert "context sent:" not in caplog.text
    finally:
        await worker.close()


@pytest.mark.asyncio
async def test_factory_uses_both_documents_and_dedicated_client(tmp_path: Path, monkeypatch):
    """The advisor receives both grounding files through its own Claude client."""
    tutor = tmp_path / "tutor.md"
    tutor.write_text("Ask one question at a time.")
    shop = tmp_path / "shop.md"
    shop.write_text("Staff must approve materials.")
    monkeypatch.setattr(config, "REASONING_ENABLED", True)
    monkeypatch.setattr(config, "REASONING_GROUNDING_FILE", str(tutor))
    monkeypatch.setattr(config, "GROUNDING_FILE", str(shop))
    monkeypatch.setattr(config, "REASONING_MODEL", "custom-reasoner")
    monkeypatch.setattr(config, "REASONING_EFFORT", "high")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    client = _client()
    constructor = MagicMock(return_value=client)
    monkeypatch.setattr(reasoning_mod, "AsyncAnthropic", constructor)
    worker = create_background_reasoner(AsyncMock(return_value=True))
    assert worker is not None
    try:
        worker.request("How do I start?")
        await _wait_status(worker, "ready")
        request = client.messages.create.call_args.kwargs
        assert request["model"] == "custom-reasoner"
        assert request["output_config"] == {"effort": "high"}
        assert tutor.read_text() in request["system"]
        assert shop.read_text() in request["system"]
        assert constructor.call_args.kwargs["api_key"] == "test-key"
        assert constructor.call_args.kwargs["max_retries"] == 0
    finally:
        await worker.close()


def test_missing_key_or_grounding_disables_only_reasoner(tmp_path: Path, monkeypatch, caplog):
    """Incomplete setup disables research without raising into the voice loop."""
    monkeypatch.setattr(config, "REASONING_ENABLED", True)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert create_background_reasoner(AsyncMock()) is None
    assert "set ANTHROPIC_API_KEY" in caplog.text
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "REASONING_GROUNDING_FILE", str(tmp_path / "missing.md"))
    assert create_background_reasoner(AsyncMock()) is None
    assert "Cannot read REACHY_MINI_REASONING_GROUNDING_FILE" in caplog.text


def test_reasoning_config_reloads_from_environment(monkeypatch):
    """Instance configuration updates both the model and web-search availability."""
    for name in (
        "REASONING_ENABLED",
        "REASONING_MODEL",
        "REASONING_EFFORT",
        "REASONING_GROUNDING_FILE",
        "REASONING_WEB_SEARCH",
    ):
        monkeypatch.setattr(config, name, getattr(config, name))
    monkeypatch.setenv("REACHY_MINI_REASONING_ENABLED", "true")
    monkeypatch.setenv("REACHY_MINI_REASONING_MODEL", "custom-reasoner")
    monkeypatch.setenv("REACHY_MINI_REASONING_EFFORT", " High ")
    monkeypatch.setenv("REACHY_MINI_REASONING_GROUNDING_FILE", "tutor.md")
    monkeypatch.setenv("REACHY_MINI_REASONING_WEB_SEARCH", "false")
    refresh_runtime_config_from_env()
    assert config.REASONING_ENABLED is True
    assert config.REASONING_MODEL == "custom-reasoner"
    assert config.REASONING_EFFORT == "high"
    assert config.REASONING_GROUNDING_FILE == "tutor.md"
    assert config.REASONING_WEB_SEARCH is False


@pytest.mark.asyncio
async def test_general_question_search_and_answer_are_visible_in_status_and_recording(tmp_path):
    """A history question retains its topic and records actual search execution independently of citations."""
    archive = ExperimentLog(tmp_path)
    client = _client(ReasoningAdvice(snippets=["A historical explanation."], next_question="", uncertainty=""))
    client.messages.create.return_value = _message(
        ReasoningAdvice(snippets=["A historical explanation."], next_question="", uncertainty=""),
        extra=[SimpleNamespace(type="server_tool_use", name="web_search")],
    )
    worker = BackgroundReasoner(
        client,
        "general researcher",
        "test-model",
        AsyncMock(return_value=True),
        debounce_seconds=0,
        experiment_log=archive,
    )
    try:
        question = "Look up the causes of the Yom Kippur War."
        worker.observe("user", question)
        worker.request(question, True)
        await _wait_status(worker, "ready")
        request = client.messages.create.call_args.kwargs
        assert question in _prompt(request)
        assert "must use web search" in _prompt(request)
        assert worker.research_status["web_search_calls"] == 1
        assert worker.research_status["question"] == question
        assert worker.research_status["model"] == "test-model"
        await archive.access("status")
        rows = [json.loads(line) for line in gzip.decompress(archive.path.read_bytes()).splitlines()]
        assert next(row for row in rows if row["e"] == "research_requested")["search_web"] is True
        assert next(row for row in rows if row["e"] == "research_response")["web_search_calls"] == 1
    finally:
        await worker.close()


@pytest.mark.asyncio
async def test_explicit_lookup_does_not_pretend_to_search_when_search_disabled():
    """A requested lookup is rejected truthfully when the operator disables web search."""
    client = _client()
    worker = BackgroundReasoner(client, "grounding", "model", AsyncMock(return_value=True), web_search=False)
    try:
        assert "disabled" in worker.request("Look up a historical event", True)["error"]
        await asyncio.sleep(0.01)
        client.messages.create.assert_not_awaited()
    finally:
        await worker.close()


@pytest.mark.asyncio
async def test_request_failure_has_actionable_status_without_exposing_provider_payload(tmp_path):
    """Configuration failures are visible without copying provider error bodies into the archive."""
    client = _client()
    client.messages.create.side_effect = BadRequestError(
        "private-provider-payload",
        response=httpx2.Response(400, request=httpx2.Request("POST", "https://example.org")),
        body=None,
    )
    archive = ExperimentLog(tmp_path)
    worker = BackgroundReasoner(
        client, "grounding", "model", AsyncMock(return_value=True), debounce_seconds=0, experiment_log=archive
    )
    try:
        worker.request("Explain an event")
        await _wait_status(worker, "unavailable")
        assert "Check the model" in worker.research_status["error"]
        await archive.access("status")
        saved = gzip.decompress(archive.path.read_bytes()).decode()
        assert "Check the model" in saved
        assert "private-provider-payload" not in saved
    finally:
        await worker.close()


@pytest.mark.asyncio
async def test_disabled_setup_is_recorded_for_later_diagnosis(tmp_path, monkeypatch):
    """A dump can distinguish missing setup from a voice model that never asks for research."""
    monkeypatch.setattr(config, "REASONING_ENABLED", True)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    archive = ExperimentLog(tmp_path)
    assert create_background_reasoner(AsyncMock(), experiment_log=archive) is None
    await archive.access("status")
    row = json.loads(gzip.decompress(archive.path.read_bytes()))
    assert row["e"] == "research_setup" and row["enabled"] is False
    assert "ANTHROPIC_API_KEY" in row["reason"]
