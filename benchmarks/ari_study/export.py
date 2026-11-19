"""Export recorded trial timings and blank human annotations without inferring usefulness."""

import csv
import gzip
import json
import math
import logging
import argparse
from pathlib import Path
from statistics import median


logger = logging.getLogger(__name__)
FIELDS = (
    "session_id turn_id input_mode input_text first_response_created_ms first_audio_generated_ms "
    "first_audio_timing_status assistant_text response_status useful_answer_ms audible_response_ms outcome notes"
).split()
SETUP_FIELDS = (
    "backend connection_mode label profile_requested profile voice advisor_requested advisor advisor_model "
    "advisor_effort advisor_web_search memory_enabled camera_enabled recording_requested recording_enabled "
    "instructions_sha256"
).split()
HASH_FIELDS = "profile grounding reasoning_grounding realtime_implementation reasoning_implementation".split()


def export_archive(archive: Path, output: Path) -> int:
    """Write turn annotations, allowlisted session provenance, and generation-only timing summaries."""
    for filename in ("turns.csv", "session_setup.json", "summary.json"):
        if (output / filename).exists():
            raise FileExistsError(f"Refusing to overwrite {output / filename}; choose a new output directory")
    with gzip.open(archive, "rt", encoding="utf-8") as stream:
        events: list[dict[str, object]] = [json.loads(line) for line in stream if line.strip()]
    turns: dict[tuple[str, int], dict[str, str | int | float]] = {}
    timestamps: dict[tuple[str, int], int | float] = {}
    unfinished: set[tuple[str, int]] = set()
    response_starts: set[tuple[str, int]] = set()
    setups: dict[str, dict[str, object]] = {}
    for event in events:
        if not isinstance(event, dict) or not isinstance(event.get("s"), str):
            raise ValueError("Every archive event must be an object with a session ID")
        session_id = str(event["s"])
        if event.get("e") == "session_start":
            setup = {name: event[name] for name in SETUP_FIELDS if name in event}
            tool_names = event.get("tools")
            if isinstance(tool_names, list):
                setup["tools"] = [name for name in tool_names if isinstance(name, str)]
            for name, allowed in (
                ("package_versions", ("reachy_mini_conversation_app", "reachy-mini", "openai", "anthropic")),
                ("source_sha256", HASH_FIELDS),
            ):
                values = event.get(name)
                if isinstance(values, dict):
                    setup[name] = {key: values[key] for key in allowed if key in values}
            setups.setdefault(session_id, {}).update(setup)
        if event.get("e") == "voice_session":
            voice_sessions = setups.setdefault(session_id, {}).setdefault("voice_sessions", [])
            if isinstance(voice_sessions, list):
                reported_session = {name: event[name] for name in ("model", "voice", "source_event") if name in event}
                voice_sessions.append(reported_session)
        if event.get("e") != "input" or event.get("role") not in {"user", "operator"}:
            continue
        turn_id, timestamp = event.get("turn_id"), event.get("t")
        if not isinstance(turn_id, int) or isinstance(turn_id, bool) or turn_id < 1:
            raise ValueError("Archive contains user inputs without valid turn IDs; use the instrumented app")
        if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool) or not math.isfinite(timestamp):
            raise ValueError("Archive contains an input without a finite timestamp")
        key = (session_id, turn_id)
        if key in turns:
            raise ValueError(f"Duplicate input turn ID {turn_id} in session {session_id}")
        turns[key] = dict.fromkeys(FIELDS, "")
        turns[key].update(
            session_id=session_id,
            turn_id=turn_id,
            input_mode=str(event.get("input_mode", "")),
            input_text=str(event.get("text", "")),
            response_status="unanswered",
        )
        timestamps[key] = timestamp
    for event in events:
        turn_id = event.get("turn_id")
        if not isinstance(turn_id, int) or isinstance(turn_id, bool):
            continue
        key = (str(event["s"]), turn_id)
        if key not in turns:
            continue
        turn = turns[key]
        if event.get("e") == "response_started":
            unfinished.add(key)
            timestamp = event.get("t")
            if key not in response_starts:
                response_starts.add(key)
                if isinstance(timestamp, (int, float)) and math.isfinite(timestamp) and timestamp >= timestamps[key]:
                    turn["first_response_created_ms"] = timestamp - timestamps[key]
            if turn["response_status"] == "unanswered":
                turn["response_status"] = "incomplete"
        elif event.get("e") == "first_audio_generated":
            if turn["first_audio_timing_status"] != "":
                continue
            turn["first_audio_timing_status"] = str(event.get("timing_status") or "unmeasured")
            if turn["response_status"] == "unanswered":
                turn["response_status"] = "incomplete"
            elapsed = event.get("elapsed_ms")
            if (
                isinstance(elapsed, (int, float))
                and not isinstance(elapsed, bool)
                and math.isfinite(elapsed)
                and elapsed >= 0
            ):
                turn["first_audio_generated_ms"] = elapsed
                turn["first_audio_timing_status"] = "measured"
        elif event.get("e") == "response":
            unfinished.discard(key)
            text = str(event.get("text") or "").strip()
            if text:
                turn["assistant_text"] = "\n".join(filter(None, (str(turn["assistant_text"]), text)))
            status = str(event.get("status") or "incomplete")
            if event.get("interrupted"):
                status += " (interrupted)"
            previous = turn["response_status"]
            turn["response_status"] = status if previous in {"unanswered", "incomplete"} else f"{previous}; {status}"
    for key in unfinished:
        if turns[key]["response_status"] != "incomplete":
            turns[key]["response_status"] = f"{turns[key]['response_status']}; incomplete"
    summaries: list[dict[str, object]] = []
    for session_id in dict.fromkeys(key[0] for key in turns):
        session_turns = [turn for (session, _), turn in turns.items() if session == session_id]
        latencies = sorted(
            float(turn["first_audio_generated_ms"]) for turn in session_turns if turn["first_audio_generated_ms"] != ""
        )
        audio_count = sum(turn["first_audio_timing_status"] != "" for turn in session_turns)
        summaries.append(
            {
                "session_id": session_id,
                "label": setups.get(session_id, {}).get("label"),
                "advisor": setups.get(session_id, {}).get("advisor"),
                "attempted_turns": len(session_turns),
                "first_audio_recorded": audio_count,
                "first_audio_missing": len(session_turns) - audio_count,
                "first_audio_timing_measured": len(latencies),
                "first_audio_timing_unmeasured": audio_count - len(latencies),
                "first_audio_generated_median_ms": median(latencies) if latencies else None,
                "first_audio_generated_p95_ms": latencies[math.ceil(0.95 * len(latencies)) - 1] if latencies else None,
            }
        )
    output.mkdir(parents=True, exist_ok=True)
    with (output / "turns.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(turns.values())
    reports = {
        "session_setup.json": {"schema_version": 1, "sessions": setups},
        "summary.json": {
            "measurement": "Client receipt of generated audio, relative to completed input; not audible playback or useful-answer latency.",
            "percentile_method": "Nearest rank: sorted measured latencies at ceil(0.95 * n); missing or unmeasured audio is excluded from latency statistics and counted separately.",
            "sessions": summaries,
        },
    }
    for filename, report in reports.items():
        with (output / filename).open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    return len(turns)


def main(argv: list[str] | None = None) -> int:
    """Export one archive while preserving existing annotated files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Recorded experiment.jsonl.gz")
    parser.add_argument("--output", type=Path, required=True, help="Directory without existing export files")
    args = parser.parse_args(argv)
    try:
        count = export_archive(args.archive, args.output)
    except (OSError, ValueError, EOFError) as exc:
        logger.error("Could not export study archive: %s", exc)
        return 1
    print(f"Exported {count} input turns to {args.output}; useful-answer and playback fields need human annotation.")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
