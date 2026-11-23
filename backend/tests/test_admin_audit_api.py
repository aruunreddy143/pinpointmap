"""Admin reads (jurisdictions, staff + invites) and the audit-events listing."""

import pytest

from app.core.settings import get_settings
from app.models.enums import Role
from tests.factories import make_staff
from tests.world import active_place, register

pytestmark = pytest.mark.db


# ---------- jurisdictions and staff ----------
def test_jurisdictions_are_the_callers_areas_plus_everything_below(client, world, db_session):
    district_admin = client.get("/admin/jurisdictions", headers=world.h("admin")).json()
    assert [j["name"] for j in district_admin] == ["Bengaluru Urban"]
    state_admin, _ = make_staff(db_session, Role.ADMIN, world.ka)
    from tests.world import auth

    rows = client.get("/admin/jurisdictions", headers=auth(state_admin)).json()
    assert sorted(j["name"] for j in rows) == ["Bengaluru Urban", "Karnataka", "Mysuru"]
    assert {j["level"] for j in rows} == {"state", "district"}
    ka = next(j for j in rows if j["name"] == "Karnataka")
    assert ka["parent_id"] is None and all(j["parent_id"] == ka["id"] for j in rows if j is not ka)


def test_a_state_admin_can_invite_into_a_district_below_their_grant(client, world, db_session, outbox):
    from tests.world import auth

    state_admin, _ = make_staff(db_session, Role.ADMIN, world.ka)
    r = client.post(
        "/admin/invites",
        json={"email": "new.person@pinpoint.test", "role": "registrar", "jurisdiction_id": str(world.mys.id)},
        headers=auth(state_admin),
    )
    assert r.status_code == 201, r.text
    # ...but a district admin still cannot invite into a sibling district
    r = client.post(
        "/admin/invites",
        json={"email": "other@pinpoint.test", "role": "registrar", "jurisdiction_id": str(world.mys.id)},
        headers=world.h("admin"),
    )
    assert r.status_code == 403


def test_staff_list_shows_active_staff_and_pending_invites_in_scope(client, world):
    client.post(
        "/admin/invites",
        json={"email": "Pending@Pinpoint.test", "role": "verifier", "jurisdiction_id": str(world.blr.id)},
        headers=world.h("admin"),
    )
    rows = client.get("/admin/staff", headers=world.h("admin")).json()
    emails = {r["email"] for r in rows}
    assert world.registrar.email in emails and world.admin.email in emails
    assert world.mys_registrar.email not in emails  # a different district
    assert world.verifier.email not in emails  # held at state level, which this admin does not manage
    by_status = {r["email"]: r for r in rows}
    pending = by_status["pending@pinpoint.test"]
    assert pending["status"] == "invited" and pending["role"] == "verifier" and pending["name"] == ""
    assert pending["jurisdiction_name"] == "Bengaluru Urban" and pending["user_id"] is None
    reg = by_status[world.registrar.email]
    assert reg["status"] == "active" and reg["role"] == "registrar" and reg["name"] == "Arun R."
    assert reg["invite_token"] is None
    assert set(reg) >= {"id", "email", "name", "role", "jurisdiction_name", "status", "invite_token"}


def test_the_invite_token_is_only_for_the_creator_and_never_in_production(
    client, world, db_session, monkeypatch
):
    from tests.world import auth

    r = client.post(
        "/admin/invites",
        json={"email": "pending@pinpoint.test", "role": "printer", "jurisdiction_id": str(world.blr.id)},
        headers=world.h("admin"),
    ).json()
    token_from_link = r["invite_url"].rsplit("/", 1)[1]

    def pending(headers):
        rows = client.get("/admin/staff", headers=headers).json()
        return next(x for x in rows if x["status"] == "invited")

    assert pending(world.h("admin"))["invite_token"] == token_from_link
    # the token really opens the invite, so the UI can rebuild the link after a reload
    assert client.get(f"/auth/invites/{token_from_link}").json()["email"] == "pending@pinpoint.test"
    other_admin, _ = make_staff(db_session, Role.ADMIN, world.blr)
    assert pending(auth(other_admin))["invite_token"] is None  # not the creator
    monkeypatch.setattr(
        "app.api.admin.get_settings", lambda: get_settings().model_copy(update={"environment": "production"})
    )
    assert pending(world.h("admin"))["invite_token"] is None


def test_accepted_and_expired_invites_leave_the_list(client, world, db_session):
    from datetime import datetime, timedelta, timezone

    from app.models import Invite

    client.post(
        "/admin/invites",
        json={"email": "gone@pinpoint.test", "role": "printer", "jurisdiction_id": str(world.blr.id)},
        headers=world.h("admin"),
    )
    invite = db_session.query(Invite).one()
    invite.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.flush()
    assert all(r["status"] == "active" for r in client.get("/admin/staff", headers=world.h("admin")).json())


# ---------- audit events ----------
def test_auditors_see_events_in_their_jurisdiction_newest_first_with_filters(client, world):
    a = register(client, world.h("registrar"), 0)
    client.post(f"/places/{a['id']}/decision", json={"decision": "approve"}, headers=world.h("verifier"))
    register(client, world.h("mys_registrar"), 5)  # a different district
    page = client.get("/audit/events", headers=world.h("auditor")).json()
    actions = [e["action"] for e in page["items"]]
    assert actions == ["place.approve", "place.create"]
    assert page["items"][0]["actor_name"] == "Ravi M." and page["items"][0]["resource_id"] == a["id"]
    assert page["items"][0]["jurisdiction_id"] == str(world.blr.id)
    assert "ip" not in page["items"][0]
    only = client.get("/audit/events", params={"action": "place.create"}, headers=world.h("auditor")).json()
    assert [e["action"] for e in only["items"]] == ["place.create"]
    by_resource = client.get(
        "/audit/events", params={"resource_id": a["id"]}, headers=world.h("auditor")
    ).json()
    assert len(by_resource["items"]) == 2
    by_actor = client.get(
        "/audit/events", params={"actor_id": str(world.verifier.id)}, headers=world.h("auditor")
    ).json()
    assert [e["action"] for e in by_actor["items"]] == ["place.approve"]
    # the state-level verifier cannot read the log; the Mysuru view never contains Bengaluru events
    assert client.get("/audit/events", headers=world.h("verifier")).status_code == 403


def test_audit_events_never_cross_jurisdictions(client, world, db_session):
    from tests.world import auth

    register(client, world.h("registrar"), 0)
    mys_auditor, _ = make_staff(db_session, Role.AUDITOR, world.mys)
    assert client.get("/audit/events", headers=auth(mys_auditor)).json()["items"] == []
    state_auditor, _ = make_staff(db_session, Role.AUDITOR, world.ka)
    assert len(client.get("/audit/events", headers=auth(state_auditor)).json()["items"]) == 1


def test_events_without_a_jurisdiction_are_for_super_admins_only(client, world, db_session):
    from app.models import AuditEvent
    from tests.world import auth

    db_session.add(AuditEvent(action="auth.login", resource_type="user", actor_id=world.admin.id))
    db_session.flush()
    assert client.get("/audit/events", headers=world.h("auditor")).json()["items"] == []
    root, _ = make_staff(db_session, Role.SUPER_ADMIN, world.ka)
    assert [e["action"] for e in client.get("/audit/events", headers=auth(root)).json()["items"]] == [
        "auth.login"
    ]


def test_audit_listing_is_paged_and_viewer_names_stay_private(client, world, db_session):
    from tests.world import auth, public_place

    p = public_place(client, world, 0)
    client.post(
        f"/places/{p['id']}/corrections", json={"note": "Wrong gate shown"}, headers=auth(world.viewer)
    )
    page = client.get("/audit/events", params={"limit": 2}, headers=world.h("auditor")).json()
    assert len(page["items"]) == 2 and page["next_before_id"] == page["items"][-1]["id"]
    seen = [e["id"] for e in page["items"]]
    while page["next_before_id"]:
        page = client.get(
            "/audit/events",
            params={"limit": 2, "before_id": page["next_before_id"]},
            headers=world.h("auditor"),
        ).json()
        seen += [e["id"] for e in page["items"]]
    assert seen == sorted(seen, reverse=True) and len(seen) == len(set(seen)) >= 4
    report = client.get(
        "/audit/events", params={"action": "correction.submit"}, headers=world.h("auditor")
    ).json()["items"][0]
    assert report["actor_name"] == "Normal user" and "Vina" not in str(report)
    assert client.get("/audit/events", params={"limit": 500}, headers=world.h("auditor")).status_code == 422
    active_place(client, world, 8)
