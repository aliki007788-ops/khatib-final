from __future__ import annotations

from pydantic import BaseModel


class ProgressSummaryResponse(BaseModel):
    practice_count: int
    best_score: int | None
    average_score: float | None
    weekly_average_score: float | None
    monthly_average_score: float | None
    current_streak_days: int
    score_trend: list[dict]


class DimensionTrendResponse(BaseModel):
    dimension: str
    label_fa: str
    recent_average: float
    previous_average: float
    change_percent: float
