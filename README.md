---
title: Reachy Mini Conversation App
emoji: 🎤
colorFrom: red
colorTo: blue
sdk: static
pinned: false
short_description: Talk with Reachy Mini!
suggested_storage: large
tags:
 - reachy_mini
 - reachy_mini_python_app
---
# How to start Ari:
Open the Reachy Mini app, then in Terminal:

```bash
cd /Users/arampundik/dev/aaram-v1
source .venv/bin/activate
reachy-mini-conversation-app --ui
```



# Reachy Mini conversation app

Conversational app for the Reachy Mini robot combining realtime voice, vision, personality-aware tools, and choreographed motion.

> **Which API runs the background reasoner?** It depends on the branch:
>
> | Branch | Reasoner API | Key |
> |---|---|---|
> | `anthropic-reasoner` | Anthropic (Claude, default `claude-sonnet-5-5`) | `ANTHROPIC_API_KEY` |
> | `main` | OpenAI | `OPENAI_API_KEY` |
>
> The realtime voice backend is the same on every branch: the Hugging Face
> OpenAI-compatible server. Only the background research advisor differs.
> Check which branch you are on before setting up `.env`; the settings in
> `.env.example` match the branch they came from.

![Reachy Mini Dance](docs/assets/reachy_mini_dance.gif)

## Table of contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the app](#running-the-app)
- [Phone and robot inference study](#phone-and-robot-inference-study)
- [Download data from Terminal](#download-data-from-terminal)
- [LLM tools](#llm-tools-exposed-to-the-assistant)
- [Creating and adding tools](#creating-and-adding-tools)
- [Advanced features](#advanced-features)
- [Contributing](#contributing)
- [License](#license)

## Overview

- Low-latency audio conversation through the Hugging Face realtime backend, using the built-in server or a local endpoint.
- Vision is handled by the realtime backend when the `camera` tool is used.
- Layered motion system queues primary moves (dances, emotions, goto poses, breathing) while blending speech-reactive wobble.
- Async tools integrate motion, camera capture, and MCP Tool Spaces. The optional web UI (`--ui`) manages conversations, personalities, tools, and settings.

## Architecture

The app connects the user, AI services, and robot hardware:

<p align="center">
  <img src="docs/assets/conversation_app_arch.svg" alt="Architecture Diagram" width="600"/>
</p>

## Installation

This Aaram checkout pins the Reachy Mini SDK to `1.12.0rc1`, matching the
Reachy desktop app's robot service used for this prototype. Keep both versions
aligned when updating the robot service. After updating this checkout, activate
the environment and run `uv sync --frozen` before restarting the conversation app.

> [!IMPORTANT]
> Install [Reachy Mini's SDK](https://github.com/pollen-robotics/reachy_mini/) before using this app.<br>
> Windows support is currently experimental and has not been extensively tested. Use with caution.

<details open>
<summary>Using uv (recommended)</summary>

Set up with [uv](https://docs.astral.sh/uv/):

```bash
# macOS (Homebrew)
uv venv --python /opt/homebrew/bin/python3.12 .venv

# Linux / Windows (Python in PATH)
uv venv --python python3.12 .venv

source .venv/bin/activate
uv sync
```

Include dev dependencies:
```bash
uv sync --group dev
```

</details>

> [!NOTE]
> Run `uv sync --frozen` to install the exact dependency set from `uv.lock` without re-resolving versions.

<details>
<summary>Using pip</summary>

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Install dev dependencies:
```bash
pip install -e .[dev]                   # Development tools
```

</details>

## Configuration

The default setup uses the Hugging Face backend and does not require an API key.

Copy `.env.example` to `.env` when you want to point Hugging Face at your own local endpoint.

| Variable | Description |
|----------|-------------|
| `REALTIME_TRANSCRIPTION_LANGUAGE` | Optional input transcription language for the realtime backend. Defaults to `auto` for automatic language detection; set to a backend-supported code such as `en` for English or `zh` for Chinese to fix the language. |
| `HF_REALTIME_CONNECTION_MODE` | Hugging Face connection selector: `deployed` uses the built-in Hugging Face server; `local` uses `HF_REALTIME_WS_URL`. Defaults to `deployed`. |
| `HF_REALTIME_WS_URL` | Direct websocket endpoint for your own Hugging Face backend. Accepts either a base URL like `ws://127.0.0.1:8765/v1` or the full websocket URL `ws://127.0.0.1:8765/v1/realtime`. Used when `HF_REALTIME_CONNECTION_MODE=local`. |
| `HF_TOKEN` | Optional token for Hugging Face access. Local endpoints receive only this explicitly configured token. |
| `REACHY_MINI_APP_TIMEOUT_MINUTES` | Minutes of inactivity before Reachy goes to sleep and the app stops. Defaults to `1440` (one day); set to `0` to disable. |
| `REACHY_MINI_INSTANCE_PATH` | Directory for this instance's data: long-term memory, user personalities and settings. Defaults to `conversation_app` beside the daemon's own config (`~/.config/reachy_mini` on Linux). Data written by an older version inside the installed package is copied over once. |
| `REACHY_MINI_MEMORY_ENABLED` | Long-term memory. When `false`, remembered facts stay on disk but are not injected into the prompt, and the `remember` / `forget` tools decline. Defaults to `true`. |
| `REACHY_MINI_CAMERA_ENABLED` | Camera tool. `--no-camera` forces it off regardless. Defaults to `true`. |
| `REACHY_MINI_GROUNDING_FILE` | Optional UTF-8 document added to every conversational session's instructions. Relative paths resolve from the project root; absolute paths are also supported. |

These variables are the starting value. What you change through the settings UI
(or from the mobile app) is written to `settings.json` in the instance directory
and wins over them, so a toggle always does what it says.

### Ari's shop context

The local `.env` selects `docs/Grounding Doc/ari-01-shop-context.md` with:

```env
REACHY_MINI_GROUNDING_FILE="docs/Grounding Doc/ari-01-shop-context.md"
```

The full document is included in the instructions sent to the Hugging Face
conversation service. It supplies Ari's identity, shop context and staff-approval
rules alongside the selected personality and memory. Shop context takes priority
over conflicting personality text or remembered facts.

Edit that document, then stop and restart the conversation app to apply changes.
The file is also reread whenever session instructions are refreshed. A configured
file that is missing, unreadable or empty prevents an ungrounded session from
starting and produces an error naming the file. Unset the variable to disable it.
For a wheel-only installation, provide an absolute path to your own document.

### Ari's background research

This experiment gives Ari local expertise in laser cutting while keeping
conversation open to any topic, including history, science, art, and project
context. It uses the Hugging Face voice model for short conversation and a
separate Claude advisor for questions beyond the local documents, uncertain
answers, complicated explanations, and web research. The voice model chooses the
`research_question` tool when it needs help; there is no calibrated confidence
score. Ordinary conversation alone does not start paid research requests.

```text
Reachy mic → Hugging Face conversation model → Reachy speaker
                     │ research_question         ↑
                     │ immediate acknowledgement │ brief at a conversational pause
                     └→ Claude advisor + web search
```

The advisor receives recent transcripts, the requested question, the shop context,
and `docs/Grounding Doc/ari-02-reasoner-playbook.md`. Local rules and staff approval
requirements remain in the immediate voice prompt. Web findings do not override
those rules, approve materials, or supply permission to operate a machine.
The general architecture image above does not yet show this research handoff.

Configure the local `.env`:

```env
REACHY_MINI_CUSTOM_PROFILE=ari
REACHY_MINI_GROUNDING_FILE="docs/Grounding Doc/ari-01-shop-context.md"
REACHY_MINI_REASONING_ENABLED=true
ANTHROPIC_API_KEY=your-api-key
REACHY_MINI_REASONING_MODEL=claude-sonnet-5-5
REACHY_MINI_REASONING_EFFORT=medium
REACHY_MINI_REASONING_GROUNDING_FILE="docs/Grounding Doc/ari-02-reasoner-playbook.md"
REACHY_MINI_REASONING_WEB_SEARCH=true
```

Use a Claude model that supports the Messages API, the selected effort level
and, when enabled, the `web_search` server tool (for example `claude-sonnet-5-5` or
`claude-opus-5-5`). Existing model choices
in `.env` are preserved. API usage and web searches are billed to the API account;
Claude.ai subscriptions do not cover them. Search is enabled by default for the
advisor; set `REACHY_MINI_REASONING_WEB_SEARCH=false` to disable internet access.
The advisor can still reason from its knowledge and the supplied context. No
additional dependency is needed.

Restart the conversation app after changing configuration or the reasoner playbook:

```bash
source .venv/bin/activate
reachy-mini-conversation-app --no-camera --ui
```

When launching through the desktop app, instance-local `.env` and saved personality
settings can override the checkout's configuration. Select Ari in the UI if a
previously saved personality is active. Startup logs identify the selected profile
and advisor model. A missing key or unreadable playbook disables the advisor and
logs the reason; voice conversation remains available. A missing configured shop
document still prevents an ungrounded voice session from starting.

#### Conversation flow

1. The voice model handles small talk, established facts, and brainstorming directly.
   For uncertain specifics, current facts, explicit lookups, or explanations needing
   research and synthesis, `research_question` queues work and returns immediately.
2. Ari acknowledges the lookup once and keeps responding to the student's actual
   comments while the advisor works. Established context, explicitly framed
   brainstorming, and occasional situational humor keep the exchange natural.
   Questions should be useful, not fill silence; a clear question needs no
   clarification before research starts. Ari must not invent facts or sources,
   claim unfinished research is verified, or repeat waiting announcements.
3. The advisor can search sources appropriate to any topic. The voice tool sets
   `search_web=true` for explicit lookups, current information, or requested
   sources; this requires a web-search call when search is enabled. Other requests
   allow the advisor to choose whether to search. A materially changed question
   replaces and cancels the previous request. Identical requests within a user
   turn are deduplicated.
4. Results remain available across follow-up turns and update the voice instructions
   without interrupting a response. Ari can continue after the active response,
   estimated queued speaker audio, and a 0.75-second quiet interval. The final sender
   checks again for new speech before sending that continuation.
5. Before speaking a finding, the voice model checks its relevance to the latest
   conversation. It can connect the answer to new details or remain silent if the
   topic is obsolete or resolved. A correction to Ari's earlier claim takes priority.
   Ordinary notes expire after more than four further user turns. A completed audio
   response that had access to a note consumes it; this records exposure, not proof
   that the model used it.

While the advisor is available, the voice session replaces its bundled direct web
and knowledge lookup tools with the immediate research handoff. Robot tools keep
working. If the advisor is disabled, the original lookup tools remain available.
The conversation screen shows **Research ready**, **Research running**, and
**Research complete · web searched** (or **no web search used**), plus the model
and actionable errors. The completed status counts actual search calls, even
when the response contains no citation. Source links come from cited API annotations
or, when none are available, actual web search results. A returned search link does
not establish that the advisor cited or relied on it. Status and source links are
also available through `conversation.research`.
They are not read aloud. The live reference panel covers the current session;
the experiment archive retains research results and citations across sessions.

The worker batches requests for 0.75 seconds, starts requests at least five seconds
apart, and runs one inference at a time. It sends at most 24 utterances and 24,000
transcript characters, capped at 4,000 characters per utterance. Each inference
has a 45-second timeout and an 8,000-token output cap including reasoning. Failures
leave conversation running and publish an unavailable state. At a quiet pause, Ari
can briefly explain that the lookup failed if the question is still relevant,
without claiming a verified answer. A new explicit request
can retry after a minimum 15-second cooldown; there is no automatic paid retry loop.
The result contains at most two 600-character snippets, one next question, and uncertainty.

The archive records `research_setup` with the configured model, search availability,
or a setup failure reason. `research_tool_available` confirms whether the voice
session has the handoff tool. Logs connect queued, started, ready, expired and
response-exposure events using `research_id`, with source turn, result age, elapsed
inference time, and the actual `web_search_calls` count in `research_response`. Publication
success means the update was sent, not that the remote model used it. Speech latency
logs measure from completed transcription, not from microphone input to physical
speaker playback. Actual fluency and model tool selection still require a live check.

Enabling research sends the question, recent text transcripts and both grounding
documents to Anthropic; returned notes and citations go to the Hugging Face service.
Search queries may be generated from that context. The advisor receives no camera
images or microphone audio, uses `store=False`, and keeps history in memory. This
is not a promise of zero provider retention. It cannot operate hardware.

To test general research, say: **"Look up the Yom Kippur War and explain its causes
for my diorama."** Ari should acknowledge that subject, start research, and stay
available for conversation. Watch for **Research running**, then **Research complete
· web searched** and source links. Leave a quiet pause for Ari to work the answer
into the conversation. Also try a complex laser question, such as why a test cut
is incomplete only in some areas. Interrupting or changing topics should not cause
a research result to interrupt speech or force a return to the old topic.

If research never starts, check the downloaded archive: `research_setup` with
`enabled: false` indicates a configuration problem; `research_failed` indicates
an upstream request failed. If setup and tool availability are enabled but there
is no `research_requested`, the voice model did not call the tool. Ensure Ari is
selected, restart after prompt changes, and try an explicit lookup. A
`research_response` with `web_search_calls: 0` means the advisor answered without
using web search, regardless of what it said conversationally.

### Experiment data

Text recording is automatic. The Talk screen shows the recording status and saved
size, with **Download data** and **Clear data…** controls. Downloading copies the
archive without stopping recording. Clearing requires confirmation, erases the
saved archive, and leaves recording active for new events. There is no automatic
rotation, expiry, or deletion; app restarts keep appending to the same file.

The file is `experiment.jsonl.gz`, alongside the app's memory file in its persistent
instance directory. In terminal mode without an instance path, it is under
`$XDG_DATA_HOME/reachy_mini_conversation_app/`, or
`~/.local/share/reachy_mini_conversation_app/` when that variable is unset. Hover
over the recording status to see the actual path. Recording works without the UI.
For copy-and-paste export commands, see [Download data from Terminal](#download-data-from-terminal).

Each JSON line contains schema version `v`, UTC Unix time in milliseconds `t`,
session ID `s`, and event type `e`. Event-specific fields retain user transcripts,
operator text, generated assistant text, response completion/interruption status,
tool calls/results, and research requests, results, sources, timings, and failures.
Research IDs link requests to results within a session. Generated text is not proof
that all those words reached the speaker; cancelled replies retain available partial
transcripts. A disconnected session retains available assistant text too.

To keep files compact, the recorder stores UTF-8 text with compact JSON and maximum
gzip compression. It excludes raw audio, camera images (see [Session recording](#session-recording) for those), token-by-token duplicates,
private model reasoning, and repeated system prompts. It uses complete gzip members
per event so ordinary restarts can append without rewriting old data; standard gzip
readers, Python and pandas read all members. Compression and writes run on a separate
worker to keep disk work off the voice loop. File errors appear in the Talk status
and app logs. A forced process or machine crash can lose events still queued for writing.
The archive contains participant speech as text and stays on the app's host unless
you download or share it. Clearing long-term memory does not clear this archive.

For analysis, Python's standard library can stream the file without extra packages:

```python
import gzip
import json

with gzip.open("experiment.jsonl.gz", "rt", encoding="utf-8") as archive:
    for line in archive:
        event = json.loads(line)
        if event["e"] in ("input", "response"):
            print(event["s"], event["t"], event["e"], event.get("text", ""))
```

Downloads use bounded chunks of a fixed file snapshot; new entries remain in the
live archive for the next download. Clearing during a download invalidates it,
instead of mixing old and new records. The same actions are available to clients
through `experiment.log` with `action: "status"`, `"read"`, or `"clear"` (the last
requires `confirm: true`).

### Session recording

Set `REACHY_MINI_SESSION_RECORDING=true` to save speech and video for each session in
`<start>_<id>/` folders under `REACHY_MINI_SESSION_RECORDING_DIR` (default: `sessions/` beside the experiment archive): `mic.wav` (participants),
`assistant.wav` (what Ari says), `camera.mp4` with `camera.index.jsonl` (continuous
robot-camera video at `REACHY_MINI_SESSION_RECORDING_FPS`, default 5), `transcript.txt`
(readable text of what participants and Ari said, plus `TOOL` calls/results and every
`REASONER` step: asked with its question and turn, started, answered with its advice,
web-search count and duration, and whether Ari's reply could use it; mm:ss times from
session start),
and `meta.json`.
Both WAVs start at session time zero (pauses are padded with silence), and every video
frame carries a UTC millisecond timestamp on the same clock as `experiment.jsonl.gz`, so
you can line up speech, video and logged events. Video is encoded live by ffmpeg
(`brew install ffmpeg`); without it the app falls back to a very large raw
`camera.mjpg` (about 10 GB/hour at 1080p). To sync an extra camera such
as a phone, clap once on camera after the session starts; the clap shows in `mic.wav`
and in the phone's audio. Recordings stay on the app host and are never cleared
automatically; only record people who know about it.

### Hugging Face Connection Modes

Use the built-in Hugging Face server through the app-managed Space proxy. This is the default for a new install; set it explicitly only when you want to switch back from a saved local endpoint:

```env
HF_REALTIME_CONNECTION_MODE=deployed
```

Deployed session allocation falls back to cached `hf auth login` credentials and reports the daemon-provided hardware ID when available. Cached credentials and the hardware ID are not sent to local endpoints.

Run your own realtime voice backend using [speech-to-speech](https://github.com/huggingface/speech-to-speech) on the same machine as the conversation app:

```env
HF_REALTIME_CONNECTION_MODE=local
HF_REALTIME_WS_URL=ws://127.0.0.1:8765/v1/realtime
```

Run your own Hugging Face backend on your laptop and connect to it from Reachy Mini Wireless over the same Wi-Fi network:

```env
HF_REALTIME_CONNECTION_MODE=local
HF_REALTIME_WS_URL=ws://<your-laptop-lan-ip>:8765/v1/realtime
```

For that LAN setup, make sure the backend listens on an address reachable from the robot, not only on `127.0.0.1`.

If the backend stays bound to loopback on your laptop, you can forward it into the robot over SSH instead:

```bash
ssh -N -R 8765:127.0.0.1:8765 <robot-user>@<robot-host>
```

Then set this on the robot:

```env
HF_REALTIME_CONNECTION_MODE=local
HF_REALTIME_WS_URL=ws://127.0.0.1:8765/v1/realtime
```

In the web UI's Settings view, the Connection section lets you choose either the built-in server or a local `host:port` target. The UI writes `HF_REALTIME_CONNECTION_MODE` for you, and the local path writes `HF_REALTIME_WS_URL` with a default of `localhost:8765`.


## Running the app

### Start this laser-cutting experiment from Terminal

On this Mac, first open the Reachy Mini desktop app and connect the robot. Its
robot service (daemon) must be running. If the conversation app is already running
there or in another terminal, stop that conversation instance before starting this one.
Keep the robot service running.

Paste these commands into Terminal:

```bash
cd /path/to/aaram-v1
source .venv/bin/activate
reachy-mini-conversation-app --no-camera --ui
```

These commands use the existing environment and `.env` in this checkout. For a
fresh installation, complete [Installation](#installation) and
[Ari's background research configuration](#aris-background-research) first. On
another computer, replace the `cd` path with your checkout's location. The shell
examples use macOS/Linux syntax; in Windows PowerShell, activate the environment
with `.venv\Scripts\Activate.ps1`.

Keep this terminal open while talking to Ari. The camera is disabled for this
experiment. Open [the Talk screen](http://127.0.0.1:7860/) to see research references
and recording status; the browser is optional. After the session connects, check
the terminal for the Ari profile and the "Background reasoning enabled" message.
If the advisor is disabled, its log message explains which setting is missing.

Press **Control+C** in this terminal to stop the app. Starting it again with the
same commands continues adding to the existing experiment archive.

If the command is missing, activate `.venv` and check the installation steps. A
robot connection `TimeoutError` usually means the robot service is unavailable.
If port `7860` is already in use, stop the earlier app instance before relaunching.

### Author-operated paper experiments

The Ari profile implements five flexible teaching modes: Tell, Guide, Ask, Offer,
and Hand over. Missing prerequisites receive explanation or options immediately;
the student need not fail two questions first. Handoffs summarize the project,
what is known or tried, and the question for staff without inventing missing details.
Safety rules, staff approvals, and the existing motion limits still apply.

Use the same checkout on each Mac. Install its locked environment with `uv sync --frozen`
and activate `.venv`. Keep credentials in each Mac's own ignored `.env`; the advisor
uses `ANTHROPIC_API_KEY`, while voice uses the Hugging Face connection. The OpenAI key
is not needed for this advisor. Start and connect the Reachy daemon before launching
a trial, and stop any other conversation instance. The launcher does not install or
start the daemon, grant macOS permissions, or move the robot during a dry run.

```bash
python -m benchmarks.ari_study.launch --experiment latency --condition on --dry-run
python -m benchmarks.ari_study.launch --experiment latency --condition on --case lookup-01 --repetition 1
```

Use `--condition off` for conversation-only, and select `--experiment safety` or
`--experiment teaching` for the other tests. `--voice` fixes a supported voice;
use the same voice in comparisons. Each launch creates a fresh instance under
`recordings/paper/<trial-id>/`, forces Ari, disables long-term memory and camera
tools/recording, and records speech and transcripts. `--output` changes the local
recordings root; paths are resolved independently on each Mac. Only operate these
recorded author tests where nearby people know speech may be processed and recorded.
The physical visor does not control microphone processing or retention.

`trial.json` records the requested condition without credentials. The session's
`meta.json` and `session_start` log event record the effective profile, voice,
advisor setup, memory/camera settings, installed package versions, and source/prompt
hashes. Check requested versus actual advisor state before accepting an ON trial.
Record the voice service's reported model version when available; a client package
version alone does not pin the hosted conversation model. Changing prompts during
collection produces a new configuration, not additional runs of the old one.

- **Safety:** the existing 65 cases are in `benchmarks/ari_safety/cases.json`.
  `python -m benchmarks.ari_safety.coverage` checks rule coverage. The live runner
  `python -m benchmarks.ari_safety.run --url ws://127.0.0.1:7860/rpc --repeats 3`
  sends typed prompts. It runs cases in one session, so report that context carryover;
  for isolated cases, launch fresh and use `--only <case-id> --repeats 1`.
  Word checks are screening results. Human review must distinguish incomplete
  responses from critical violations and retain unanswered attempts.
- **Latency:** deliver the same authored request in fresh OFF/ON sessions, alternate
  order across repetitions, and keep voice, input delivery, source availability,
  hardware and network conditions consistent. OFF uses installed direct lookup tools;
  ON uses the Anthropic advisor and its search. This compares whole configurations,
  not identical retrieval implementations. Confirm lookup tools actually loaded.
- **Teaching:** `benchmarks/ari_teaching/cases.json` contains eight provisional fixed
  fictional scripts, two per category, plus behavioral criteria and a blank scoring
  template. Use a fresh trial per script repetition, deliver turns verbatim, and
  score the actual responses. Three repetitions are a planned protocol, not collected
  results. Keep failed or mismatched responses rather than improvising a rescue.

Export a completed trial's timing and annotation sheet:

```bash
python -m benchmarks.ari_study.export recordings/paper/<trial-id>/instance/experiment.jsonl.gz --output recordings/paper/<trial-id>/analysis
```

`first_audio_generated` measures client receipt of the first audio chunk relative
to completed transcription or typed input. It is not physical speaker playback.
If generation precedes completed transcription, the interval is unmeasured rather
than zero. The exporter retains attempts without audio and leaves useful-answer,
audible-response, outcome and notes columns for human annotation. Use independently
observed playback when reporting audible timing; `assistant.wav` records generated
audio and is not proof that an interrupted chunk was heard. The exported median
and nearest-rank 95th percentile describe measured generation latency only.

These tools support the paper's author-operated evaluations. They do not implement
material recognition, visor-position sensing, selective listening, wake/lift controls,
or measured learning outcomes. No dummy values from the draft are evaluation results.

### Download data from Terminal

**Simplest option: copy the archive after stopping the app.** Press Control+C in
the app terminal and wait for it to exit. Then run this in Terminal:

```bash
aaram_log="${XDG_DATA_HOME:-$HOME/.local/share}/reachy_mini_conversation_app/experiment.jsonl.gz"
mkdir -p "$HOME/Downloads"
cp -i "$aaram_log" "$HOME/Downloads/aaram-experiment-$(date +%Y%m%d-%H%M%S).jsonl.gz"
```

The copy appears in **Downloads** with the date and time in its filename. The
original remains in place, and the next app run keeps appending to it. This path
matches the terminal launch above. If you launched through the desktop app, use
the actual archive path shown when hovering over the Talk screen's recording
status. A "No such file" error means no archive has been recorded at that path yet.

**To download while the conversation keeps running**, leave the first terminal
open and open a second Terminal window. This version asks the running app for a
complete snapshot, so new recording can continue safely. It needs the `--ui`
option from the startup command, but does not need an open browser.

```bash
cd "/Users/adityade/Documents/ITP/Aaram/version 1"
source .venv/bin/activate
python - <<'PY'
import base64
import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from websockets.sync.client import connect

with connect("ws://127.0.0.1:7860/rpc", proxy=None) as socket:
    def request(params):
        socket.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "experiment.log", "params": params}))
        while True:
            reply = json.loads(socket.recv(timeout=30))
            if reply.get("id") == 1:
                if "error" in reply:
                    raise RuntimeError(reply["error"]["message"])
                return reply["result"]

    snapshot = request({"action": "status"})
    if snapshot["error"]:
        raise SystemExit(snapshot["error"])
    if not snapshot["bytes"]:
        raise SystemExit("No recorded data yet. Start a conversation, then try again.")

    downloads = Path.home() / "Downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = downloads / f"aaram-experiment-{stamp}.jsonl.gz"
    with TemporaryDirectory(prefix="aaram-download-", dir=downloads) as folder:
        temporary = Path(folder) / "experiment.jsonl.gz"
        with temporary.open("wb") as output:
            offset = 0
            while offset < snapshot["bytes"]:
                chunk = request({"action": "read", "offset": offset,
                                 "limit": snapshot["bytes"], "generation": snapshot["generation"]})
                if chunk["next_offset"] <= offset:
                    raise RuntimeError("Download stopped. Please try again.")
                output.write(base64.b64decode(chunk["content"], validate=True))
                offset = chunk["next_offset"]
        temporary.replace(destination)

print(f"Saved {snapshot['bytes']:,} bytes to {destination}")
print("Recording continues. The original archive has not been cleared.")
PY
```

This uses the app's installed dependencies; no extra package is needed. It prints
the saved file's full path. If the connection is refused, check that the app is
running with `--ui` in the first terminal. If someone clears the log during export,
the download fails cleanly; run the command again to download the new archive.

Both methods retain the compact `.jsonl.gz` format. To inspect a downloaded file,
replace the example filename below with the saved path:

```bash
gzip -t "$HOME/Downloads/aaram-experiment-YYYYMMDD-HHMMSS.jsonl.gz"
gzip -dc "$HOME/Downloads/aaram-experiment-YYYYMMDD-HHMMSS.jsonl.gz" | less
```

`gzip -t` prints nothing when the archive is valid. In `less`, press **q** to exit.
Neither command changes the saved file. Downloading never clears the live archive;
use **Clear data…** on the Talk screen only when you want to erase the saved history.

### CLI options

| Option | Default | Description |
|--------|---------|-------------|
| `--no-camera` | `False` | Run without camera capture. |
| `--ui` | `False` | Serve the web UI at http://127.0.0.1:7860/, in addition to console mode. |
| `--robot-name` | `None` | Optional. Connect to a specific robot by name when running multiple daemons on the same subnet. See [Multiple robots on the same subnet](#advanced-features). |
| `--debug` | `False` | Enable verbose logging for troubleshooting. |

### Examples

```bash
# Audio-only conversation (no camera)
reachy-mini-conversation-app --no-camera

# Launch with the minimal web UI for personality/mic/settings control
reachy-mini-conversation-app --ui
```

## LLM tools exposed to the assistant

The default profile exposes these tools. Use Tools → Tool access to customize any profile.
Every bundled profile enables `head_tracking` by default; users can still disable it per personality.

| Tool | Action | Dependencies |
|------|--------|--------------|
| `dance` | Queue a dance from `reachy_mini_dances_library`. | Core install only. |
| `stop_dance` | Clear queued dances. | Core install only. |
| `play_emotion` | Play a recorded emotion clip via Hugging Face datasets. | Core install only. Uses the default open emotions dataset: [`pollen-robotics/reachy-mini-emotions-library`](https://huggingface.co/datasets/pollen-robotics/reachy-mini-emotions-library). |
| `stop_emotion` | Clear queued emotions. | Core install only. |
| `camera` | Capture the latest camera frame and analyze it with the selected realtime backend. | Core install only. Requires the camera (disable with `--no-camera`). |
| `idle_do_nothing` | Explicitly remain idle during an idle turn. Not intended for normal conversation turns. | Core install only. |
| `move_head` | Queue a head pose change (left/right/up/down/front). | Core install only. |
| `head_tracking` | Follow the user's face with the head, or stop following. | Core install only. Requires a daemon with the `vision` extra and a camera. |
| `go_to_sleep` | Run Reachy's sleep movement and stop the current app after an explicit user request. | Core install only. |
| `sweep_look` | Sweep Reachy's head left, right, and back to center. | Shared tool, enabled by default in the default profile. |
| `remember` | Save one short, stable fact about the user for future sessions. | Core install only. Stored in the app instance data directory. |
| `forget` | Remove a saved memory fact by matching a short query. | Core install only. |
| `volume_control` | Read or change Reachy's speaker or microphone volume. | Core install only. Uses the daemon REST API; setting the speaker volume plays a short confirmation sound. |
| `robot_status` | Read one status topic: `name`, `software` (version, update available), `wifi` (IP address, network), `account` (Hugging Face sign-in), `imu` (which way the head is tilted, motion, temperature), `apps` (installed apps). | Core install only. Uses the daemon REST API. The update check and the Wi-Fi network details are wireless-version only; the IP address is reported on any robot. |
| `pollen_robotics_reachy_mini_search_tool__search_web` | Search the web and return a short list of results. | Preinstalled MCP Space: `pollen-robotics/reachy-mini-search-tool`. |
| `pollen_robotics_reachy_mini_weather_tool__get_weather` | Report today's weather for a place: current conditions, high and low temperature, and rain chance. | Preinstalled MCP Space: `pollen-robotics/reachy-mini-weather-tool`. |
| `pollen_robotics_reachy_mini_time_tool__get_time` | Report the current time for a timezone or the user's local time, or the difference between two timezones. | Preinstalled MCP Space: `pollen-robotics/reachy-mini-time-tool`. |
| `pollen_robotics_reachy_mini_knowledge_tool__get_info` | Read the official overview, capabilities, versions, and prices for a Pollen Robotics product or the company. | Preinstalled MCP Space: `pollen-robotics/reachy-mini-knowledge-tool`. |
| `pollen_robotics_reachy_mini_knowledge_tool__search_docs` | Search the official Reachy Mini FAQ and troubleshooting documentation. | Preinstalled MCP Space: `pollen-robotics/reachy-mini-knowledge-tool`. |

> [!NOTE]
> `remember`/`forget` facts are stored in `memory.v1.json` inside the app's instance data directory (`~/.local/share/reachy_mini_conversation_app/` by default, or the instance path used by the desktop launcher). `forget` only removes facts matched by query. To reset all remembered facts, delete this file.

## Creating and adding tools

Tools can run locally as Python code or remotely in an MCP-compatible Hugging Face Space. Keep robot, camera, and local-data operations in local tools. A Space is a better fit for shareable, stateless services such as search and external API lookups.

### Local tools

Create one Python module per tool, with the file name matching the tool's unique `name`. See [`idle_do_nothing.py`](src/reachy_mini_conversation_app/tools/idle_do_nothing.py) for a minimal implementation.

Each tool subclasses `Tool` and defines `name`, a model-facing `description`, an object-shaped JSON Schema in `parameters_schema`, and an async `__call__` method. Use `ToolDependencies` for runtime services, and set `needs_response = False` for actions that should not trigger a spoken follow-up. Catch expected operational failures, log them with the module logger, and return `{"error": "..."}` so the conversation can continue.

Restart the app after adding the module. Use Tools → Tool access to enable it for a personality, or add its name to that profile's `default_tools` in `profile.md`. See [External profiles and tools](#external-profiles-and-tools) for external directories and autoload behavior.

### Hugging Face Space tools

To publish a remote tool, create a Gradio Space, expose its API as MCP with `mcp_server=True`, and give each function clear type hints and docstrings. Verify that `https://<space-subdomain>.hf.space/gradio_api/mcp/schema` lists the expected tools before installing the Space.

Use the maintained [weather](https://huggingface.co/spaces/pollen-robotics/reachy-mini-weather-tool), [time](https://huggingface.co/spaces/pollen-robotics/reachy-mini-time-tool), and [search](https://huggingface.co/spaces/pollen-robotics/reachy-mini-search-tool) Spaces as examples. See Gradio's [MCP server guide](https://www.gradio.app/guides/building-mcp-server-with-gradio) for additional publishing guidance and [Installing Hugging Face Space tools](#installing-hugging-face-space-tools) for this app's installation steps.

## Advanced features

Built-in motion content is published as open Hugging Face datasets:

- Emotions: [`pollen-robotics/reachy-mini-emotions-library`](https://huggingface.co/datasets/pollen-robotics/reachy-mini-emotions-library)
- Dances: [`pollen-robotics/reachy-mini-dances-library`](https://huggingface.co/datasets/pollen-robotics/reachy-mini-dances-library)

<details>
<summary>Custom profiles</summary>

Create custom profiles with dedicated instructions and per-profile tool access.

Select and save a startup profile in the UI. The choice is stored in `startup_settings.json`. Before one is saved, `REACHY_MINI_CUSTOM_PROFILE=<name>` can select `profiles/<name>/`; otherwise the app uses `default`.

Every profile directory contains one strict schema-version-1 `profile.md`. TOML metadata is enclosed by `+++`; the remaining Markdown body is the realtime assistant prompt:

```markdown
+++
schema_version = 1
voice = "Aiden"
greeting = "Greet me warmly in one sentence, in character, and vary the wording each time."
hidden = false
default_tools = [
  "dance",
  "camera",
  "sweep_look",
]
+++

## Identity

You are a concise, friendly robot guide.
```

`schema_version`, `default_tools`, and a non-empty Markdown body are required. `voice`, `greeting`, and `hidden` are optional. Set `hidden = true` to omit a profile from the UI. An empty `default_tools` list is valid and inherits nothing.

`default_tools` is the authored baseline. Tools → Tool access stores overrides in instance-local `profile_toolsets.json` without changing bundled profiles. Restoring defaults removes the override. Active-profile changes reconnect the conversation; other changes apply when selected.

Profile directories are data-only. Python tool implementations belong in `src/reachy_mini_conversation_app/tools/`, or in `REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY` for external tools. Each enabled tool ID must resolve to a shared tool, an external tool, or a tool from an installed Hugging Face Space.

See [Creating and adding tools](#creating-and-adding-tools) for the local tool interface and a maintained example.

To manage personalities in the UI:

With `--ui`, Home lists the available profiles and the built-in default:

- Tap a card to apply that personality and start talking.
- Tap "Manage tools" on a saved personality to open its tool access directly.
- Tap "Custom" to create a personality with a name, instructions, and optional greeting. It inherits the default tools, which can be changed under "Manage tools". Managed instances store it at `user_personalities/<name>/profile.md`; standalone runs use `external_content/user_personalities/<name>/profile.md`.

Switching a personality reloads its prompt and effective tools through a quick backend reconnect. Editing `profile.md` directly requires re-selecting the profile or restarting the app.

</details>

<details>
<summary>Locked profile mode</summary>

To create a locked variant of the app that cannot switch profiles, edit `src/reachy_mini_conversation_app/config.py` and set the `LOCKED_PROFILE` constant to the desired profile name:
```python
LOCKED_PROFILE: str | None = "mars_rover"  # Lock to this profile
```
When set, the app ignores saved startup settings, `REACHY_MINI_CUSTOM_PROFILE`, and UI selection. The UI marks the profile as locked and disables editing.

</details>

<a id="external-profiles-and-tools"></a>

<details>
<summary>External profiles and tools</summary>

You can extend the app with profiles/tools stored outside the repository defaults.

- Core profiles are under `profiles/`.
- Core tools are under `src/reachy_mini_conversation_app/tools/`.

Recommended layout:

```text
external_content/
├── external_profiles/
│   └── my_profile/
│       └── profile.md
├── external_tools/
│   └── my_custom_tool.py
├── user_personalities/
│   └── my_custom_profile/
│       └── profile.md
├── installed_tool_spaces.json
└── profile_toolsets.json
```

Environment variables:

Set these values in your `.env` when you want env-driven external profile/tool selection:

```env
# Optional fallback/manual profile selector:
REACHY_MINI_CUSTOM_PROFILE=my_profile
REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY=./external_content/external_profiles
REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY=./external_content/external_tools
# Optional convenience mode:
# AUTOLOAD_EXTERNAL_TOOLS=1
```

Loading rules:

- Profiles: each directory requires a schema-version-1 `profile.md` with explicit `default_tools`; there is no cross-profile fallback.
- Default mode: enabled IDs must resolve to a shared, external, or installed Tool Space tool.
- Autoload: `AUTOLOAD_EXTERNAL_TOOLS=1` adds every valid `*.py` module from `REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY`.
- Web UI: Tools → Tool access enables external modules per profile; it does not upload or edit Python.
- Separation: profile directories contain data only; external Python belongs in `REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY`.
- Tool names: every loaded class needs a unique `Tool.name`; duplicates fail fast.

</details>

<a id="installing-hugging-face-space-tools"></a>

<details>
<summary>Installing Hugging Face Space tools</summary>

You can install MCP-compatible Hugging Face Spaces as remote tool sources for this app. Private Spaces work too, as long as `HF_TOKEN` is set (or you have run `hf auth login`) for an account that can access them. To publish a new Space, follow [Creating and adding tools](#hugging-face-space-tools).

Tools → Tool Spaces installs or refreshes a global source. Its tools then appear under Tools → Tool access for per-profile selection. Removing a Space removes its tools from every profile. Active-profile changes reconnect the conversation; other changes apply when selected.

The app accepts Hugging Face Spaces exposing the standard `/gradio_api/mcp/` endpoint, not arbitrary MCP URLs. Installation discovers the Space's tools and assigns namespaced local IDs, so do not guess or hard-code those IDs beforehand.

```bash
# install + enable in active profile
reachy-mini-conversation-app tool-spaces add <owner/space-name>

# enable in a specific profile
reachy-mini-conversation-app tool-spaces add <owner/space-name> --profile NAME

# install without enabling
reachy-mini-conversation-app tool-spaces add <owner/space-name> --install-only

# list installed spaces
reachy-mini-conversation-app tool-spaces list

# remove an installed space
reachy-mini-conversation-app tool-spaces remove owner/space-name
```

Bundled Pollen Spaces use static specs and are enabled by the default profile. Newly bundled Spaces are added to existing installations without restoring older tools the user removed. Custom Spaces are validated through the Hugging Face Hub; HF tokens are sent only to private Spaces. Tool metadata is cached in:

- `installed_tool_spaces.json` in the managed app instance directory
- `external_content/installed_tool_spaces.json` in terminal mode

Startup and profile switching read this cache without discovery or MCP probing. Network access occurs only during install, refresh, or remote tool calls. Per-profile access is stored in `profile_toolsets.json` beside the manifest, or under `external_content/` in terminal mode.

Recommended tags for discoverability on Hugging Face:

- `reachy-mini-tool`
- `mcp`

Tags are advisory; installation still requires successful MCP validation.

> [!NOTE]
> Preinstalled Pollen Spaces can be removed like any other (`tool-spaces remove pollen-robotics/reachy-mini-weather-tool`). To restore access, reinstall the Space and restore or update the relevant profile under "Tool access".

</details>

<details>
<summary>Multiple robots on the same subnet</summary>

If you run multiple Reachy Mini daemons on the same network, use:

```bash
reachy-mini-conversation-app --robot-name <name>
```

`<name>` must match the daemon's `--robot-name` value so the app connects to the correct robot.

</details>

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the development workflow and [`AGENTS.md`](AGENTS.md) for coding-agent standards.

## License

Apache 2.0

## Phone and robot inference study

The `inferencetesting` branch adds an exploratory study client for both interfaces. The existing architecture diagram does not show this separate shared Node backend or its inline/background modes.

Two audio clients share one study backend. Either client supports both inference architectures. The study clients live under `ari-study/`; the existing robot application remains available. Run the commands below from `ari-study/`.

| Mode | Web access | Who interprets the sources? | Conversation behavior |
| --- | --- | --- | --- |
| inline | Enabled | Conversation model itself | May acknowledge before a lookup; gets real source excerpts on completion; microphone remains live |
| background | Enabled through the same search service | Separate Claude researcher sends a brief to the voice model | Immediate tool acknowledgement allows useful dialogue while the researcher works |

The background mode is the concurrent one. Neither mode is forced to remain silent or generate filler, and no synthetic inference delay is added. This compares architectures, not latency alone: an additional model can also change answer quality. Legacy on/off conditions are rejected rather than silently reinterpreted.

### What changed

- Both modes use the same `lookup_information` tool, shared search service and result budget. Inline never invokes the separate reasoning model.
- Phone and robot receive the same model session configuration within each mode.
- A new Reachy Mini client streams robot microphone/speaker audio and enables speech-reactive head movement. It does not reproduce every model-selected gesture in the old app.
- Search completion, background processing, tool delivery, speech and cancellations are logged separately.
- Background findings can re-enter naturally after follow-up turns. Delivery waits until the user and model are idle and a 750 ms quiet window has passed after reported playback/turn activity. This is a turn-taking safeguard, not a simulated inference delay.
- The voice model can explicitly skip an unsolicited research follow-up if the topic changed, it was resolved, or the note is not useful. No extra spoken reply is requested for a skipped note. Results older than eight new turns or three minutes at delivery are discarded.
- The protocol, UI, previews and allocation list use inline/background terminology. Old browser records remain accessible with their original labels.

### Verification and remaining work

The study checks cover 19 backend behaviors and three robot transport scenarios with simulated hardware; syntax checks are also provided. The robot client also loads in the existing Reachy Python environment. Tests cover direct search without a second model, background concurrency, shared phone/robot configuration, input during pending lookups, cancellation, failures, stale notes and exports.

Real phone audio, the robot adapter, provider access and deployment remain unverified. A matching backend configuration does not prove matching audio latency or recognition on hardware.

### Configure the shared server

Use Node 24+. Copy `.env.example` to `.env` and configure values locally. Never put keys into public frontend files. Run `npm ci` inside `ari-study/` to install the pinned MIT-licensed ws dependency. No Python dependency changes are required for the existing robot environment.

| Setting | Purpose |
| --- | --- |
| HF_REALTIME_WS_URL | Actual direct voice endpoint, or leave blank for the allocator used by the inspected robot |
| HF_TOKEN / HF_HARDWARE_ID | Authorized provider token/actual registered hardware identity if required |
| HF_VOICE | Default Aiden; both clients receive the same value |
| REALTIME_TRANSCRIPTION_LANGUAGE | Default en; shared by both clients |
| BRAVE_SEARCH_API_KEY | Required in both modes for the common search adapter |
| ANTHROPIC_API_KEY | Required only in background mode |
| REACHY_MINI_REASONING_MODEL | Explicit deployed researcher model ID; required only in background mode |
| REACHY_MINI_REASONING_EFFORT | Default medium; verify compatibility with that model |
| STUDY_ACCESS_TOKEN | Required for hosted/network access; enter the same code on the phone/client |
| ALLOWED_ORIGINS | Exact frontend origin when frontend and voice backend are hosted separately |
| HOST / PORT | Local defaults 127.0.0.1 / 4173 |

The current raw-search adapter uses Brave Search, returning at most five source excerpts per request. It does not fetch full pages. The background researcher receives those same results and has no extra browsing tools. No account was created and no search subscription or provider charge was initiated. You can replace `server/search.mjs` with your existing search service while keeping the same bounded result contract for both modes.

Run `npm run build`, then `npm start` from this folder, or use Start_Ari.command on macOS. Open http://127.0.0.1:4173 on the computer. The app refuses live sessions with missing required configuration; it never silently substitutes a different mode.

### Phone client

Open the app over HTTPS on a phone. In Research desk, set participant code, sequence, task and inference architecture. Both modes can search. Apply settings, complete the consent step, and begin. The participant view hides researcher metadata and transcripts. Export after every block. Leaving the page ends the block rather than silently resuming its memory later.

The separately exported package's standalone `Ari_Phone_Preview.html` is a scripted demonstration without a microphone or live model. Its timing is illustrative and is not study evidence.

### Robot client

Use the existing working Reachy Python environment, with the compatible Reachy Mini SDK (the inspected checkout pins 1.12.0rc1), NumPy and websockets. Do not upgrade the robot SDK independently of its daemon. The new client has not been installed into the original app or tested on the robot.

Stop the old conversation app before running this client. Leave the robot daemon running, with the robot awake and audio available. Run from this package's directory, using that environment's Python:

```sh
python robot/voice_client.py --server https://YOUR-STUDY-HOST --mode inline --participant P01 --task X --consent-confirmed
```

For the other mode, replace `--mode inline` with `--mode background`. Both use the same server-side voice/search configuration. Set STUDY_ACCESS_TOKEN in the client process environment; do not place it on the command line or in a URL. Optional flags select the robot name/host, media backend and output directory; `--help` lists them.

The adapter uses the SDK's microphone, speaker, `enable_wobbling` and immediate `clear_player` for interruption. It reads or sends no images, performs no head tracking and provides no machine-control tools. Disable any separate camera/vision consumers in the robot setup. Speech-reactive motion is the pilot's initial gesture policy; confirm whether this matches the intended robot condition before recruiting.

This initial adapter requires native 16 kHz input and output, matching the inspected voice loop. It reports unsupported media rates instead of silently changing speech timing. Validate this on your robot before use. The terminal reports startup/errors; Ctrl-C stops the session. Robot events and transcripts are saved as JSONL under `recordings/` or `--output`. They contain participant data and must not be put in a public deployment or source archive. The robot CLI does not provide the phone's mute button or rating form; document this control difference and collect robot ratings using the same paper questions.

### Hosting

The frontend can run on Netlify. The included Netlify Server entry supports `/api/*` and WebSockets on accounts with Server Early Access. Current Netlify documentation specifies Node 24+ and CLI 27.17+; confirm availability for the account. Build command: `npm run build`; publish directory: `dist`. Configure secrets in the server/Functions environment scope, then deploy. No catch-all static rewrite should swallow `/api/voice`.

Alternatively host this Node server on the droplet behind an HTTPS reverse proxy with WebSocket support, put the frontend on Netlify, and configure its exact origin in ALLOWED_ORIGINS. Set HOST=0.0.0.0 and a study access code on a network server. Enter its HTTPS origin in the phone research desk and the robot's `--server` argument. A phone's normal browser microphone access will not work over an ordinary HTTP LAN IP.

No deployment, droplet change or credential installation has been performed. Live sessions have a 25-minute limit, use fresh memory, and end on a connection loss. Exports and robot JSONL files are the study records; browser and hosting instance memory are not institutional archival storage.

### Before collecting data

- Confirm ethics/consent and staff review of the idle-machine preparation tasks and grounding document.
- Verify both modes on both interfaces: a factual lookup should cause the shared search call, and only background should cause a second reasoning-model request.
- Check real speech during pending calls, interruptions, and response-scoped tools for skipping irrelevant follow-ups. A prompt alone does not prove that a deployed voice backend supports continuing a turn during a tool wait.
- Match service versions, voice, language, volume, practice and task time. Compare microphone recognition, speaker delay and movement on actual hardware.
- Keep vision and cross-session memory out of both conditions. Confirm portability; use stationary tasks if the robot is tethered.
- Obtain actual source/model identifiers and credentials. API access remains unverified.

The first study remains interface-first: each participant tries robot and phone with one fixed inference architecture. The optional 16-person allocation has two people in each of eight sequence-by-architecture cells. It is exploratory, not a powered latency experiment.

### Files and development

- `study/Ari_Study_Protocol.md` and `public/protocol.html`: full draft with tasks, 40-minute procedure, ratings, interview questions, controls, analysis and data handling.
- `public/task-cards.html`: printable preparation props and worksheet.
- `study/allocation.csv` and `study/observations.csv`: allocation and observer templates.
- `robot/voice_client.py`: robot audio frontend to the shared backend.
- `robot/prompts/`: audit snapshots, not installable profiles for the old robot app.

Edit shared/*.md, then `npm run build` to refresh the server prompt bundle and frontend. `node scripts/export-robot.mjs` regenerates the audit snapshots. Run `npm test`, `npm run check` and the robot syntax check after relevant changes. `python scripts/render_protocol.py` regenerates the printable protocol.

Grounding was copied from the supplied Aaram checkout and still needs staff review. Participant data and provider secrets must remain out of Git. Official implementation references: https://api-dashboard.search.brave.com/app/documentation/web-search ; https://huggingface.co/docs/reachy_mini/API/reachymini ; https://huggingface.co/docs/reachy_mini/API/media ; https://docs.netlify.com/build/server/ .
