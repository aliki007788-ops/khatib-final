"""
Chat service — Iraqi Arabic coach conversations powered by AI.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import Conversation, Message, MessageRole, User
from app.services import ai as ai_service

logger = logging.getLogger("khatib.chat")


class ChatServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def create_conversation(db: Session, user: User, title: str | None = None) -> Conversation:
    conv = Conversation(
        user_id=user.id,
        title=title or "مکالمه جدید",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def list_conversations(db: Session, user: User, limit: int = 50) -> list[Conversation]:
    return list(
        db.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        ).scalars().all()
    )


def get_conversation(db: Session, user: User, conversation_id: str) -> Conversation | None:
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        return None
    return conv


def send_message(db: Session, user: User, conversation_id: str, text: str) -> Message:
    conv = get_conversation(db, user, conversation_id)
    if conv is None:
        raise ChatServiceError("گفتگو یافت نشد.", status_code=404)

    # Save user message
    user_msg = Message(
        conversation_id=conv.id,
        role=MessageRole.user,
        content=text,
    )
    db.add(user_msg)
    db.flush()

    # Build short history summary for context
    recent = db.execute(
        select(Message)
        .where(Message.conversation_id == conv.id)
        .order_by(Message.created_at.desc())
        .limit(6)
    ).scalars().all()
    recent = list(reversed(recent))
    history_parts = []
    for m in recent[:-1]:  # exclude the just-added user message for summary
        role = "کاربر" if m.role == MessageRole.user else "مربی"
        history_parts.append(f"{role}: {m.content[:200]}")
    history_summary = " | ".join(history_parts[-4:]) if history_parts else ""

    try:
        ai_reply = ai_service.chat_iraqi_coach(
            db, user.id, text, history_summary=history_summary
        )
        reply_text = ai_reply.reply
        if ai_reply.corrections:
            reply_text += "\n\n📝 اصلاحات:\n" + "\n".join(f"• {c}" for c in ai_reply.corrections)
        if ai_reply.notes:
            reply_text += f"\n\n💡 {ai_reply.notes}"
    except Exception as exc:
        logger.exception("AI chat failed")
        reply_text = "متأسفانه الان نمی‌توانم پاسخ بدهم. لطفاً کمی بعد دوباره تلاش کنید."

    assistant_msg = Message(
        conversation_id=conv.id,
        role=MessageRole.assistant,
        content=reply_text,
    )
    db.add(assistant_msg)

    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg


def delete_conversation(db: Session, user: User, conversation_id: str) -> bool:
    conv = get_conversation(db, user, conversation_id)
    if conv is None:
        return False
    db.delete(conv)
    db.commit()
    return True
