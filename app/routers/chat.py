from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import User
from app.routers.auth import get_current_user
from app.schemas.chat import (
    ConversationListItem,
    ConversationResponse,
    CreateConversationRequest,
    MessageResponse,
    SendMessageRequest,
)
from app.services import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: CreateConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = chat_service.create_conversation(db, current_user, payload.title)
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        summary=conv.summary,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[],
    )


@router.get("/conversations", response_model=list[ConversationListItem])
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    convs = chat_service.list_conversations(db, current_user)
    return [ConversationListItem.model_validate(c) for c in convs]


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = chat_service.get_conversation(db, current_user, conversation_id)
    if conv is None:
        raise HTTPException(404, "گفتگو یافت نشد.")
    messages = [
        MessageResponse(id=m.id, role=m.role.value, content=m.content, created_at=m.created_at)
        for m in sorted(conv.messages, key=lambda x: x.created_at)
    ]
    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        summary=conv.summary,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages,
    )


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
def send_message(
    conversation_id: str,
    payload: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        msg = chat_service.send_message(db, current_user, conversation_id, payload.text)
    except chat_service.ChatServiceError as exc:
        raise HTTPException(exc.status_code, exc.message)
    return MessageResponse(
        id=msg.id,
        role=msg.role.value,
        content=msg.content,
        created_at=msg.created_at,
    )


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ok = chat_service.delete_conversation(db, current_user, conversation_id)
    if not ok:
        raise HTTPException(404, "گفتگو یافت نشد.")
    return None
