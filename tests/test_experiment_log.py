import gzip
import json
import base64
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from reachy_mini_conversation_app.console import LocalStream
from reachy_mini_conversation_app.experiment_log import ExperimentLog


@pytest.mark.asyncio
async def test_archive_appends_across_restarts_and_download_is_a_snapshot(tmp_path):
    """Restarting and downloading never replace earlier experiment records."""
    first = ExperimentLog(tmp_path)
    first.record("input", {"text": "Why did my café sign not cut through? " * 100})
    await first.access("status")
    original = first.path.read_bytes()
    restarted = ExperimentLog(tmp_path)
    restarted.record("response", {"text": "Which material did you use?"})
    snapshot = await restarted.access("status")
    restarted.record("input", {"text": "Acrylic."})
    chunk = await restarted.access("read", offset=0, limit=snapshot["bytes"], generation=snapshot["generation"])
    records = [json.loads(line) for line in gzip.decompress(base64.b64decode(chunk["content"])).splitlines()]
    assert [row["e"] for row in records] == ["input", "response"]
    assert records[0]["s"] != records[1]["s"]
    assert records[0]["t"] <= records[1]["t"]
    assert "café" in records[0]["text"]
    assert first.path.read_bytes().startswith(original)
    assert len(gzip.decompress(first.path.read_bytes()).splitlines()) == 3
    assert len(original) < len(records[0]["text"].encode()) / 2


@pytest.mark.asyncio
async def test_clear_rejects_an_old_download_and_new_events_continue(tmp_path):
    """A manual clear is ordered after pending writes and before subsequent ones."""
    archive = ExperimentLog(tmp_path)
    archive.record("input", {"text": "old"})
    before = await archive.access("status")
    assert (await archive.access("clear"))["bytes"] == 0
    archive.record("input", {"text": "new"})
    after = await archive.access("status")
    assert after["bytes"] > 0
    with pytest.raises(ValueError, match="changed"):
        await archive.access("read", limit=before["bytes"], generation=before["generation"])
    records = [json.loads(line) for line in gzip.decompress(archive.path.read_bytes()).splitlines()]
    assert [row["text"] for row in records] == ["new"]


@pytest.mark.asyncio
async def test_download_is_chunked_and_rejects_out_of_bounds_ranges(tmp_path):
    """Large logs use bounded messages instead of loading the full archive into the RPC server."""
    archive = ExperimentLog(tmp_path)
    for index in range(2200):
        archive.record("input", {"text": str(index) * 100})
    snapshot = await archive.access("status")
    assert snapshot["bytes"] > 192 * 1024
    offset, chunks = 0, []
    while offset < snapshot["bytes"]:
        chunk = await archive.access("read", offset=offset, limit=snapshot["bytes"], generation=snapshot["generation"])
        decoded = base64.b64decode(chunk["content"])
        assert len(decoded) <= 192 * 1024
        chunks.append(decoded)
        offset = chunk["next_offset"]
    assert len(gzip.decompress(b"".join(chunks)).splitlines()) == 2200
    with pytest.raises(ValueError):
        await archive.access("read", offset=-1, limit=snapshot["bytes"], generation=snapshot["generation"])


@pytest.mark.asyncio
async def test_storage_failure_does_not_interrupt_recording_caller(tmp_path, caplog):
    """A write failure is visible to researchers without breaking voice processing."""
    archive = ExperimentLog(tmp_path)
    archive.path.mkdir()
    archive.record("input", {"text": "Question"})
    assert (await archive.access("status"))["error"]
    assert "Could not append experiment log" in caplog.text


def test_log_rpc_download_and_explicit_clear(tmp_path):
    """The UI can retrieve gzip bytes; only an explicitly confirmed action erases them."""
    app = FastAPI()
    handler = MagicMock()
    handler.experiment_log = ExperimentLog(tmp_path)
    handler.experiment_log.record("input", {"text": "Question"})
    stream = LocalStream(handler, SimpleNamespace(media=SimpleNamespace(audio=None, backend=None)), settings_app=app)
    stream._init_settings_ui_if_needed()
    with TestClient(app).websocket_connect("/rpc") as socket:

        def call(params):
            socket.send_json({"jsonrpc": "2.0", "id": "1", "method": "experiment.log", "params": params})
            return socket.receive_json()

        snapshot = call({})["result"]
        assert snapshot["bytes"] > 0
        assert "error" in call({"action": "clear"})
        chunk = call({"action": "read", "limit": snapshot["bytes"], "generation": snapshot["generation"]})["result"]
        assert json.loads(gzip.decompress(base64.b64decode(chunk["content"])))["text"] == "Question"
        assert call({"action": "clear", "confirm": True})["result"]["bytes"] == 0
