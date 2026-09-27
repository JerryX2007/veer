"""Data model: a Match (one uploaded video) has many Rallies; each Rally gets one Clip; Reels stitch clips together."""
from __future__ import annotations

<<<<<<< Updated upstream
from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .analysis.highlights import KIND_LABELS
from .database import Base
=======
import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Outcome(str, enum.Enum):
    """How the rally ended. Drives the highlight path (teal in the plan)."""
    kill = "kill"
    ace = "ace"
    block = "block"
    dig = "dig"
    error = "error"
    other = "other"


class Skill(str, enum.Enum):
    """What happened in the rally worth analysing. Drives the technique path (purple in the plan)."""
    serve = "serve"
    attack = "attack"
    set = "set"
    pass_ = "pass"
    block = "block"
    dig = "dig"


HIGHLIGHT_OUTCOMES = {Outcome.kill, Outcome.ace, Outcome.block}
POSE_SKILLS = {Skill.serve, Skill.attack}


class JobStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class PoseStatus(str, enum.Enum):
    not_applicable = "not_applicable"  # clip isn't a serve/attack
    queued = "queued"                  # waiting for Phase 2 pose estimation
    processing = "processing"
    ready = "ready"
    failed = "failed"
>>>>>>> Stashed changes


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    played_on: Mapped[str | None] = mapped_column(String(10))  # YYYY-MM-DD, used for trends later
    original_filename: Mapped[str] = mapped_column(String(255))
    video_path: Mapped[str] = mapped_column(String(500))
    duration: Mapped[float] = mapped_column(Float)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    fps: Mapped[float] = mapped_column(Float)
    has_audio: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    rallies: Mapped[list[Rally]] = relationship(
        back_populates="match", cascade="all, delete-orphan", order_by="Rally.start"
    )
    analysis_runs = relationship(
        "AnalysisRun", back_populates="match", cascade="all, delete-orphan"
    )


class Rally(Base):
    __tablename__ = "rallies"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    start: Mapped[float] = mapped_column(Float)  # seconds into the match video
    end: Mapped[float] = mapped_column(Float)
    outcome: Mapped[Outcome] = mapped_column(Enum(Outcome))
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    player: Mapped[str | None] = mapped_column(String(100))  # e.g. "me", a jersey number
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    match: Mapped[Match] = relationship(back_populates="rallies")
    clip: Mapped[Clip | None] = relationship(back_populates="rally", cascade="all, delete-orphan", uselist=False)

    @property
    def is_highlight(self) -> bool:
        return self.outcome in HIGHLIGHT_OUTCOMES

    @property
    def wants_pose(self) -> bool:
        return any(s in {p.value for p in POSE_SKILLS} for s in self.skills or [])


class Clip(Base):
    __tablename__ = "clips"

    id: Mapped[int] = mapped_column(primary_key=True)
    rally_id: Mapped[int] = mapped_column(ForeignKey("rallies.id", ondelete="CASCADE"), unique=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.pending)
    error: Mapped[str | None] = mapped_column(Text)
    path: Mapped[str | None] = mapped_column(String(500))
    thumbnail_path: Mapped[str | None] = mapped_column(String(500))
    # The padded window actually cut from the source (may differ from rally start/end).
    source_start: Mapped[float] = mapped_column(Float)
    source_end: Mapped[float] = mapped_column(Float)
    duration: Mapped[float | None] = mapped_column(Float)
    pose_status: Mapped[PoseStatus] = mapped_column(Enum(PoseStatus), default=PoseStatus.not_applicable)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    rally: Mapped[Rally] = relationship(back_populates="clip")

<<<<<<< Updated upstream
    rally = relationship("Rally", back_populates="metrics")


class AnalysisRun(Base):
    """One pass of automatic rally/highlight detection over a match video."""

    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="pending")  # pending, running, done, failed
    progress = Column(Float, nullable=False, default=0.0)  # 0-1
    error = Column(String, nullable=True)
    settings = Column(JSON, nullable=False, default=dict)  # AnalysisConfig overrides
    diagnostics = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    match = relationship("Match", back_populates="analysis_runs")
    rallies = relationship(
        "DetectedRally", back_populates="run", cascade="all, delete-orphan",
        order_by="DetectedRally.index",
    )


class DetectedRally(Base):
    """A rally found automatically: the clip runs from just before the serve to the dead ball."""

    __tablename__ = "detected_rallies"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("analysis_runs.id"), nullable=False, index=True)
    index = Column(Integer, nullable=False)  # order within the match
    start_time = Column(Float, nullable=False)  # clip start (serve minus pre-roll)
    end_time = Column(Float, nullable=False)  # clip end (dead ball plus post-roll)
    serve_time = Column(Float, nullable=True)  # null if the serve wasn't seen

    run = relationship("AnalysisRun", back_populates="rallies")
    highlights = relationship(
        "DetectedHighlight", back_populates="rally", cascade="all, delete-orphan",
        order_by="DetectedHighlight.time",
    )


class DetectedHighlight(Base):
    """A highlight moment inside a detected rally (big kill, great save, block...)."""

    __tablename__ = "detected_highlights"

    id = Column(Integer, primary_key=True, index=True)
    rally_id = Column(Integer, ForeignKey("detected_rallies.id"), nullable=False, index=True)
    kind = Column(String, nullable=False, index=True)
    time = Column(Float, nullable=False)  # seconds into the source video
    score = Column(Float, nullable=False)  # 0.5-1
    description = Column(String, nullable=False, default="")
    details = Column(JSON, nullable=False, default=dict)

    rally = relationship("DetectedRally", back_populates="highlights")

    @property
    def label(self) -> str:
        return KIND_LABELS.get(self.kind, self.kind)
=======

class Reel(Base):
    __tablename__ = "reels"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    filters: Mapped[dict] = mapped_column(JSON, default=dict)  # the query that picked the clips
    clip_ids: Mapped[list[int]] = mapped_column(JSON, default=list)  # frozen, in play order
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.pending)
    error: Mapped[str | None] = mapped_column(Text)
    path: Mapped[str | None] = mapped_column(String(500))
    duration: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
>>>>>>> Stashed changes
