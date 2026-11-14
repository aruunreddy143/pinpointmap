import re
from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from sqlalchemy import select

from app.models import Invite, RefreshToken
from app.models.enums import Role
from tests.factories import STAFF_PASSWORD, make_jurisdiction, make_staff

pytestmark = pytest.mark.db

CSRF = {"x-pinpoint-csrf": "1"}


def sign_in(client, email, secret, password=STAFF_PASSWORD):
    ticket = client.post("/auth/staff/login", json={"email": email, "password": password}).json()["ticket"]
    return client.post("/auth/staff/totp", json={"ticket": ticket, "code": pyotp.TOTP(secret).now()})


@pytest.fixture
def admin(db_session):
    j = make_jurisdiction(db_session)
    user, secret = make_staff(db_session, Role.ADMIN, j, email="admin@pinpoint.test")
    return user, secret, j


# ---------- refresh tokens ----------
def test_refresh_rotates_and_reusing_an_old_token_kills_the_whole_family(client, admin):
    _, secret, _ = admin
    r = sign_in(client, "admin@pinpoint.test", secret)
    first = client.cookies.get("pinpoint_refresh")
    assert first
    second_resp = client.post("/auth/refresh", headers=CSRF)
    assert second_resp.status_code == 200
    second = client.cookies.get("pinpoint_refresh")
    assert second != first
    # Someone presents the first (already used) token again: reuse is detected.
    client.cookies.set("pinpoint_refresh", first, path="/auth")
    assert client.post("/auth/refresh", headers=CSRF).status_code == 401
    # ... and the newest token in that family no longer works either.
    client.cookies.set("pinpoint_refresh", second, path="/auth")
    assert client.post("/auth/refresh", headers=CSRF).status_code == 401
    assert r.status_code == 200


def test_refresh_needs_the_csrf_header_and_a_cookie(client, admin):
    _, secret, _ = admin
    sign_in(client, "admin@pinpoint.test", secret)
    assert client.post("/auth/refresh").status_code == 401  # no header
    client.cookies.clear()
    assert client.post("/auth/refresh", headers=CSRF).status_code == 401  # no cookie


def test_logout_revokes_the_session(client, admin, db_session):
    _, secret, _ = admin
    sign_in(client, "admin@pinpoint.test", secret)
    token = client.cookies.get("pinpoint_refresh")
    assert client.post("/auth/logout", headers=CSRF).status_code == 204
    client.cookies.set("pinpoint_refresh", token, path="/auth")
    assert client.post("/auth/refresh", headers=CSRF).status_code == 401
    assert all(t.revoked_at for t in db_session.scalars(select(RefreshToken)))


def test_an_expired_refresh_token_is_refused(client, admin, db_session):
    _, secret, _ = admin
    sign_in(client, "admin@pinpoint.test", secret)
    for t in db_session.scalars(select(RefreshToken)):
        t.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.flush()
    assert client.post("/auth/refresh", headers=CSRF).status_code == 401


def test_access_tokens_must_be_the_right_kind(client, admin):
    from app.core import security

    forged = security.make_jwt("something_else", "00000000-0000-0000-0000-000000000000", 5)
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


# ---------- invites ----------
def make_invite(client, admin, email="new.person@pinpoint.test", role="verifier", jurisdiction=None):
    user, secret, j = admin
    access = sign_in(client, "admin@pinpoint.test", secret).json()["access_token"]
    return client.post(
        "/admin/invites",
        headers={"Authorization": f"Bearer {access}"},
        json={"email": email, "role": role, "jurisdiction_id": str(jurisdiction or j.id)},
    )


def token_from(outbox) -> str:
    return re.search(r"/invite/(\S+)", outbox.sent[-1].body).group(1)


def test_invite_to_working_account_end_to_end(client, outbox, admin):
    created = make_invite(client, admin)
    assert created.status_code == 201
    token = token_from(outbox)
    assert created.json()["invite_url"].endswith(token)
    assert outbox.sent[-1].to == "new.person@pinpoint.test"

    client.cookies.clear()
    info = client.get(f"/auth/invites/{token}").json()
    assert info["email"] == "new.person@pinpoint.test" and info["role"] == "verifier"
    code = pyotp.TOTP(info["totp_secret"]).now()
    accepted = client.post(
        f"/auth/invites/{token}/accept",
        json={"name": "New Person", "password": "Str0ngPassword!", "totp_code": code},
    )
    assert accepted.status_code == 200
    assert accepted.json()["user"]["roles"][0]["role"] == "verifier"

    # The new person can now sign in the normal way, with the same authenticator secret.
    again = sign_in(client, "new.person@pinpoint.test", info["totp_secret"], "Str0ngPassword!")
    assert again.status_code == 200


def test_an_invite_link_works_only_once(client, outbox, admin):
    make_invite(client, admin)
    token = token_from(outbox)
    secret = client.get(f"/auth/invites/{token}").json()["totp_secret"]
    body = {"name": "New Person", "password": "Str0ngPassword!", "totp_code": pyotp.TOTP(secret).now()}
    assert client.post(f"/auth/invites/{token}/accept", json=body).status_code == 200
    assert client.post(f"/auth/invites/{token}/accept", json=body).status_code == 404
    assert client.get(f"/auth/invites/{token}").status_code == 404


def test_accepting_needs_a_good_password_and_the_right_authenticator_code(client, outbox, admin):
    make_invite(client, admin)
    token = token_from(outbox)
    secret = client.get(f"/auth/invites/{token}").json()["totp_secret"]
    good = pyotp.TOTP(secret).now()
    assert (
        client.post(
            f"/auth/invites/{token}/accept", json={"name": "N P", "password": "weak", "totp_code": good}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/auth/invites/{token}/accept",
            json={"name": "N P", "password": "Str0ngPassword!", "totp_code": "000000"},
        ).status_code
        == 422
    )


def test_an_expired_or_unknown_invite_is_not_found(client, outbox, admin, db_session):
    make_invite(client, admin)
    token = token_from(outbox)
    db_session.scalars(select(Invite)).one().expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.flush()
    assert client.get(f"/auth/invites/{token}").status_code == 404
    assert client.get("/auth/invites/not-a-real-token").status_code == 404


def test_only_a_manager_of_that_jurisdiction_can_invite_there(client, admin, db_session):
    other = make_jurisdiction(db_session)
    assert make_invite(client, admin, jurisdiction=other.id).status_code == 403


def test_a_registrar_cannot_invite_anyone(client, db_session):
    j = make_jurisdiction(db_session)
    _, secret = make_staff(db_session, Role.REGISTRAR, j, email="reg@pinpoint.test")
    access = sign_in(client, "reg@pinpoint.test", secret).json()["access_token"]
    r = client.post(
        "/admin/invites",
        headers={"Authorization": f"Bearer {access}"},
        json={"email": "x@pinpoint.test", "role": "printer", "jurisdiction_id": str(j.id)},
    )
    assert r.status_code == 403


def test_an_admin_cannot_grant_a_role_above_their_own(client, admin):
    assert make_invite(client, admin, role="super_admin").status_code == 403


def test_duplicate_email_and_duplicate_pending_invite_are_refused(client, admin):
    assert make_invite(client, admin, email="admin@pinpoint.test").status_code == 409
    assert make_invite(client, admin).status_code == 201
    assert make_invite(client, admin).status_code == 409


# ---------- password reset ----------
def test_forgot_password_answers_the_same_for_every_email(client, outbox, admin):
    known = client.post("/auth/password/forgot", json={"email": "admin@pinpoint.test"})
    unknown = client.post("/auth/password/forgot", json={"email": "nobody@pinpoint.test"})
    assert known.status_code == unknown.status_code == 204
    assert len(outbox.sent) == 1 and outbox.sent[0].to == "admin@pinpoint.test"


def test_reset_works_once_changes_the_password_and_signs_everyone_out(client, outbox, admin, db_session):
    _, secret, _ = admin
    sign_in(client, "admin@pinpoint.test", secret)
    old_refresh = client.cookies.get("pinpoint_refresh")
    client.post("/auth/password/forgot", json={"email": "admin@pinpoint.test"})
    token = re.search(r"/reset/(\S+)", outbox.sent[-1].body).group(1)

    assert client.post("/auth/password/reset", json={"token": token, "password": "weak"}).status_code == 422
    assert (
        client.post("/auth/password/reset", json={"token": token, "password": "BrandNewPass1!"}).status_code
        == 204
    )
    assert (
        client.post("/auth/password/reset", json={"token": token, "password": "AnotherPass1!!"}).status_code
        == 401
    )  # used

    client.cookies.set("pinpoint_refresh", old_refresh, path="/auth")
    assert client.post("/auth/refresh", headers=CSRF).status_code == 401
    assert (
        client.post(
            "/auth/staff/login", json={"email": "admin@pinpoint.test", "password": STAFF_PASSWORD}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/auth/staff/login", json={"email": "admin@pinpoint.test", "password": "BrandNewPass1!"}
        ).status_code
        == 200
    )


def test_a_bad_reset_token_is_refused(client):
    assert (
        client.post("/auth/password/reset", json={"token": "nope", "password": "BrandNewPass1!"}).status_code
        == 401
    )
