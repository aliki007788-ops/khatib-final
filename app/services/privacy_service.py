"""
Privacy-preserving account operations.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.models import (
    Conversation,
    EitaaAccountLink,
    Message,
    PrivacyRequest,
    PrivacyRequestStatus,
    PrivacyRequestType,
    RefreshToken,
    Speech,
    Subscription,
    Transaction,
    User,
)
from app.core.security import hash_password
from app.core.models import PlanEnum


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_user_export(db: Session, user: User) -> dict:
    speeches = db.execute(
        select(Speech).where(Speech.user_id == user.id).order_by(Speech.created_at.asc())
    ).scalars().all()

    conversations = db.execute(
        select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.created_at.asc())
    ).scalars().all()

    subscriptions = db.execute(
        select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.created_at.asc())
    ).scalars().all()

    payments = db.execute(
        select(Transaction).where(Transaction.user_id == user.id).order_by(Transaction.created_at.asc())
    ).scalars().all()

    messages_by_conversation: dict[str, list[dict]] = {}
    for conversation in conversations:
        messages = db.execute(
            select(Message).where(Message.conversation_id == conversation.id).order_by(Message.created_at.asc())
        ).scalars().all()
        messages_by_conversation[conversation.id] = [
            {
                "id": m.id,
                "role": m.role.value,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]

    return {
        "exported_at": utc_now().isoformat(),
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "plan": user.plan.value,
            "created_at": user.created_at.isoformat(),
            "email_verified": user.email_verified,
        },
        "speeches": [
            {
                "id": s.id,
                "mode": s.mode.value,
                "status": s.status.value,
                "topic_label": s.topic_label,
                "input_text": s.input_text,
                "transcript": s.transcript,
                "duration_sec": s.duration_sec,
                "created_at": s.created_at.isoformat(),
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "analysis": (
                    {
                        "overall_score": s.analysis.overall_score,
                        "dimension_scores": s.analysis.dimension_scores,
                        "strengths": s.analysis.ai_strengths,
                        "weaknesses": s.analysis.ai_weaknesses,
                        "improvements": s.analysis.ai_improvements,
                    }
                    if s.analysis else None
                ),
            }
            for s in speeches
        ],
        "conversations": [
            {
                "id": c.id,
                "title": c.title,
                "summary": c.summary,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
                "messages": messages_by_conversation.get(c.id, []),
            }
            for c in conversations
        ],
        "subscriptions": [
            {
                "id": sub.id,
                "plan": sub.plan.value,
                "status": sub.status.value,
                "starts_at": sub.starts_at.isoformat(),
                "expires_at": sub.expires_at.isoformat(),
            }
            for sub in subscriptions
        ],
        "payments": [
            {
                "id": p.id,
                "plan": p.plan.value,
                "amount_toman": p.amount_toman,
                "status": p.status.value,
                "provider": p.provider.value,
                "created_at": p.created_at.isoformat(),
            }
            for p in payments
        ],
        "privacy": {
            "note": "فایل صوتی خام در این خروجی قرار نمی‌گیرد.",
        },
    }


def delete_user_account(db: Session, user: User) -> None:
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == user.id))
    db.execute(delete(EitaaAccountLink).where(EitaaAccountLink.user_id == user.id))
    db.execute(delete(Conversation).where(Conversation.user_id == user.id))
    db.execute(delete(Speech).where(Speech.user_id == user.id))

    anonymous_email = f"deleted_{user.id}_{secrets.token_hex(6)}@deleted.khatib.local"
    user.email = anonymous_email
    user.name = "کاربر حذف‌شده"
    user.password_hash = hash_password(secrets.token_urlsafe(48))
    user.email_verified = False
    user.active = False
    user.deleted_at = utc_now()
    user.deletion_requested_at = utc_now()
    user.plan = PlanEnum.free
    user.plan_expires_at = None

    db.add(PrivacyRequest(
        user_id=None,
        request_type=PrivacyRequestType.delete_account,
        status=PrivacyRequestStatus.completed,
        requested_at=utc_now(),
        completed_at=utc_now(),
    ))
    db.commit()
