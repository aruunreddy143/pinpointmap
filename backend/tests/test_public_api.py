"""Resolver, public search/detail and "Report a problem": the visibility matrix
(anonymous / viewer / staff in jurisdiction / staff outside) and the no-leak rules."""

import json

import pytest
from sqlalchemy import select

from app.core.deps import get_session
from app.domain import place_id as pid
from app.models import AuditEvent, CorrectionRequest, Place, PlaceEvent
from app.models.enums import PlaceStatus
from tests.world import active_place, auth, public_place, register

pytestmark = pytest.mark.db


def scan(client, public_id, headers=None):
    return client.get(f"/p/{public_id}", headers=headers or {})


@pytest.fixture
def places(client, world):
    """A private active building, a public active building, and a pending one."""
    return {
        "private": active_place(client, world, 0, name="Private Heights", address="SECRET LANE 9"),
        "public": public_place(client, world, 3, name="Public Court", unit_labels=["1", "2"]),
        "pending": register(client, world.h("registrar"), 6, name="Pending Place"),
    }


# ---------- resolver ----------
def test_a_mistyped_id_is_refused_without_touching_the_database(client):
    class NoDatabase:
        def __getattr__(self, name):
            raise AssertionError(f"the database was used ({name})")

    client.app.dependency_overrides[get_session] = lambda: NoDatabase()
    good = pid.make_id("FC98J327K4", "56LM")
    bad = good[:5] + ("C" if good[5] == "F" else "F") + good[6:]
    r = scan(client, bad)
    assert r.status_code == 404 and r.json()["kind"] == "invalid"
    assert scan(client, "PP1").json()["kind"] == "invalid"


def test_a_valid_but_unregistered_id_is_not_found(client, world):
    r = scan(client, pid.make_id("FC98J327K4", "56LM"))
    assert r.status_code == 404 and r.json()["kind"] == "not_found"


def test_anonymous_and_viewer_scans_of_a_private_place_see_nothing_but_the_id(client, world, places):
    p = places["private"]
    for headers in ({}, auth(world.viewer)):
        r = scan(client, p["public_id"], headers)
        assert r.status_code == 200
        body = r.json()
        assert body["kind"] == "minimal" and body["public_id"] == p["public_id"]
        assert body["place"] is None and body["staff_place"] is None and body["units"] == []
        assert "SECRET LANE" not in r.text and "Private Heights" not in r.text
        assert "12.97" not in r.text  # no coordinates either


def test_a_pending_place_is_minimal_to_the_public(client, world, places):
    assert scan(client, places["pending"]["public_id"]).json()["kind"] == "minimal"


def test_a_public_place_shows_its_public_view_to_everyone_with_active_units(client, world, places):
    p = places["public"]
    for headers in ({}, auth(world.viewer), auth(world.mys_registrar)):  # outside staff = anonymous
        body = scan(client, p["public_id"], headers).json()
        assert body["kind"] == "public" and body["place"]["name"] == "Public Court"
        assert [u["label"] for u in body["units"]] == ["1", "2"]
        assert body["staff_place"] is None
        assert "created_by" not in json.dumps(body) and "status" not in body["place"]


def test_staff_in_jurisdiction_get_the_full_view_and_private_reads_are_audited(
    client, world, places, db_session
):
    p = places["private"]
    for who in ("registrar", "auditor", "verifier", "printer"):
        body = scan(client, p["public_id"], world.h(who)).json()
        assert body["kind"] == "staff" and body["staff_place"]["address"] == "SECRET LANE 9"
    rows = db_session.scalars(select(AuditEvent).where(AuditEvent.action == "place.read_private")).all()
    assert len(rows) == 4 and {r.detail["via"] for r in rows} == {"resolver"}


def test_staff_outside_the_jurisdiction_are_treated_like_anyone_else(client, world, places):
    assert scan(client, places["private"]["public_id"], world.h("mys_verifier")).json()["kind"] == "minimal"


def test_a_bad_bearer_token_is_just_anonymous(client, world, places):
    r = scan(client, places["public"]["public_id"], {"Authorization": "Bearer garbage"})
    assert r.status_code == 200 and r.json()["kind"] == "public"


def test_retired_public_places_answer_with_a_tombstone_pointing_to_public_successors(
    client, world, places, db_session
):
    old, new = places["public"], places["private"]
    db_session.execute(
        Place.__table__.update()
        .where(Place.id == old["id"])
        .values(status=PlaceStatus.MERGED, successor_ids=[new["id"]])
    )
    body = scan(client, old["public_id"]).json()
    assert body["kind"] == "tombstone" and body["status"] == "merged"
    assert body["successor_ids"] == []  # the successor is private, so its ID is not revealed
    db_session.execute(Place.__table__.update().where(Place.id == new["id"]).values(visibility="public"))
    assert scan(client, old["public_id"]).json()["successor_ids"] == [new["public_id"]]
    # a private retired place does not even admit it was retired
    db_session.execute(
        Place.__table__.update()
        .where(Place.id == new["id"])
        .values(visibility="private", status=PlaceStatus.RETIRED)
    )
    assert scan(client, new["public_id"]).json()["kind"] == "minimal"


def test_the_resolver_is_rate_limited(client, world):
    code = pid.make_id("FC98J327K4", "56LM")
    statuses = [scan(client, code).status_code for _ in range(62)]
    assert statuses[:60] == [404] * 60 and statuses[60:] == [429, 429]


# ---------- public search / detail ----------
def test_search_returns_only_public_active_places_and_never_private_ones(client, world, places, db_session):
    found = client.get("/public/places", params={"q": "a"}).json()
    assert [p["name"] for p in found] == ["Public Court"]
    everything = json.dumps(client.get("/public/places", params={"q": "e"}).json())
    for secret in (places["private"]["public_id"], places["pending"]["public_id"], "SECRET LANE"):
        assert secret not in everything
    assert client.get("/public/places", params={"q": ""}).json() == []
    assert client.get("/public/places", params={"q": "private heights"}).json() == []
    by_id = client.get("/public/places", params={"q": places["public"]["public_id"].lower()}).json()
    assert [p["name"] for p in by_id] == ["Public Court"]
    assert set(found[0]) == {  # a small model: no staff or private field
        "id",
        "public_id",
        "type",
        "parent_id",
        "label",
        "name",
        "geo",
        "address",
        "landmark",
        "locality",
        "district",
        "state",
        "postal_pin",
    }


def test_search_does_not_list_units_or_pending_or_retired(client, world, places, db_session):
    db_session.execute(
        Place.__table__.update().where(Place.id == places["public"]["id"]).values(status=PlaceStatus.RETIRED)
    )
    assert client.get("/public/places", params={"q": "court"}).json() == []


def test_public_detail_is_404_for_private_pending_and_unknown_places(client, world, places):
    assert client.get(f"/public/places/{places['private']['id']}").status_code == 404
    assert client.get(f"/public/places/{places['pending']['id']}").status_code == 404
    assert client.get(f"/public/places/{places['private']['public_id']}").status_code == 404
    assert client.get("/public/places/not-an-id").status_code == 404
    assert client.get("/public/places/00000000-0000-0000-0000-000000000000").status_code == 404
    ok = client.get(f"/public/places/{places['public']['id']}")
    assert ok.status_code == 200 and [u["label"] for u in ok.json()["units"]] == ["1", "2"]
    assert client.get(f"/public/places/{places['public']['public_id']}").status_code == 200


def test_public_units_hide_units_that_are_not_active(client, world, places, db_session):
    db_session.execute(
        Place.__table__.update()
        .where(Place.parent_id == places["public"]["id"], Place.label == "2")
        .values(status=PlaceStatus.RETIRED)
    )
    units = client.get(f"/public/places/{places['public']['id']}").json()["units"]
    assert [u["label"] for u in units] == ["1"]


def test_search_is_rate_limited(client):
    codes = [client.get("/public/places", params={"q": "x"}).status_code for _ in range(62)]
    assert codes[:60] == [200] * 60 and codes[60:] == [429, 429]


# ---------- report a problem ----------
def test_a_viewer_can_report_a_problem_on_a_public_place(client, world, places, db_session):
    p = places["public"]
    r = client.post(
        f"/places/{p['id']}/corrections",
        json={"note": "The gate is on the other side."},
        headers=auth(world.viewer),
    )
    assert r.status_code == 201 and r.json()["status"] == "open"
    row = db_session.scalars(select(CorrectionRequest)).one()
    assert row.submitted_by == world.viewer.id and str(row.place_id) == p["id"]
    assert "correction.submit" in [a.action for a in db_session.scalars(select(AuditEvent))]
    events = db_session.scalars(select(PlaceEvent).where(PlaceEvent.type == "correction_requested")).all()
    assert len(events) == 1
    # staff see that a problem was reported, but not the viewer's name
    history = client.get(f"/places/{p['id']}/history", headers=world.h("registrar")).json()
    assert history[0]["title"] == "Problem reported by a user" and history[0]["actor_name"] == "Normal user"
    # it also works with the PINPOINT ID
    assert (
        client.post(
            f"/places/{p['public_id']}/corrections",
            json={"note": "Name is misspelt"},
            headers=auth(world.viewer),
        ).status_code
        == 201
    )


def test_a_correction_on_a_place_the_viewer_cannot_see_is_404(client, world, places):
    for key in ("private", "pending"):
        r = client.post(
            f"/places/{places[key]['id']}/corrections",
            json={"note": "Something wrong here"},
            headers=auth(world.viewer),
        )
        assert r.status_code == 404


def test_only_five_reports_a_day_and_notes_are_validated(client, world, places):
    p, h = places["public"], auth(world.viewer)
    for i in range(5):
        assert (
            client.post(
                f"/places/{p['id']}/corrections", json={"note": f"Problem number {i}"}, headers=h
            ).status_code
            == 201
        )
    assert (
        client.post(f"/places/{p['id']}/corrections", json={"note": "One too many"}, headers=h).status_code
        == 429
    )
    assert client.post(f"/places/{p['id']}/corrections", json={"note": "no"}, headers=h).status_code == 422


def test_staff_cannot_file_viewer_reports_and_anonymous_cannot_either(client, world, places):
    p = places["public"]
    body = {"note": "Looks wrong to me"}
    assert (
        client.post(f"/places/{p['id']}/corrections", json=body, headers=world.h("admin")).status_code == 403
    )
    assert client.post(f"/places/{p['id']}/corrections", json=body).status_code == 401


def test_a_viewer_cannot_use_any_staff_endpoint(client, world, places):
    h = auth(world.viewer)
    p = places["public"]["id"]
    for method, path in [
        ("get", "/places"),
        ("get", f"/places/{p}"),
        ("get", f"/places/{p}/history"),
        ("get", f"/places/{p}/label"),
        ("get", "/review"),
        ("get", "/audit/events"),
        ("get", "/admin/staff"),
        ("get", "/admin/jurisdictions"),
    ]:
        assert client.request(method, path, headers=h).status_code == 403, path
    assert client.post("/places", json={}, headers=h).status_code == 403
    assert client.patch(f"/places/{p}", json={}, headers=h).status_code == 403
    assert client.put(f"/places/{p}/visibility", json={"visibility": "private"}, headers=h).status_code == 403
    assert client.post(f"/places/{p}/decision", json={"decision": "approve"}, headers=h).status_code == 403
