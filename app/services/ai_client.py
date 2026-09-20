"""
Low-level AI provider HTTP client. OpenAI-compatible.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from app.core.config import settings


class AIProviderError(Exception):
    def __init__(self, message: str, is_retryable: bool = True, status_code: int | None = None):
        self.message = message
        self.is_retryable = is_retryable
        self.status_code = status_code
        super().__init__(message)


@dataclass
class ProviderConfig:
    label: str
    base_url: str
    api_key: str
    model: str


@dataclass
class ChatCompletionResult:
    content: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


def get_primary_config() -> ProviderConfig:
    return ProviderConfig(
        label="primary",
        base_url=settings.ai_base_url,
        api_key=settings.ai_api_key,
        model=settings.ai_model,
    )


def get_fallback_config() -> ProviderConfig | None:
    if not settings.ai_fallback_base_url or not settings.ai_fallback_api_key:
        return None
    return ProviderConfig(
        label="fallback",
        base_url=settings.ai_fallback_base_url,
        api_key=settings.ai_fallback_api_key,
        model=settings.ai_fallback_model or settings.ai_model,
    )


def chat_completion(
    provider: ProviderConfig,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.4,
    max_tokens: int = 1000,
    force_json: bool = True,
) -> ChatCompletionResult:
    if not provider.api_key:
        raise AIProviderError(
            f"AI provider '{provider.label}' has no API key configured.",
            is_retryable=False,
        )

    url = f"{provider.base_url.rstrip('/')}/chat/completions"
    payload: dict = {
        "model": provider.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if force_json:
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
    }

    start = time.monotonic()
    try:
        resp = httpx.post(
            url, json=payload, headers=headers,
            timeout=settings.ai_request_timeout_seconds,
        )
    except httpx.TimeoutException as exc:
        raise AIProviderError(f"Timeout calling {provider.label} AI provider", is_retryable=True) from exc
    except httpx.HTTPError as exc:
        raise AIProviderError(f"Network error calling {provider.label} AI provider: {exc}", is_retryable=True) from exc

    latency_ms = int((time.monotonic() - start) * 1000)

    if resp.status_code == 429:
        raise AIProviderError("Rate limited by provider", is_retryable=True, status_code=429)
    if resp.status_code in (401, 403):
        raise AIProviderError("AI provider authentication failed", is_retryable=False, status_code=resp.status_code)
    if resp.status_code >= 500:
        raise AIProviderError(f"AI provider server error: {resp.status_code}", is_retryable=True, status_code=resp.status_code)
    if resp.status_code >= 400:
        raise AIProviderError(f"AI provider rejected request: {resp.text[:300]}", is_retryable=False, status_code=resp.status_code)

    try:
        body = resp.json()
        content = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        input_tokens = usage.get("prompt_tokens", _estimate_tokens(system_prompt + user_prompt))
        output_tokens = usage.get("completion_tokens", _estimate_tokens(content))
    except (KeyError, IndexError, ValueError) as exc:
        raise AIProviderError(f"Unexpected response shape from provider: {exc}", is_retryable=False) from exc

    return ChatCompletionResult(
        content=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
    )


def transcribe_audio(provider: ProviderConfig, file_path: str, language: str | None = None) -> str:
    if not provider.api_key:
        raise AIProviderError(f"AI provider '{provider.label}' has no API key configured.", is_retryable=False)

    url = f"{provider.base_url.rstrip('/')}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {provider.api_key}"}
    data = {"model": "whisper-1"}
    if language:
        data["language"] = language

    try:
        with open(file_path, "rb") as f:
            files = {"file": (file_path, f, "audio/mpeg")}
            resp = httpx.post(
                url, headers=headers, data=data, files=files,
                timeout=settings.ai_request_timeout_seconds * 2,
            )
    except httpx.TimeoutException as exc:
        raise AIProviderError("Timeout during transcription", is_retryable=True) from exc
    except httpx.HTTPError as exc:
        raise AIProviderError(f"Network error during transcription: {exc}", is_retryable=True) from exc

    if resp.status_code >= 500:
        raise AIProviderError(f"Transcription server error: {resp.status_code}", is_retryable=True)
    if resp.status_code >= 400:
        raise AIProviderError(f"Transcription request rejected: {resp.text[:300]}", is_retryable=False)

    body = resp.json()
    return body.get("text", "")


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
