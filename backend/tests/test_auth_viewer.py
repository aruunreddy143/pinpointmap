from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core import security
from app.models import AppUser, OtpChallenge

pytestmark = pytest.mark.db

MOBILE = "98765 43210"
EMAIL = "priya@example.com"


def request_code(client, identifier):
    return client.post("/auth/otp/request", json={"identifier": identifier})


def last_code(outbox) -> str:
    return outbox.sent[-1].body.split(" ")[0]


def verify(client, identifier, code):
    return client.post("/auth/otp/verify", json={"identifier": identifier, "code": code})


def sign_up(client, outbox, identifier, name="Priya Kumar"):
    request_code(client, identifier)
    r = verify(client, identifier, last_code(outbox))
    assert r.status_code == 202
    return client.post(
        "/auth/otp/signup",
        json={"identifier": identifier, "signup_token": r.json()["signup_token"], "name": name},
    )


@pytest.mark.parametrize(
    "identifier,channel,sent_to",
    [
        (MOBILE, "sms", "+919876543210"),
        ("+91-98765-43210", "sms", "+919876543210"),
        ("Priya@Example.com", "email", EMAIL),
    ],
)
def test_a_code_goes_by_sms_for_a_mobile_number_and_by_email_for_an_email(
    client, outbox, identifier, channel, sent_to
):
    assert request_code(client, identifier).status_code == 204
    msg = outbox.sent[-1]
    assert (msg.channel, msg.to) == (channel, sent_to)
    assert len(last_code(outbox)) == 6 and last_code(outbox).isdigit()


@pytest.mark.parametrize("bad", ["12345", "5876543210", "priya@", "hello", "   "])
def test_neither_a_mobile_number_nor_an_email_is_refused(client, bad):
    r = request_code(client, bad + "xx" if len(bad.strip()) < 3 else bad)
    assert r.status_code == 422


def test_new_mobile_signs_up_then_signs_in_again(client, outbox):
    r = sign_up(client, outbox, MOBILE)
    assert r.status_code == 200 and r.json()["user"]["kind"] == "viewer" and r.json()["user"]["roles"] == []
    again = None
    request_code(client, MOBILE)
    again = verify(client, "+91 98765 43210", last_code(outbox))  # a different way of writing the same number
    assert again.status_code == 200 and again.json()["user"]["name"] == "Priya Kumar"


def test_new_email_signs_up_and_the_email_is_not_leaked_back(client, outbox):
    r = sign_up(client, outbox, EMAIL)
    assert r.status_code == 200
    assert r.json()["user"]["email"] is None  # viewers' contact details are never echoed


def test_the_mobile_number_is_stored_only_as_a_keyed_hash(client, outbox, db_session):
    sign_up(client, outbox, MOBILE)
    user = db_session.scalars(select(AppUser).where(AppUser.name == "Priya Kumar")).one()
    assert user.mobile_hash == security.keyed_hash("mobile", "+919876543210")
    assert user.email is None
    challenges = db_session.scalars(select(OtpChallenge)).all()
    assert all("9876543210" not in (c.identifier_hash + c.code_hash) for c in challenges)


def test_requesting_a_code_gives_the_same_answer_for_known_and_unknown_identifiers(client, outbox):
    sign_up(client, outbox, EMAIL)
    known = request_code(client, EMAIL)
    unknown = request_code(client, "stranger@example.com")
    assert known.status_code == unknown.status_code == 204 and known.content == unknown.content


def test_wrong_codes_count_down_then_lock_even_for_the_right_code(client, outbox):
    request_code(client, EMAIL)
    right = last_code(outbox)
    wrong = "000000" if right != "000000" else "111111"
    msgs = [verify(client, EMAIL, wrong).json()["message"] for _ in range(4)]
    assert "4 tries left" in msgs[0] and "1 try left" in msgs[3]
    locked = verify(client, EMAIL, wrong)
    assert locked.status_code == 429
    assert verify(client, EMAIL, right).status_code == 429


def test_a_new_code_unlocks_after_lockout_and_old_codes_stop_working(client, outbox):
    request_code(client, EMAIL)
    first = last_code(outbox)
    wrong = "000000" if first != "000000" else "111111"
    for _ in range(5):
        verify(client, EMAIL, wrong)
    request_code(client, EMAIL)
    second = last_code(outbox)
    if second != first:
        assert verify(client, EMAIL, first).status_code == 401
    assert verify(client, EMAIL, second).status_code in (200, 202)


def test_a_code_works_once(client, outbox):
    request_code(client, EMAIL)
    code = last_code(outbox)
    assert verify(client, EMAIL, code).status_code == 202
    assert verify(client, EMAIL, code).status_code == 401


def test_an_expired_code_is_refused(client, outbox, db_session):
    request_code(client, EMAIL)
    ch = db_session.scalars(select(OtpChallenge)).one()
    ch.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.flush()
    assert verify(client, EMAIL, last_code(outbox)).status_code == 401


def test_only_three_codes_per_identifier_per_window(client):
    statuses = [request_code(client, EMAIL).status_code for _ in range(4)]
    assert statuses == [204, 204, 204, 429]


def test_signup_token_cannot_be_used_for_another_identifier(client, outbox):
    request_code(client, EMAIL)
    token = verify(client, EMAIL, last_code(outbox)).json()["signup_token"]
    r = client.post(
        "/auth/otp/signup",
        json={"identifier": "someone.else@example.com", "signup_token": token, "name": "Mallory"},
    )
    assert r.status_code == 401


def test_staff_emails_cannot_sign_in_through_the_viewer_flow(client, outbox, db_session):
    from app.models.enums import Role
    from tests.factories import make_jurisdiction, make_staff

    make_staff(db_session, Role.ADMIN, make_jurisdiction(db_session), email="boss@pinpoint.test")
    request_code(client, "boss@pinpoint.test")
    r = verify(client, "boss@pinpoint.test", last_code(outbox))
    assert r.status_code == 401


def test_a_viewer_cannot_use_staff_endpoints(client, outbox):
    token = sign_up(client, outbox, EMAIL).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/auth/me", headers=h).status_code == 200
    r = client.post(
        "/admin/invites",
        headers=h,
        json={
            "email": "x@pinpoint.test",
            "role": "registrar",
            "jurisdiction_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert r.status_code == 403
