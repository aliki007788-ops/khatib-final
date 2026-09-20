"""
Structured output schemas for AI responses.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SpeechAnalysisResponse(BaseModel):
    score: int = Field(ge=0, le=100, description="Overall speech quality score, 0-100")
    strengths: list[str] = Field(default_factory=list, max_length=10)
    weaknesses: list[str] = Field(default_factory=list, max_length=10)
    improvements: list[str] = Field(default_factory=list, max_length=10)
    structure_notes: str = Field(max_length=1000)
    next_practice: str = Field(max_length=500)

    @field_validator("strengths", "weaknesses", "improvements")
    @classmethod
    def non_empty_strings(cls, v: list[str]) -> list[str]:
        return [s.strip() for s in v if s and s.strip()]


class ChatReplyResponse(BaseModel):
    reply: str = Field(max_length=2000)
    corrections: list[str] = Field(default_factory=list, max_length=10)
    notes: str | None = Field(default=None, max_length=500)


class TranslationResponse(BaseModel):
    translated_text: str = Field(max_length=3000)
    notes: str | None = Field(default=None, max_length=500)


class TranscriptionResponse(BaseModel):
    text: str
    duration_seconds: float | None = None
    language: str | None = None
