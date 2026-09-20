from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.models import User
from app.routers.auth import get_current_user
from app.schemas.speech import SpeechListItem, SpeechResponse, TextSpeechRequest
from app.services import speech_service

router = APIRouter(prefix="/api/speech", tags=["speech"])


def _to_response(speech) -> SpeechResponse:
    analysis = speech.analysis
    return SpeechResponse(
        id=speech.id,
        mode=speech.mode.value,
        status=speech.status.value,
        topic_label=speech.topic_label,
        input_text=speech.input_text,
        transcript=speech.transcript,
        duration_sec=speech.duration_sec,
        overall_score=analysis.overall_score if analysis else None,
        dimension_scores=analysis.dimension_scores if analysis else None,
        strengths=analysis.ai_strengths if analysis else None,
        weaknesses=analysis.ai_weaknesses if analysis else None,
        improvements=analysis.ai_improvements if analysis else None,
        structure_notes=analysis.structure_notes if analysis else None,
        next_practice=analysis.next_practice if analysis else None,
        created_at=speech.created_at,
        completed_at=speech.completed_at,
    )


@router.post("/text", response_model=SpeechResponse, status_code=status.HTTP_201_CREATED)
def create_text_speech(
    payload: TextSpeechRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        speech = speech_service.create_text_speech(
            db, current_user, payload.topic_label, payload.text
        )
    except speech_service.SpeechServiceError as exc:
        raise HTTPException(exc.status_code, exc.message)
    return _to_response(speech)


@router.post("/audio", response_model=SpeechResponse, status_code=status.HTTP_201_CREATED)
async def create_audio_speech(
    topic_label: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    try:
        speech = speech_service.create_audio_speech(
            db,
            current_user,
            topic_label,
            content,
            file.filename or "audio.mp3",
            file.content_type or "audio/mpeg",
        )
    except speech_service.SpeechServiceError as exc:
        raise HTTPException(exc.status_code, exc.message)
    return _to_response(speech)


@router.get("", response_model=list[SpeechListItem])
def list_my_speeches(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    speeches = speech_service.list_speeches(db, current_user)
    result = []
    for s in speeches:
        result.append(SpeechListItem(
            id=s.id,
            mode=s.mode.value,
            status=s.status.value,
            topic_label=s.topic_label,
            overall_score=s.analysis.overall_score if s.analysis else None,
            created_at=s.created_at,
            completed_at=s.completed_at,
        ))
    return result


@router.get("/{speech_id}", response_model=SpeechResponse)
def get_speech(
    speech_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    speech = speech_service.get_speech(db, current_user, speech_id)
    if speech is None:
        raise HTTPException(404, "تمرین یافت نشد.")
    return _to_response(speech)


@router.delete("/{speech_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_speech(
    speech_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ok = speech_service.delete_speech(db, current_user, speech_id)
    if not ok:
        raise HTTPException(404, "تمرین یافت نشد.")
    return None
