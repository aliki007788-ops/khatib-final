"""Pydantic schemas for billing endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.core.models import PaymentStatus, PlanEnum, SubscriptionStatus


class CheckoutRequest(BaseModel):
    plan: PlanEnum


class CheckoutResponse(BaseModel):
    payment_url: str
    authority: str
    transaction_id: str


class TransactionResponse(BaseModel):
    id: str
    plan: PlanEnum
    amount_toman: int
    status: PaymentStatus
    provider: str
    ref_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionResponse(BaseModel):
    plan: PlanEnum
    status: SubscriptionStatus
    starts_at: datetime
    expires_at: datetime
    auto_renew: bool

    model_config = {"from_attributes": True}


class NoActiveSubscriptionResponse(BaseModel):
    plan: PlanEnum = PlanEnum.free
    status: str = "none"
    message: str = "کاربر در حال حاضر اشتراک فعالی ندارد و از پلن رایگان استفاده می‌کند."
