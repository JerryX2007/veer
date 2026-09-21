from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

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
