"""Thin client for the Paystack calls checkout and farmer payouts need, plus webhook signature checks."""
import hashlib
import hmac
from urllib.parse import urlencode
import logging
from typing import Any, Dict, Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 20


class PaystackError(Exception):
    """A Paystack call failed; `message` is safe to show the buyer. `upstream_status` is
    the HTTP status Paystack answered with (None when it couldn't be reached)."""

    def __init__(self, message: str, status_code: int = 502, upstream_status: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.upstream_status = upstream_status


def is_configured() -> bool:
    return bool(settings.PAYSTACK_SECRET_KEY)


def is_test_mode() -> bool:
    """A test secret key: no real money moves, and Paystack allows only 3 lookups of
    real bank accounts a day (its Test Bank, code 001, has no limit)."""
    return (settings.PAYSTACK_SECRET_KEY or "").startswith("sk_test_")


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
        raise PaystackError(body.get("message") or "The payment service returned an error. Please try again.",
                            upstream_status=response.status_code)
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


# ---------------------------------------------------------------------------
# Payouts: banks, account lookup, transfer recipients and transfers
# ---------------------------------------------------------------------------

async def list_banks() -> list:
    """Nigerian banks that can receive transfers: [{name, code, ...}]."""
    return await _request("GET", "/bank?country=nigeria&currency=NGN&perPage=200")


async def resolve_account(account_number: str, bank_code: str) -> Dict[str, Any]:
    """The name on a bank account: {account_number, account_name}. Errors if it doesn't exist."""
    query = urlencode({"account_number": account_number, "bank_code": bank_code})
    return await _request("GET", f"/bank/resolve?{query}")


async def create_transfer_recipient(account_name: str, account_number: str, bank_code: str) -> Dict[str, Any]:
    """Register a bank account to send transfers to; returns {recipient_code, ...}."""
    return await _request("POST", "/transferrecipient", {
        "type": "nuban",
        "name": account_name,
        "account_number": account_number,
        "bank_code": bank_code,
        "currency": "NGN",
    })


async def initiate_transfer(amount_kobo: int, recipient_code: str, reference: str, reason: str) -> Dict[str, Any]:
    """Send money from the Paystack balance; returns {status: success|pending|otp|..., transfer_code, ...}."""
    return await _request("POST", "/transfer", {
        "source": "balance",
        "amount": amount_kobo,
        "recipient": recipient_code,
        "reference": reference,
        "reason": reason,
        "currency": "NGN",
    })


def valid_webhook_signature(raw_body: bytes, signature: Optional[str]) -> bool:
    """Paystack signs webhooks with HMAC-SHA512 of the raw body using the secret key."""
    if not signature or not is_configured():
        return False
    expected = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)
