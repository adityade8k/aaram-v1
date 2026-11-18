import os
import json
import time
import wave
import shutil
import logging
import threading
import subprocess
from typing import IO, Callable
from pathlib import Path
from datetime import datetime
from concurrent.futures import Future, ThreadPoolExecutor

import numpy as np
from numpy.typing import NDArray

from reachy_mini_conversation_app.memory import memory_path_for_instance

LABEL_ENV = "REACHY_MINI_SESSION_LABEL"


logger = logging.getLogger(__name__)

DEFAULT_CAMERA_FPS = 5.0
RECORDING_DIR_ENV = "REACHY_MINI_SESSION_RECORDING_DIR"


def _clip(value: object, limit: int = 300) -> str:
    """Compact one-line rendering of a tool result or list for the transcript."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[: limit - 3] + "..."


class _WavTrack:
    """Mono 16-bit WAV kept on the session's wall clock, padding gaps with silence."""

    def __init__(self, path: Path, t0: float) -> None:
        self._path = path
        self._t0 = t0
        self._wav: wave.Wave_write | None = None
        self._rate = 0
        self._written = 0

    def write(self, rate: int, samples: NDArray[np.int16], now: float) -> None:
        if self._wav is None:
            self._rate = rate
            self._wav = wave.open(str(self._path), "wb")
            self._wav.setnchannels(1)
            self._wav.setsampwidth(2)
            self._wav.setframerate(rate)
        # Bursty assistant audio arrives faster than real time: queue it after what is already written.
        start = self._written
        due = int((now - self._t0) * self._rate)
        if due - self._written > self._rate // 4:  # ignore jitter; pad real pauses to keep the timeline
            start = due
        if start > self._written:
            self._wav.writeframes(np.zeros(start - self._written, dtype=np.int16).tobytes())
        self._wav.writeframes(samples.astype("<i2", copy=False).tobytes())
        self._written = start + samples.size

    def close(self) -> None:
        if self._wav is not None:
            self._wav.close()
            self._wav = None


class SessionRecorder:
    """Record speech (both sides) and continuous camera video for one session, time-aligned.

    Files go in ``<start>_<id>/``: ``mic.wav`` and ``assistant.wav`` (both start at session
    time zero), ``camera.mp4`` (H.264, encoded live by ffmpeg; without ffmpeg it falls back
    to ``camera.mjpg``, concatenated full-size JPEGs) with ``camera.index.jsonl`` (true
    capture time of every frame), and ``meta.json``. The parent folder is
    ``REACHY_MINI_SESSION_RECORDING_DIR`` when set, else ``sessions/`` beside the experiment
    log. All times are UTC Unix milliseconds on the same clock as ``experiment.jsonl.gz``.
    """

    def __init__(
        self,
        instance_path: str | Path | None,
        session_id: str,
        frame_source: Callable[[], bytes | None] | None = None,
        camera_fps: float = DEFAULT_CAMERA_FPS,
        use_ffmpeg: bool | None = None,
        condition: dict[str, object] | None = None,
    ) -> None:
        """Create the session folder and start capturing.

        ``condition`` describes the experimental setup (advisor on/off, model, profile) and is
        written to ``meta.json`` and the transcript header. ``REACHY_MINI_SESSION_LABEL`` adds a
        free-text label (for example ``Q1-5 advisor-off``).
        """
        self.started_ms = time.time_ns() // 1_000_000
        stamp = datetime.fromtimestamp(self.started_ms / 1000).strftime("%Y%m%d-%H%M%S")
        override = (os.getenv(RECORDING_DIR_ENV) or "").strip()
        base = Path(override).expanduser() if override else memory_path_for_instance(instance_path).parent / "sessions"
        self.directory = base / f"{stamp}_{session_id[:8]}"
        self.directory.mkdir(parents=True, exist_ok=True)
        self._session_id = session_id
        self._condition = dict(condition or {})
        label = (os.getenv(LABEL_ENV) or "").strip()
        if label:
            self._condition["label"] = label
        self._t0 = time.time()
        self._writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix="session-recorder")
        self._mic = _WavTrack(self.directory / "mic.wav", self._t0)
        self._assistant = _WavTrack(self.directory / "assistant.wav", self._t0)
        self._frame_source = frame_source
        self._interval = 1.0 / max(camera_fps, 0.1)
        self._ffmpeg_path = shutil.which("ffmpeg") if use_ffmpeg is not False else None
        self._encoder: subprocess.Popen[bytes] | None = None
        self._stop = threading.Event()
        self._camera_thread: threading.Thread | None = None
        self._video: IO[bytes] | None = None
        self._index: IO[str] | None = None
        self._transcript: IO[str] | None = None
        self._frames = 0
        self._closed = False
        self._write_meta(ended=False)
        if frame_source is not None:
            if self._ffmpeg_path is None:
                logger.warning("ffmpeg not found; saving large raw camera.mjpg instead of camera.mp4")
            self._camera_thread = threading.Thread(target=self._camera_loop, name="session-camera", daemon=True)
            self._camera_thread.start()
        logger.info("Session recording started: %s", self.directory)

    def _write_meta(self, ended: bool) -> None:
        meta = {
            "v": 1,
            "session_id": self._session_id,
            "started_ms": self.started_ms,
            "condition": self._condition,
            "camera_fps": round(1.0 / self._interval, 3) if self._frame_source else None,
            "frames": self._frames,
            "ended": ended,
        }
        (self.directory / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def record_mic(self, rate: int, samples: NDArray[np.int16]) -> None:
        """Queue a mono microphone chunk."""
        self._submit(self._mic.write, rate, samples.copy(), time.time())

    def record_assistant(self, rate: int, samples: NDArray[np.int16]) -> None:
        """Queue a mono chunk of what Ari says."""
        self._submit(self._assistant.write, rate, samples.reshape(-1).copy(), time.time())

    def log_event(self, event: str, fields: dict[str, object], t_ms: int) -> None:
        """Add a conversation event to the readable transcript (other events are ignored)."""
        text = str(fields.get("text") or "").strip()
        if event == "input" and text:
            speaker = {"user": "USER", "operator": "OPERATOR", "system": "SYSTEM"}.get(str(fields.get("role")), "USER")
        elif event == "response" and text:
            speaker = "ARI (interrupted)" if fields.get("interrupted") else "ARI"
        elif event == "tool_call":
            speaker, text = "TOOL", f"call {fields.get('name')} {fields.get('arguments') or ''}".strip()
        elif event == "tool_result":
            speaker, text = "TOOL", f"result {fields.get('name')} -> {_clip(fields.get('result'))}"
        elif event == "research_requested":
            web = ", web search required" if fields.get("search_web") else ""
            speaker, text = (
                "REASONER",
                f"#{fields.get('research_id')} asked (user turn {fields.get('user_turn')}{web}): {fields.get('question')}",
            )
        elif event == "research_started":
            speaker, text = (
                "REASONER",
                f"#{fields.get('research_id')} started ({fields.get('model')}, effort {fields.get('effort')})",
            )
        elif event == "research_response":
            advice = fields.get("advice")
            notes = advice.get("snippets") if isinstance(advice, dict) else None
            summary = " | ".join(str(n) for n in notes) if notes else "no usable advice"
            seconds = float(fields.get("elapsed_ms") or 0) / 1000  # type: ignore[arg-type]
            flags = ", stale and discarded" if fields.get("stale") else ""
            speaker = "REASONER"
            text = (
                f"#{fields.get('research_id')} answered in {seconds:.1f}s "
                f"({fields.get('web_search_calls')} web searches, {fields.get('status')}{flags}): {summary}"
            )
        elif event == "research_sources":
            speaker, text = "REASONER", f"#{fields.get('research_id')} sources: {_clip(fields.get('sources'), 400)}"
        elif event == "research_exposed":
            speaker, text = "REASONER", f"#{fields.get('research_id')} advice was available to Ari's spoken reply"
        elif event == "research_cancelled":
            speaker, text = "REASONER", f"#{fields.get('research_id')} cancelled"
        elif event == "research_failed":
            speaker, text = (
                "REASONER",
                f"#{fields.get('research_id')} failed: {fields.get('message')} ({fields.get('error')})",
            )
        else:
            return
        self._submit(self._write_transcript, t_ms, speaker, text)

    def _write_transcript(self, t_ms: int, speaker: str, text: str) -> None:
        if self._transcript is None:
            self._transcript = (self.directory / "transcript.txt").open("w", encoding="utf-8")
            started = datetime.fromtimestamp(self.started_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
            self._transcript.write(
                f"Session started {started}. Times are mm:ss from start, taken when each line was completed.\n"
            )
            if self._condition:
                summary = ", ".join(f"{k}={v}" for k, v in self._condition.items())
                self._transcript.write(f"Condition: {summary}\n")
            self._transcript.write("\n")
        seconds = max(0.0, (t_ms - self.started_ms) / 1000)
        stamp = f"[{int(seconds // 60):02d}:{seconds % 60:04.1f}]"
        body = text.replace("\n", "\n" + " " * (len(stamp) + 1))
        self._transcript.write(f"{stamp} {speaker}: {body}\n")
        self._transcript.flush()

    def _submit(self, fn: Callable[..., None], *args: object) -> None:
        if self._closed:
            return
        self._writer.submit(fn, *args).add_done_callback(self._log_failure)

    @staticmethod
    def _log_failure(future: "Future[None]") -> None:
        exc = future.exception()
        if exc is not None:
            logger.error("Session recording write failed: %s", exc)

    def _camera_loop(self) -> None:
        assert self._frame_source is not None
        next_at = time.monotonic()
        while not self._stop.is_set():
            try:
                jpeg = self._frame_source()
            except Exception as exc:  # camera hiccups must never break the conversation
                logger.debug("Session camera frame failed: %s", exc)
                jpeg = None
            if jpeg:
                self._submit(self._write_frame, time.time_ns() // 1_000_000, jpeg)
            next_at += self._interval
            self._stop.wait(max(0.0, next_at - time.monotonic()))

    def _start_video(self) -> None:
        self._index = (self.directory / "camera.index.jsonl").open("w", encoding="utf-8")
        if self._ffmpeg_path is None:
            self._video = (self.directory / "camera.mjpg").open("wb")
            return
        command = [
            self._ffmpeg_path, "-loglevel", "error", "-y",
            "-f", "image2pipe", "-framerate", f"{1.0 / self._interval:g}", "-i", "-",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
            # Fragmented MP4 stays playable even if the app is killed mid-session.
            "-movflags", "+frag_keyframe+empty_moov",
            str(self.directory / "camera.mp4"),
        ]  # fmt: skip
        self._encoder = subprocess.Popen(command, stdin=subprocess.PIPE)

    def _write_frame(self, t_ms: int, jpeg: bytes) -> None:
        if self._index is None:
            self._start_video()
        assert self._index is not None
        entry: dict[str, int] = {"t": t_ms, "bytes": len(jpeg)}
        if self._encoder is not None and self._encoder.stdin is not None:
            self._encoder.stdin.write(jpeg)
        elif self._video is not None:
            entry["offset"] = self._video.tell()
            self._video.write(jpeg)
        self._index.write(json.dumps(entry) + "\n")
        self._frames += 1

    def close(self) -> None:
        """Stop capture, flush everything queued, and finalize the files."""
        if self._closed:
            return
        self._stop.set()
        if self._camera_thread is not None:
            self._camera_thread.join(timeout=2)
        self._writer.submit(self._finalize).result()
        self._closed = True
        self._writer.shutdown(wait=True)
        logger.info("Session recording saved: %s (%d camera frames)", self.directory, self._frames)

    def _finalize(self) -> None:
        self._mic.close()
        self._assistant.close()
        for handle in (self._video, self._index, self._transcript):
            if handle is not None:
                handle.close()
        if self._encoder is not None:
            if self._encoder.stdin is not None:
                self._encoder.stdin.close()
            try:
                self._encoder.wait(timeout=120)
            except subprocess.TimeoutExpired:
                self._encoder.kill()
                logger.error("ffmpeg did not finish in time; camera.mp4 may be truncated")
        self._write_meta(ended=True)
