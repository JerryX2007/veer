import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..media import pipeline
from ..media.ffmpeg import FFmpegError
from ..models import Match
from ..schemas import MatchOut

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("", response_model=MatchOut, status_code=201)
def upload_match(
    file: UploadFile = File(..., description="Raw match footage"),
    title: str = Form(...),
    played_on: str | None = Form(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db),
):
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    # Stream to disk in chunks; match footage is easily several GB.
    with tempfile.NamedTemporaryFile(dir=settings.uploads_dir, suffix=".upload", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp, length=8 * 1024 * 1024)
        tmp_path = Path(tmp.name)
    try:
        match = pipeline.ingest_upload(db, tmp_path, file.filename or "upload.mp4", title, played_on)
    except FFmpegError as exc:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(422, f"Not a readable video: {exc}") from exc
    return MatchOut.build(match)


@router.get("", response_model=list[MatchOut])
def list_matches(db: Session = Depends(get_db)):
    return [MatchOut.build(m) for m in db.scalars(select(Match).order_by(Match.played_on.desc(), Match.id.desc()))]


@router.get("/{match_id}", response_model=MatchOut)
def get_match(match_id: int, db: Session = Depends(get_db)):
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(404, "Match not found")
    return MatchOut.build(match)


@router.delete("/{match_id}", status_code=204)
def delete_match(match_id: int, db: Session = Depends(get_db)):
    match = db.get(Match, match_id)
    if match is None:
        raise HTTPException(404, "Match not found")
    for rally in match.rallies:
        pipeline.delete_clip_files(rally.clip)
    Path(match.video_path).unlink(missing_ok=True)
    db.delete(match)
    db.commit()
