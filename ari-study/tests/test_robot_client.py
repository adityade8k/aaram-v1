"""Exercise the robot transport with simulated audio hardware and a local fake socket."""

import json
import base64
import asyncio
import argparse
import tempfile
import unittest
import importlib.util
from types import TracebackType
from pathlib import Path
from unittest.mock import Mock, patch
from collections.abc import AsyncIterator

import numpy as np


spec = importlib.util.spec_from_file_location("robot_client", Path(__file__).parents[1] / "robot/voice_client.py")
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class FakeSocket:
    """Simulate bidirectional messages without a network connection."""

    def __init__(self, messages: list[dict[str, object]]) -> None:
        """Queue provider events and retain outbound messages for assertions."""
        self.messages = messages
        self.sent: list[dict[str, object]] = []

    async def __aenter__(self) -> "FakeSocket":
        """Open the simulated connection."""
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> bool:
        """Propagate errors to the client's cleanup path."""
        return False

    async def send(self, value: str) -> None:
        """Capture a message sent by the robot client."""
        self.sent.append(json.loads(value))

    async def __aiter__(self) -> AsyncIterator[str]:
        """Deliver provider messages while allowing capture tasks to run."""
        for message in self.messages:
            yield json.dumps(message)
            await asyncio.sleep(0.005)


class RobotClientTests(unittest.IsolatedAsyncioTestCase):
    """Check audio transport, consent and cleanup with simulated hardware."""

    def arguments(self, output: Path, mode: str = "inline", consent: bool = True) -> argparse.Namespace:
        """Build the settings used across robot transport scenarios."""
        return argparse.Namespace(
            server="http://127.0.0.1:4173",
            mode=mode,
            participant="P01",
            task="X",
            consent_confirmed=consent,
            output=output,
            robot_name="reachy_mini",
            robot_host="reachy-mini.local",
            media_backend="default",
        )

    async def test_both_modes_stream_audio_and_use_the_shared_session_protocol(self) -> None:
        """Both architectures use the same audio transport and clear playback on interruption."""
        for mode in ["inline", "background"]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                robot = Mock()
                robot.__enter__ = Mock(return_value=robot)
                robot.__exit__ = Mock(return_value=False)
                robot.media.get_input_audio_samplerate.return_value = 16000
                robot.media.get_output_audio_samplerate.return_value = 16000
                samples = [np.array([0.1, -0.1], dtype=np.float32)]
                robot.media.get_audio_sample.side_effect = lambda: samples.pop() if samples else None
                audio = base64.b64encode(np.array([100, -100], dtype="<i2").tobytes()).decode()
                socket = FakeSocket(
                    [
                        {"type": "ready"},
                        {"type": "audio", "audio": audio, "response_id": "r1"},
                        {"type": "clear_audio"},
                        {"type": "log", "entry": {"event": "transcript", "text": "Hello"}},
                    ]
                )
                with (
                    patch.object(client, "ReachyMini", return_value=robot),
                    patch.object(client, "connect", return_value=socket),
                ):
                    await client.run(self.arguments(Path(directory), mode))
                self.assertEqual(socket.sent[0]["mode"], mode)
                self.assertEqual(socket.sent[0]["interface"], "robot")
                self.assertTrue(any(message["type"] == "audio" for message in socket.sent))
                robot.enable_wobbling.assert_called_once()
                robot.media.push_audio_sample.assert_called_once()
                robot.media.audio.clear_player.assert_called_once()
                robot.media.stop_recording.assert_called_once()
                robot.disable_wobbling.assert_called_once()
                record = next(Path(directory).glob("*.jsonl")).read_text()
                self.assertIn("Hello", record)
                self.assertNotIn(audio, record)

    async def test_missing_consent_prevents_hardware_connection(self) -> None:
        """Unconfirmed consent prevents hardware access and recording."""
        with tempfile.TemporaryDirectory() as directory, patch.object(client, "ReachyMini") as robot:
            with self.assertRaises(ValueError):
                await client.run(self.arguments(Path(directory), consent=False))
            robot.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [])

    async def test_provider_error_stops_microphone_and_playback(self) -> None:
        """A provider error closes robot audio resources."""
        with tempfile.TemporaryDirectory() as directory:
            robot = Mock()
            robot.__enter__ = Mock(return_value=robot)
            robot.__exit__ = Mock(return_value=False)
            robot.media.get_input_audio_samplerate.return_value = 16000
            robot.media.get_output_audio_samplerate.return_value = 16000
            socket = FakeSocket([{"type": "error", "message": "Missing provider configuration"}])
            with (
                patch.object(client, "ReachyMini", return_value=robot),
                patch.object(client, "connect", return_value=socket),
            ):
                with self.assertRaises(RuntimeError):
                    await client.run(self.arguments(Path(directory)))
            robot.media.start_recording.assert_not_called()
            robot.media.stop_recording.assert_called_once()
            robot.media.stop_playing.assert_called_once()


if __name__ == "__main__":
    unittest.main()
