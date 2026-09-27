from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..media import jobs, pipeline
from ..models import Match, PoseStatus, Rally
from ..schemas import RallyIn, RallyOut, RallyPatch

router = APIRouter(tags=["rallies"])

# Allow a little slack past the probed duration (container durations are approximate).
_END_SLACK = 0.5


def _check_bounds(match: Match, start: float, end: float) -> None:
    if end <= start:
        raise HTTPException(422, "end must be after start")
    if start >= match.duration or end > match.duration + _END_SLACK:
        raise HTTPException(422, f"rally {start}-{end}s is outside the video (duration {match.duration:.2f}s)")


def _get_rally(db: Session, rally_id: int) -> Rally:
    rally = db.get(Rally, rally_id)
    if rally is None:
        raise HTTPException(404, "Rally not found")
    return rally


@router.post("/matches/{match_id}/rallies", response_model=RallyOut, status_code=201)
def tag_rally(match_id: int, body: RallyIn, db: Session = Depends(get_db)):
    """Tag a rally. Its clip is cut in the background; poll the rally until clip.status == 'ready'."""
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(404, "Match not found")
    _check_bounds(match, body.start, body.end)
    rally = Rally(match=match, start=body.start, end=body.end, outcome=body.outcome,
                  skills=[s.value for s in body.skills], player=body.player, notes=body.notes)
    db.add(rally)
    db.commit()
    pipeline.prepare_clip(db, rally)
    jobs.submit(pipeline.process_rally, rally.id)
    db.refresh(rally)
    return RallyOut.build(rally)


@router.get("/matches/{match_id}/rallies", response_model=list[RallyOut])
def list_rallies(match_id: int, db: Session = Depends(get_db)):
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(404, "Match not found")
    return [RallyOut.build(r) for r in match.rallies]


@router.get("/rallies/{rally_id}", response_model=RallyOut)
def get_rally(rally_id: int, db: Session = Depends(get_db)):
    return RallyOut.build(_get_rally(db, rally_id))


@router.patch("/rallies/{rally_id}", response_model=RallyOut)
def update_rally(rally_id: int, body: RallyPatch, db: Session = Depends(get_db)):
    """Edit tags. Changing start/end re-cuts the clip; changing skills re-evaluates the pose queue."""
    rally = _get_rally(db, rally_id)
    data = body.model_dump(exclude_unset=True)
    new_start, new_end = data.get("start", rally.start), data.get("end", rally.end)
    _check_bounds(rally.match, new_start, new_end)
    times_changed = (new_start, new_end) != (rally.start, rally.end)

    for key, value in data.items():
        setattr(rally, key, [s.value for s in value] if key == "skills" else value)
    db.commit()

    if times_changed or rally.clip is None:
        pipeline.prepare_clip(db, rally)
        jobs.submit(pipeline.process_rally, rally.id)
    elif "skills" in data and rally.clip.pose_status in (PoseStatus.not_applicable, PoseStatus.queued):
        rally.clip.pose_status = PoseStatus.queued if rally.wants_pose else PoseStatus.not_applicable
        db.commit()
    db.refresh(rally)
    return RallyOut.build(rally)


@router.post("/rallies/{rally_id}/reclip", response_model=RallyOut, status_code=202)
def reclip(rally_id: int, db: Session = Depends(get_db)):
    """Re-run clip cutting (e.g. after a failure or a padding change)."""
    rally = _get_rally(db, rally_id)
    pipeline.prepare_clip(db, rally)
    jobs.submit(pipeline.process_rally, rally.id)
    db.refresh(rally)
    return RallyOut.build(rally)


@router.delete("/rallies/{rally_id}", status_code=204)
def delete_rally(rally_id: int, db: Session = Depends(get_db)):
    rally = _get_rally(db, rally_id)
    pipeline.delete_clip_files(rally.clip)
    db.delete(rally)
    db.commit()
