from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import User
from app.routers.auth import get_current_user
from app.services import ai as ai_service

router = APIRouter(prefix="/api/translate", tags=["translate"])


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    direction: str = Field(default="fa_to_iq", pattern="^(fa_to_iq|iq_to_fa)$")


class TranslateResponse(BaseModel):
    translated_text: str
    notes: str | None = None


@router.post("", response_model=TranslateResponse)
def translate(
    payload: TranslateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = ai_service.translate(db, current_user.id, payload.text, payload.direction)
    except Exception as exc:
        raise HTTPException(502, "خطا در سرویس ترجمه.") from exc
    return TranslateResponse(translated_text=result.translated_text, notes=result.notes)
