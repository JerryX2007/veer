from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..media import jobs, pipeline
from ..models import Clip, JobStatus, Reel
from ..schemas import ClipOut, ReelIn, ReelOut

router = APIRouter(tags=["reels"])


@router.post("/reels", response_model=ReelOut, status_code=202)
def export_reel(body: ReelIn, db: Session = Depends(get_db)):
    """Pick clips by tag (e.g. outcomes=["kill"], player="me") or explicit ids, then concatenate them."""
    if body.clip_ids:
        clips = [db.get(Clip, cid) for cid in body.clip_ids]
        missing = [cid for cid, c in zip(body.clip_ids, clips) if c is None or c.status != JobStatus.ready]
        if missing:
            raise HTTPException(422, f"clips not found or not ready: {missing}")
    else:
        clips = pipeline.select_clips(
            db,
            outcomes=[o.value for o in body.outcomes] or None,
            skills=[s.value for s in body.skills] or None,
            match_ids=body.match_ids or None,
            player=body.player,
            highlights_only=body.highlights_only and not body.outcomes,
        )
    if not clips:
        raise HTTPException(422, "No ready clips match those filters")

    reel = Reel(title=body.title, filters=body.model_dump(mode="json", exclude={"title"}),
                clip_ids=[c.id for c in clips])
    db.add(reel)
    db.commit()
    jobs.submit(pipeline.render_reel, reel.id)
    db.refresh(reel)
    return ReelOut.build(reel)


@router.get("/reels", response_model=list[ReelOut])
def list_reels(db: Session = Depends(get_db)):
    return [ReelOut.build(r) for r in db.scalars(select(Reel).order_by(Reel.id.desc()))]


@router.get("/reels/{reel_id}", response_model=ReelOut)
def get_reel(reel_id: int, db: Session = Depends(get_db)):
    reel = db.get(Reel, reel_id)
    if reel is None:
        raise HTTPException(404, "Reel not found")
    return ReelOut.build(reel)


@router.get("/reels/{reel_id}/download")
def download_reel(reel_id: int, db: Session = Depends(get_db)):
    reel = db.get(Reel, reel_id)
    if reel is None:
        raise HTTPException(404, "Reel not found")
    if reel.status != JobStatus.ready or not reel.path:
        raise HTTPException(409, f"Reel is {reel.status.value}")
    safe = "".join(ch if ch.isalnum() or ch in "-_ " else "_" for ch in reel.title).strip() or "reel"
    return FileResponse(reel.path, media_type="video/mp4", filename=f"{safe}.mp4")


@router.delete("/reels/{reel_id}", status_code=204)
def delete_reel(reel_id: int, db: Session = Depends(get_db)):
    reel = db.get(Reel, reel_id)
    if reel is None:
        raise HTTPException(404, "Reel not found")
    if reel.path:
        Path(reel.path).unlink(missing_ok=True)
    db.delete(reel)
    db.commit()


@router.get("/pipeline/pose-queue", response_model=list[ClipOut], tags=["pipeline"])
def pose_queue(limit: int = 50, db: Session = Depends(get_db)):
    """Serve/attack clips ready for pose estimation (Phase 2 consumes this)."""
    return [ClipOut.build(c) for c in pipeline.pose_queue(db, limit)]
