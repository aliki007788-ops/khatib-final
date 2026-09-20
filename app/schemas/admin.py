from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class AdminUserResponse(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    plan: str
    active: bool
    created_at: datetime
    deleted_at: datetime | None

    model_config = {"from_attributes": True}


class SetUserPlanRequest(BaseModel):
    plan: str = Field(pattern="^(free|base|pro|enterprise)$")


class SetUserActiveRequest(BaseModel):
    active: bool


class AdminStatsResponse(BaseModel):
    total_users: int
    active_users: int
    deleted_users: int
    total_speeches: int
    completed_speeches: int
    active_subscriptions: int
    paid_transactions: int
    total_revenue_toman: int
