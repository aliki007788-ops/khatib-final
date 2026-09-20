"""
Eitaa Bot webhook adapter (secure).
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.models import EitaaAccountLink, User

logger = logging.getLogger("khatib.eitaa")

router = APIRouter(prefix="/api/eitaa", tags=["eitaa"])


def _verify_secret(x_eitaa_bot_api_secret_token: str | None = Header(default=None)) -> None:
    expected = settings.eitaa_webhook_secret
    if not expected:
        # If secret not configured, reject in non-dev
        if settings.is_production:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Eitaa webhook not configured.")
        return
    if not x_eitaa_bot_api_secret_token or x_eitaa_bot_api_secret_token != expected:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid webhook secret.")


@router.post("/webhook")
async def eitaa_webhook(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(_verify_secret),
):
    """
    Receives updates from Eitaa Bot.
    Minimal implementation: handles /start for account linking.
    """
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body.")

    message = body.get("message") or body.get("edited_message") or {}
    chat = message.get("chat") or {}
    text = (message.get("text") or "").strip()
    chat_id = str(chat.get("id", ""))
    from_user = message.get("from") or {}
    eitaa_user_id = str(from_user.get("id", ""))

    if not chat_id:
        return {"ok": True}

    logger.info("Eitaa update chat_id=%s text=%s", chat_id, text[:50] if text else "")

    if text.startswith("/start"):
        # Optional deep-link: /start <user_uuid>
        parts = text.split(maxsplit=1)
        if len(parts) == 2:
            target_user_id = parts[1].strip()
            user = db.get(User, target_user_id)
            if user and user.active and not user.deleted_at:
                existing = db.execute(
                    select(EitaaAccountLink).where(EitaaAccountLink.eitaa_user_id == eitaa_user_id)
                ).scalar_one_or_none()
                if existing:
                    existing.user_id = user.id
                    existing.eitaa_chat_id = chat_id
                else:
                    db.add(EitaaAccountLink(
                        user_id=user.id,
                        eitaa_user_id=eitaa_user_id,
                        eitaa_chat_id=chat_id,
                    ))
                db.commit()
                logger.info("Linked Eitaa user %s to Khatib user %s", eitaa_user_id, user.id)

    return {"ok": True}


@router.get("/link-status")
def link_status(
    current_user: User = Depends(__import__("app.routers.auth", fromlist=["get_current_user"]).get_current_user),
    db: Session = Depends(get_db),
):
    link = db.execute(
        select(EitaaAccountLink).where(EitaaAccountLink.user_id == current_user.id)
    ).scalar_one_or_none()
    return {
        "linked": link is not None,
        "eitaa_user_id": link.eitaa_user_id if link else None,
        "linked_at": link.linked_at.isoformat() if link else None,
    }
