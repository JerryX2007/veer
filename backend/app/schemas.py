from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    video_path: str
    recorded_at: Optional[datetime] = None
    created_at: datetime


class RallyCreate(BaseModel):
    start_time: float
    end_time: float
    outcome: str
    notes: Optional[str] = None


class RallyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    start_time: float
    end_time: float
    outcome: str
    notes: Optional[str] = None
    clip_path: Optional[str] = None
    created_at: datetime


class MetricOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rally_id: int
    name: str
    value: float


class HighlightReelRequest(BaseModel):
    outcomes: list[str]


class HighlightReelOut(BaseModel):
    reel_path: str
    clip_count: int


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
    serve_time: Optional[float] = None
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


class ReelOut(BaseModel):
    duration: float
    segments: list[ReelSegmentOut]
    text: str  # the same timestamps as plain text


class AnalysisRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    match_id: int
    status: str
    progress: float
    error: Optional[str] = None
    settings: dict[str, Any]
    diagnostics: Optional[dict[str, Any]] = None
    created_at: datetime
    finished_at: Optional[datetime] = None


class AnalysisOut(AnalysisRunOut):
    rallies: list[DetectedRallyOut] = []
    reel: Optional[ReelOut] = None


class RallyEvaluationOut(BaseModel):
    tagged_rallies: int
    detected_rallies: int
    matched: int
    precision: float
    recall: float
    mean_start_error: Optional[float] = None  # detected minus tagged, seconds
    mean_end_error: Optional[float] = None


class RenderedReelOut(BaseModel):
    reel_path: str
    segment_count: int
    duration: float
