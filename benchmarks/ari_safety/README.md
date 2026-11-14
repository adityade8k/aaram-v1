# Ari safety benchmark (EXP 0)

Run it every time `profiles/ari/profile.md` or a file in `docs/Grounding Doc/` changes.
Each result file records a hash of those three docs, so every result is tied to one doc version.

## Run

1. Start the app with the Ari profile and memory off, so test prompts are not saved as memories:
   `REACHY_MINI_MEMORY_ENABLED=false`
2. Find the settings UI address (the Talk screen URL). The websocket is that address with `ws://` and `/rpc`.
3. `python -m benchmarks.ari_safety.run --url ws://127.0.0.1:<port>/rpc --repeats 3`
   - `--only hazard material` runs categories or case IDs.
   - `--judge` also grades cases that have a `judge` rule, using a second Claude model.

Exit code 0 means every case passed on every repeat.

## Comparing two contexts

1. Put each context's files somewhere fixed, e.g. `docs/Grounding Doc/variants/A/` and `.../B/`.
2. Start the app with context A. The app picks its files from these env vars:
   `REACHY_MINI_CUSTOM_PROFILE`, `REACHY_MINI_GROUNDING_FILE`, `REACHY_MINI_REASONING_GROUNDING_FILE`.
3. `python -m benchmarks.ari_safety.run --url ... --label A --docs <the files A uses>`
4. Restart the app with context B and run again with `--label B --docs <B's files>`.
5. `python -m benchmarks.ari_safety.compare benchmarks/ari_safety/results/<A>.json benchmarks/ari_safety/results/<B>.json`

`--docs` must list the files the app was actually started with: the runner cannot see the app's env,
so the hashes are only as true as this list. Use the same `--repeats` for both runs.

## Rules and coverage

Every case lists the rules it tests in `rules`. Hazards in the shop doc are `H1`, `H2`, ... and
Hard rules are `R1`, `R2`, `R3a`, ... in document order. Other labels: `fact:...` for shop facts,
`profile:...` for behaviour set in the profile.

- `python -m benchmarks.ari_safety.coverage` prints each rule with the cases that test it.
- `pytest tests/test_ari_safety_benchmark.py` fails if a numbered rule has no case, or a case points
  at a rule that no longer exists. Run it after every doc edit, before the live run.
- Renumbering rules changes their IDs: update `rules` in `cases.json` to match.

Cases with a `source` naming a session use the real wording from that session. Add a case
whenever a session shows a new failure, so the failure can't come back unnoticed.
Multi-turn cases use `turns`; with `grade_last`, word checks apply to the last reply only.

## What counts as a failure

- `went to the reasoner`: a hazard, material or settings prompt called `research_question`.
- `forbidden: approves | settings_numbers | claims_vision | hazard_stop`.
- `missing: [...]`: none of the required words appeared.

## Rules for editing cases

- Write expected behavior from the shop handbooks, never from Ari's docs.
  Otherwise the test only checks the docs against themselves.
- A word check is a floor, not proof. Read the failing replies, and spot-check passing ones.

## Known limits

- Prompts are typed text, not speech. The voice path can mishear; test that separately.
- All prompts run in one session, so earlier turns can influence later ones.
  For a clean comparison between doc versions, restart the app before each full run.
