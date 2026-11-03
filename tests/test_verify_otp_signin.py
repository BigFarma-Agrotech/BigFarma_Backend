"""Verifying a sign-up OTP signs the user in; reset codes and reused codes don't."""
from datetime import datetime, timedelta, timezone

from features.auth.models import OTPCode, OTPMedium, OTPType
from features.auth.models import User
from tests.test_order_notifications_api import env  # noqa: F401


import pytest


@pytest.fixture(autouse=True)
def aware_expiry(monkeypatch):
    # SQLite drops the timezone Postgres keeps, which breaks the service's
    # aware-vs-naive expiry check; hand back the tz the column declares
    from repositories.otp_repository import OTPRepository
    original = OTPRepository.get_valid_otp

    def get_valid_otp(self, *args, **kwargs):
        record = original(self, *args, **kwargs)
        if record and record.expires_at.tzinfo is None:
            record.expires_at = record.expires_at.replace(tzinfo=timezone.utc)
        return record

    monkeypatch.setattr(OTPRepository, "get_valid_otp", get_valid_otp)


def _db():
    from database import get_db
    import main
    return next(main.app.dependency_overrides[get_db]())


def _add_new_user_with_code(code, otp_type=OTPType.VERIFICATION):
    from features.auth.models import UserCategory
    db = _db()
    user = User(email="new@example.com", password="x", category=UserCategory.CONSUMER,
                is_verified=False, is_active=True)
    db.add(user)
    db.commit()
    db.add(OTPCode(user_id=user.id, code=code, medium=OTPMedium.EMAIL, otp_type=otp_type,
                   expires_at=datetime.now(timezone.utc) + timedelta(minutes=10)))
    db.commit()
    return user.id


def _verify(client, code, otp_type="verification"):
    return client.post("/api/v1/auth/verify-otp", json={
        "email": "new@example.com", "medium": "email", "code": code, "otp_type": otp_type,
    })


def test_verification_code_signs_user_in_once(env):
    client = env[0]
    user_id = _add_new_user_with_code("123456")

    res = _verify(client, "123456")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["user_category"] == "consumer"
    assert body["profile_setup"] is False

    db = _db()
    assert db.get(User, user_id).is_verified
    # The code is spent: it can't mint a second session
    assert db.query(OTPCode).filter(OTPCode.user_id == user_id).count() == 0
    assert _verify(client, "123456").status_code == 400


def test_wrong_code_gets_no_token(env):
    client = env[0]
    _add_new_user_with_code("123456")
    res = _verify(client, "654321")
    assert res.status_code == 400
    assert "access_token" not in res.json()


def test_password_reset_code_does_not_sign_in(env):
    client = env[0]
    _add_new_user_with_code("111111", otp_type=OTPType.PASSWORD_RESET)
    res = _verify(client, "111111", otp_type="password_reset")
    assert res.status_code == 200, res.text
    assert "access_token" not in res.json()
