"""Launch one fresh author-operated safety, latency, or teaching trial."""

import os
import sys
import json
import uuid
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone

from dotenv import dotenv_values


logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
APP_COMMAND = (
    "import json, os, sys; "
    "os.environ.update(json.loads(sys.argv.pop(1))); "
    "from reachy_mini_conversation_app.main import run; "
    "from reachy_mini_conversation_app.utils import parse_args; "
    "args, _ = parse_args(); "
    "run(args, instance_path=os.environ['REACHY_MINI_INSTANCE_PATH'])"
)


def main(argv: list[str] | None = None) -> int:
    """Start an isolated trial with camera and cross-session memory disabled."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", choices=("safety", "latency", "teaching"), required=True)
    parser.add_argument("--condition", choices=("off", "on"), required=True, help="Background advisor condition")
    parser.add_argument("--case", default="manual", help="Authored case or script ID")
    parser.add_argument("--repetition", type=int, default=1)
    parser.add_argument("--env", type=Path, default=ROOT / ".env", help="Existing credentials file; never copied")
    parser.add_argument("--output", type=Path, default=ROOT / "recordings" / "paper")
    parser.add_argument("--voice", help="Use the same voice in every comparison trial")
    parser.add_argument("--dry-run", action="store_true", help="Show non-secret setup without starting or recording")
    args = parser.parse_args(argv)
    if args.repetition < 1:
        parser.error("--repetition must be positive")
    if not args.case or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for character in args.case
    ):
        parser.error("--case must contain only letters, numbers, hyphens, or underscores")

    environment = os.environ.copy()
    if args.env.is_file():
        environment.update({key: value for key, value in dotenv_values(args.env).items() if value is not None})
    elif args.env != ROOT / ".env":
        parser.error(f"Credentials file does not exist: {args.env}")
    if args.condition == "on" and not args.dry_run and not environment.get("ANTHROPIC_API_KEY", "").strip():
        parser.error("The ON condition requires ANTHROPIC_API_KEY in the environment or --env file")

    trial_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    directory = args.output.expanduser().resolve() / trial_id
    instance = directory / "instance"
    settings = {
        "REACHY_MINI_SKIP_DOTENV": "true",
        "REACHY_MINI_INSTANCE_PATH": str(instance),
        "REACHY_MINI_CUSTOM_PROFILE": "ari",
        "REACHY_MINI_GROUNDING_FILE": str(ROOT / "docs" / "Grounding Doc" / "ari-01-shop-context.md"),
        "REACHY_MINI_REASONING_GROUNDING_FILE": str(ROOT / "docs" / "Grounding Doc" / "ari-02-reasoner-playbook.md"),
        "REACHY_MINI_REASONING_ENABLED": str(args.condition == "on").lower(),
        "REACHY_MINI_REASONING_MODEL": environment.get("REACHY_MINI_REASONING_MODEL") or "claude-sonnet-5-5",
        "REACHY_MINI_REASONING_EFFORT": environment.get("REACHY_MINI_REASONING_EFFORT") or "medium",
        "REACHY_MINI_REASONING_WEB_SEARCH": "true",
        "REACHY_MINI_MEMORY_ENABLED": "false",
        "REACHY_MINI_CAMERA_ENABLED": "false",
        "REACHY_MINI_SESSION_RECORDING": "true",
        "REACHY_MINI_SESSION_RECORDING_DIR": str(directory / "sessions"),
        "REACHY_MINI_SESSION_LABEL": f"paper-{args.experiment} {args.condition.upper()} {args.case} repeat-{args.repetition}",
        "REALTIME_TRANSCRIPTION_LANGUAGE": environment.get("REALTIME_TRANSCRIPTION_LANGUAGE") or "en",
    }
    for name in (
        "REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY",
        "REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY",
        "AUTOLOAD_EXTERNAL_TOOLS",
    ):
        environment.pop(name, None)
    environment.update(settings)
    environment["PYTHONPATH"] = os.pathsep.join(filter(None, (str(ROOT / "src"), environment.get("PYTHONPATH"))))
    manifest = {
        "trial_id": trial_id,
        "experiment": args.experiment,
        "condition_requested": args.condition,
        "case": args.case,
        "repetition": args.repetition,
        "voice_requested": args.voice,
        "settings": settings,
        "source_access": "advisor-web-search" if args.condition == "on" else "installed-direct-lookup-tools",
        "measurement": "Generation events are not audible playback; useful answers require human annotation.",
    }
    if args.dry_run:
        print(json.dumps(manifest, indent=2))
        return 0

    instance.mkdir(parents=True)
    startup = {"profile": "ari"}
    if args.voice:
        startup["voice"] = args.voice
    (instance / "startup_settings.json").write_text(json.dumps(startup, indent=2), encoding="utf-8")
    (directory / "trial.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Trial {trial_id}: {settings['REACHY_MINI_SESSION_LABEL']}")
    print("Author-operated recording: nearby speech is processed externally; audio and transcripts are saved locally.")
    print("Camera and long-term memory are off. The visor does not mute audio. Ctrl-C ends this app session.")
    print(f"Records: {directory}", flush=True)
    # The GStreamer wheel's child startup treats these scalar paths as path lists.
    media_environment = {
        name: environment[name] for name in ("GST_PLUGIN_SCANNER_1_0", "GST_REGISTRY_1_0") if name in environment
    }
    try:
        exit_code = subprocess.call(
            [sys.executable, "-c", APP_COMMAND, json.dumps(media_environment), "--no-camera", "--ui"],
            cwd=ROOT,
            env=environment,
        )
    except KeyboardInterrupt:
        exit_code = 130
    except OSError as exc:
        logger.error("Could not start study session: %s", exc)
        exit_code = 1
    manifest["app_exit_code"] = exit_code
    manifest["ended_at"] = datetime.now(timezone.utc).isoformat()
    (directory / "trial.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
