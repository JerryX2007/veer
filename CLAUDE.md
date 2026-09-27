# SideOut — volleyball VOD analyzer

<!-- Maintainers: keep this file under 200 lines. Area-specific rules belong in
.claude/rules/*.md with `paths:` frontmatter (e.g. app/** or engine/sideout/stages/**). -->

Local-first desktop app: the user uploads a volleyball match video and gets a box score
(kills, attack errors, attempts, hitting %, aces, service errors, reception errors, digs,
blocks, assists), a clickable event log that seeks an in-app player, a "describe a player"
tracker, and highlight reels. Everything runs on the user's machine. Product spec:
`docs/PRD.md` (read the relevant section before building a feature; don't import it here).

## Repo layout

```
app/                React + TypeScript (Vite) UI
  src/viewer/       video element, timeline, overlay canvas, keyboard shortcuts
  src/events/       event log, filters, review mode
  src/players/      player gallery, describe-a-player, merge/split
  src/highlights/   highlight list, playlist preview, export dialog
  src/api/          GENERATED client + types from the engine's OpenAPI schema
desktop/            Tauri shell; starts the engine as a sidecar
engine/sideout/     Python package: local API + inference pipeline
  api/              FastAPI routes; schemas.py holds every request/response model
  jobs/             job runner, rally chunking, resume
  stages/           one module per pipeline stage (see "Pipeline")
  domain/           events.py, stats.py (stat definitions), rules.py (rally grammar)
  media/            FFmpeg/PyAV: proxy, frame reading, clips, reels
  models/           ONNX Runtime sessions + model registry
  store/            SQLite (projects, events, jobs) and Parquet (per-frame tracks); migrations/
engine/tests/       unit, golden (short clips + expected event logs), fixtures
training/           PyTorch training and ONNX export. NEVER imported by engine/
eval/               evaluation harness, metric code, reports/
data/               gitignored: videos, labels, weights
```

## Commands

- Setup: `make setup` (runs `uv sync` in engine/ and `pnpm install` in app/)
- Dev: `make dev` (engine API on 127.0.0.1:8765 with reload + Vite + Tauri window)
- Engine only: `cd engine && uv run sideout serve --reload`
- Tests: `cd engine && uv run pytest -q`; golden clips: `uv run pytest -m golden`; UI: `pnpm -C app test`
- Lint/types: `cd engine && uv run ruff check . && uv run ruff format --check . && uv run mypy sideout`;
  UI: `pnpm -C app lint && pnpm -C app typecheck`
- Regenerate API types after any schema change: `pnpm -C app gen:api`
- Accuracy eval: `make eval SPLIT=dev` → `eval/reports/<timestamp>.md`
- Speed benchmark: `make bench` (10-minute fixture, per-stage fps)
- License audit: `make licenses`

Before saying a change is done, run lint, typecheck and tests for every area you touched.

## Pipeline

Stages run in this order; each is a module in `engine/sideout/stages/`:
`ingest` → `court` → `rallies` → (`ball` ‖ `players` → `identity`) → `touches` → `outcome`
→ event log → `stats` / `highlights`.

- Every stage implements the contract in `stages/base.py`: `run(ctx, inputs) -> StageOutput`.
  A stage reads only the declared outputs of earlier stages, never their internals.
- Outputs are cached under `(video_hash, stage, model_version)`. Changing a model or stage
  logic means bumping its version string, or stale cache will be reused.
- Heavy stages (`ball`, `players`, `identity`, `touches`) run only inside rally windows
  (+2 s padding). Never run them over the whole video.
- Ball runs at full fps; players at 10–15 fps with interpolation; jersey OCR on ≤ ~20
  legible crops per track. Stream frames; never hold a whole video's frames in memory.
- Rallies are independent work units in a process pool; results stream to the UI per rally.

## Domain invariants (do not break)

1. **The event log is the only source of truth.** Stats are computed from events in
   `domain/stats.py` and never stored as truth. Caches must be invalidated on edit.
2. **Time = seconds on the proxy timeline + frame index.** All analysis and playback use the
   720p constant-frame-rate proxy made at ingest. Never use source-file timestamps after
   ingest (phone video is often variable frame rate). `frame = round(t * fps)` is only valid
   on the proxy.
3. **Court coordinates are meters:** origin at a court corner, x along the 18 m length,
   net at x = 9, y across the 9 m width. Pixels live only in tracks and overlays.
   Boxes are stored as xyxy pixels at proxy resolution.
4. **Never overwrite model output.** A user edit writes a new event with `source="user"`
   that supersedes the old one (this is what makes undo and "show original" work).
5. **Team = jersey color, never court side.** Teams switch ends every set. The libero wears a
   contrasting jersey: flag as libero, don't cluster as a third team.
6. **Stat definitions live only in `domain/stats.py`,** one function per stat, each with
   table-driven tests that mirror the PRD's definitions table. Hitting % = (K − E) / TA,
   `None` when TA = 0 (UI shows "—"), displayed as `.312` / `-.083`. Total blocks =
   BS + 0.5 × BA. Points = K + SA + BS + 0.5 × BA.
7. **Rally grammar lives in `domain/rules.py`:** every rally starts with a serve; max 3
   contacts per side; a block touch is not one of the 3; possession flips when the ball
   crosses the net. The `touches` stage decodes classifier output under these rules.

## Frontend rules

- TypeScript strict. Function components. Viewer state in Zustand (`src/viewer/store.ts`);
  server data via TanStack Query. Styling with Tailwind.
- Never hand-write API types; they come from `src/api/` (generated).
- The UI never computes stats; it renders what the engine returns.
- Seeking: set `video.currentTime`, then act on the `seeked` event. Overlays sync with
  `requestVideoFrameCallback` using `metadata.mediaTime`, not `currentTime`.
- Every stat cell, event row and highlight must be clickable and seek to its moment
  (event time minus the 3 s pre-roll).

## Engine rules

- Python 3.12, full type hints, ruff (line length 100), mypy strict on `sideout/`.
- Data crossing module boundaries: pydantic v2 models or frozen dataclasses, not dicts.
- Comment numpy shapes where arrays are created or returned: `# (T, 17, 3) keypoints xyc`.
- OpenCV frames are BGR; models take RGB. Convert only in `media/frames.py`.
- Inference uses ONNX Runtime only (CUDA / DirectML / CoreML providers). No `torch` import
  anywhere under `engine/` — it would bloat the shipped app. Training code goes in `training/`.
- Load models through `models/registry.py` by name + version; weights are verified by checksum.
- The engine makes no network calls at runtime unless a feature is explicitly opt-in.
- DB schema changes need a migration in `store/migrations/`.

## Licensing (checked by `make licenses`)

Only MIT, BSD, Apache-2.0, ISC, or LGPL (FFmpeg, dynamically linked) dependencies and model
weights. Do NOT add Ultralytics/YOLO packages or any AGPL/GPL code or weights. Check a
dataset's terms before using it to train shipped weights (e.g. VNL-STES is research data).

## Privacy and safety (hard rules)

- No face recognition, and no model or code that outputs a person's race, ethnicity or other
  protected attribute. Appearance words from a user's description (hair, skin tone, clothing)
  go only to image-text similarity scoring against player crops.
- Identities are per video. Do not persist embeddings across projects.
- Never log description text, frames or crops. Telemetry (opt-in) never includes media.
- Never commit videos, frames, crops, labels or weights. Test media comes only from
  `engine/tests/fixtures/` (synthetic or licensed clips).
- "Delete project" must remove proxy, crops, tracks, events and saved corrections.

## Testing expectations

- Domain code (stats, rules, outcome logic): unit tests for every rule, including edge cases
  (TA = 0, block assist with 3 blockers, overpass, ace touched by receiver, antenna).
- Stage changes: run `uv run pytest -m golden` and include the `make eval SPLIT=dev` report
  diff in the PR description. CI blocks any metric drop > 2 points.
- Performance: `make bench` must not regress any stage's throughput by more than 10%.
- Budgets to protect: 1 h Tier A match in ≤ 15 min on the reference GPU laptop, first rally
  timestamps ≤ 2 min, seek ≤ 300 ms, peak RAM ≤ 4 GB.

## Adding a new event type or stat

Touch all of these in one change: `domain/events.py` (enum) → `domain/stats.py` + tests →
`api/schemas.py` → `pnpm -C app gen:api` → UI label/color map in `app/src/events/labels.ts`
→ highlight weight in `stages/highlights.py` → `docs/PRD.md` definitions table.

## Ask before

- Changing any stat definition, the rally grammar, or the time/coordinate conventions.
- Adding a dependency or model (state its license).
- Changing the DB schema or the stage output format.
- Anything that sends data off the machine.
