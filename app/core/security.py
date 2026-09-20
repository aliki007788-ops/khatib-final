"""
Security core: password hashing, JWT tokens, rate limiting.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash
from jose import JWTError, jwt

from app.core.config import settings

# =========================================================
# Password Hashing
# =========================================================

_argon2_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # 64 MB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def _pepper(raw_password: str) -> str:
    """Combine password with server-side pepper via HMAC (not plain concat)."""
    return hmac.new(
        settings.password_pepper.encode("utf-8"),
        raw_password.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def hash_password(raw_password: str) -> str:
    peppered = _pepper(raw_password)
    return _argon2_hasher.hash(peppered)


def verify_password(raw_password: str, stored_hash: str) -> bool:
    """
    Verifies Argon2 hashes. Supports legacy PBKDF2 hashes
    (format: 'pbkdf2$<iterations>$<salt_hex>$<hash_hex>') for backward
    compatibility with data migrated from an older system.
    """
    peppered = _pepper(raw_password)

    if stored_hash.startswith("pbkdf2$"):
        try:
            _, iterations_s, salt_hex, hash_hex = stored_hash.split("$")
            iterations = int(iterations_s)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(hash_hex)
            derived = hashlib.pbkdf2_hmac(
                "sha256", peppered.encode("utf-8"), salt, iterations
            )
            return hmac.compare_digest(derived, expected)
        except (ValueError, IndexError):
            return False

    try:
        return _argon2_hasher.verify(stored_hash, peppered)
    except (VerifyMismatchError, InvalidHash):
        return False


def needs_rehash(stored_hash: str) -> bool:
    if stored_hash.startswith("pbkdf2$"):
        return True
    try:
        return _argon2_hasher.check_needs_rehash(stored_hash)
    except InvalidHash:
        return True


# =========================================================
# JWT Tokens
# =========================================================

ALGORITHM = "HS256"


def create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        return None


def generate_refresh_token_raw() -> str:
    """Cryptographically random opaque token (not JWT) for refresh tokens."""
    return secrets.token_urlsafe(64)


def hash_refresh_token(raw_token: str) -> str:
    """Refresh tokens are stored hashed, similar to passwords but simpler (HMAC-SHA256)
    since they're already high-entropy random strings."""
    return hmac.new(
        settings.jwt_secret.encode("utf-8"),
        raw_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)


# =========================================================
# Rate Limiting (Redis-backed with in-memory fallback)
# =========================================================

class RateLimiter:
    """
    Sliding-window-ish fixed-window rate limiter.
    Uses Redis if available; falls back to in-process memory
    (NOTE: memory fallback is per-process only — acceptable for
    single-instance dev, NOT sufficient for multi-instance production
    without Redis).
    """

    def __init__(self) -> None:
        self._redis = None
        self._memory: dict[str, list[float]] = {}
        self._init_redis()

    def _init_redis(self) -> None:
        try:
            import redis

            client = redis.from_url(settings.redis_url, socket_connect_timeout=1)
            client.ping()
            self._redis = client
        except Exception:
            self._redis = None

    def allow(self, key: str, max_requests: int, window_seconds: int) -> bool:
        if self._redis is not None:
            return self._allow_redis(key, max_requests, window_seconds)
        return self._allow_memory(key, max_requests, window_seconds)

    def _allow_redis(self, key: str, max_requests: int, window_seconds: int) -> bool:
        try:
            pipe = self._redis.pipeline()
            now = time.time()
            window_key = f"ratelimit:{key}"
            pipe.zremrangebyscore(window_key, 0, now - window_seconds)
            pipe.zadd(window_key, {str(now): now})
            pipe.zcard(window_key)
            pipe.expire(window_key, window_seconds)
            _, _, count, _ = pipe.execute()
            return count <= max_requests
        except Exception:
            return self._allow_memory(key, max_requests, window_seconds)

    def _allow_memory(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.time()
        bucket = self._memory.setdefault(key, [])
        bucket[:] = [t for t in bucket if now - t < window_seconds]
        if len(bucket) >= max_requests:
            return False
        bucket.append(now)
        return True


rate_limiter = RateLimiter()
