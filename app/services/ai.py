"""
High-level AI orchestration service.
Retry + Fallback + Structured Validation + Logging.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.core.ai_pricing import estimate_cost_usd
from app.core.config import settings
from app.core.models import AIProviderUsed, AIRequestLog, AIRequestStatus, AITaskType
from app.schemas.ai import ChatReplyResponse, SpeechAnalysisResponse, TranslationResponse
from app.services import ai_client
from app.services.ai_client import AIProviderError, ChatCompletionResult, ProviderConfig
from app.services.ai_prompts import (
    PROMPT_VERSIONS,
    build_chat_iraqi_coach_prompt,
    build_speech_analysis_prompt,
    build_translation_prompt,
)

logger = logging.getLogger("khatib.ai")

T = TypeVar("T", bound=BaseModel)


class AIServiceError(Exception):
    def __init__(self, message: str, user_facing_message: str = "سرویس هوش مصنوعی موقتاً در دسترس نیست."):
        self.user_facing_message = user_facing_message
        super().__init__(message)


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(json)?", "", raw)
        raw = re.sub(r"```$", "", raw)
        raw = raw.strip()
    return json.loads(raw)


def _call_with_retry(
    provider: ProviderConfig,
    system_prompt: str,
    user_prompt: str,
) -> tuple[ChatCompletionResult, int]:
    last_error: AIProviderError | None = None

    for attempt in range(settings.ai_max_retries + 1):
        try:
            result = ai_client.chat_completion(provider, system_prompt, user_prompt)
            return result, attempt
        except AIProviderError as exc:
            last_error = exc
            if not exc.is_retryable or attempt == settings.ai_max_retries:
                raise
            delay = settings.ai_retry_base_delay_seconds * (2 ** attempt)
            logger.warning(
                "AI call to %s failed (attempt %d/%d): %s — retrying in %.1fs",
                provider.label, attempt + 1, settings.ai_max_retries + 1, exc.message, delay,
            )
            time.sleep(delay)

    assert last_error is not None
    raise last_error


def _call_with_fallback(system_prompt: str, user_prompt: str) -> tuple[ChatCompletionResult, AIProviderUsed, str, int]:
    primary = ai_client.get_primary_config()
    try:
        result, retries = _call_with_retry(primary, system_prompt, user_prompt)
        return result, AIProviderUsed.primary, primary.model, retries
    except AIProviderError as primary_error:
        logger.error("Primary AI provider exhausted retries: %s", primary_error.message)

        fallback = ai_client.get_fallback_config()
        if fallback is None:
            raise AIServiceError(f"Primary provider failed and no fallback configured: {primary_error.message}") from primary_error

        try:
            result, retries = _call_with_retry(fallback, system_prompt, user_prompt)
            logger.warning("Fallback AI provider used successfully after primary failure.")
            return result, AIProviderUsed.fallback, fallback.model, retries
        except AIProviderError as fallback_error:
            raise AIServiceError(
                f"Both primary and fallback providers failed. Primary: {primary_error.message}; Fallback: {fallback_error.message}"
            ) from fallback_error


def _parse_structured(raw: str, model_cls: type[T]) -> T:
    try:
        data = _extract_json(raw)
        return model_cls.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AIServiceError(f"Structured output validation failed: {exc}") from exc


def _log_request(
    db: Session,
    user_id: str | None,
    task_type: AITaskType,
    prompt_version: str,
    provider_used: AIProviderUsed,
    model: str,
    status: AIRequestStatus,
    latency_ms: int,
    retry_count: int,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error_message: str | None = None,
) -> None:
    cost = None
    if input_tokens is not None and output_tokens is not None:
        cost = estimate_cost_usd(model, input_tokens, output_tokens)

    log = AIRequestLog(
        user_id=user_id,
        task_type=task_type,
        prompt_version=prompt_version,
        provider_used=provider_used,
        model=model,
        status=status,
        error_message=error_message,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        latency_ms=latency_ms,
        retry_count=retry_count,
    )
    db.add(log)
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to write AIRequestLog")


def analyze_speech(
    db: Session,
    user_id: str | None,
    topic: str,
    text: str,
) -> SpeechAnalysisResponse:
    system, user = build_speech_analysis_prompt(topic, text)
    prompt_version = PROMPT_VERSIONS["speech_analysis"]

    try:
        result, provider_used, model, retries = _call_with_fallback(system, user)
        parsed = _parse_structured(result.content, SpeechAnalysisResponse)
        _log_request(
            db, user_id, AITaskType.speech_analysis, prompt_version,
            provider_used, model, AIRequestStatus.success,
            result.latency_ms, retries,
            result.input_tokens, result.output_tokens,
        )
        return parsed
    except AIServiceError as exc:
        _log_request(
            db, user_id, AITaskType.speech_analysis, prompt_version,
            AIProviderUsed.primary, settings.ai_model, AIRequestStatus.failed,
            0, 0, error_message=str(exc),
        )
        raise
    except Exception as exc:
        _log_request(
            db, user_id, AITaskType.speech_analysis, prompt_version,
            AIProviderUsed.primary, settings.ai_model, AIRequestStatus.validation_failed,
            0, 0, error_message=str(exc),
        )
        raise AIServiceError(str(exc)) from exc


def chat_iraqi_coach(
    db: Session,
    user_id: str | None,
    user_message: str,
    history_summary: str = "",
) -> ChatReplyResponse:
    system, user = build_chat_iraqi_coach_prompt(user_message, history_summary)
    prompt_version = PROMPT_VERSIONS["chat_iraqi_coach"]

    try:
        result, provider_used, model, retries = _call_with_fallback(system, user)
        parsed = _parse_structured(result.content, ChatReplyResponse)
        _log_request(
            db, user_id, AITaskType.chat_reply, prompt_version,
            provider_used, model, AIRequestStatus.success,
            result.latency_ms, retries,
            result.input_tokens, result.output_tokens,
        )
        return parsed
    except AIServiceError as exc:
        _log_request(
            db, user_id, AITaskType.chat_reply, prompt_version,
            AIProviderUsed.primary, settings.ai_model, AIRequestStatus.failed,
            0, 0, error_message=str(exc),
        )
        raise


def translate(
    db: Session,
    user_id: str | None,
    text: str,
    direction: str = "fa_to_iq",
) -> TranslationResponse:
    system, user = build_translation_prompt(text, direction)
    prompt_version = PROMPT_VERSIONS["translation_fa_iq"]

    try:
        result, provider_used, model, retries = _call_with_fallback(system, user)
        parsed = _parse_structured(result.content, TranslationResponse)
        _log_request(
            db, user_id, AITaskType.translation, prompt_version,
            provider_used, model, AIRequestStatus.success,
            result.latency_ms, retries,
            result.input_tokens, result.output_tokens,
        )
        return parsed
    except AIServiceError as exc:
        _log_request(
            db, user_id, AITaskType.translation, prompt_version,
            AIProviderUsed.primary, settings.ai_model, AIRequestStatus.failed,
            0, 0, error_message=str(exc),
        )
        raise
