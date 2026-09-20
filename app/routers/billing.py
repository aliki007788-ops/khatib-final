"""
Billing endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import Transaction, User
from app.routers.auth import get_current_user
from app.schemas.billing import (
    CheckoutRequest,
    CheckoutResponse,
    NoActiveSubscriptionResponse,
    SubscriptionResponse,
    TransactionResponse,
)
from app.services import billing as billing_service

router = APIRouter(prefix="/api/billing", tags=["billing"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(
    payload: CheckoutRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        txn, payment_url = billing_service.create_checkout(
            db, current_user, payload.plan, _client_ip(request)
        )
    except billing_service.BillingError as exc:
        raise HTTPException(exc.status_code, exc.message)

    return CheckoutResponse(
        payment_url=payment_url,
        authority=txn.authority or "",
        transaction_id=txn.id,
    )


@router.get("/callback")
def zarinpal_callback(
    request: Request,
    Authority: str = Query(...),
    Status: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        txn = billing_service.process_callback(db, Authority, Status, _client_ip(request))
    except billing_service.BillingError as exc:
        return RedirectResponse(url=f"/payment-result.html?status=error&message={exc.message}")

    if txn.status.value == "paid":
        return RedirectResponse(url=f"/payment-result.html?status=success&plan={txn.plan.value}")
    return RedirectResponse(url=f"/payment-result.html?status=failed&reason={txn.failure_reason or ''}")


@router.get("/demo-pay")
def demo_pay(authority: str = Query(...), db: Session = Depends(get_db)):
    txn = db.execute(select(Transaction).where(Transaction.authority == authority)).scalar_one_or_none()
    if txn is None:
        raise HTTPException(404, "تراکنش یافت نشد.")
    result_txn = billing_service.process_callback(db, authority, "OK", "demo")
    return RedirectResponse(url=f"/payment-result.html?status={'success' if result_txn.status.value == 'paid' else 'failed'}")


@router.get("/subscription", response_model=SubscriptionResponse | NoActiveSubscriptionResponse)
def my_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = billing_service.get_active_subscription(db, current_user.id)
    if sub is None:
        return NoActiveSubscriptionResponse()
    return SubscriptionResponse.model_validate(sub)


@router.get("/history", response_model=list[TransactionResponse])
def my_transaction_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .order_by(Transaction.created_at.desc())
        .limit(100)
    ).scalars().all()
    return [TransactionResponse.model_validate(r) for r in rows]
