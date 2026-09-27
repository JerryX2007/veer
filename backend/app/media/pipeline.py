"""Pipeline stages, following the plan's diagram:

    Video upload ──► Rally tagger ──┬─► Highlight clips ─► Highlight reel export   (teal)
                                    └─► Serve/attack clips ─► Pose ─► Metrics      (purple)

Every tagged rally gets a clip (`process_rally`). Clips whose rally is tagged serve/attack are marked
`pose_status=queued`, which is the hand-off point for Phase 2: the pose stage only ever reads clips from
that queue, so it never has to process a whole match.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models import Clip, JobStatus, Match, PoseStatus, Rally, Reel
from . import clipper, ffmpeg

log = logging.getLogger(__name__)


# ---------- stage 1: upload -------------------------------------------------------------------------------

def ingest_upload(db: Session, tmp_file: Path, original_filename: str, title: str, played_on: str | None) -> Match:
    """Probe the uploaded file and register it as a Match. Raises FFmpegError if it isn't a readable video."""
    info = ffmpeg.probe(tmp_file)
    match = Match(
        title=title, played_on=played_on, original_filename=original_filename, video_path="",
        duration=info.duration, width=info.width, height=info.height, fps=info.fps, has_audio=info.has_audio,
    )
    db.add(match)
    db.flush()  # assigns match.id
    suffix = Path(original_filename).suffix.lower() or ".mp4"
    dest = settings.uploads_dir / f"match_{match.id}{suffix}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp_file), dest)
    match.video_path = str(dest)
    db.commit()
    return match


# ---------- stage 2 → clips -------------------------------------------------------------------------------

def prepare_clip(db: Session, rally: Rally) -> Clip:
    """Create or reset the Clip row for a rally (called whenever a rally is created or its times change)."""
    window = clipper.padded_window(rally.start, rally.end, rally.match.duration)
    clip = rally.clip or Clip(rally=rally)
    clip.status = JobStatus.pending
    clip.error = None
    clip.source_start, clip.source_end = window.start, window.end
    clip.pose_status = PoseStatus.queued if rally.wants_pose else PoseStatus.not_applicable
    db.add(clip)
    db.commit()
    return clip


def process_rally(rally_id: int) -> None:
    """Background job: cut the rally's clip and a thumbnail. Safe to re-run."""
    with SessionLocal() as db:
        rally = db.get(Rally, rally_id)
        if rally is None or rally.clip is None:
            return
        clip = rally.clip
        clip.status = JobStatus.processing
        db.commit()
        try:
            window = clipper.Window(clip.source_start, clip.source_end)
            out = settings.clips_dir / f"match_{rally.match_id}" / f"rally_{rally.id}.mp4"
            clipper.cut_clip(Path(rally.match.video_path), window, out, source_has_audio=rally.match.has_audio)
            # Thumbnail at the middle of the actual rally, not the padding.
            mid = (rally.start + rally.end) / 2 - window.start
            thumb = settings.thumbs_dir / f"rally_{rally.id}.jpg"
            clipper.thumbnail(out, mid, thumb)
            clip.path, clip.thumbnail_path = str(out), str(thumb)
            clip.duration = ffmpeg.probe(out).duration
            clip.status = JobStatus.ready
        except Exception as exc:  # noqa: BLE001 — record any failure on the row for the UI
            log.exception("clip for rally %s failed", rally_id)
            clip.status, clip.error = JobStatus.failed, str(exc)[:2000]
        db.commit()


def delete_clip_files(clip: Clip | None) -> None:
    if clip is None:
        return
    for p in (clip.path, clip.thumbnail_path):
        if p:
            Path(p).unlink(missing_ok=True)


# ---------- teal path: highlight reel ---------------------------------------------------------------------

def select_clips(db: Session, *, outcomes: list[str] | None = None, skills: list[str] | None = None,
                 match_ids: list[int] | None = None, player: str | None = None,
                 highlights_only: bool = False) -> list[Clip]:
    """Ready clips matching the filters, in match date then video-time order."""
    q = (select(Clip).join(Clip.rally).join(Rally.match)
         .where(Clip.status == JobStatus.ready)
         .order_by(Match.played_on, Match.id, Rally.start))
    if match_ids:
        q = q.where(Rally.match_id.in_(match_ids))
    if outcomes:
        q = q.where(Rally.outcome.in_(outcomes))
    if player:
        q = q.where(Rally.player == player)
    clips = list(db.scalars(q))
    if highlights_only:
        clips = [c for c in clips if c.rally.is_highlight]
    if skills:  # JSON list column: filter in Python, it's small
        wanted = set(skills)
        clips = [c for c in clips if wanted & set(c.rally.skills or [])]
    return clips


def render_reel(reel_id: int) -> None:
    """Background job: concatenate the reel's clips with ffmpeg."""
    with SessionLocal() as db:
        reel = db.get(Reel, reel_id)
        if reel is None:
            return
        reel.status = JobStatus.processing
        db.commit()
        try:
            clips = [db.get(Clip, cid) for cid in reel.clip_ids]
            paths = [Path(c.path) for c in clips if c is not None and c.path and Path(c.path).exists()]
            if not paths:
                raise ValueError("none of the reel's clips are available")
            out = settings.reels_dir / f"reel_{reel.id}.mp4"
            clipper.concat_reel(paths, out)
            reel.path = str(out)
            reel.duration = ffmpeg.probe(out).duration
            reel.status = JobStatus.ready
        except Exception as exc:  # noqa: BLE001
            log.exception("reel %s failed", reel_id)
            reel.status, reel.error = JobStatus.failed, str(exc)[:2000]
        db.commit()


# ---------- purple path: pose queue (Phase 2 plugs in here) -----------------------------------------------

def pose_queue(db: Session, limit: int = 50) -> list[Clip]:
    """Clips waiting for pose estimation: ready serve/attack clips only."""
    q = (select(Clip).where(Clip.status == JobStatus.ready, Clip.pose_status == PoseStatus.queued)
         .order_by(Clip.id).limit(limit))
    return list(db.scalars(q))
