from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import settings
from .models import JobStatus, Outcome, PoseStatus, Skill


def media_url(path: str | None) -> str | None:
    """Turn a stored file path into the URL it's served at (/media/...)."""
    if not path:
        return None
    try:
        rel = Path(path).resolve().relative_to(settings.media_root.resolve())
    except ValueError:
        return None
    return f"/media/{rel.as_posix()}"


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    played_on: str | None
    original_filename: str
    duration: float
    width: int
    height: int
    fps: float
    has_audio: bool
    created_at: datetime
    video_url: str | None = None

    @classmethod
    def build(cls, m) -> MatchOut:
        out = cls.model_validate(m)
        out.video_url = media_url(m.video_path)
        return out


class RallyIn(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(gt=0)
    outcome: Outcome
    skills: list[Skill] = []
    player: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _order(self):
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class RallyPatch(BaseModel):
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, gt=0)
    outcome: Outcome | None = None
    skills: list[Skill] | None = None
    player: str | None = None
    notes: str | None = None


class ClipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: JobStatus
    error: str | None
    source_start: float
    source_end: float
    duration: float | None
    pose_status: PoseStatus
    url: str | None = None
    thumbnail_url: str | None = None

    @classmethod
    def build(cls, c) -> ClipOut:
        out = cls.model_validate(c)
        out.url, out.thumbnail_url = media_url(c.path), media_url(c.thumbnail_path)
        return out


class RallyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    match_id: int
    start: float
    end: float
    outcome: Outcome
    skills: list[str]
    player: str | None
    notes: str | None
    is_highlight: bool
    clip: ClipOut | None = None

    @classmethod
    def build(cls, r) -> RallyOut:
        return cls(
            id=r.id, match_id=r.match_id, start=r.start, end=r.end, outcome=r.outcome, skills=r.skills or [],
            player=r.player, notes=r.notes, is_highlight=r.is_highlight,
            clip=ClipOut.build(r.clip) if r.clip else None,
        )


class ReelIn(BaseModel):
    title: str = "Highlight reel"
    outcomes: list[Outcome] = []
    skills: list[Skill] = []
    match_ids: list[int] = []
    player: str | None = None
    highlights_only: bool = Field(
        default=False, description="Only kills, aces and blocks (ignored if outcomes is set)")
    clip_ids: list[int] = Field(default=[], description="Explicit clips in this order; overrides the filters")


class ReelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    filters: dict
    clip_ids: list[int]
    status: JobStatus
    error: str | None
    duration: float | None
    created_at: datetime
    url: str | None = None

    @classmethod
    def build(cls, r) -> ReelOut:
        out = cls.model_validate(r)
        out.url = media_url(r.path)
        return out


# ---------- automatic highlight detection (routers/analysis.py) -------------------------------------------

class AnalysisRequest(BaseModel):
    # AnalysisConfig overrides, e.g. {"net_x": 0.45}
    settings: dict[str, Any] = {}


class DetectedHighlightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    kind: str
    label: str
    time: float
    score: float
    description: str
    details: dict[str, Any]


class DetectedRallyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    index: int
    start_time: float
    end_time: float
    serve_time: float | None = None
    highlights: list[DetectedHighlightOut]


class ReelHighlightOut(BaseModel):
    kind: str
    label: str
    time: float
    reel_time: float
    score: float
    description: str


class ReelSegmentOut(BaseModel):
    start: float
    end: float
    reel_start: float
    reel_end: float
    rally_indices: list[int]
    highlights: list[ReelHighlightOut]


class AutoReelOut(BaseModel):
    """The automatic highlight reel as timestamps into the source video (not a rendered file)."""
    duration: float
    segments: list[ReelSegmentOut]
    text: str  # the same timestamps as plain text


class AnalysisRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    match_id: int
    status: str
    progress: float
    error: str | None = None
    settings: dict[str, Any]
    diagnostics: dict[str, Any] | None = None
    created_at: datetime
    finished_at: datetime | None = None


class AnalysisOut(AnalysisRunOut):
    rallies: list[DetectedRallyOut] = []
    reel: AutoReelOut | None = None


class RallyEvaluationOut(BaseModel):
    tagged_rallies: int
    detected_rallies: int
    matched: int
    precision: float
    recall: float
    mean_start_error: float | None = None  # detected minus tagged, seconds
    mean_end_error: float | None = None


class RenderedReelOut(BaseModel):
    reel_path: str
    reel_url: str | None = None
    segment_count: int
    duration: float
