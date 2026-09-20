from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class PrivacyRequestResponse(BaseModel):
    id: str
    request_type: str
    status: str
    requested_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class DeleteAccountRequest(BaseModel):
    confirmation: str = Field(description="باید عبارت DELETE_ACCOUNT ارسال شود.")


class ExportDataResponse(BaseModel):
    user: dict
    speeches: list[dict]
    conversations: list[dict]
    subscriptions: list[dict]
    payments: list[dict]
    privacy: dict
