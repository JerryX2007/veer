# Veer — volleyball VOD analyzer

Local web app: upload match footage, tag rallies (clips are cut automatically), detect rallies and
highlights automatically, click any timestamp to jump the video there, and export highlight reels.
Single user, runs on your own machine. `PRD.md` is the long-term product spec (box score, player
tracking, "describe a player"); this code is its early phase. Read the relevant PRD section before
building a new feature, and check the "Where the code is vs the PRD" list below.

## Layout

```
backend/                FastAPI + SQLAlchemy 2 + SQLite (Python 3.10+)
  app/main.py           app factory, lifespan (checks ffmpeg, creates dirs, init DB), /media static mount
  app/config.py         Settings (pydantic-settings); every field overridable via VB_* env vars
  app/db.py             DeclarativeBase, init_engine(), get_db()
  app/models.py         Match, Rally, Clip, Reel (manual path) + AnalysisRun, DetectedRally, DetectedHighlight
  app/schemas.py        all request/response models; media_url() turns stored paths into /media/... URLs
  app/routers/          matches, rallies, reels (+ /pipeline/pose-queue), analysis (/matches/{id}/analysis/)
  app/media/            ffmpeg wrappers, clipper (cut/concat/render_segments), pipeline stages, jobs (thread pool)
  app/analysis/         automatic detection: pure Python + NumPy/OpenCV, no web/DB imports; CLI via -m app.analysis
  app/services/         analysis_jobs.py (runs detection, stores results); video.py is legacy, unused
  tests/                pytest; synthetic.py renders a fake match with scripted highlights
frontend/               React 18 + Vite, plain JS, no router/state library
  src/api.js            every backend call; API_BASE = http://localhost:8000
  src/components/       UploadMatch, RallyTagger (video + manual tagging), AutoHighlights
```

## Commands

- Backend setup: `cd backend && python3 -m venv venv && ./venv/bin/pip install -r requirements-dev.txt`
- Run backend: `cd backend && ./venv/bin/uvicorn app.main:app --reload` (API docs at :8000/docs)
- Run frontend: `cd frontend && npm install && npm run dev` (http://localhost:5173)
- Tests: `cd backend && ./venv/bin/python -m pytest -q` (≈40 s; needs ffmpeg on PATH)
- Frontend check: `cd frontend && npm run build` (there are no frontend tests or linter yet)
- Tune detection on real footage: `./venv/bin/python -m app.analysis match.mp4 --set net_x=0.45 --json out.json`

Before saying a change is done, run the backend tests and `npm run build` if you touched the frontend.

## How it works

Two paths share one Match and its video:

1. **Manual:** `POST /matches/{id}/rallies` → `pipeline.prepare_clip` → `jobs.submit(process_rally)` cuts a
   padded clip + thumbnail. Clips tagged serve/attack get `pose_status=queued` (Phase 2 hook).
   `POST /reels` concatenates ready clips picked by filters.
2. **Automatic:** `POST /matches/{id}/analysis/` starts a background run (`services/analysis_jobs.run_analysis`)
   → `analysis.analyze_video` → DetectedRally/DetectedHighlight rows. The reel is computed on read from
   whichever highlights haven't been rejected; `POST .../reel/render` makes an MP4 in `media/reels/`.

## Conventions and gotchas

- Times are seconds into the uploaded video, as floats. Manual rallies use `start`/`end`;
  detected rallies use `start_time`/`end_time`/`serve_time`. Don't mix them up.
- Files live under `settings.media_root` (default `backend/data/media/`) and are served at `/media/...`.
  Store absolute/relative file paths in the DB; send URLs to the frontend via `schemas.media_url()`.
- Every clip is re-encoded to one house format (`media/clipper.py`) so reels can stream-copy. Use
  `clipper.cut_clip` / `concat_reel` / `render_segments`; don't shell out to ffmpeg elsewhere.
- `app/analysis/` must stay free of FastAPI/SQLAlchemy imports. The ball tracker sits behind
  `analysis/ball.py` → `Trajectory`, so a learned detector can replace it without touching downstream code.
- Detection thresholds live only in `analysis/config.py` (`AnalysisConfig`); expose new ones there.
- Two response models are named for reels: `ReelOut` (rendered manual reel) and `AutoReelOut`
  (analysis reel as timestamps). Keep them separate.
- No migrations yet: tables come from `Base.metadata.create_all`. After changing a model, delete
  `backend/data/volleyball.db` locally (or add Alembic if data must be kept).
- Tests set `VB_SYNC_JOBS=true` so jobs run inline, and use a temp media root/DB (`tests/conftest.py`).
  Test media is generated (ffmpeg test patterns, `tests/synthetic.py`); never commit real footage.
- When adding an endpoint, add its call to `frontend/src/api.js` and keep field names in sync by hand.

## Where the code is vs the PRD

- Done: upload, video viewer, clickable timestamps, rally detection, highlight detection, reels.
- Not started: learned ball tracking (VballNet), player tracking/jersey OCR, describe-a-player,
  touch/action classification, box score (kills, hitting %, digs…), review queue, desktop packaging.
- The PRD's stat definitions are the spec for any stats code: hitting % = (K − E) / TA, shown as `.312`,
  `None`/"—" when TA = 0. Put stat logic in one module, computed from events, with table-driven tests.

## Rules

- Licensing: only MIT/BSD/Apache-2.0/ISC (or LGPL ffmpeg) dependencies and model weights. No Ultralytics
  YOLO or other AGPL/GPL code or weights. State a new dependency's license when adding it.
- Privacy: no face recognition, and nothing that outputs a person's race or ethnicity. Footage stays
  local; the backend makes no outbound network calls.
- Ask before: changing the DB schema in a way that loses data, adding a dependency or model,
  or changing API field names the frontend relies on.
