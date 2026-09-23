from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from .. import database, models, schemas
from ..analysis import AnalysisConfig
from ..analysis.evaluate import evaluate_rallies
from ..analysis.reel import reel_to_text
from ..database import get_db
from ..services.analysis_jobs import ACTIVE_STATUSES, reel_for_run, run_analysis
from ..services.video import render_segments

router = APIRouter(prefix="/matches/{match_id}/analysis", tags=["analysis"])


def _latest_run(match_id: int, db: Session) -> models.AnalysisRun:
    run = (
        db.query(models.AnalysisRun)
        .filter(models.AnalysisRun.match_id == match_id)
        .order_by(models.AnalysisRun.id.desc())
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="This match hasn't been analysed yet")
    return run


def _finished_run(match_id: int, db: Session) -> models.AnalysisRun:
    run = _latest_run(match_id, db)
    if run.status != "done":
        raise HTTPException(status_code=409, detail=f"Analysis is {run.status}, not finished")
    return run


def _reel_out(run: models.AnalysisRun) -> dict:
    reel = reel_for_run(run)
    return {**reel.to_dict(), "text": reel_to_text(reel)}


@router.post("/", response_model=schemas.AnalysisRunOut, status_code=202)
def start_analysis(
    match_id: int,
    background: BackgroundTasks,
    request: schemas.AnalysisRequest = schemas.AnalysisRequest(),
    db: Session = Depends(get_db),
):
    """Detect rallies and highlights in the match video, in the background.

    Poll GET /matches/{id}/analysis for progress and results.
    """
    match = db.get(models.Match, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    try:
        AnalysisConfig.from_overrides(request.settings)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    active = (
        db.query(models.AnalysisRun)
        .filter(models.AnalysisRun.match_id == match_id, models.AnalysisRun.status.in_(ACTIVE_STATUSES))
        .first()
    )
    if active:
        raise HTTPException(status_code=409, detail="An analysis of this match is already running")

    run = models.AnalysisRun(match_id=match_id, settings=request.settings)
    db.add(run)
    db.commit()
    db.refresh(run)
    background.add_task(run_analysis, run.id, database.SessionLocal)
    return run


@router.get("/", response_model=schemas.AnalysisOut)
def get_analysis(match_id: int, db: Session = Depends(get_db)):
    """The latest run: status and progress, then rallies, highlights and the reel once done."""
    run = _latest_run(match_id, db)
    out = schemas.AnalysisOut.model_validate(run)
    if run.status == "done":
        out.reel = schemas.ReelOut(**_reel_out(run))
    return out


@router.get("/reel", response_model=schemas.ReelOut)
def get_reel(match_id: int, db: Session = Depends(get_db)):
    """The highlight reel as timestamps: one serve-to-end segment per highlighted rally."""
    return _reel_out(_finished_run(match_id, db))


@router.delete("/highlights/{highlight_id}", status_code=204)
def delete_highlight(match_id: int, highlight_id: int, db: Session = Depends(get_db)):
    """Reject a false positive. Its rally drops out of the reel if nothing else is left in it."""
    highlight = db.get(models.DetectedHighlight, highlight_id)
    if not highlight or highlight.rally.run.match_id != match_id:
        raise HTTPException(status_code=404, detail="Highlight not found")
    db.delete(highlight)
    db.commit()
    return Response(status_code=204)


@router.get("/evaluation", response_model=schemas.RallyEvaluationOut)
def evaluate(match_id: int, db: Session = Depends(get_db)):
    """Compare detected rallies with the rallies you tagged by hand for this match."""
    run = _finished_run(match_id, db)
    tagged = db.query(models.Rally).filter(models.Rally.match_id == match_id).all()
    if not tagged:
        raise HTTPException(status_code=400, detail="Tag some rallies by hand first to compare against")
    return evaluate_rallies(
        [(r.start_time, r.end_time) for r in run.rallies],
        [(r.start_time, r.end_time) for r in tagged],
    )


@router.post("/reel/render", response_model=schemas.RenderedReelOut)
def render_reel(match_id: int, db: Session = Depends(get_db)):
    """Render the reel into a single mp4 (optional: the timestamps alone are enough to play it)."""
    run = _finished_run(match_id, db)
    reel = reel_for_run(run)
    if not reel.segments:
        raise HTTPException(status_code=400, detail="No highlights to put in a reel")
    path = render_segments(
        run.match.video_path,
        [(s.start, s.end) for s in reel.segments],
        f"match{match_id}_auto_highlights.mp4",
    )
    return {"reel_path": path, "segment_count": len(reel.segments), "duration": round(reel.duration, 2)}
