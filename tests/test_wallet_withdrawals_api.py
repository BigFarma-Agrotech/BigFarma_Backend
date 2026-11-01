"""Farmers link bank accounts (checked with Paystack) and withdraw by Paystack transfer."""
import hashlib
import hmac
import json

import pytest

from config import settings
from features.payments import paystack
from features.wallet import services as wallet_services
from features.wallet.models import TransactionCategory, Wallet
from features.wallet.services import WalletService
from tests.test_order_notifications_api import env  # noqa: F401
from tests.test_stock import _db

API = "/api/v1/wallet"
BANKS = [
    {"name": "Guaranty Trust Bank", "code": "058", "active": True, "type": "nuban"},
    {"name": "Access Bank", "code": "044", "active": True, "type": "nuban"},
    {"name": "Old Bank", "code": "999", "active": False, "type": "nuban"},
]
ACCOUNTS = {("0123456789", "058"): "ADA OBI FARMS", ("9876543210", "044"): "ADA OBI"}


@pytest.fixture()
def gateway(monkeypatch):
    """Fake Paystack payouts; `state['transfer_status']` sets how transfers come back."""
    state = {"transfers": [], "transfer_status": "success", "transfer_error": None}
    wallet_services._BANKS_CACHE.update(banks=None, fetched_at=None)

    async def list_banks():
        return BANKS

    async def resolve_account(account_number, bank_code):
        if (account_number, bank_code) not in ACCOUNTS:
            raise paystack.PaystackError("Could not resolve account name")
        return {"account_number": account_number, "account_name": ACCOUNTS[(account_number, bank_code)]}

    async def create_recipient(account_name, account_number, bank_code):
        return {"recipient_code": f"RCP_{account_number}"}

    async def initiate_transfer(amount_kobo, recipient_code, reference, reason):
        if state["transfer_error"]:
            raise paystack.PaystackError(state["transfer_error"])
        state["transfers"].append({"amount": amount_kobo, "recipient": recipient_code, "reference": reference})
        return {"status": state["transfer_status"], "transfer_code": f"TRF_{len(state['transfers'])}"}

    monkeypatch.setattr(paystack, "list_banks", list_banks)
    monkeypatch.setattr(paystack, "resolve_account", resolve_account)
    monkeypatch.setattr(paystack, "create_transfer_recipient", create_recipient)
    monkeypatch.setattr(paystack, "initiate_transfer", initiate_transfer)
    return state


def _fund(farmer_id, amount):
    db = _db()
    service = WalletService(db)
    try:
        wallet = service.get_wallet_by_farmer_id(farmer_id)
    except Exception:
        wallet = service.create_wallet(farmer_id)
    service.credit_wallet(wallet.id, amount, TransactionCategory.PRODUCT_SALE, "Sale")


def _balance(farmer_id):
    db = _db()
    return db.query(Wallet).filter(Wallet.farmer_id == farmer_id).one().balance


def _webhook(client, event, reference):
    body = json.dumps({"event": event, "data": {"reference": reference}}).encode()
    signature = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), body, hashlib.sha512).hexdigest()
    return client.post("/api/v1/payments/paystack/webhook", content=body,
                       headers={"x-paystack-signature": signature, "Content-Type": "application/json"})


def _link(client, account_number="0123456789", bank_code="058"):
    return client.post(f"{API}/bank-accounts", json={"account_number": account_number, "bank_code": bank_code})


def test_only_farmers_use_the_wallet(env, gateway):
    client, current, _, consumer_id, _, _ = env
    current["user_id"] = consumer_id
    assert client.get(f"{API}/bank-accounts").status_code == 403


def test_link_bank_accounts(env, gateway):
    client, current, farmer_id, _, _, _ = env
    current["user_id"] = farmer_id

    banks = client.get(f"{API}/banks").json()["banks"]
    assert banks == [{"name": "Access Bank", "code": "044"}, {"name": "Guaranty Trust Bank", "code": "058"}]

    looked_up = client.post(f"{API}/bank-accounts/verify", json={"account_number": "0123456789", "bank_code": "058"})
    assert looked_up.status_code == 200 and looked_up.json()["account_name"] == "ADA OBI FARMS"

    wrong = client.post(f"{API}/bank-accounts/verify", json={"account_number": "1111111111", "bank_code": "058"})
    assert wrong.status_code == 400 and "couldn't find account" in wrong.json()["detail"]
    assert _link(client, bank_code="999").status_code == 400  # not a listed bank
    assert client.post(f"{API}/bank-accounts", json={"account_number": "123", "bank_code": "058"}).status_code == 422

    first = _link(client)
    assert first.status_code == 200, first.text
    assert first.json()["account_name"] == "ADA OBI FARMS" and first.json()["is_primary"] is True
    assert _link(client).status_code == 409  # already linked

    second = _link(client, "9876543210", "044").json()
    assert second["is_primary"] is False
    assert client.put(f"{API}/bank-accounts/{second['id']}/primary").json()["is_primary"] is True
    accounts = client.get(f"{API}/bank-accounts").json()
    assert [a["id"] for a in accounts] == [second["id"], first.json()["id"]]  # primary first

    # Removing the primary account promotes the other one
    assert client.delete(f"{API}/bank-accounts/{second['id']}").status_code == 204
    accounts = client.get(f"{API}/bank-accounts").json()
    assert len(accounts) == 1 and accounts[0]["is_primary"] is True


def test_withdraw_sends_transfer_less_fee(env, gateway):
    client, current, farmer_id, _, _, _ = env
    current["user_id"] = farmer_id
    _fund(farmer_id, 10_000)
    account = _link(client).json()

    res = client.post(f"{API}/withdraw", json={"amount": 2000, "bank_account_id": account["id"],
                                               "idempotency_key": "key-1"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["status"], body["fee"], body["final_amount"]) == ("completed", 30, 1970)
    assert gateway["transfers"] == [{"amount": 197000, "recipient": "RCP_0123456789", "reference": body["reference"]}]
    assert _balance(farmer_id) == 8000

    # A retry with the same key doesn't pay out twice
    again = client.post(f"{API}/withdraw", json={"amount": 2000, "bank_account_id": account["id"],
                                                 "idempotency_key": "key-1"})
    assert again.json()["id"] == body["id"] and len(gateway["transfers"]) == 1

    assert client.get(f"{API}/withdrawals").json()[0]["id"] == body["id"]

    too_much = client.post(f"{API}/withdraw", json={"amount": 9000, "bank_account_id": account["id"]})
    assert too_much.status_code == 400 and too_much.json()["error"] == "insufficient_funds"
    too_little = client.post(f"{API}/withdraw", json={"amount": 100, "bank_account_id": account["id"]})
    assert too_little.status_code == 422


def test_failed_transfer_refunds_wallet(env, gateway):
    client, current, farmer_id, _, _, _ = env
    current["user_id"] = farmer_id
    _fund(farmer_id, 5_000)
    account = _link(client).json()

    gateway["transfer_error"] = "Your balance is not enough to fulfil this request"
    res = client.post(f"{API}/withdraw", json={"amount": 3000, "bank_account_id": account["id"]})
    assert res.status_code == 502 and "back in your wallet" in res.json()["detail"]
    assert _balance(farmer_id) == 5000
    assert client.get(f"{API}/withdrawals").json()[0]["status"] == "failed"


def test_pending_transfer_settles_by_webhook(env, gateway):
    client, current, farmer_id, _, _, _ = env
    current["user_id"] = farmer_id
    _fund(farmer_id, 5_000)
    account = _link(client).json()
    gateway["transfer_status"] = "pending"

    first = client.post(f"{API}/withdraw", json={"amount": 1000, "bank_account_id": account["id"]}).json()
    assert first["status"] == "processing" and _balance(farmer_id) == 4000
    # Only one withdrawal at a time
    assert client.post(f"{API}/withdraw", json={"amount": 1000, "bank_account_id": account["id"]}).status_code == 409
    # Can't unlink an account with a transfer in flight
    assert client.delete(f"{API}/bank-accounts/{account['id']}").status_code == 409

    assert _webhook(client, "transfer.success", first["reference"]).status_code == 200
    assert client.get(f"{API}/withdrawal/{first['id']}").json()["status"] == "completed"

    second = client.post(f"{API}/withdraw", json={"amount": 1000, "bank_account_id": account["id"]}).json()
    assert _balance(farmer_id) == 3000
    _webhook(client, "transfer.failed", second["reference"])
    _webhook(client, "transfer.failed", second["reference"])  # Paystack retries: refund only once
    assert client.get(f"{API}/withdrawal/{second['id']}").json()["status"] == "failed"
    assert _balance(farmer_id) == 4000

    # A completed transfer the bank later reverses goes back to the wallet too
    _webhook(client, "transfer.reversed", first["reference"])
    assert _balance(farmer_id) == 5000
