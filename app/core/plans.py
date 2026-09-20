"""
Plan / Entitlement definitions.
`None` represents unlimited — never fake large numbers like 9999.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.models import PlanEnum


@dataclass(frozen=True)
class PlanLimits:
    max_speech_per_month: int | None  # None = unlimited
    max_audio_seconds_per_month: int | None
    price_toman: int
    label_fa: str


PLAN_CATALOG: dict[PlanEnum, PlanLimits] = {
    PlanEnum.free: PlanLimits(
        max_speech_per_month=3,
        max_audio_seconds_per_month=180,
        price_toman=0,
        label_fa="رایگان",
    ),
    PlanEnum.base: PlanLimits(
        max_speech_per_month=30,
        max_audio_seconds_per_month=1800,
        price_toman=99_000,
        label_fa="پایه",
    ),
    PlanEnum.pro: PlanLimits(
        max_speech_per_month=None,
        max_audio_seconds_per_month=None,
        price_toman=249_000,
        label_fa="حرفه‌ای",
    ),
    PlanEnum.enterprise: PlanLimits(
        max_speech_per_month=None,
        max_audio_seconds_per_month=None,
        price_toman=499_000,
        label_fa="سازمانی",
    ),
}


def get_plan_limits(plan: PlanEnum) -> PlanLimits:
    return PLAN_CATALOG[plan]


def is_unlimited(value: int | None) -> bool:
    return value is None
