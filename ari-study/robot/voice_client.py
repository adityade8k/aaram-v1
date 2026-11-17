"""Run the shared study assistant through Reachy Mini audio and speech-reactive motion."""

import os
import json
import time
import base64
import asyncio
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import numpy as np
from websockets.asyncio.client import connect

from reachy_mini import ReachyMini


logger = logging.getLogger(__name__)


async def run(args: argparse.Namespace) -> None:
    """Connect robot audio to the same condition-locked backend as the phone."""
    parsed = urlsplit(args.server)
    if parsed.scheme not in {"http", "https"} or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Use an HTTP(S) server origin without a path or query.")
    if parsed.username or parsed.password:
        raise ValueError("Pass the study code through STUDY_ACCESS_TOKEN, not a URL.")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Use HTTPS for a remote voice server.")
    if not args.consent_confirmed:
        raise ValueError("Obtain consent, then pass --consent-confirmed before streaming audio.")
    origin = urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    address = urlunsplit(("wss" if parsed.scheme == "https" else "ws", parsed.netloc, "/api/voice", "", ""))
    args.output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    filename = args.output / f"ari-robot-{stamp}.jsonl"
    ready = asyncio.Event()
    started = time.monotonic()
    playback_until = 0.0
    seen_responses: set[str] = set()

    with filename.open("x", encoding="utf-8") as archive:

        def record(event: str, fields: dict[str, object]) -> None:
            entry = {
                "schema": 2,
                "time": datetime.now(timezone.utc).isoformat(),
                "elapsed_ms": round((time.monotonic() - started) * 1000),
                "clock": "robot",
                "event": event,
                **fields,
            }
            archive.write(json.dumps(entry, ensure_ascii=False) + "\n")
            archive.flush()

        record(
            "block_started",
            {
                "participant": args.participant,
                "interface": "robot",
                "mode": args.mode,
                "task": args.task,
                "consent_confirmed": True,
                "raw_audio_saved": False,
                "camera_to_model": False,
                "gestures": "speech_reactive_wobble",
            },
        )
        try:
            with ReachyMini(
                robot_name=args.robot_name, host=args.robot_host, media_backend=args.media_backend
            ) as robot:
                if (
                    robot.media.get_input_audio_samplerate() != 16000
                    or robot.media.get_output_audio_samplerate() != 16000
                ):
                    raise RuntimeError(
                        "This adapter requires native 16 kHz input and output. Verify the robot media configuration before a study block."
                    )
                if robot.media.audio is None:
                    raise RuntimeError("Robot audio is unavailable.")
                # Fail before a block if immediate playback interruption is unsupported.
                clear_player = robot.media.audio.clear_player
                async with connect(address, origin=origin, max_size=4 * 1024 * 1024, open_timeout=15) as socket:
                    await socket.send(
                        json.dumps(
                            {
                                "type": "start",
                                "interface": "robot",
                                "participant": args.participant,
                                "mode": args.mode,
                                "task": args.task,
                                "consent": True,
                                "token": os.environ.get("STUDY_ACCESS_TOKEN", ""),
                            }
                        )
                    )

                    async def capture() -> None:
                        await ready.wait()
                        while True:
                            samples = await asyncio.to_thread(robot.media.get_audio_sample)
                            if samples is None:
                                await asyncio.sleep(0.005)
                                continue
                            mono = np.asarray(samples)
                            if mono.ndim == 2:
                                mono = mono[:, 0]
                            if mono.dtype == np.int16:
                                pcm = mono.astype("<i2", copy=False)
                            else:
                                pcm = (np.clip(mono, -1, 1) * 32767).astype("<i2")
                            for offset in range(0, len(pcm), 640):
                                chunk = base64.b64encode(pcm[offset : offset + 640].tobytes()).decode("ascii")
                                await socket.send(json.dumps({"type": "audio", "audio": chunk}))
                            await asyncio.sleep(0)

                    async def receive() -> None:
                        nonlocal playback_until
                        async for raw in socket:
                            message = json.loads(raw)
                            kind = message.get("type")
                            if kind == "ready":
                                robot.enable_wobbling()
                                robot.media.start_playing()
                                robot.media.start_recording()
                                ready.set()
                                logger.info("Robot session ready: %s", args.mode)
                            elif kind == "audio":
                                samples = (
                                    np.frombuffer(
                                        base64.b64decode(message["audio"], validate=True), dtype="<i2"
                                    ).astype(np.float32)
                                    / 32768
                                )
                                robot.media.push_audio_sample(samples)
                                playback_until = max(time.monotonic(), playback_until) + len(samples) / 16000
                                response_id = str(message.get("response_id", "unknown"))
                                if response_id not in seen_responses:
                                    seen_responses.add(response_id)
                                    record(
                                        "audio_submitted_to_device",
                                        {
                                            "response_id": response_id,
                                            "measurement": "queue_estimate_not_acoustic_onset",
                                        },
                                    )
                                await socket.send(
                                    json.dumps(
                                        {
                                            "type": "playback",
                                            "remaining_ms": max(0, playback_until - time.monotonic()) * 1000,
                                        }
                                    )
                                )
                            elif kind == "clear_audio":
                                clear_player()
                                playback_until = 0.0
                                await socket.send(json.dumps({"type": "playback", "remaining_ms": 0}))
                                record("playback_cleared", {})
                            elif kind == "log":
                                archive.write(json.dumps(message["entry"], ensure_ascii=False) + "\n")
                                archive.flush()
                            elif kind == "error":
                                raise RuntimeError(message.get("message", "Voice service error"))
                            elif kind == "notice":
                                logger.warning("Assistant notice: %s", message.get("message"))

                    tasks = [asyncio.create_task(capture()), asyncio.create_task(receive())]
                    try:
                        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                        for task in done:
                            task.result()
                    finally:
                        for task in tasks:
                            task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                        robot.media.stop_recording()
                        robot.media.stop_playing()
                        robot.disable_wobbling()
        except (Exception, asyncio.CancelledError) as error:
            record("block_interrupted", {"reason": type(error).__name__})
            logger.error("Robot block ended: %s", error)
            raise
        finally:
            record("block_ended", {})
            logger.info("Robot record: %s", filename)


def main() -> None:
    """Parse a study block and start the robot client."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:4173")
    parser.add_argument("--mode", choices=["inline", "background"], required=True)
    parser.add_argument("--participant", required=True)
    parser.add_argument("--task", choices=["X", "Y", "practice"], required=True)
    parser.add_argument("--consent-confirmed", action="store_true")
    parser.add_argument("--robot-name", default="reachy_mini")
    parser.add_argument("--robot-host", default="reachy-mini.local")
    parser.add_argument("--media-backend", choices=["default", "local", "webrtc"], default="default")
    parser.add_argument("--output", type=Path, default=Path("recordings"))
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run(parser.parse_args()))
    except KeyboardInterrupt:
        logger.info("Stopped by researcher.")


if __name__ == "__main__":
    main()
