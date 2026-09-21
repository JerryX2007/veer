from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services.video import extract_clip

router = APIRouter(prefix="/matches/{match_id}/rallies", tags=["rallies"])


@router.post("/", response_model=schemas.RallyOut)
def create_rally(match_id: int, rally: schemas.RallyCreate, db: Session = Depends(get_db)):
    match = db.query(models.Match).get(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    db_rally = models.Rally(match_id=match_id, **rally.model_dump())
    db.add(db_rally)
    db.commit()
    db.refresh(db_rally)
    return db_rally


@router.get("/", response_model=list[schemas.RallyOut])
def list_rallies(match_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Rally)
        .filter(models.Rally.match_id == match_id)
        .order_by(models.Rally.start_time)
        .all()
    )


@router.post("/{rally_id}/export-clip", response_model=schemas.RallyOut)
def export_clip(match_id: int, rally_id: int, db: Session = Depends(get_db)):
    rally = db.query(models.Rally).get(rally_id)
    if not rally or rally.match_id != match_id:
        raise HTTPException(status_code=404, detail="Rally not found")

    match = db.query(models.Match).get(match_id)
    clip_name = f"match{match_id}_rally{rally_id}.mp4"
    rally.clip_path = extract_clip(
        match.video_path, rally.start_time, rally.end_time, clip_name
    )
    db.commit()
    db.refresh(rally)
    return rally
