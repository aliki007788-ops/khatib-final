"""
Learning Engine — Iraqi Arabic level/scenario curriculum.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import (
    Conversation,
    IraqiScenario,
    LearningLevel,
    Message,
    MessageRole,
    ScenarioProgressStatus,
    User,
    UserLearningState,
    UserScenarioProgress,
)
from app.services import progress_engine

LEVEL_UNLOCK_THRESHOLD = 0.6
MIN_USER_MESSAGES_TO_COMPLETE = 3


class LearningEngineError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


@dataclass
class ScenarioWithStatus:
    scenario: IraqiScenario
    status: ScenarioProgressStatus
    unlocked: bool


@dataclass
class LevelWithProgress:
    level: LearningLevel
    unlocked: bool
    completed_count: int
    total_count: int


def _completed_scenario_ids(db: Session, user_id: str) -> set[str]:
    rows = db.execute(
        select(UserScenarioProgress.scenario_id).where(
            UserScenarioProgress.user_id == user_id,
            UserScenarioProgress.status == ScenarioProgressStatus.completed,
        )
    ).scalars().all()
    return set(rows)


def get_levels_with_progress(db: Session, user_id: str) -> list[LevelWithProgress]:
    levels = db.execute(select(LearningLevel).order_by(LearningLevel.order_index)).scalars().all()
    completed_ids = _completed_scenario_ids(db, user_id)

    result: list[LevelWithProgress] = []
    previous_unlocked_and_sufficient = True

    for level in levels:
        total = len(level.scenarios)
        completed = sum(1 for s in level.scenarios if s.id in completed_ids)

        unlocked = previous_unlocked_and_sufficient
        result.append(LevelWithProgress(level=level, unlocked=unlocked, completed_count=completed, total_count=total))

        ratio = (completed / total) if total > 0 else 0
        previous_unlocked_and_sufficient = unlocked and ratio >= LEVEL_UNLOCK_THRESHOLD

    return result


def get_scenarios_for_level(db: Session, user_id: str, level_id: str) -> list[ScenarioWithStatus]:
    level = db.get(LearningLevel, level_id)
    if level is None:
        raise LearningEngineError("سطح یافت نشد.")

    progress_rows = db.execute(
        select(UserScenarioProgress).where(
            UserScenarioProgress.user_id == user_id,
            UserScenarioProgress.scenario_id.in_([s.id for s in level.scenarios]),
        )
    ).scalars().all()
    progress_by_scenario = {p.scenario_id: p.status for p in progress_rows}

    result: list[ScenarioWithStatus] = []
    previous_completed = True

    for scenario in sorted(level.scenarios, key=lambda s: s.order_index):
        status = progress_by_scenario.get(scenario.id, ScenarioProgressStatus.not_started)
        unlocked = previous_completed
        result.append(ScenarioWithStatus(scenario=scenario, status=status, unlocked=unlocked))
        previous_completed = status == ScenarioProgressStatus.completed

    return result


def start_scenario(db: Session, user: User, scenario_id: str) -> Conversation:
    scenario = db.get(IraqiScenario, scenario_id)
    if scenario is None or not scenario.active:
        raise LearningEngineError("سناریو یافت نشد.")

    existing = db.execute(
        select(UserScenarioProgress).where(
            UserScenarioProgress.user_id == user.id,
            UserScenarioProgress.scenario_id == scenario_id,
        )
    ).scalar_one_or_none()

    if existing and existing.conversation_id:
        conv = db.get(Conversation, existing.conversation_id)
        if conv is not None:
            return conv

    conv = Conversation(user_id=user.id, title=scenario.title_fa)
    db.add(conv)
    db.flush()

    opening = Message(
        conversation_id=conv.id,
        role=MessageRole.assistant,
        content=scenario.practice_prompt,
    )
    db.add(opening)

    if existing:
        existing.conversation_id = conv.id
        existing.status = ScenarioProgressStatus.in_progress
        existing.started_at = existing.started_at or datetime.now(timezone.utc)
    else:
        db.add(UserScenarioProgress(
            user_id=user.id,
            scenario_id=scenario_id,
            conversation_id=conv.id,
            status=ScenarioProgressStatus.in_progress,
            started_at=datetime.now(timezone.utc),
        ))

    db.commit()
    db.refresh(conv)
    return conv


def complete_scenario(db: Session, user: User, scenario_id: str) -> None:
    progress = db.execute(
        select(UserScenarioProgress).where(
            UserScenarioProgress.user_id == user.id,
            UserScenarioProgress.scenario_id == scenario_id,
        )
    ).scalar_one_or_none()

    if progress is None or progress.conversation_id is None:
        raise LearningEngineError("ابتدا باید تمرین این سناریو را شروع کنید.")

    user_messages = db.execute(
        select(Message).where(
            Message.conversation_id == progress.conversation_id,
            Message.role == MessageRole.user,
        )
    ).scalars().all()

    if len(user_messages) < MIN_USER_MESSAGES_TO_COMPLETE:
        raise LearningEngineError(
            f"برای تکمیل این سناریو، حداقل باید {MIN_USER_MESSAGES_TO_COMPLETE} پیام رد و بدل کنید."
        )

    progress.status = ScenarioProgressStatus.completed
    progress.completed_at = datetime.now(timezone.utc)
    db.commit()


@dataclass
class DailyPracticeRecommendation:
    kind: str
    title_fa: str
    description_fa: str
    action_scenario_id: str | None = None
    action_topic_label: str | None = None


def get_daily_recommendation(db: Session, user: User) -> DailyPracticeRecommendation:
    in_progress = db.execute(
        select(UserScenarioProgress).where(
            UserScenarioProgress.user_id == user.id,
            UserScenarioProgress.status == ScenarioProgressStatus.in_progress,
        )
    ).scalars().first()

    if in_progress:
        scenario = db.get(IraqiScenario, in_progress.scenario_id)
        if scenario:
            return DailyPracticeRecommendation(
                kind="scenario",
                title_fa=f"ادامه تمرین: {scenario.title_fa}",
                description_fa=scenario.description_fa,
                action_scenario_id=scenario.id,
            )

    weakest = progress_engine.get_weakest_dimension(db, user.id)
    if weakest:
        topic_map = {
            "pace": "امروز روی سرعت بیان خود تمرکز کنید؛ یک متن را با سرعت متعادل بخوانید.",
            "fillers": "امروز تمرین کنید بدون گفتن «یعنی»، «چیزه» و کلمات پرکننده صحبت کنید.",
            "energy": "امروز با انرژی بیشتری صحبت کنید؛ سعی کنید صدای خود را متغیرتر کنید.",
            "structure": "امروز یک سخنرانی با مقدمه، بدنه و نتیجه‌گیری مشخص تمرین کنید.",
            "pitch": "امروز روی متغیر کردن زیر و بمی صدای خود تمرین کنید.",
        }
        description = topic_map.get(weakest, "امروز یک تمرین سخنرانی جدید انجام دهید.")
        return DailyPracticeRecommendation(
            kind="speech_topic",
            title_fa="تمرین هدفمند امروز",
            description_fa=description,
            action_topic_label=weakest,
        )

    default_level = db.execute(select(LearningLevel).order_by(LearningLevel.order_index)).scalars().first()
    if default_level and default_level.scenarios:
        first_scenario = sorted(default_level.scenarios, key=lambda s: s.order_index)[0]
        return DailyPracticeRecommendation(
            kind="scenario",
            title_fa=f"شروع کنید: {first_scenario.title_fa}",
            description_fa=first_scenario.description_fa,
            action_scenario_id=first_scenario.id,
        )

    return DailyPracticeRecommendation(
        kind="speech_topic",
        title_fa="اولین تمرین خود را ثبت کنید",
        description_fa="یک موضوع دلخواه انتخاب کنید و اولین سخنرانی خود را تمرین کنید.",
    )
