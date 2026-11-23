"""Places: registration, duplicate guard, four-eyes verification, jurisdiction scope, visibility, history,
review queue. Rule tests ported from frontend/src/mocks/api.test.ts, now against the real API + PostGIS."""

import pytest
from sqlalchemy import func, select

from app.domain import digipin
from app.domain import place_id as pid
from app.models import AuditEvent, ConsentRecord, Place, PlaceEvent
from tests.world import active_place, approve, at, payload, register

pytestmark = pytest.mark.db


# ---------- registration ----------
def test_submit_issues_a_valid_id_and_creates_pending_private_units(client, world, db_session):
    p = register(client, world.h("registrar"), unit_labels=["1", "2", "3-4"])
    assert p["status"] == "pending_verification"
    assert p["visibility"] == "private"
    assert pid.validate(p["public_id"]).ok
    assert p["unit_count"] == 4
    units = client.get(f"/places/{p['id']}/units", headers=world.h("registrar")).json()
    assert [u["label"] for u in units] == ["1", "2", "3", "4"]
    assert {u["status"] for u in units} == {"pending_verification"}
    assert {u["visibility"] for u in units} == {"private"}
    ids = {p["public_id"], *(u["public_id"] for u in units)}
    assert len(ids) == 5 and all(pid.validate(i).ok for i in ids)
    # state and district come from the jurisdiction tree, not from the request
    assert (p["state"], p["district"]) == ("Karnataka", "Bengaluru Urban")
    assert p["created_by_name"] == "Arun R."


def test_axis_order_round_trips_through_api_and_database(client, world, db_session):
    p = register(client, world.h("registrar"))
    assert p["geo"] == {"lat": 12.971599, "lon": 77.594566}
    x, y = db_session.execute(
        select(func.ST_X(Place.geometry), func.ST_Y(Place.geometry)).where(Place.id == p["id"])
    ).one()
    assert (round(x, 6), round(y, 6)) == (77.594566, 12.971599)  # PostGIS is (lon, lat)
    assert pid.geo_cell(p["public_id"]) == digipin.encode(12.971599, 77.594566)  # lat first, then lon


def test_registering_writes_history_and_audit_in_the_same_transaction(client, world, db_session):
    p = register(client, world.h("registrar"), unit_labels=["1"])
    ev = db_session.scalars(select(PlaceEvent).where(PlaceEvent.place_id == p["id"])).all()
    assert [e.type for e in ev] == ["submitted"]
    audit = db_session.scalars(select(AuditEvent).where(AuditEvent.resource_id == p["id"])).all()
    assert [a.action for a in audit] == ["place.create"]
    assert audit[0].actor_id == world.registrar.id and audit[0].jurisdiction_id == world.blr.id
    assert "Test Court" not in str(audit[0].detail)  # ids and field names only


def test_outside_india_is_refused(client, world):
    r = client.post("/places", json=payload(geo={"lat": 51.5, "lon": -0.12}), headers=world.h("registrar"))
    assert r.status_code == 422


def test_a_house_cannot_have_units_and_bad_unit_input_is_refused(client, world):
    h = world.h("registrar")
    assert client.post("/places", json=payload(type="house", unit_labels=["1"]), headers=h).status_code == 422
    assert client.post("/places", json=payload(unit_labels=["10-5"]), headers=h).status_code == 422
    assert client.post("/places", json=payload(unit_labels=["1", "1"]), headers=h).status_code == 422
    assert client.post("/places", json=payload(unit_labels=["2b", "2B"]), headers=h).status_code == 422


def test_audit_failure_rolls_the_whole_registration_back(client, world, db_session, monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("audit store is down")

    monkeypatch.setattr("app.services.audit.record", broken)
    before = db_session.scalar(select(func.count()).select_from(Place))
    with pytest.raises(RuntimeError):
        client.post("/places", json=payload(unit_labels=["1", "2"]), headers=world.h("registrar"))
    assert db_session.scalar(select(func.count()).select_from(Place)) == before
    assert db_session.scalar(select(func.count()).select_from(PlaceEvent)) == 0


def test_two_requests_racing_for_one_id_never_produce_a_duplicate(client, world, db_session, monkeypatch):
    first = register(client, world.h("registrar"), 0)
    real = pid.generate
    calls = {"n": 0}

    def racing(lat, lon, exists):
        calls["n"] += 1
        # The first candidate is an ID that another request just took (our existence check missed it).
        return first["public_id"] if calls["n"] == 1 else real(lat, lon, exists)

    monkeypatch.setattr(pid, "generate", racing)
    second = register(client, world.h("registrar"), 3)
    assert second["public_id"] != first["public_id"]
    assert calls["n"] == 2  # the insert hit the unique constraint, then retried with a fresh ID


# ---------- duplicate guard ----------
def test_nearby_finds_places_within_15_m_nearest_first_and_nothing_far_away(client, world):
    p = register(client, world.h("registrar"))
    h = world.h("registrar")
    near = client.get("/places/nearby", params={"lat": 12.97165, "lon": 77.5946}, headers=h).json()
    assert [n["id"] for n in near] == [p["id"]]
    assert all(n["distance_m"] <= 15 for n in near)
    assert client.get("/places/nearby", params={"lat": 12.5, "lon": 77.0}, headers=h).json() == []
    assert (
        client.get(
            "/places/nearby", params={"lat": 12.97, "lon": 77.59, "radius_m": 5000}, headers=h
        ).status_code
        == 422
    )
    assert client.get("/places/nearby", params={"lat": 51, "lon": 0}, headers=h).status_code == 422


def test_a_second_place_on_the_same_spot_needs_a_reason(client, world):
    register(client, world.h("registrar"))
    h = world.h("registrar2")
    r = client.post("/places", json=payload(name="Same spot"), headers=h)
    assert r.status_code == 409 and r.json()["error"] == "duplicate_suspect"
    ok = client.post(
        "/places", json=payload(name="Same spot", different_place_reason="A separate block"), headers=h
    )
    assert ok.status_code == 201


def test_the_guard_does_not_reveal_places_in_other_jurisdictions(client, world):
    register(client, world.h("registrar"))
    near = client.get(
        "/places/nearby", params={"lat": 12.97165, "lon": 77.5946}, headers=world.h("mys_registrar")
    )
    assert near.json() == []


# ---------- four-eyes ----------
def test_submitter_cannot_approve_their_own_place(client, world):
    p = register(client, world.h("admin"))  # an admin may create AND verify, but not both on one place
    r = approve(client, world.h("admin"), p["id"])
    assert r.status_code == 403 and "different verifier" in r.json()["message"]
    pending = client.get(
        "/places", params={"status": "pending_verification"}, headers=world.h("admin")
    ).json()
    assert [x["id"] for x in pending] == [p["id"]]


def test_a_different_verifier_activates_the_place_and_its_units(client, world, db_session):
    p = register(client, world.h("registrar"), unit_labels=["1", "2"])
    r = approve(client, world.h("verifier"), p["id"])
    assert r.status_code == 200
    assert r.json()["status"] == "active" and r.json()["verified_at"]
    units = client.get(f"/places/{p['id']}/units", headers=world.h("verifier")).json()
    assert {u["status"] for u in units} == {"active"}
    kinds = [e.type for e in db_session.scalars(select(PlaceEvent).where(PlaceEvent.place_id == p["id"]))]
    assert sorted(kinds) == ["submitted", "verified"]
    assert "place.approve" in [a.action for a in db_session.scalars(select(AuditEvent))]


def test_rejecting_needs_a_reason_then_the_registrar_can_fix_and_resubmit(client, world):
    p = register(client, world.h("registrar"), unit_labels=["1"])
    v = world.h("verifier")
    bad = client.post(f"/places/{p['id']}/decision", json={"decision": "reject", "reason": "  "}, headers=v)
    assert bad.status_code == 422 and "reason" in bad.json()["message"].lower()
    rej = client.post(
        f"/places/{p['id']}/decision", json={"decision": "reject", "reason": "Pin is off"}, headers=v
    )
    assert rej.json()["status"] == "rejected"
    assert client.get(f"/places/{p['id']}/units", headers=v).json()[0]["status"] == "rejected"
    assert approve(client, v, p["id"]).status_code == 409  # rejected places cannot be approved
    re = client.post(f"/places/{p['id']}/resubmit", headers=world.h("registrar"))
    assert re.json()["status"] == "pending_verification"
    assert approve(client, v, p["id"]).json()["status"] == "active"
    titles = [e["title"] for e in client.get(f"/places/{p['id']}/history", headers=v).json()]
    assert "Rejected: Pin is off" in titles and "Verified and activated" in titles


def test_resubmitting_makes_the_resubmitter_the_one_who_cannot_approve(client, world):
    p = register(client, world.h("registrar"))
    client.post(
        f"/places/{p['id']}/decision",
        json={"decision": "reject", "reason": "Fix pin"},
        headers=world.h("admin"),
    )
    client.post(f"/places/{p['id']}/resubmit", headers=world.h("admin"))
    assert approve(client, world.h("admin"), p["id"]).status_code == 403
    assert approve(client, world.h("verifier"), p["id"]).status_code == 200


def test_an_active_place_cannot_be_decided_again(client, world):
    p = active_place(client, world)
    assert approve(client, world.h("verifier"), p["id"]).status_code == 409


# ---------- units added later ----------
def test_units_added_to_a_verified_building_wait_for_a_verifier(client, world):
    p = active_place(client, world, unit_labels=["1"])
    r = client.post(f"/places/{p['id']}/units", json={"labels": ["2-3"]}, headers=world.h("registrar"))
    assert r.status_code == 201 and r.json()["unit_count"] == 3
    q = client.get("/review", params={"kind": "change"}, headers=world.h("verifier")).json()
    assert [i["place_id"] for i in q] == [p["id"]]
    assert "units" in q[0]["checks"][-1]["detail"]
    assert client.get("/review", headers=world.h("verifier")).json() == []  # not a "new" item
    assert approve(client, world.h("registrar2"), p["id"]).status_code == 403  # registrars cannot verify
    # the person who added them cannot approve them either
    client.post(f"/places/{p['id']}/units", json={"labels": ["9"]}, headers=world.h("admin"))
    assert approve(client, world.h("admin"), p["id"]).status_code == 403
    assert approve(client, world.h("verifier"), p["id"]).status_code == 200
    states = {
        u["label"]: u["status"]
        for u in client.get(f"/places/{p['id']}/units", headers=world.h("admin")).json()
    }
    assert set(states.values()) == {"active"}
    assert client.get("/review", params={"kind": "change"}, headers=world.h("verifier")).json() == []


def test_adding_a_label_the_building_already_has_is_a_conflict(client, world):
    p = register(client, world.h("registrar"), unit_labels=["101"])
    r = client.post(f"/places/{p['id']}/units", json={"labels": ["101"]}, headers=world.h("registrar"))
    assert r.status_code == 409


# ---------- jurisdiction ----------
def test_other_districts_places_do_not_exist_for_you(client, world):
    p = active_place(client, world, unit_labels=["1"])
    out = world.h("mys_registrar")
    pid_ = p["id"]
    for method, path, body in [
        ("get", f"/places/{pid_}", None),
        ("get", f"/places/{pid_}/units", None),
        ("get", f"/places/{pid_}/history", None),
        ("patch", f"/places/{pid_}", {"name": "x"}),
        ("post", f"/places/{pid_}/units", {"labels": ["7"]}),
        ("put", f"/places/{pid_}/visibility", {"visibility": "private"}),
        ("post", f"/places/{pid_}/resubmit", None),
    ]:
        r = client.request(method, path, json=body, headers=out)
        assert r.status_code == 404, f"{method} {path} gave {r.status_code}"
    r = client.post(f"/places/{pid_}/decision", json={"decision": "approve"}, headers=world.h("mys_verifier"))
    assert r.status_code == 404
    assert client.get("/places", headers=out).json() == []
    assert client.get("/review", headers=world.h("mys_verifier")).json() == []


def test_state_grant_covers_every_district_below_it(client, world):
    register(client, world.h("registrar"))
    seen = client.get("/places", headers=world.h("verifier")).json()  # verifier holds the STATE grant
    assert len(seen) == 1
    mys = register(client, world.h("mys_registrar"), 5)
    assert mys["district"] == "Mysuru"
    assert {p["id"] for p in client.get("/places", headers=world.h("verifier")).json()} >= {mys["id"]}
    assert {p["id"] for p in client.get("/places", headers=world.h("registrar")).json()}.isdisjoint(
        {mys["id"]}
    )


def test_you_can_only_register_where_you_work(client, world):
    h = world.h("registrar")
    r = client.post("/places", json=payload(jurisdiction_id=str(world.mys.id)), headers=h)
    assert r.status_code == 403
    ok = client.post("/places", json=payload(jurisdiction_id=str(world.blr.id)), headers=h)
    assert ok.status_code == 201


# ---------- editing ----------
def test_editing_keeps_the_id_and_units_follow_the_building(client, world):
    p = register(client, world.h("registrar"), unit_labels=["1"])
    r = client.patch(
        f"/places/{p['id']}",
        json={"name": "Renamed Court", "address": "New road"},
        headers=world.h("registrar"),
    )
    assert r.status_code == 200 and r.json()["public_id"] == p["public_id"]
    unit = client.get(f"/places/{p['id']}/units", headers=world.h("registrar")).json()[0]
    assert unit["name"] == "Renamed Court, 1" and unit["address"] == "New road"
    history = client.get(f"/places/{p['id']}/history", headers=world.h("registrar")).json()
    assert history[0]["title"] == "Details updated (address, name)"


def test_a_small_pin_move_is_fine_but_over_50_m_needs_a_verifier(client, world):
    p = register(client, world.h("registrar"), unit_labels=["1"])
    small = client.patch(
        f"/places/{p['id']}", json={"geo": {"lat": 12.971699, "lon": 77.594566}}, headers=world.h("registrar")
    )
    assert small.status_code == 200
    far = {"geo": {"lat": 12.9750, "lon": 77.594566}}
    assert client.patch(f"/places/{p['id']}", json=far, headers=world.h("registrar")).status_code == 403
    moved = client.patch(f"/places/{p['id']}", json=far, headers=world.h("admin"))  # admin holds verify too
    assert moved.status_code == 200 and moved.json()["public_id"] == p["public_id"]
    unit = client.get(f"/places/{p['id']}/units", headers=world.h("admin")).json()[0]
    assert unit["geo"]["lat"] == 12.975
    titles = [e["title"] for e in client.get(f"/places/{p['id']}/history", headers=world.h("admin")).json()]
    assert any(t.startswith("Pin moved") for t in titles)


def test_a_patch_that_changes_nothing_writes_nothing(client, world, db_session):
    p = register(client, world.h("registrar"))
    n = db_session.scalar(select(func.count()).select_from(PlaceEvent))
    client.patch(f"/places/{p['id']}", json={"name": p["name"]}, headers=world.h("registrar"))
    assert db_session.scalar(select(func.count()).select_from(PlaceEvent)) == n


# ---------- visibility ----------
def test_going_public_needs_a_verifier_who_did_not_register_it_plus_consent(client, world, db_session):
    p = active_place(client, world, unit_labels=["1"])
    url = f"/places/{p['id']}/visibility"
    body = {"visibility": "public", "consent_given_by": "Owner Name"}
    assert client.put(url, json=body, headers=world.h("registrar")).status_code == 403  # no verify right
    assert client.put(url, json=body, headers=world.h("printer")).status_code == 403
    assert (
        client.put(url, json={"visibility": "public"}, headers=world.h("verifier")).status_code == 422
    )  # no consent
    r = client.put(url, json=body, headers=world.h("verifier"))
    assert r.status_code == 200 and r.json()["visibility"] == "public"
    assert (
        client.get(f"/places/{p['id']}/units", headers=world.h("verifier")).json()[0]["visibility"]
        == "public"
    )
    consent = db_session.scalars(select(ConsentRecord).where(ConsentRecord.place_id == p["id"])).one()
    assert consent.given_by_name == "Owner Name" and consent.revoked_at is None
    # Back to private: allowed for update-or-verify roles, and the consent is revoked.
    back = client.put(url, json={"visibility": "private"}, headers=world.h("registrar"))
    assert back.json()["visibility"] == "private"
    db_session.refresh(consent)
    assert consent.revoked_at is not None


def test_the_registrar_of_a_place_cannot_make_it_public_even_as_admin(client, world):
    p = register(client, world.h("admin"))
    approve(client, world.h("verifier"), p["id"])
    r = client.put(
        f"/places/{p['id']}/visibility",
        json={"visibility": "public", "consent_given_by": "Owner Name"},
        headers=world.h("admin"),
    )
    assert r.status_code == 403


def test_only_active_unrestricted_places_can_go_public(client, world, db_session):
    pending = register(client, world.h("registrar"))
    body = {"visibility": "public", "consent_given_by": "Owner Name"}
    assert (
        client.put(f"/places/{pending['id']}/visibility", json=body, headers=world.h("verifier")).status_code
        == 409
    )
    active = active_place(client, world, 4)
    db_session.execute(Place.__table__.update().where(Place.id == active["id"]).values(restricted=True))
    assert (
        client.put(f"/places/{active['id']}/visibility", json=body, headers=world.h("verifier")).status_code
        == 409
    )


# ---------- reads, history, audit of private reads ----------
def test_listing_searches_name_address_locality_and_id_and_escapes_wildcards(client, world):
    a = register(client, world.h("registrar"), 0, name="Sunrise Apartments")
    register(client, world.h("registrar"), 3, name="Green Court", locality="Koramangala")
    h = world.h("registrar")
    names = lambda q: sorted(p["name"] for p in client.get("/places", params={"q": q}, headers=h).json())  # noqa: E731
    assert names("sunrise") == ["Sunrise Apartments"]
    assert names("koramangala") == ["Green Court"]
    assert names(a["public_id"].lower()) == ["Sunrise Apartments"]
    assert names("%") == []  # a wildcard is just a character
    assert len(names("")) == 2
    assert client.get("/places", params={"status": "active"}, headers=h).json() == []


def test_units_are_not_in_the_top_level_list(client, world):
    register(client, world.h("registrar"), unit_labels=["1", "2"])
    listed = client.get("/places", headers=world.h("registrar")).json()
    assert [p["type"] for p in listed] == ["building"]


def test_staff_reads_of_private_places_are_audited(client, world, db_session):
    p = register(client, world.h("registrar"))
    client.get(f"/places/{p['id']}", headers=world.h("verifier"))
    row = db_session.scalars(select(AuditEvent).where(AuditEvent.action == "place.read_private")).one()
    assert row.actor_id == world.verifier.id and row.resource_id == p["id"]


def test_history_is_newest_first_with_titles_and_tones(client, world):
    p = register(client, world.h("registrar"), unit_labels=["1", "2"])
    approve(client, world.h("verifier"), p["id"])
    events = client.get(f"/places/{p['id']}/history", headers=world.h("auditor")).json()
    assert [(e["title"], e["tone"], e["actor_name"]) for e in events] == [
        ("Verified and activated", "ok", "Ravi M."),
        ("Submitted for verification with 2 units", "accent", "Arun R."),
    ]


# ---------- review queue ----------
def test_review_queue_is_oldest_first_with_distance_and_checks(client, world):
    first = register(client, world.h("registrar"), 0, name="First")
    near_active = active_place(client, world, 1, name="Neighbour")
    second = client.post(
        "/places",
        json=payload(
            1,
            name="Second",
            geo={"lat": at(1)["lat"] + 0.00008, "lon": at(1)["lon"]},
            different_place_reason="Different block",
        ),
        headers=world.h("registrar2"),
    ).json()
    queue = client.get("/review", headers=world.h("verifier")).json()
    assert [i["place_id"] for i in queue] == [first["id"], second["id"]]
    a, b = queue
    assert a["kind"] == "new" and a["submitted_by"] == "Arun R." and a["place"]["name"] == "First"
    assert a["duplicate_suspect"] is False and a["nearest_m"] is not None and a["nearest_m"] > 15
    assert b["duplicate_suspect"] is True and b["nearest_m"] <= 15
    checks = {c["title"]: c for c in b["checks"]}
    assert checks["No duplicate nearby"]["ok"] is False
    assert (
        checks["Pin accuracy"]["ok"] is True and "within the 20 m limit" in checks["Pin accuracy"]["detail"]
    )
    assert near_active["id"] not in {i["place_id"] for i in queue}  # already active
    assert client.get("/review", params={"kind": "merge"}, headers=world.h("verifier")).json() == []


def test_a_poor_pin_fails_its_check(client, world):
    register(client, world.h("registrar"), accuracy_m=45)
    item = client.get("/review", headers=world.h("verifier")).json()[0]
    assert [c["ok"] for c in item["checks"] if c["title"] == "Pin accuracy"] == [False]
    assert item["nearest_m"] is None
