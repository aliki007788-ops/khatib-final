from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.models import (
    PaymentStatus,
    Speech,
    SpeechStatus,
    Subscription,
    SubscriptionStatus,
    Transaction,
    User,
)


def get_admin_stats(db: Session) -> dict:
    total_users = db.scalar(select(func.count(User.id))) or 0
    active_users = db.scalar(
        select(func.count(User.id)).where(User.active.is_(True), User.deleted_at.is_(None))
    ) or 0
    deleted_users = db.scalar(
        select(func.count(User.id)).where(User.deleted_at.is_not(None))
    ) or 0
    total_speeches = db.scalar(select(func.count(Speech.id))) or 0
    completed_speeches = db.scalar(
        select(func.count(Speech.id)).where(Speech.status == SpeechStatus.completed)
    ) or 0
    active_subscriptions = db.scalar(
        select(func.count(Subscription.id)).where(Subscription.status == SubscriptionStatus.active)
    ) or 0
    paid_transactions = db.scalar(
        select(func.count(Transaction.id)).where(Transaction.status == PaymentStatus.paid)
    ) or 0
    total_revenue = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount_toman), 0)).where(
            Transaction.status == PaymentStatus.paid
        )
    ) or 0

    return {
        "total_users": total_users,
        "active_users": active_users,
        "deleted_users": deleted_users,
        "total_speeches": total_speeches,
        "completed_speeches": completed_speeches,
        "active_subscriptions": active_subscriptions,
        "paid_transactions": paid_transactions,
        "total_revenue_toman": int(total_revenue),
    }
