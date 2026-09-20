from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class TextSpeechRequest(BaseModel):
    topic_label: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=20, max_length=10000)


class SpeechResponse(BaseModel):
    id: str
    mode: str
    status: str
    topic_label: str | None
    input_text: str | None
    transcript: str | None
    duration_sec: float | None
    overall_score: int | None = None
    dimension_scores: dict | None = None
    strengths: list[str] | None = None
    weaknesses: list[str] | None = None
    improvements: list[str] | None = None
    structure_notes: str | None = None
    next_practice: str | None = None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class SpeechListItem(BaseModel):
    id: str
    mode: str
    status: str
    topic_label: str | None
    overall_score: int | None = None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
