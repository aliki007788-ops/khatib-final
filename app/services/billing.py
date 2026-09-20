"""
Billing orchestration — the payment state machine.

CRITICAL INVARIANT (enforced here):
    A given Transaction may transition into PaymentStatus.paid
    AT MOST ONCE, and Subscription activation happens EXACTLY ONCE
    per transaction.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import (
    AuditLog,
    Invoice,
    PaymentProvider,
    PaymentStatus,
    PlanEnum,
    Subscription,
    SubscriptionStatus,
    Transaction,
    User,
)
from app.core.plans import get_plan_limits
from app.services import zarinpal

logger = logging.getLogger("khatib.billing")

SUBSCRIPTION_DURATION_DAYS = 30
DUPLICATE_CHECKOUT_WINDOW_MINUTES = 15


class BillingError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _generate_invoice_number(db: Session) -> str:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"INV-{today}-{uuid.uuid4().hex[:8].upper()}"


def create_checkout(db: Session, user: User, plan: PlanEnum, request_ip: str) -> tuple[Transaction, str]:
    if plan == PlanEnum.free:
        raise BillingError("پلن رایگان نیازی به پرداخت ندارد.")

    limits = get_plan_limits(plan)
    if limits.price_toman <= 0:
        raise BillingError("این پلن قابل خرید نیست.")

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=DUPLICATE_CHECKOUT_WINDOW_MINUTES)
    existing = db.execute(
        select(Transaction).where(
            Transaction.user_id == user.id,
            Transaction.plan == plan,
            Transaction.status.in_([PaymentStatus.pending, PaymentStatus.redirected]),
            Transaction.created_at >= cutoff,
        ).order_by(Transaction.created_at.desc())
    ).scalars().first()

    if existing and existing.authority:
        payment_url = _build_gateway_url(existing.authority)
        return existing, payment_url

    idempotency_key = uuid.uuid4().hex

    txn = Transaction(
        user_id=user.id,
        plan=plan,
        amount_toman=limits.price_toman,
        provider=PaymentProvider(settings.payment_provider),
        status=PaymentStatus.created,
        idempotency_key=idempotency_key,
    )
    db.add(txn)
    db.flush()

    if settings.payment_provider == "demo":
        txn.status = PaymentStatus.pending
        txn.authority = f"demo-{txn.id}"
        db.commit()
        payment_url = f"/api/billing/demo-pay?authority={txn.authority}"
        return txn, payment_url

    try:
        result = zarinpal.request_payment(
            amount_toman=limits.price_toman,
            description=f"خرید پلن {limits.label_fa} - خطیب",
            callback_url=settings.zarinpal_callback_url,
        )
    except zarinpal.ZarinPalError as exc:
        txn.status = PaymentStatus.failed
        txn.failure_reason = exc.message
        db.commit()
        raise BillingError(f"خطا در اتصال به درگاه پرداخت: {exc.message}") from exc

    txn.authority = result.authority
    txn.status = PaymentStatus.redirected
    db.add(AuditLog(user_id=user.id, action="checkout_created",
                     detail=f"plan={plan.value} amount={limits.price_toman}", ip_address=request_ip))
    db.commit()

    return txn, result.payment_url


def _build_gateway_url(authority: str) -> str:
    base = "https://sandbox.zarinpal.com" if settings.zarinpal_sandbox else "https://www.zarinpal.com"
    return f"{base}/pg/StartPay/{authority}"


def process_callback(db: Session, authority: str, provider_status: str, request_ip: str) -> Transaction:
    txn = db.execute(
        select(Transaction).where(Transaction.authority == authority).with_for_update()
    ).scalar_one_or_none()

    if txn is None:
        raise BillingError("تراکنش یافت نشد.", status_code=404)

    if txn.status in (PaymentStatus.paid, PaymentStatus.failed,
                      PaymentStatus.cancelled, PaymentStatus.refunded):
        logger.info("Duplicate callback for already-terminal transaction %s (status=%s)",
                    txn.id, txn.status.value)
        return txn

    txn.status = PaymentStatus.callback_received

    if provider_status != "OK":
        txn.status = PaymentStatus.cancelled
        txn.failure_reason = "کاربر پرداخت را لغو کرد یا ناموفق بود."
        db.commit()
        return txn

    txn.status = PaymentStatus.verifying
    db.flush()

    try:
        if txn.provider == PaymentProvider.demo:
            ref_id = f"demo-ref-{txn.id}"
        else:
            verify_result = zarinpal.verify_payment(txn.amount_toman, authority)
            ref_id = verify_result.ref_id
    except zarinpal.ZarinPalError as exc:
        txn.status = PaymentStatus.failed
        txn.failure_reason = exc.message
        db.commit()
        return txn

    txn.status = PaymentStatus.paid
    txn.ref_id = ref_id
    txn.callback_processed = True

    _activate_subscription(db, txn)
    _create_invoice(db, txn)

    db.add(AuditLog(user_id=txn.user_id, action="payment_success",
                     detail=f"transaction={txn.id} ref_id={ref_id}", ip_address=request_ip))
    db.commit()

    return txn


def _activate_subscription(db: Session, txn: Transaction) -> None:
    now = datetime.now(timezone.utc)

    current_active = db.execute(
        select(Subscription).where(
            Subscription.user_id == txn.user_id,
            Subscription.status == SubscriptionStatus.active,
        )
    ).scalars().all()

    base_start = now
    for sub in current_active:
        if sub.expires_at > base_start:
            base_start = sub.expires_at
        sub.status = SubscriptionStatus.expired

    new_expiry = base_start + timedelta(days=SUBSCRIPTION_DURATION_DAYS)

    new_sub = Subscription(
        user_id=txn.user_id,
        plan=txn.plan,
        status=SubscriptionStatus.active,
        starts_at=now,
        expires_at=new_expiry,
        auto_renew=False,
        source_transaction_id=txn.id,
    )
    db.add(new_sub)

    user = db.get(User, txn.user_id)
    if user:
        user.plan = txn.plan
        user.plan_expires_at = new_expiry


def _create_invoice(db: Session, txn: Transaction) -> Invoice:
    invoice = Invoice(
        invoice_number=_generate_invoice_number(db),
        user_id=txn.user_id,
        transaction_id=txn.id,
        plan=txn.plan,
        amount_toman=txn.amount_toman,
    )
    db.add(invoice)
    return invoice


def get_active_subscription(db: Session, user_id: str) -> Subscription | None:
    return db.execute(
        select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.active,
        ).order_by(Subscription.expires_at.desc())
    ).scalars().first()


def expire_due_subscriptions(db: Session) -> int:
    now = datetime.now(timezone.utc)
    due = db.execute(
        select(Subscription).where(
            Subscription.status == SubscriptionStatus.active,
            Subscription.expires_at < now,
        )
    ).scalars().all()

    count = 0
    for sub in due:
        sub.status = SubscriptionStatus.expired
        user = db.get(User, sub.user_id)
        if user and user.plan == sub.plan:
            user.plan = PlanEnum.free
            user.plan_expires_at = None
        count += 1

    if count:
        db.commit()
    return count
