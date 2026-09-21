from datetime import datetime
from typing import Optional

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
