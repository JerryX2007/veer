from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services.video import save_upload

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("/", response_model=schemas.MatchOut)
def create_match(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = file.file.read()
    video_path = save_upload(file.filename, content)
    match = models.Match(title=title, video_path=video_path)
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


@router.get("/", response_model=list[schemas.MatchOut])
def list_matches(db: Session = Depends(get_db)):
    return db.query(models.Match).order_by(models.Match.created_at.desc()).all()


@router.get("/{match_id}", response_model=schemas.MatchOut)
def get_match(match_id: int, db: Session = Depends(get_db)):
    match = db.query(models.Match).get(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match
