"""Tests for the session recorder."""

import json
import time
import wave
import shutil
import subprocess

import numpy as np
import pytest

from reachy_mini_conversation_app.session_recorder import SessionRecorder


def test_records_audio_tracks_and_camera(tmp_path):
    """Both audio tracks share one timeline and every camera frame is indexed."""
    frames = iter([b"\xff\xd8aaa\xff\xd9", b"\xff\xd8bbbb\xff\xd9"] * 50)
    recorder = SessionRecorder(
        tmp_path, "abcdef1234567890", frame_source=lambda: next(frames), camera_fps=50, use_ffmpeg=False
    )
    recorder.record_mic(16000, np.ones(1600, dtype=np.int16))
    time.sleep(0.6)  # assistant starts speaking half a second in
    recorder.record_assistant(16000, np.full((1, 1600), 2, dtype=np.int16))
    recorder.close()

    mic = wave.open(str(recorder.directory / "mic.wav"))
    assert mic.getframerate() == 16000 and mic.getnframes() == 1600
    assistant = wave.open(str(recorder.directory / "assistant.wav"))
    assert assistant.getnframes() >= 16000 * 0.5 + 1600  # silence padded so it lines up with the mic timeline

    index = [json.loads(line) for line in (recorder.directory / "camera.index.jsonl").read_text().splitlines()]
    assert len(index) >= 5
    data = (recorder.directory / "camera.mjpg").read_bytes()
    assert data[index[0]["offset"] : index[0]["offset"] + index[0]["bytes"]].startswith(b"\xff\xd8")
    meta = json.loads((recorder.directory / "meta.json").read_text())
    assert meta["ended"] and meta["frames"] == len(index)


def test_works_without_camera(tmp_path):
    """Audio-only recording leaves no video files."""
    recorder = SessionRecorder(tmp_path, "abcdef1234567890")
    recorder.record_mic(16000, np.zeros(160, dtype=np.int16))
    recorder.close()
    assert not (recorder.directory / "camera.mjpg").exists()


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_encodes_camera_to_mp4(tmp_path):
    """With ffmpeg available the video is written directly as a playable mp4."""
    jpeg = subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=160x90",
            "-frames:v",
            "1",
            "-f",
            "mjpeg",
            "-",
        ],
        capture_output=True,
        check=True,
    ).stdout
    recorder = SessionRecorder(tmp_path, "abcdef1234567890", frame_source=lambda: jpeg, camera_fps=20)
    time.sleep(0.5)
    recorder.close()
    assert (recorder.directory / "camera.mp4").stat().st_size > 0
    assert not (recorder.directory / "camera.mjpg").exists()


def test_writes_readable_transcript(tmp_path):
    """User speech and Ari's replies become timestamped lines in transcript.txt."""
    recorder = SessionRecorder(tmp_path, "abcdef1234567890")
    t = recorder.started_ms
    recorder.log_event("input", {"role": "user", "text": "hello Ari"}, t + 2500)
    recorder.log_event("response", {"text": "Hi!\nHow can I help?", "interrupted": False}, t + 4100)
    recorder.log_event("response", {"text": "Let me tell you", "interrupted": True}, t + 65000)
    recorder.log_event("speech_started", {}, t + 70000)  # not part of the transcript
    recorder.close()
    lines = (recorder.directory / "transcript.txt").read_text().splitlines()
    assert "[00:02.5] USER: hello Ari" in lines
    assert "[00:04.1] ARI: Hi!" in lines
    assert "          How can I help?" in lines
    assert "[01:05.0] ARI (interrupted): Let me tell you" in lines
    assert not any("speech_started" in line for line in lines)


def test_transcript_shows_when_and_why_reasoner_was_used(tmp_path):
    """Tool calls and every reasoner step appear with times so researchers can see if, when and why."""
    recorder = SessionRecorder(tmp_path, "abcdef1234567890")
    t = recorder.started_ms
    recorder.log_event("tool_call", {"name": "research_question", "arguments": '{"question":"kerf?"}'}, t + 1000)
    recorder.log_event(
        "research_requested",
        {"research_id": 1, "question": "kerf on 3mm acrylic", "user_turn": 2, "search_web": True},
        t + 1100,
    )
    recorder.log_event(
        "research_started", {"research_id": 1, "model": "claude-sonnet-5-5", "effort": "medium"}, t + 1200
    )
    recorder.log_event(
        "research_response",
        {
            "research_id": 1,
            "status": "end_turn",
            "advice": {"snippets": ["Kerf is ~0.2mm"]},
            "stale": False,
            "web_search_calls": 1,
            "elapsed_ms": 4200,
        },
        t + 5400,
    )
    recorder.log_event("research_exposed", {"research_id": 1}, t + 7000)
    recorder.close()
    text = (recorder.directory / "transcript.txt").read_text()
    assert "TOOL: call research_question" in text
    assert "REASONER: #1 asked (user turn 2, web search required): kerf on 3mm acrylic" in text
    assert "REASONER: #1 answered in 4.2s (1 web searches, end_turn): Kerf is ~0.2mm" in text
    assert "[00:07.0] REASONER: #1 advice was available" in text


def test_records_experimental_condition(tmp_path, monkeypatch):
    """The advisor condition and an optional label land in meta.json and the transcript header."""
    monkeypatch.setenv("REACHY_MINI_SESSION_LABEL", "Q1-5 advisor-off")
    recorder = SessionRecorder(tmp_path, "abcdef1234567890", condition={"advisor": "off", "profile": "ari"})
    recorder.log_event("input", {"role": "user", "text": "hi"}, recorder.started_ms + 1000)
    recorder.close()
    meta = json.loads((recorder.directory / "meta.json").read_text())
    assert meta["condition"] == {"advisor": "off", "profile": "ari", "label": "Q1-5 advisor-off"}
    lines = (recorder.directory / "transcript.txt").read_text().splitlines()
    assert lines[1] == "Condition: advisor=off, profile=ari, label=Q1-5 advisor-off"
    assert "[00:01.0] USER: hi" in lines
