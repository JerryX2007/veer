# Volleyball rally tagger & technique analyzer

A personal project: tag rallies in your own match footage, export highlight
reels, and (phase 2) run pose estimation on your serve/attack clips to track
technique metrics like jump height and arm angle over time.

## How it's organized

- `backend/` — FastAPI + SQLite. Handles video upload, rally tagging, clip
  export (ffmpeg), and highlight reel concatenation.
- `frontend/` — React + Vite. Upload a match, scrub through it, mark rally
  start/end points, tag an outcome, and export clips.

The `data/` directory (uploaded videos and exported clips) and the SQLite
file are created automatically on first run and are git-ignored.

## Requirements

- Python 3.10+
- Node 18+
- [ffmpeg](https://ffmpeg.org/) installed and on your PATH
  (`brew install ffmpeg` on macOS, `apt install ffmpeg` on Ubuntu/Debian)

## Running it

**Backend**

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/uvicorn app.main:app --reload
```

The API is now at `http://localhost:8000` — interactive docs at
`http://localhost:8000/docs`.

**Frontend** (separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`).

## Using it

1. Upload a match video with a title.
2. Click it to open the tagger. Play the video, click **Mark rally start**
   at the beginning of a rally, then click the outcome (kill, ace, error...)
   once the rally ends — that saves the tagged time range.
3. Click **Export clip** on any tagged rally to cut it out with ffmpeg.
4. Once you've exported a few clips, `POST /matches/{id}/highlight-reel/`
   with `{"outcomes": ["kill", "ace"]}` (via the `/docs` page, or a frontend
   button once you add one) to concatenate them into one reel.

## Roadmap

This scaffold covers **phase 1** — the reliable, demoable core: upload, tag,
export, highlight reel. It's fully working end to end.

**Phase 2** (not yet implemented — see `backend/app/services/pose.py` for
the plan): run MediaPipe Pose on clips already tagged `serve` or `attack`
(never a whole match — that's what keeps this tractable), extract a couple
of concrete metrics (jump height, arm angle at contact), and store them
against each rally via the `Metric` model, which already exists.

**Phase 3**: a trends view charting those metrics over time, and optionally
a skeleton overlay rendered on top of the clip.

## Data model

- `Match` — one uploaded video
- `Rally` — a tagged time range within a match, with an outcome and,
  once exported, a `clip_path`
- `Metric` — a named value attached to a rally (populated in phase 2)
