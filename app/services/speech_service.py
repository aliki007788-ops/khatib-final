"""
Speech analysis orchestration (text + audio).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.models import (
    AudioAsset,
    JobStatus,
    ProcessingJob,
    Speech,
    SpeechAnalysis,
    SpeechMode,
    SpeechStatus,
    User,
)
from app.services import ai as ai_service
from app.services.storage import get_storage_backend, StorageError
from app.services.usage import try_consume_speech

logger = logging.getLogger("khatib.speech")

ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
}


class SpeechServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def create_text_speech(
    db: Session,
    user: User,
    topic_label: str,
    text: str,
) -> Speech:
    usage = try_consume_speech(db, user, audio_seconds=0)
    if not usage.allowed:
        raise SpeechServiceError(
            "سهمیه تحلیل سخنرانی این ماه به پایان رسیده است.",
            status_code=402,
        )

    speech = Speech(
        user_id=user.id,
        mode=SpeechMode.text,
        status=SpeechStatus.processing,
        topic_label=topic_label,
        input_text=text,
    )
    db.add(speech)
    db.flush()

    try:
        analysis_result = ai_service.analyze_speech(
            db, user.id, topic_label, text
        )

        analysis = SpeechAnalysis(
            speech_id=speech.id,
            overall_score=analysis_result.score,
            dimension_scores={
                "content": analysis_result.score,
                "structure": max(0, analysis_result.score - 5),
                "fluency": max(0, analysis_result.score - 3),
            },
            ai_strengths=analysis_result.strengths,
            ai_weaknesses=analysis_result.weaknesses,
            ai_improvements=analysis_result.improvements,
            structure_notes=analysis_result.structure_notes,
            next_practice=analysis_result.next_practice,
        )
        db.add(analysis)

        speech.status = SpeechStatus.completed
        speech.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(speech)
        return speech

    except Exception as exc:
        logger.exception("Speech analysis failed for speech %s", speech.id)
        speech.status = SpeechStatus.failed
        speech.failure_reason = str(exc)[:1000]
        db.commit()
        raise SpeechServiceError(
            "تحلیل سخنرانی با خطا مواجه شد. لطفاً دوباره تلاش کنید.",
            status_code=502,
        ) from exc


def create_audio_speech(
    db: Session,
    user: User,
    topic_label: str,
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> Speech:
    if content_type not in ALLOWED_AUDIO_TYPES and not any(
        filename.lower().endswith(ext) for ext in (".mp3", ".wav", ".webm", ".ogg", ".m4a", ".mp4")
    ):
        raise SpeechServiceError("فرمت فایل صوتی پشتیبانی نمی‌شود.")

    if len(file_bytes) > settings.max_upload_size_bytes:
        raise SpeechServiceError("حجم فایل بیش از حد مجاز است.")

    estimated_seconds = max(1, len(file_bytes) // 2000)
    if estimated_seconds > settings.max_audio_duration_seconds:
        raise SpeechServiceError("مدت زمان فایل صوتی بیش از حد مجاز است.")

    usage = try_consume_speech(db, user, audio_seconds=estimated_seconds)
    if not usage.allowed:
        raise SpeechServiceError(
            "سهمیه تحلیل سخنرانی این ماه به پایان رسیده است.",
            status_code=402,
        )

    storage = get_storage_backend()
    try:
        storage_key = storage.save(file_bytes, filename, content_type)
    except StorageError as exc:
        raise SpeechServiceError(f"خطا در ذخیره فایل: {exc}") from exc

    asset = AudioAsset(
        user_id=user.id,
        storage_key=storage_key,
        original_filename=filename,
        content_type=content_type,
        size_bytes=len(file_bytes),
        duration_sec=float(estimated_seconds),
    )
    db.add(asset)
    db.flush()

    speech = Speech(
        user_id=user.id,
        mode=SpeechMode.audio,
        status=SpeechStatus.pending,
        topic_label=topic_label,
        audio_asset_id=asset.id,
        duration_sec=float(estimated_seconds),
    )
    db.add(speech)
    db.flush()

    job = ProcessingJob(
        speech_id=speech.id,
        status=JobStatus.queued,
    )
    db.add(job)
    db.commit()
    db.refresh(speech)

    try:
        _process_audio_speech(db, speech, asset)
    except Exception:
        logger.exception("Inline audio processing failed; job remains queued")

    db.refresh(speech)
    return speech


def _process_audio_speech(db: Session, speech: Speech, asset: AudioAsset) -> None:
    speech.status = SpeechStatus.processing
    db.commit()

    storage = get_storage_backend()
    local_path = storage.get_local_path(asset.storage_key)
    if local_path is None:
        raise SpeechServiceError("پردازش صوتی فقط روی storage محلی پشتیبانی می‌شود در این نسخه.")

    from app.services.ai_client import get_primary_config, transcribe_audio, AIProviderError

    provider = get_primary_config()
    try:
        transcript = transcribe_audio(provider, local_path, language="fa")
    except AIProviderError as exc:
        speech.status = SpeechStatus.failed
        speech.failure_reason = f"خطا در تبدیل گفتار به متن: {exc.message}"[:1000]
        db.commit()
        raise

    speech.transcript = transcript
    speech.input_text = transcript

    if not transcript or len(transcript.strip()) < 10:
        speech.status = SpeechStatus.failed
        speech.failure_reason = "متن استخراج‌شده از صوت خیلی کوتاه یا خالی است."
        db.commit()
        return

    try:
        analysis_result = ai_service.analyze_speech(
            db, speech.user_id, speech.topic_label or "سخنرانی", transcript
        )
        analysis = SpeechAnalysis(
            speech_id=speech.id,
            overall_score=analysis_result.score,
            dimension_scores={
                "content": analysis_result.score,
                "structure": max(0, analysis_result.score - 5),
                "fluency": max(0, analysis_result.score - 3),
                "pace": max(0, analysis_result.score - 4),
            },
            ai_strengths=analysis_result.strengths,
            ai_weaknesses=analysis_result.weaknesses,
            ai_improvements=analysis_result.improvements,
            structure_notes=analysis_result.structure_notes,
            next_practice=analysis_result.next_practice,
        )
        db.add(analysis)
        speech.status = SpeechStatus.completed
        speech.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        speech.status = SpeechStatus.failed
        speech.failure_reason = str(exc)[:1000]
        db.commit()
        raise


def get_speech(db: Session, user: User, speech_id: str) -> Speech | None:
    speech = db.get(Speech, speech_id)
    if speech is None or speech.user_id != user.id:
        return None
    return speech


def list_speeches(db: Session, user: User, limit: int = 50) -> list[Speech]:
    return list(
        db.execute(
            select(Speech)
            .where(Speech.user_id == user.id)
            .order_by(Speech.created_at.desc())
            .limit(limit)
        ).scalars().all()
    )


def delete_speech(db: Session, user: User, speech_id: str) -> bool:
    speech = db.get(Speech, speech_id)
    if speech is None or speech.user_id != user.id:
        return False

    if speech.audio_asset:
        try:
            storage = get_storage_backend()
            storage.delete(speech.audio_asset.storage_key)
        except StorageError:
            pass

    db.delete(speech)
    db.commit()
    return True
