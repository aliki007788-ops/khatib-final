"""
Atomic usage accounting.

CRITICAL: Never implement usage checks as:
    if current_usage < limit:
        current_usage += 1
This is a classic Time-Of-Check-Time-Of-Use race condition.
"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.models import PlanEnum, User
from app.core.plans import get_plan_limits


def _current_period() -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = monthrange(now.year, now.month)[1]
    end = start.replace(day=last_day, hour=23, minute=59, second=59)
    return start, end


def _ensure_counter_row(db: Session, user_id: str) -> None:
    start, end = _current_period()
    try:
        db.execute(
            text(
                """
                INSERT INTO usage_counters
                    (id, user_id, period_start, period_end, speech_count, audio_seconds, created_at)
                VALUES
                    (:id, :user_id, :period_start, :period_end, 0, 0, :now)
                ON CONFLICT (user_id, period_start) DO NOTHING
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "period_start": start,
                "period_end": end,
                "now": datetime.now(timezone.utc),
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()


@dataclass
class UsageResult:
    allowed: bool
    remaining_speech: int | None
    remaining_seconds: int | None


def try_consume_speech(db: Session, user: User, audio_seconds: int = 0) -> UsageResult:
    limits = get_plan_limits(user.plan)
    start, _ = _current_period()

    _ensure_counter_row(db, user.id)

    speech_limit_clause = "TRUE" if limits.max_speech_per_month is None else "speech_count < :speech_limit"
    seconds_limit_clause = "TRUE" if limits.max_audio_seconds_per_month is None else "audio_seconds + :add_seconds <= :seconds_limit"

    sql = text(
        f"""
        UPDATE usage_counters
        SET speech_count = speech_count + 1,
            audio_seconds = audio_seconds + :add_seconds
        WHERE user_id = :user_id
          AND period_start = :period_start
          AND ({speech_limit_clause})
          AND ({seconds_limit_clause})
        RETURNING speech_count, audio_seconds
        """
    )

    params = {
        "user_id": user.id,
        "period_start": start,
        "add_seconds": audio_seconds,
    }
    if limits.max_speech_per_month is not None:
        params["speech_limit"] = limits.max_speech_per_month
    if limits.max_audio_seconds_per_month is not None:
        params["seconds_limit"] = limits.max_audio_seconds_per_month

    row = db.execute(sql, params).first()
    db.commit()

    if row is None:
        current = db.execute(
            text(
                "SELECT speech_count, audio_seconds FROM usage_counters "
                "WHERE user_id = :user_id AND period_start = :period_start"
            ),
            {"user_id": user.id, "period_start": start},
        ).first()
        used_speech = current[0] if current else 0
        used_seconds = current[1] if current else 0
        return UsageResult(
            allowed=False,
            remaining_speech=(
                None if limits.max_speech_per_month is None
                else max(0, limits.max_speech_per_month - used_speech)
            ),
            remaining_seconds=(
                None if limits.max_audio_seconds_per_month is None
                else max(0, limits.max_audio_seconds_per_month - used_seconds)
            ),
        )

    new_speech, new_seconds = row
    return UsageResult(
        allowed=True,
        remaining_speech=(
            None if limits.max_speech_per_month is None
            else max(0, limits.max_speech_per_month - new_speech)
        ),
        remaining_seconds=(
            None if limits.max_audio_seconds_per_month is None
            else max(0, limits.max_audio_seconds_per_month - new_seconds)
        ),
    )
