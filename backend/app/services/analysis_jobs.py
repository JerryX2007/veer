"""Running highlight detection in the background and storing the results.

Analysing a full match takes minutes, so the API starts a run and returns
immediately; the frontend polls the run's status and progress.
"""

import time
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from .. import models
from ..analysis import AnalysisConfig, analyze_video
from ..analysis.highlights import Highlight
from ..analysis.rallies import Rally
from ..analysis.reel import Reel, build_reel

ACTIVE_STATUSES = ("pending", "running")
PROGRESS_INTERVAL_S = 1.0


def run_analysis(run_id: int, session_factory: sessionmaker) -> None:
    db: Session = session_factory()
    run = db.get(models.AnalysisRun, run_id)
    if run is None:
        db.close()
        return
    try:
        run.status = "running"
        db.commit()

        last_saved = 0.0

        def progress(fraction: float) -> None:
            nonlocal last_saved
            if time.monotonic() - last_saved >= PROGRESS_INTERVAL_S:
                run.progress = round(fraction, 3)
                db.commit()
                last_saved = time.monotonic()

        config = AnalysisConfig.from_overrides(run.settings)
        result = analyze_video(run.match.video_path, config, progress)

        for rally in result.rallies:
            row = models.DetectedRally(
                index=rally.index,
                start_time=rally.start,
                end_time=rally.end,
                serve_time=rally.serve_time,
            )
            row.highlights = [
                models.DetectedHighlight(
                    kind=h.kind, time=h.time, score=h.score,
                    description=h.description, details=h.details,
                )
                for h in result.highlights
                if h.rally_index == rally.index
            ]
            run.rallies.append(row)
        run.diagnostics = result.diagnostics
        run.status = "done"
        run.progress = 1.0
    except Exception as e:  # surfaced to the user via the run's status
        db.rollback()
        run = db.get(models.AnalysisRun, run_id)
        run.status = "failed"
        run.error = f"{type(e).__name__}: {e}"
    finally:
        run.finished_at = datetime.utcnow()
        db.commit()
        db.close()


def reel_for_run(run: models.AnalysisRun) -> Reel:
    """Build the reel from the stored rallies and whichever highlights remain."""
    rallies, highlights = [], []
    for row in run.rallies:
        rallies.append(Rally(
            index=row.index, start=row.start_time, end=row.end_time,
            play_start=row.start_time, play_end=row.end_time, serve_time=row.serve_time,
        ))
        highlights += [
            Highlight(kind=h.kind, time=h.time, score=h.score, rally_index=row.index, description=h.description)
            for h in row.highlights
        ]
    min_score = AnalysisConfig.from_overrides(run.settings).reel_min_score
    return build_reel(rallies, highlights, min_score)


def mark_interrupted_runs(db: Session) -> None:
    """Runs still 'running' at startup died with the previous server process."""
    for run in db.query(models.AnalysisRun).filter(models.AnalysisRun.status.in_(ACTIVE_STATUSES)):
        run.status = "failed"
        run.error = "Interrupted: the server restarted during analysis. Start it again."
        run.finished_at = datetime.utcnow()
    db.commit()
