"""Thin client for the two Paystack calls checkout needs, plus webhook signature checks."""
import hashlib
import hmac
import logging
from typing import Any, Dict, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 20


class PaystackError(Exception):
    """A Paystack call failed; `message` is safe to show the buyer."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def is_configured() -> bool:
    return bool(settings.PAYSTACK_SECRET_KEY)


def _headers() -> Dict[str, str]:
    if not is_configured():
        raise PaystackError("Payments are not available right now. Please try again later.", 503)
    return {"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}", "Content-Type": "application/json"}


async def _request(method: str, path: str, json: Optional[dict] = None) -> Dict[str, Any]:
    url = f"{settings.PAYSTACK_BASE_URL.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.request(method, url, headers=_headers(), json=json)
    except httpx.HTTPError as exc:
        logger.error("Paystack %s %s failed: %s", method, path, exc)
        raise PaystackError("We couldn't reach the payment service. Please try again.")

    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400 or not body.get("status"):
        logger.error("Paystack %s %s -> %s %s", method, path, response.status_code, body)
        raise PaystackError(body.get("message") or "The payment service returned an error. Please try again.")
    return body.get("data") or {}


async def initialize_transaction(email: str, amount_kobo: int, reference: str,
                                 callback_url: str, metadata: dict) -> Dict[str, Any]:
    """Start a transaction; the buyer pays at the returned authorization_url."""
    return await _request("POST", "/transaction/initialize", {
        "email": email,
        "amount": amount_kobo,
        "currency": "NGN",
        "reference": reference,
        "callback_url": callback_url,
        "metadata": metadata,
    })


async def verify_transaction(reference: str) -> Dict[str, Any]:
    """Paystack's record of the transaction: status, amount (kobo), currency, ..."""
    return await _request("GET", f"/transaction/verify/{reference}")


async def refund_transaction(reference: str) -> Dict[str, Any]:
    """Refund a successful transaction in full (Paystack sends it back to the payer's card/bank)."""
    return await _request("POST", "/refund", {"transaction": reference})


def valid_webhook_signature(raw_body: bytes, signature: Optional[str]) -> bool:
    """Paystack signs webhooks with HMAC-SHA512 of the raw body using the secret key."""
    if not signature or not is_configured():
        return False
    expected = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)
