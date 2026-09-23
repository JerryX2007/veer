from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .analysis.highlights import KIND_LABELS
from .database import Base


class Match(Base):
    """A single uploaded video: a match, a practice, or a personal reps session."""

    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    video_path = Column(String, nullable=False)
    recorded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    rallies = relationship(
        "Rally", back_populates="match", cascade="all, delete-orphan"
    )
    analysis_runs = relationship(
        "AnalysisRun", back_populates="match", cascade="all, delete-orphan"
    )


class Rally(Base):
    """One tagged rally or rep within a match video: a time range plus an outcome."""

    __tablename__ = "rallies"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    start_time = Column(Float, nullable=False)  # seconds into the source video
    end_time = Column(Float, nullable=False)
    outcome = Column(String, nullable=False, index=True)  # kill, ace, error, serve, attack...
    notes = Column(String, nullable=True)
    clip_path = Column(String, nullable=True)  # set once a clip has been exported
    created_at = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match", back_populates="rallies")
    metrics = relationship(
        "Metric", back_populates="rally", cascade="all, delete-orphan"
    )


class Metric(Base):
    """A pose-estimation-derived measurement for a rally. Populated in phase 2."""

    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    rally_id = Column(Integer, ForeignKey("rallies.id"), nullable=False)
    name = Column(String, nullable=False)  # e.g. "jump_height_cm", "arm_angle_deg"
    value = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

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
