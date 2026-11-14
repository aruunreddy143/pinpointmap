import pyotp
import pytest
from sqlalchemy import select

from app.core import security
from app.models import AppUser, AuditEvent
from app.models.enums import Role
from tests.factories import STAFF_PASSWORD, make_jurisdiction, make_staff

pytestmark = pytest.mark.db


def login(client, email, password=STAFF_PASSWORD):
    return client.post("/auth/staff/login", json={"email": email, "password": password})


def totp(client, ticket, secret, code=None):
    return client.post("/auth/staff/totp", json={"ticket": ticket, "code": code or pyotp.TOTP(secret).now()})


@pytest.fixture
def registrar(db_session):
    j = make_jurisdiction(db_session)
    user, secret = make_staff(db_session, Role.REGISTRAR, j, email="arun@pinpoint.test")
    return user, secret, j


def test_password_then_authenticator_code_signs_in(client, registrar):
    user, secret, j = registrar
    r1 = login(client, "arun@pinpoint.test")
    assert r1.status_code == 200
    r2 = totp(client, r1.json()["ticket"], secret)
    assert r2.status_code == 200
    body = r2.json()
    assert body["user"]["roles"] == [{"role": "registrar", "jurisdiction_id": str(j.id)}]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["id"] == str(user.id)
    # The refresh token is an httpOnly cookie, never in the body.
    assert "refresh" not in r2.text
    assert (
        "httponly" in r2.headers["set-cookie"].lower()
        and "samesite=strict" in r2.headers["set-cookie"].lower()
    )


def test_wrong_password_and_unknown_email_look_identical(client, registrar):
    a = login(client, "arun@pinpoint.test", "Wrong-password-1")
    b = login(client, "nobody@pinpoint.test", "Wrong-password-1")
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_the_authenticator_code_is_required_and_checked(client, registrar):
    _, secret, _ = registrar
    ticket = login(client, "arun@pinpoint.test").json()["ticket"]
    assert totp(client, ticket, secret, "000000").status_code == 401
    # No password-only session exists: protected routes refuse the ticket.
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {ticket}"}).status_code == 401


def test_five_wrong_passwords_lock_the_account_even_for_the_right_password(client, registrar):
    for _ in range(4):
        assert login(client, "arun@pinpoint.test", "Wrong-password-1").status_code == 401
    assert login(client, "arun@pinpoint.test", "Wrong-password-1").status_code == 429
    assert login(client, "arun@pinpoint.test").status_code == 429


def test_wrong_authenticator_codes_also_count_toward_lockout(client, registrar):
    _, secret, _ = registrar
    ticket = login(client, "arun@pinpoint.test").json()["ticket"]
    codes = [totp(client, ticket, secret, "000000").status_code for _ in range(5)]
    assert codes[:4] == [401] * 4 and codes[4] == 429
    assert login(client, "arun@pinpoint.test").status_code == 429


def test_inactive_staff_cannot_sign_in(client, db_session, registrar):
    user, _, _ = registrar
    user.is_active = False
    db_session.flush()
    assert login(client, "arun@pinpoint.test").status_code == 401


def test_the_authenticator_secret_is_encrypted_at_rest(db_session, registrar):
    user, secret, _ = registrar
    stored = db_session.scalar(select(AppUser.totp_secret).where(AppUser.id == user.id))
    assert stored != secret and secret not in stored
    assert security.decrypt_secret(stored) == secret


def test_sign_in_and_failures_are_audited_and_failures_survive_the_error(client, db_session, registrar):
    user, secret, _ = registrar
    login(client, "arun@pinpoint.test", "Wrong-password-1")
    ticket = login(client, "arun@pinpoint.test").json()["ticket"]
    totp(client, ticket, secret)
    actions = db_session.scalars(select(AuditEvent.action).where(AuditEvent.actor_id == user.id)).all()
    assert "auth.login_failed" in actions and "auth.login" in actions


def test_audit_details_never_contain_the_email_or_password(client, db_session, registrar):
    login(client, "arun@pinpoint.test", "Wrong-password-1")
    rows = db_session.scalars(select(AuditEvent.detail)).all()
    blob = str(rows)
    assert "arun@pinpoint.test" not in blob and "Wrong-password-1" not in blob


def test_login_attempts_are_rate_limited_per_client(client):
    statuses = [login(client, f"x{i}@pinpoint.test", "Wrong-password-1").status_code for i in range(32)]
    assert statuses[:30] == [401] * 30 and statuses[30:] == [429, 429]
