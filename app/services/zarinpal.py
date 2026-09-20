"""
ZarinPal payment gateway client.
Isolated adapter — if the payment provider changes in the future,
only this file (and services/billing.py's calls to it) need updating.

IMPORTANT: ZarinPal amounts are in Rial in their v4 API, while KHATIB
prices are stored in Toman (common Iranian convention). Conversion
(x10) happens at the boundary of this client — nowhere else.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.core.config import settings

logger = logging.getLogger("khatib.zarinpal")

_BASE = "https://sandbox.zarinpal.com" if settings.zarinpal_sandbox else "https://api.zarinpal.com"
_GATEWAY_BASE = "https://sandbox.zarinpal.com" if settings.zarinpal_sandbox else "https://www.zarinpal.com"

REQUEST_URL = f"{_BASE}/pg/v4/payment/request.json"
VERIFY_URL = f"{_BASE}/pg/v4/payment/verify.json"


class ZarinPalError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"ZarinPal error {code}: {message}")


@dataclass
class PaymentRequestResult:
    authority: str
    payment_url: str


@dataclass
class VerifyResult:
    ref_id: str
    already_verified: bool  # True if ZarinPal code == 101 (idempotent duplicate verify)


def request_payment(amount_toman: int, description: str, callback_url: str, mobile: str = "") -> PaymentRequestResult:
    """
    Initiates a payment request. Raises ZarinPalError on failure.
    Caller (services/billing.py) is responsible for persisting the
    resulting authority BEFORE redirecting the user.
    """
    amount_rial = amount_toman * 10

    payload = {
        "merchant_id": settings.zarinpal_merchant_id,
        "amount": amount_rial,
        "callback_url": callback_url,
        "description": description,
    }
    if mobile:
        payload["metadata"] = {"mobile": mobile}

    try:
        resp = httpx.post(REQUEST_URL, json=payload, timeout=15.0)
        resp.raise_for_status()
        body = resp.json()
    except httpx.HTTPError as exc:
        logger.error("ZarinPal request_payment network error: %s", exc)
        raise ZarinPalError(-1, "خطا در ارتباط با درگاه پرداخت") from exc

    data = body.get("data") or {}
    code = data.get("code")

    if code != 100:
        errors = body.get("errors") or {}
        message = errors.get("message", "خطای نامشخص از درگاه پرداخت")
        raise ZarinPalError(code or -1, message)

    authority = data["authority"]
    payment_url = f"{_GATEWAY_BASE}/pg/StartPay/{authority}"
    return PaymentRequestResult(authority=authority, payment_url=payment_url)


def verify_payment(amount_toman: int, authority: str) -> VerifyResult:
    """
    Verifies a payment with the provider. Raises ZarinPalError on failure.

    ZarinPal code 100 = newly verified success.
    ZarinPal code 101 = already verified before (provider-side idempotency) —
    treated as success here, but callers MUST still guard against
    duplicate subscription activation at the application level.
    """
    amount_rial = amount_toman * 10

    payload = {
        "merchant_id": settings.zarinpal_merchant_id,
        "amount": amount_rial,
        "authority": authority,
    }

    try:
        resp = httpx.post(VERIFY_URL, json=payload, timeout=15.0)
        resp.raise_for_status()
        body = resp.json()
    except httpx.HTTPError as exc:
        logger.error("ZarinPal verify_payment network error: %s", exc)
        raise ZarinPalError(-1, "خطا در تایید پرداخت") from exc

    data = body.get("data") or {}
    code = data.get("code")

    if code not in (100, 101):
        errors = body.get("errors") or {}
        message = errors.get("message", "پرداخت تایید نشد")
        raise ZarinPalError(code or -1, message)

    return VerifyResult(ref_id=str(data.get("ref_id", "")), already_verified=(code == 101))
