"""Study exports preserve attempts and leave interpretation to human scorers."""

import csv
import gzip
import json
from pathlib import Path

import pytest

from benchmarks.ari_study.export import main, export_archive


def _archive(directory: Path, events: list[dict[str, object]]) -> Path:
    path = directory / "experiment.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write("\n".join(json.dumps(event) for event in events))
    return path


def test_export_keeps_session_turn_associations_and_manual_fields_blank(tmp_path: Path) -> None:
    """Repeated turn IDs, multiple replies, and missing answers remain distinguishable."""
    events = [
        {"s": "a", "e": "session_start", "advisor": "on", "voice": "same-voice", "ANTHROPIC_API_KEY": "secret"},
        {"s": "a", "e": "input", "t": 900, "role": "system", "text": "Greeting"},
        {"s": "a", "e": "response_started", "t": 1020, "turn_id": 1},
        {"s": "a", "e": "input", "t": 1000, "turn_id": 1, "role": "user", "input_mode": "audio", "text": "Question A"},
        {
            "s": "a",
            "e": "first_audio_generated",
            "turn_id": 1,
            "elapsed_ms": 120,
            "measurement": "client_received_audio_delta",
        },
        {"s": "a", "e": "response", "turn_id": 1, "text": "I will check.", "status": "completed"},
        {"s": "a", "e": "response_started", "t": 1500, "turn_id": 1},
        {
            "s": "a",
            "e": "response",
            "turn_id": 1,
            "text": "Partial finding",
            "status": "cancelled",
            "interrupted": True,
        },
        {"s": "a", "e": "response_started", "t": 1800, "turn_id": 1},
        {
            "s": "a",
            "e": "input",
            "t": 2000,
            "turn_id": 2,
            "role": "operator",
            "input_mode": "text",
            "text": "Question B",
        },
        {"s": "a", "e": "response_started", "t": 2020, "turn_id": 2},
        {"s": "a", "e": "input", "t": 3000, "turn_id": 3, "role": "user", "input_mode": "audio", "text": "Question C"},
        {
            "s": "b",
            "e": "session_start",
            "advisor": "off",
            "text": "not metadata",
            "package_versions": {"openai": "2", "api_key": "secret"},
        },
        {"s": "b", "e": "input", "t": 5000, "turn_id": 1, "role": "user", "input_mode": "audio", "text": "Question D"},
        {"s": "b", "e": "first_audio_generated", "turn_id": 1, "elapsed_ms": 240},
        {"s": "b", "e": "response", "turn_id": 1, "text": "Reply D", "status": "completed"},
    ]
    output = tmp_path / "export"
    assert export_archive(_archive(tmp_path, events), output) == 4
    with (output / "turns.csv").open(newline="", encoding="utf-8") as stream:
        turns = list(csv.DictReader(stream))
    assert [(turn["session_id"], turn["turn_id"]) for turn in turns] == [
        ("a", "1"),
        ("a", "2"),
        ("a", "3"),
        ("b", "1"),
    ]
    assert turns[0]["first_response_created_ms"] == "20"
    assert turns[0]["first_audio_generated_ms"] == "120"
    assert turns[0]["assistant_text"] == "I will check.\nPartial finding"
    assert turns[0]["response_status"] == "completed; cancelled (interrupted); incomplete"
    assert turns[1]["first_audio_generated_ms"] == ""
    assert turns[1]["response_status"] == "incomplete"
    assert turns[2]["response_status"] == "unanswered"
    assert turns[3]["assistant_text"] == "Reply D"
    assert all(
        turn[field] == ""
        for turn in turns
        for field in ("useful_answer_ms", "audible_response_ms", "outcome", "notes")
    )
    setup = (output / "session_setup.json").read_text(encoding="utf-8")
    assert "secret" not in setup and "not metadata" not in setup and "Question" not in setup
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    first = summary["sessions"][0]
    assert first["advisor"] == "on"
    assert first["attempted_turns"] == 3
    assert first["first_audio_recorded"] == 1
    assert first["first_audio_missing"] == 2
    assert first["first_audio_generated_median_ms"] == first["first_audio_generated_p95_ms"] == 120


def test_audio_before_transcription_retains_unmeasured_timing(tmp_path: Path) -> None:
    """Audio received before input completion is recorded without fabricating latency."""
    events = [
        {
            "s": "a",
            "e": "first_audio_generated",
            "turn_id": 1,
            "elapsed_ms": None,
            "timing_status": "input_completion_not_yet_observed",
        },
        {"s": "a", "e": "input", "t": 1000, "turn_id": 1, "role": "user", "text": "Question"},
        {"s": "a", "e": "first_audio_generated", "turn_id": 1, "elapsed_ms": 300},
    ]
    output = tmp_path / "export"
    export_archive(_archive(tmp_path, events), output)
    with (output / "turns.csv").open(newline="", encoding="utf-8") as stream:
        turn = next(csv.DictReader(stream))
    assert turn["first_audio_timing_status"] == "input_completion_not_yet_observed"
    assert turn["first_audio_generated_ms"] == turn["useful_answer_ms"] == turn["audible_response_ms"] == ""
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))["sessions"][0]
    assert summary["first_audio_recorded"] == summary["first_audio_timing_unmeasured"] == 1
    assert summary["first_audio_missing"] == summary["first_audio_timing_measured"] == 0
    assert summary["first_audio_generated_median_ms"] is None
    assert summary["first_audio_generated_p95_ms"] is None


def test_export_preserves_reported_models_and_unknown_first_response_timing(tmp_path: Path) -> None:
    """Hosted model updates survive export without treating later replies as the first."""
    events = [
        {
            "s": "a",
            "e": "voice_session",
            "model": "hosted-model-one",
            "voice": None,
            "source_event": "session.created",
            "api_key": "secret",
        },
        {
            "s": "a",
            "e": "session_start",
            "backend": "huggingface",
            "voice": "requested-voice",
            "recording_requested": True,
            "recording_enabled": False,
            "source_sha256": {"reasoning_implementation": "hash", "api_key": "secret"},
        },
        {
            "s": "a",
            "e": "voice_session",
            "model": "hosted-model-two",
            "voice": "reported-voice",
            "source_event": "session.updated",
            "text": "not metadata",
        },
        {"s": "a", "e": "response_started", "t": 900, "turn_id": 1},
        {"s": "a", "e": "input", "t": 1000, "turn_id": 1, "role": "user", "text": "Question"},
        {"s": "a", "e": "response", "turn_id": 1, "text": "Acknowledgment", "status": "completed"},
        {"s": "a", "e": "response_started", "t": 1500, "turn_id": 1},
    ]
    output = tmp_path / "export"
    export_archive(_archive(tmp_path, events), output)
    with (output / "turns.csv").open(newline="", encoding="utf-8") as stream:
        turn = next(csv.DictReader(stream))
    assert turn["first_response_created_ms"] == ""
    assert turn["response_status"] == "completed; incomplete"
    setup = json.loads((output / "session_setup.json").read_text(encoding="utf-8"))["sessions"]["a"]
    assert setup["backend"] == "huggingface"
    assert setup["voice"] == "requested-voice"
    assert setup["recording_requested"] is True and setup["recording_enabled"] is False
    assert setup["source_sha256"] == {"reasoning_implementation": "hash"}
    assert setup["voice_sessions"] == [
        {"model": "hosted-model-one", "voice": None, "source_event": "session.created"},
        {"model": "hosted-model-two", "voice": "reported-voice", "source_event": "session.updated"},
    ]


def test_export_refuses_to_replace_human_annotations(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Rerunning the exporter cannot erase the scorer's edits."""
    archive = _archive(tmp_path, [{"s": "a", "e": "input", "t": 0, "turn_id": 1, "role": "user", "text": "Question"}])
    output = tmp_path / "export"
    assert main([str(archive), "--output", str(output)]) == 0
    annotations = output / "turns.csv"
    annotations.write_text("human annotation\n", encoding="utf-8")
    assert main([str(archive), "--output", str(output)]) == 1
    assert annotations.read_text(encoding="utf-8") == "human annotation\n"
    assert "Refusing to overwrite" in caplog.text


def test_legacy_inputs_without_turn_ids_fail_instead_of_disappearing(tmp_path: Path) -> None:
    """An older log cannot silently produce a misleading zero-attempt export."""
    archive = _archive(tmp_path, [{"s": "a", "e": "input", "t": 0, "role": "user", "text": "Question"}])
    output = tmp_path / "export"
    with pytest.raises(ValueError, match="turn IDs"):
        export_archive(archive, output)
    assert not output.exists()
