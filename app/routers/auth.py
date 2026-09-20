"""
Authentication router.
Implements: register, login, refresh (with rotation), logout, current user.
Security features: Argon2 hashing, short-lived access tokens, rotating
refresh tokens stored hashed, account lockout after repeated failures,
rate limiting, audit logging.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.models import AuditLog, RefreshToken, RoleEnum, User
from app.core.security import (
    create_access_token,
    decode_token,
    generate_refresh_token_raw,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    rate_limiter,
    refresh_token_expiry,
    verify_password,
)
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "khatib_refresh"
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _log_audit(db: Session, user_id: str | None, action: str, detail: str, ip: str) -> None:
    db.add(AuditLog(user_id=user_id, action=action, detail=detail, ip_address=ip))


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain or None,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        domain=settings.cookie_domain or None,
        path="/api/auth",
    )


def _issue_tokens(db: Session, response: Response, user: User, request: Request) -> TokenResponse:
    access_token = create_access_token(user.id, user.role.value)

    raw_refresh = generate_refresh_token_raw()
    token_row = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw_refresh),
        user_agent=request.headers.get("user-agent", "")[:500],
        ip_address=_client_ip(request),
        expires_at=refresh_token_expiry(),
    )
    db.add(token_row)
    _set_refresh_cookie(response, raw_refresh)

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)

    if not rate_limiter.allow(f"register:{ip}", max_requests=5, window_seconds=3600):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "تعداد درخواست بیش از حد مجاز است.")

    existing = db.execute(select(User).where(User.email == payload.email.lower())).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "این ایمیل قبلاً ثبت شده است.")

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        password_algo="argon2",
        name=payload.name,
        role=RoleEnum.user,
    )
    db.add(user)
    db.flush()
    _log_audit(db, user.id, "register", f"user registered: {user.email}", ip)
    db.commit()
    db.refresh(user)

    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = _client_ip(request)

    if not rate_limiter.allow(f"login:{ip}", max_requests=10, window_seconds=300):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "تعداد تلاش بیش از حد مجاز است.")
    if not rate_limiter.allow(f"login:{payload.email.lower()}", max_requests=5, window_seconds=300):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "تعداد تلاش بیش از حد مجاز است.")

    user = db.execute(select(User).where(User.email == payload.email.lower())).scalar_one_or_none()

    generic_error = HTTPException(status.HTTP_401_UNAUTHORIZED, "ایمیل یا رمز عبور نادرست است.")

    if user is None:
        raise generic_error

    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_423_LOCKED, "حساب کاربری موقتاً قفل شده است. بعداً تلاش کنید.")

    if not user.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "حساب کاربری غیرفعال است.")

    if not verify_password(payload.password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= MAX_FAILED_LOGINS:
            from datetime import timedelta
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
            _log_audit(db, user.id, "account_locked", "too many failed logins", ip)
        db.commit()
        raise generic_error

    # success
    user.failed_login_count = 0
    user.locked_until = None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    _log_audit(db, user.id, "login", "successful login", ip)

    tokens = _issue_tokens(db, response, user, request)
    db.commit()
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    khatib_refresh: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: Session = Depends(get_db),
):
    if not khatib_refresh:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "نشست معتبر نیست.")

    token_hash = hash_refresh_token(khatib_refresh)
    token_row = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).scalar_one_or_none()

    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "نشست معتبر نیست.")

    if token_row is None:
        raise invalid

    # Reuse detection: if a rotated (already-replaced) token is presented again,
    # this indicates possible token theft — revoke the entire chain.
    if token_row.revoked or token_row.replaced_by is not None:
        user_id = token_row.user_id
        all_tokens = db.execute(
            select(RefreshToken).where(RefreshToken.user_id == user_id, RefreshToken.revoked == False)  # noqa: E712
        ).scalars().all()
        for t in all_tokens:
            t.revoked = True
            t.revoked_at = datetime.now(timezone.utc)
        _log_audit(db, user_id, "refresh_reuse_detected", "revoked all sessions", _client_ip(request))
        db.commit()
        raise invalid

    if token_row.expires_at < datetime.now(timezone.utc):
        raise invalid

    user = db.get(User, token_row.user_id)
    if user is None or not user.active:
        raise invalid

    # Rotate: revoke old, issue new
    token_row.revoked = True
    token_row.revoked_at = datetime.now(timezone.utc)

    new_raw = generate_refresh_token_raw()
    new_token_row = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(new_raw),
        user_agent=request.headers.get("user-agent", "")[:500],
        ip_address=_client_ip(request),
        expires_at=refresh_token_expiry(),
    )
    db.add(new_token_row)
    db.flush()
    token_row.replaced_by = new_token_row.id

    _set_refresh_cookie(response, new_raw)

    access_token = create_access_token(user.id, user.role.value)
    db.commit()

    return TokenResponse(access_token=access_token, expires_in=settings.access_token_expire_minutes * 60)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    khatib_refresh: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    db: Session = Depends(get_db),
):
    if khatib_refresh:
        token_hash = hash_refresh_token(khatib_refresh)
        token_row = db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        ).scalar_one_or_none()
        if token_row and not token_row.revoked:
            token_row.revoked = True
            token_row.revoked_at = datetime.now(timezone.utc)
            db.commit()

    _clear_refresh_cookie(response)
    return None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "احراز هویت لازم است.")

    token = auth_header.split(" ", 1)[1]
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "توکن نامعتبر است.")

    user = db.get(User, payload["sub"])
    if user is None or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "کاربر یافت نشد.")

    return user


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)
