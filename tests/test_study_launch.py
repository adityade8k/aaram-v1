"""Study launch conditions remain isolated and credentials stay out of records."""

import os
import sys
import json
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from benchmarks.ari_study import launch


def test_dry_run_has_no_recording_or_credential_output(tmp_path, monkeypatch, capsys):
    """Previewing a trial does not launch audio or create records."""
    credentials = tmp_path / ".env"
    credentials.write_text("ANTHROPIC_API_KEY=test-only-secret\n", encoding="utf-8")
    child = MagicMock()
    monkeypatch.setattr(launch.subprocess, "call", child)
    output = tmp_path / "recordings"
    assert (
        launch.main(
            [
                "--experiment",
                "latency",
                "--condition",
                "on",
                "--env",
                str(credentials),
                "--output",
                str(output),
                "--dry-run",
            ]
        )
        == 0
    )
    captured = capsys.readouterr().out
    assert "test-only-secret" not in captured
    assert json.loads(captured)["condition_requested"] == "on"
    assert not output.exists()
    child.assert_not_called()


@pytest.mark.parametrize("condition", ["on", "off"])
def test_study_conditions_override_local_settings_without_copying_keys(tmp_path, monkeypatch, capsys, condition):
    """Fresh trial directories prevent prior profiles, memory, and camera settings leaking in."""
    credentials = tmp_path / ".env"
    credentials.write_text(
        "ANTHROPIC_API_KEY=test-only-secret\nREACHY_MINI_MEMORY_ENABLED=true\n"
        "REACHY_MINI_CAMERA_ENABLED=true\nREACHY_MINI_CUSTOM_PROFILE=other\n"
        "REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY=other-profiles\n",
        encoding="utf-8",
    )
    child = MagicMock(return_value=0)
    monkeypatch.setattr(launch.subprocess, "call", child)
    output = tmp_path / "recordings"
    arguments = [
        "--experiment",
        "teaching",
        "--condition",
        condition,
        "--case",
        "guide-01",
        "--env",
        str(credentials),
        "--output",
        str(output),
        "--voice",
        "test-voice",
    ]
    assert launch.main(arguments) == 0
    assert launch.main(arguments) == 0
    trials = list(output.iterdir())
    assert len(trials) == 2
    environment = child.call_args.kwargs["env"]
    assert environment["ANTHROPIC_API_KEY"] == "test-only-secret"
    assert environment["REACHY_MINI_MEMORY_ENABLED"] == "false"
    assert environment["REACHY_MINI_CAMERA_ENABLED"] == "false"
    assert environment["REACHY_MINI_REASONING_ENABLED"] == str(condition == "on").lower()
    assert environment["REACHY_MINI_SKIP_DOTENV"] == "true"
    assert "REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY" not in environment
    assert "--no-camera" in child.call_args.args[0]
    for trial in trials:
        manifest = (trial / "trial.json").read_text()
        assert "test-only-secret" not in manifest
        startup = json.loads((trial / "instance" / "startup_settings.json").read_text())
        assert startup == {"profile": "ari", "voice": "test-voice"}
        assert not (trial / "instance" / ".env").exists()
    assert "test-only-secret" not in capsys.readouterr().out


def test_on_condition_requires_key_before_creating_trial(tmp_path, monkeypatch):
    """An unconfigured advisor cannot silently become the ON condition."""
    credentials = tmp_path / ".env"
    credentials.write_text("ANTHROPIC_API_KEY=\n", encoding="utf-8")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    child = MagicMock()
    monkeypatch.setattr(launch.subprocess, "call", child)
    output = tmp_path / "recordings"
    with pytest.raises(SystemExit) as stopped:
        launch.main(
            ["--experiment", "latency", "--condition", "on", "--env", str(credentials), "--output", str(output)]
        )
    assert stopped.value.code == 2
    assert not output.exists()
    child.assert_not_called()


@pytest.mark.parametrize("explicit_override", [False, True])
def test_child_bootstrap_restores_scalar_media_paths_before_app_start(tmp_path, monkeypatch, explicit_override):
    """Repeated wheel setup cannot turn scanner and registry paths into invalid path lists."""
    inherited = {
        "GST_PLUGIN_SCANNER_1_0": str(tmp_path / "wheel" / "gst-plugin-scanner"),
        "GST_REGISTRY_1_0": str(tmp_path / "wheel" / "registry.bin"),
    }
    for name, value in inherited.items():
        monkeypatch.setenv(name, value)
    expected = {name: str(tmp_path / "custom paths" / name) for name in inherited} if explicit_override else inherited
    credentials = tmp_path / ".env"
    credentials.write_text(
        "\n".join(f"{name}={json.dumps(value)}" for name, value in expected.items()) if explicit_override else "",
        encoding="utf-8",
    )
    application = ModuleType("reachy_mini_conversation_app.main")
    application.run = MagicMock()
    utilities = ModuleType("reachy_mini_conversation_app.utils")
    utilities.parse_args = MagicMock(return_value=(object(), []))
    monkeypatch.setitem(sys.modules, application.__name__, application)
    monkeypatch.setitem(sys.modules, utilities.__name__, utilities)

    def start_child(command, *, cwd, env):
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        for name, value in expected.items():
            monkeypatch.setenv(name, inherited[name] + os.pathsep + value)
        monkeypatch.setattr(sys, "argv", ["-c", *command[3:]])
        exec(command[2], {})
        assert {name: os.environ[name] for name in expected} == expected
        assert sys.argv == ["-c", "--no-camera", "--ui"]
        application.run.assert_called_once()
        return 0

    monkeypatch.setattr(launch.subprocess, "call", start_child)
    assert (
        launch.main(
            [
                "--experiment",
                "latency",
                "--condition",
                "off",
                "--env",
                str(credentials),
                "--output",
                str(tmp_path / "records"),
            ]
        )
        == 0
    )
