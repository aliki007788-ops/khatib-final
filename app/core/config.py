"""
Central application configuration.
Loads from environment variables / .env file.
NEVER hardcode secrets here.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- General ----
    environment: str = Field(default="development")
    app_name: str = Field(default="Khatib")
    app_version: str = Field(default="5.0.0")
    debug: bool = Field(default=False)

    # ---- Database ----
    database_url: str = Field(default="sqlite:///./data/khatib.db")

    # ---- Redis ----
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ---- Security ----
    jwt_secret: str = Field(...)
    password_pepper: str = Field(...)
    access_token_expire_minutes: int = Field(default=15)
    refresh_token_expire_days: int = Field(default=30)
    cookie_secure: bool = Field(default=False)
    cookie_domain: str | None = Field(default=None)

    # ---- CORS ----
    cors_origins: str = Field(default="")
    allowed_hosts: str = Field(default="localhost,127.0.0.1")

    # ---- AI ----
    ai_base_url: str = Field(default="https://api.openai.com/v1")
    ai_api_key: str = Field(default="")
    ai_model: str = Field(default="gpt-4o-mini")
    ai_fallback_base_url: str = Field(default="")
    ai_fallback_api_key: str = Field(default="")
    ai_fallback_model: str = Field(default="")
    ai_request_timeout_seconds: float = Field(default=30.0)
    ai_max_retries: int = Field(default=2)
    ai_retry_base_delay_seconds: float = Field(default=1.0)
    ai_max_context_tokens: int = Field(default=6000)

    # ---- Payment ----
    payment_provider: str = Field(default="demo")
    zarinpal_merchant_id: str = Field(default="")
    zarinpal_callback_url: str = Field(default="")
    zarinpal_sandbox: bool = Field(default=True)

    # ---- Eitaa ----
    eitaa_bot_token: str = Field(default="")
    eitaa_webhook_secret: str = Field(default="")

    # ---- Storage ----
    storage_backend: str = Field(default="local")
    storage_local_path: str = Field(default="./uploads")
    storage_endpoint: str = Field(default="")
    storage_access_key: str = Field(default="")
    storage_secret_key: str = Field(default="")
    storage_bucket: str = Field(default="khatib-audio")

    # ---- Production flags ----
    redis_required: bool = Field(default=True)
    worker_required: bool = Field(default=True)
    metrics_enabled: bool = Field(default=True)
    sentry_dsn: str = Field(default="")

    # ---- Limits ----
    max_upload_size_bytes: int = Field(default=15 * 1024 * 1024)
    max_audio_duration_seconds: int = Field(default=600)
    ffmpeg_path: str = Field(default="ffmpeg")
    ffprobe_path: str = Field(default="ffprobe")

    @field_validator("jwt_secret", "password_pepper")
    @classmethod
    def secrets_must_not_be_placeholder(cls, v: str) -> str:
        placeholders = {
            "CHANGE_ME_GENERATE_RANDOM_64_CHARS",
            "CHANGE_ME_GENERATE_RANDOM_32_CHARS",
            "",
        }
        if v in placeholders:
            raise ValueError(
                "Insecure or placeholder secret detected in JWT_SECRET / "
                "PASSWORD_PEPPER. Generate real random secrets before running "
                "the application. Use: python -c \"import secrets; "
                "print(secrets.token_urlsafe(64))\""
            )
        return v

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        """
        Cross-field production safety checks.
        These are intentionally FATAL (raise) rather than warnings,
        because a misconfigured production deployment here means
        real money / real user data at risk.
        """
        if self.is_production:
            if self.payment_provider == "demo":
                raise ValueError(
                    "PAYMENT_PROVIDER=demo is not allowed in production. "
                    "Set PAYMENT_PROVIDER=zarinpal with real credentials."
                )
            if not self.cookie_secure:
                raise ValueError(
                    "COOKIE_SECURE must be true in production (requires HTTPS)."
                )
            if self.payment_provider == "zarinpal" and not self.zarinpal_merchant_id:
                raise ValueError(
                    "ZARINPAL_MERCHANT_ID is required when "
                    "PAYMENT_PROVIDER=zarinpal in production."
                )
            if self.database_url.startswith("sqlite"):
                raise ValueError(
                    "SQLite is forbidden in production."
                )
            if self.storage_backend == "local":
                raise ValueError(
                    "Local storage is forbidden in production. "
                    "Use S3-compatible storage."
                )
            if len(self.jwt_secret) < 40:
                raise ValueError(
                    "JWT_SECRET must contain at least 40 characters."
                )
            if len(self.password_pepper) < 32:
                raise ValueError(
                    "PASSWORD_PEPPER must contain at least 32 characters."
                )
            if not self.allowed_hosts_list:
                raise ValueError(
                    "ALLOWED_HOSTS must be configured in production."
                )
        return self

    @property
    def cors_origins_list(self) -> List[str]:
        if not self.cors_origins:
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_hosts_list(self) -> List[str]:
        return [
            item.strip()
            for item in self.allowed_hosts.split(",")
            if item.strip()
        ]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
