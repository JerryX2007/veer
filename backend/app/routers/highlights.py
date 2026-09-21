from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services.video import concatenate_clips

router = APIRouter(prefix="/matches/{match_id}/highlight-reel", tags=["highlights"])


@router.post("/", response_model=schemas.HighlightReelOut)
def build_highlight_reel(
    match_id: int, request: schemas.HighlightReelRequest, db: Session = Depends(get_db)
):
    """Concatenate every already-exported clip whose outcome is in the request list."""
    rallies = (
        db.query(models.Rally)
        .filter(models.Rally.match_id == match_id, models.Rally.outcome.in_(request.outcomes))
        .filter(models.Rally.clip_path.isnot(None))
        .all()
    )
    if not rallies:
        raise HTTPException(
            status_code=400,
            detail="No exported clips match those outcomes — export clips for those rallies first.",
        )

    clip_paths = [r.clip_path for r in rallies]
    output_name = f"match{match_id}_highlights.mp4"
    reel_path = concatenate_clips(clip_paths, output_name)
    return {"reel_path": reel_path, "clip_count": len(clip_paths)}
