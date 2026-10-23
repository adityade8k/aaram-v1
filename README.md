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

# Reachy Mini conversation app

Conversational app for the Reachy Mini robot combining realtime voice, vision, personality-aware tools, and choreographed motion.

![Reachy Mini Dance](docs/assets/reachy_mini_dance.gif)

## Table of contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the app](#running-the-app)
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
separate OpenAI advisor for questions beyond the local documents, uncertain
answers, complicated explanations, and web research. The voice model chooses the
`research_question` tool when it needs help; there is no calibrated confidence
score. Ordinary conversation alone does not start paid research requests.

```text
Reachy mic → Hugging Face conversation model → Reachy speaker
                     │ research_question         ↑
                     │ immediate acknowledgement │ brief at a conversational pause
                     └→ OpenAI advisor + web search
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
OPENAI_API_KEY=your-api-key
REACHY_MINI_REASONING_MODEL=gpt-6-astra
REACHY_MINI_REASONING_EFFORT=medium
REACHY_MINI_REASONING_GROUNDING_FILE="docs/Grounding Doc/ari-02-reasoner-playbook.md"
REACHY_MINI_REASONING_WEB_SEARCH=true
```

Use a model that supports the Responses API, structured output, the selected
reasoning effort and, when enabled, the `web_search` tool. Existing model choices
in `.env` are preserved. API usage and web searches are billed to the API account;
ChatGPT subscriptions do not cover them. Search is enabled by default for the
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

1. The voice model handles small talk and established shop facts directly. For a
   substantive question beyond the local documents, uncertainty, or a complex
   question, `research_question` queues work and returns immediately.
2. Ari acknowledges the actual question and may offer a known fact or one useful
   clarification while the advisor works. A clear question does not need a
   clarification before research starts. Ari should not redirect general topics
   to laser cutting, repeat waiting announcements, or manufacture conversation.
3. The advisor can search sources appropriate to any topic. The voice tool sets
   `search_web=true` for explicit lookups, current information, or requested
   sources; this requires a web-search call when search is enabled. Other requests
   allow the advisor to choose whether to search. A materially changed question
   replaces and cancels the previous request. Identical requests within a user
   turn are deduplicated.
4. Results update the voice instructions without interrupting a response. If the
   student has not started another turn, Ari can continue after the active response,
   estimated queued speaker audio, and a two-second quiet interval. The final sender
   checks again for new speech before sending that continuation.
5. If another user turn has already occurred, the note stays available for a relevant
   natural reply, without forcing a return to the old topic. The model must check
   relevance against the latest conversation. Notes expire after more than four
   further user turns. A completed audio response that had access to a note consumes
   it; this records exposure, not proof that the model used it.

While the advisor is available, the voice session replaces its bundled direct web
and knowledge lookup tools with the immediate research handoff. Robot tools keep
working. If the advisor is disabled, the original lookup tools remain available.
The conversation screen shows **Research ready**, **Research running**, and
**Research complete · web searched** (or **no web search used**), plus the model
and actionable errors. The completed status counts actual search calls, even
when the response contains no citation. Clickable citations come from API
annotations. Status and source links are also available through `conversation.research`.
They are not read aloud. The live reference panel covers the current session;
the experiment archive retains research results and citations across sessions.

The worker batches requests for 0.75 seconds, starts requests at least five seconds
apart, and runs one inference at a time. It sends at most 24 utterances and 24,000
transcript characters, capped at 4,000 characters per utterance. Each inference
has a 45-second timeout and a 6,000-token output cap including reasoning. Failures
leave conversation running and publish an unavailable state. A new explicit request
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
documents to OpenAI; returned notes and citations go to the Hugging Face service.
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
gzip compression. It excludes raw audio, camera images, token-by-token duplicates,
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
cd "/Users/adityade/Documents/ITP/Aaram/version 1"
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
