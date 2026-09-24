# Volleyball rally tagger & technique analyzer

A personal project: tag rallies in your own match footage, export highlight
reels, automatically find highlight rallies (big kills, great saves,
shutdown blocks, crowd reactions, long rallies), and (phase 2) run pose
estimation on your serve/attack clips to track technique metrics like jump
height and arm angle over time.

## How it's organized

- `backend/` — FastAPI + SQLite. Handles video upload, rally tagging, clip
  export (ffmpeg), and highlight reel concatenation.
- `backend/app/analysis/` — automatic rally and highlight detection. Plain
  Python + NumPy/OpenCV with no web or database code, so it also runs from
  the command line.
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

### Automatic highlights

Under the video, click **Detect highlights**. The match is analysed in the
background (a few minutes per hour of footage). You get:

- **Highlights as timestamps**, grouped by rally: click a time to jump to
  the moment, **▶ Rally** to watch it from the serve, or **✕** to reject a
  false positive.
- **A highlight reel**: every rally with a highlight, from the serve to the
  end of the rally, in match order. It's a list of timestamps, not new
  video files. **▶ Play reel** plays it by jumping through the original
  video, **Timestamps (text)** gives a copy-pasteable list, and **Render
  reel to MP4** makes one file if you want to share it.

What it looks for:

| Highlight | How it's spotted |
| --- | --- |
| Big kill | A hard attack hits the floor and the ball rebounds high (default ≥ 3 m) |
| Great save | A hard-driven ball (≥ 10 m/s) is dug back up and play continues |
| Shutdown block | A fast attack is sent back at the net and the rally dies on the attacker's side |
| Crowd reaction | The crowd gets ≥ 6 dB louder than usual right after the rally |
| Long rally | Play lasts ≥ 18 s |

Same thing from the command line, handy for tuning:

```bash
cd backend
./venv/bin/python -m app.analysis path/to/match.mp4 --set net_x=0.45 --json result.json
```

API (also on the `/docs` page), all under `/matches/{id}/analysis`:
`POST /` starts a run (optional `{"settings": {...}}` overrides),
`GET /` gives status/progress and then rallies, highlights and the reel,
`GET /reel` gives just the reel, `DELETE /highlights/{hid}` rejects one,
`GET /evaluation` scores detection against your hand-tagged rallies, and
`POST /reel/render` renders the mp4.

#### How it works

1. **Ball tracking**: small, round, fast-moving blobs are found by frame
   differencing and linked into a trajectory. Heads and hands are dropped
   because they don't move fast for long.
2. **Contacts**: any moment the ball changes direction more sharply than
   gravity allows (a hand, a block, the floor).
3. **Scale**: the ball always falls at 9.81 m/s², so fitting parabolas to
   its flights tells us how many pixels a metre is. That lets thresholds be
   in metres and m/s whatever the camera zoom.
4. **Rallies**: stretches of continuous ball movement. Each starts ~1 s
   before the serve (the hit that first sends the ball over the net) and
   ends after the ball goes dead, stretched to include the referee's
   whistle.
5. **Highlights**: each detector reads the rally's contacts (e.g. a big
   kill is a steep, fast landing nobody plays on from, followed by a high
   rebound), and the crowd's loudness adds a score boost.

#### Tuning it on your footage

The defaults assume a **roughly side-on camera** with the net running
vertically through the frame. Tell it where the net is with `net_x`
(0 = left edge, 1 = right, default 0.5), and optionally the net tape
height with `net_top_y` so balls hit into the net aren't mistaken for
blocks. Every threshold lives in `backend/app/analysis/config.py`.

The best way to tune is to tag a match's rallies by hand, run detection,
and check `GET /matches/{id}/analysis/evaluation`: it reports how many of
your rallies were found and how far off the start/end times are.

Known limits of this first version: the ball tracker is classic computer
vision, so shaky handheld footage, busy backgrounds or a far-away camera
will hurt it. When it can barely see the ball, rallies fall back to overall
on-screen motion and only crowd-reaction and long-rally highlights work.
The tracker sits behind a small interface (`ball.py` → `Trajectory`) so a
learned ball detector can replace it without touching anything downstream.

## Tests

```bash
cd backend
./venv/bin/pip install -r requirements-dev.txt
./venv/bin/python -m pytest
```

The tests generate a synthetic side-on match (ballistic ball, wandering
players, whistles, crowd noise) with a scripted big kill, great save,
shutdown block and crowd reaction, and check the whole pipeline and API
against it. `python -m tests.synthetic out.mp4` writes it out if you want
to look at it.

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
- `AnalysisRun` — one automatic-detection pass over a match (status,
  progress, settings, diagnostics)
- `DetectedRally` / `DetectedHighlight` — what that run found; the reel is
  built from whichever highlights you haven't rejected
