"""
SQLAlchemy models — Full consolidated models for Khatib.
Identity & Auth + Billing + AI + Speech + Learning + Privacy domains.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


# =========================================================
# Enums
# =========================================================

class PlanEnum(str, enum.Enum):
    free = "free"
    base = "base"
    pro = "pro"
    enterprise = "enterprise"


class RoleEnum(str, enum.Enum):
    user = "user"
    admin = "admin"
    superadmin = "superadmin"


class PaymentStatus(str, enum.Enum):
    created = "created"
    pending = "pending"
    redirected = "redirected"
    callback_received = "callback_received"
    verifying = "verifying"
    paid = "paid"
    failed = "failed"
    cancelled = "cancelled"
    refunded = "refunded"


class PaymentProvider(str, enum.Enum):
    zarinpal = "zarinpal"
    demo = "demo"


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    cancelled = "cancelled"


class AITaskType(str, enum.Enum):
    speech_analysis = "speech_analysis"
    chat_reply = "chat_reply"
    translation = "translation"
    transcription = "transcription"


class AIProviderUsed(str, enum.Enum):
    primary = "primary"
    fallback = "fallback"


class AIRequestStatus(str, enum.Enum):
    success = "success"
    failed = "failed"
    validation_failed = "validation_failed"


class SpeechStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class SpeechMode(str, enum.Enum):
    text = "text"
    audio = "audio"


class JobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed_retryable = "failed_retryable"
    dead_letter = "dead_letter"


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class ScenarioCategory(str, enum.Enum):
    daily_conversation = "daily_conversation"
    restaurant = "restaurant"
    market = "market"
    hotel = "hotel"
    work = "work"
    travel = "travel"
    social = "social"


class ScenarioProgressStatus(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"


class PrivacyRequestType(str, enum.Enum):
    export = "export"
    delete_account = "delete_account"


class PrivacyRequestStatus(str, enum.Enum):
    requested = "requested"
    processing = "processing"
    completed = "completed"
    failed = "failed"


# =========================================================
# Identity & Auth
# =========================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_algo: Mapped[str] = mapped_column(String(20), default="argon2", nullable=False)

    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[RoleEnum] = mapped_column(
        Enum(RoleEnum), default=RoleEnum.user, nullable=False
    )

    plan: Mapped[PlanEnum] = mapped_column(
        Enum(PlanEnum), default=PlanEnum.free, nullable=False
    )
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    privacy_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    sessions: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_users_email_active", "email", "active"),
    )


class RefreshToken(Base):
    """
    Stores hashed refresh tokens for rotation & revocation.
    The raw token is NEVER stored — only its hash.
    """
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    replaced_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    user: Mapped["User"] = relationship(back_populates="sessions")

    __table_args__ = (
        Index("ix_refresh_tokens_user_revoked", "user_id", "revoked"),
    )


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    user: Mapped["User | None"] = relationship(back_populates="audit_logs")


# =========================================================
# Billing
# =========================================================

class Transaction(Base):
    """
    A single payment attempt. One Transaction may go through multiple
    state transitions but must reach exactly one terminal state.

    CRITICAL INVARIANT:
    Once `status` reaches `paid`, it must NEVER transition again, and
    subscription activation must happen EXACTLY ONCE per transaction.
    """
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    plan: Mapped[PlanEnum] = mapped_column(Enum(PlanEnum), nullable=False)
    amount_toman: Mapped[int] = mapped_column(Integer, nullable=False)

    provider: Mapped[PaymentProvider] = mapped_column(Enum(PaymentProvider), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.created, nullable=False, index=True
    )

    authority: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    ref_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    callback_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    __table_args__ = (
        Index("ix_transactions_user_status", "user_id", "status"),
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan: Mapped[PlanEnum] = mapped_column(Enum(PlanEnum), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus), default=SubscriptionStatus.active, nullable=False, index=True
    )

    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    source_transaction_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        Index("ix_subscriptions_user_status", "user_id", "status"),
    )


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transaction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    plan: Mapped[PlanEnum] = mapped_column(Enum(PlanEnum), nullable=False)
    amount_toman: Mapped[int] = mapped_column(Integer, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class UsageCounter(Base):
    """
    Atomic, period-scoped usage tracking. One row per (user, period).
    Increments MUST go through services/usage.py which uses an atomic
    conditional UPDATE — never read-modify-write from Python.
    """
    __tablename__ = "usage_counters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    speech_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    audio_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "period_start", name="uq_usage_user_period"),
    )


# =========================================================
# AI Observability
# =========================================================

class AIRequestLog(Base):
    __tablename__ = "ai_request_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    task_type: Mapped[AITaskType] = mapped_column(Enum(AITaskType), nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)

    provider_used: Mapped[AIProviderUsed] = mapped_column(Enum(AIProviderUsed), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    status: Mapped[AIRequestStatus] = mapped_column(Enum(AIRequestStatus), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False, index=True)

    __table_args__ = (
        Index("ix_ai_logs_task_status", "task_type", "status"),
    )


# =========================================================
# Speech & Audio
# =========================================================

class AudioAsset(Base):
    __tablename__ = "audio_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


class Speech(Base):
    __tablename__ = "speeches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mode: Mapped[SpeechMode] = mapped_column(Enum(SpeechMode), nullable=False)
    status: Mapped[SpeechStatus] = mapped_column(
        Enum(SpeechStatus), default=SpeechStatus.pending, nullable=False, index=True
    )
    topic_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_asset_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("audio_assets.id", ondelete="SET NULL"), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    analysis: Mapped["SpeechAnalysis | None"] = relationship(
        back_populates="speech", uselist=False, cascade="all, delete-orphan"
    )
    audio_asset: Mapped["AudioAsset | None"] = relationship()


class SpeechAnalysis(Base):
    __tablename__ = "speech_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    speech_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("speeches.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    dimension_scores: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ai_strengths: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    ai_weaknesses: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    ai_improvements: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    structure_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_practice: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    speech: Mapped["Speech"] = relationship(back_populates="analysis")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    speech_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("speeches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.queued, nullable=False, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)


# =========================================================
# Chat & Conversation
# =========================================================

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


# =========================================================
# Learning
# =========================================================

class LearningLevel(Base):
    __tablename__ = "learning_levels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name_fa: Mapped[str] = mapped_column(String(100), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    description_fa: Mapped[str | None] = mapped_column(Text, nullable=True)

    scenarios: Mapped[list["IraqiScenario"]] = relationship(
        back_populates="level", cascade="all, delete-orphan"
    )


class IraqiScenario(Base):
    __tablename__ = "iraqi_scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    level_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("learning_levels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[ScenarioCategory] = mapped_column(Enum(ScenarioCategory), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title_fa: Mapped[str] = mapped_column(String(255), nullable=False)
    description_fa: Mapped[str] = mapped_column(Text, nullable=False)
    key_vocabulary: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    practice_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    level: Mapped["LearningLevel"] = relationship(back_populates="scenarios")


class UserScenarioProgress(Base):
    __tablename__ = "user_scenario_progress"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scenario_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("iraqi_scenarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[ScenarioProgressStatus] = mapped_column(
        Enum(ScenarioProgressStatus), default=ScenarioProgressStatus.not_started, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "scenario_id", name="uq_user_scenario"),
    )


class UserLearningState(Base):
    __tablename__ = "user_learning_states"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    current_level_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("learning_levels.id", ondelete="SET NULL"), nullable=True
    )


# =========================================================
# Privacy
# =========================================================

class PrivacyRequest(Base):
    __tablename__ = "privacy_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    request_type: Mapped[PrivacyRequestType] = mapped_column(Enum(PrivacyRequestType), nullable=False)
    status: Mapped[PrivacyRequestStatus] = mapped_column(
        Enum(PrivacyRequestStatus), default=PrivacyRequestStatus.requested, nullable=False
    )
    result_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# =========================================================
# Eitaa
# =========================================================

class EitaaAccountLink(Base):
    __tablename__ = "eitaa_account_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    eitaa_user_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    eitaa_chat_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
