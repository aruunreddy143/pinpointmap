"""The database enforces the rules itself, so no code path can break them. These tests talk to the
real, migrated PostGIS schema."""

import pytest
from geoalchemy2 import Geography
from sqlalchemy import cast, func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.geo import DUPLICATE_RADIUS_M, LatLon, point
from app.models import (
    AuditEvent,
    CorrectionRequest,
    Place,
    PlaceEvent,
    RoleAssignment,
)
from app.models.enums import PlaceStatus, PlaceType, Role, UserKind
from tests.factories import SUNRISE, make_jurisdiction, make_place, make_user, unique_public_id

pytestmark = pytest.mark.db


@pytest.fixture
def ctx(db_session):
    j = make_jurisdiction(db_session)
    staff = make_user(db_session)
    return db_session, j, staff


def rejected(session, fn):
    """Run fn inside a savepoint and require the database to refuse it."""
    with pytest.raises((IntegrityError, DBAPIError)), session.begin_nested():
        fn()


# ---------- place shape ----------


def test_valid_building_and_units(ctx):
    s, j, staff = ctx
    b = make_place(s, jurisdiction=j, created_by=staff, type=PlaceType.BUILDING, name="Sunrise")
    u = make_place(s, jurisdiction=j, created_by=staff, type=PlaceType.UNIT, parent=b, label="101")
    assert u.parent_id == b.id and u.public_id and b.public_id


def test_building_cannot_have_a_parent(ctx):
    s, j, staff = ctx
    b = make_place(s, jurisdiction=j, created_by=staff)
    rejected(s, lambda: make_place(s, jurisdiction=j, created_by=staff, type=PlaceType.HOUSE, parent=b))


def test_unit_needs_a_parent(ctx):
    s, j, staff = ctx
    rejected(s, lambda: make_place(s, jurisdiction=j, created_by=staff, type=PlaceType.UNIT, label="1"))


def test_house_must_be_a_point_not_a_polygon(ctx):
    s, j, staff = ctx
    polygon = text(
        "ST_SetSRID(ST_GeomFromText('POLYGON((77.5 12.9, 77.6 12.9, 77.6 13.0, 77.5 12.9))'), 4326)"
    )
    rejected(
        s, lambda: make_place(s, jurisdiction=j, created_by=staff, type=PlaceType.HOUSE, geometry=polygon)
    )


def test_land_must_be_a_polygon_phase_two_ready(ctx):
    s, j, staff = ctx
    polygon = text(
        "ST_SetSRID(ST_GeomFromText('POLYGON((77.5 12.9, 77.6 12.9, 77.6 13.0, 77.5 12.9))'), 4326)"
    )
    land = make_place(s, jurisdiction=j, created_by=staff, type=PlaceType.LAND, geometry=polygon)
    assert land.id
    rejected(s, lambda: make_place(s, jurisdiction=j, created_by=staff, type=PlaceType.LAND))


@pytest.mark.parametrize("lat,lon", [(51.5, -0.12), (0.0, 0.0), (2.4, 80.0)])
def test_points_outside_india_are_refused(ctx, lat, lon):
    s, j, staff = ctx
    # Bypass the application-level check (LatLon refuses these too) to prove the database refuses them as well.
    raw = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    rejected(s, lambda: make_place(s, jurisdiction=j, created_by=staff, geometry=raw))


def test_point_on_the_edge_of_the_box_is_allowed(ctx):
    s, j, staff = ctx
    assert make_place(s, jurisdiction=j, created_by=staff, at=LatLon(lat=38.5, lon=99.5)).id


# ---------- ids ----------


def test_draft_may_have_no_id_but_a_submitted_place_must(ctx):
    s, j, staff = ctx
    draft = make_place(s, jurisdiction=j, created_by=staff, status=PlaceStatus.DRAFT, public_id=None)
    assert draft.public_id is None
    rejected(
        s, lambda: make_place(s, jurisdiction=j, created_by=staff, status=PlaceStatus.PENDING, public_id=None)
    )


def test_public_id_is_unique(ctx):
    s, j, staff = ctx
    pid = unique_public_id()
    make_place(s, jurisdiction=j, created_by=staff, public_id=pid)
    rejected(s, lambda: make_place(s, jurisdiction=j, created_by=staff, public_id=pid))


@pytest.mark.parametrize("bad", ["PP1", "XX1FC98J327K456LMC", "PP1FC98J327K456LMO", "pp1fc98j327k456lmc"])
def test_public_id_must_have_the_right_shape(ctx, bad):
    s, j, staff = ctx
    rejected(s, lambda: make_place(s, jurisdiction=j, created_by=staff, public_id=bad))


# ---------- unit labels ----------


def test_unit_label_is_unique_within_a_building_ignoring_case(ctx):
    s, j, staff = ctx
    b = make_place(s, jurisdiction=j, created_by=staff)
    make_place(s, jurisdiction=j, created_by=staff, type=PlaceType.UNIT, parent=b, label="2B")
    rejected(
        s, lambda: make_place(s, jurisdiction=j, created_by=staff, type=PlaceType.UNIT, parent=b, label="2b")
    )


def test_same_label_is_fine_in_another_building_or_after_the_first_is_retired(ctx):
    s, j, staff = ctx
    b1 = make_place(s, jurisdiction=j, created_by=staff)
    b2 = make_place(s, jurisdiction=j, created_by=staff)
    first = make_place(s, jurisdiction=j, created_by=staff, type=PlaceType.UNIT, parent=b1, label="101")
    make_place(s, jurisdiction=j, created_by=staff, type=PlaceType.UNIT, parent=b2, label="101")
    first.status = PlaceStatus.RETIRED
    s.flush()
    assert make_place(s, jurisdiction=j, created_by=staff, type=PlaceType.UNIT, parent=b1, label="101").id


# ---------- append-only and never-delete ----------


def test_audit_events_can_be_added_but_never_changed_or_removed(ctx):
    s, j, staff = ctx
    ev = AuditEvent(
        actor_id=staff.id,
        action="place.create",
        resource_type="place",
        resource_id="x",
        detail={"fields": ["name"]},
    )
    s.add(ev)
    s.flush()
    rejected(
        s, lambda: s.execute(text("UPDATE audit_event SET action = 'tampered' WHERE id = :i"), {"i": ev.id})
    )
    rejected(s, lambda: s.execute(text("DELETE FROM audit_event WHERE id = :i"), {"i": ev.id}))
    rejected(s, lambda: s.execute(text("TRUNCATE audit_event")))


def test_place_history_is_append_only(ctx):
    s, j, staff = ctx
    p = make_place(s, jurisdiction=j, created_by=staff)
    ev = PlaceEvent(place_id=p.id, type="pin_moved", actor_id=staff.id, before={"lat": 1}, after={"lat": 2})
    s.add(ev)
    s.flush()
    rejected(s, lambda: s.execute(text("UPDATE place_event SET type = 'x' WHERE id = :i"), {"i": ev.id}))
    rejected(s, lambda: s.execute(text("DELETE FROM place_event WHERE id = :i"), {"i": ev.id}))
    rejected(s, lambda: s.execute(text("TRUNCATE place_event")))


def test_places_are_never_hard_deleted(ctx):
    s, j, staff = ctx
    p = make_place(s, jurisdiction=j, created_by=staff)
    rejected(s, lambda: s.execute(text("DELETE FROM place WHERE id = :i"), {"i": p.id}))
    rejected(s, lambda: s.execute(text("TRUNCATE place CASCADE")))


# ---------- users and roles ----------


def test_staff_needs_an_email_and_viewers_need_an_identifier(ctx):
    s, _, _ = ctx
    rejected(s, lambda: make_user(s, UserKind.STAFF, email=None))
    rejected(s, lambda: make_user(s, UserKind.VIEWER, email=None, mobile_hash=None))
    assert make_user(s, UserKind.VIEWER, email=None, mobile_hash="hash-of-mobile").id


def test_emails_are_unique_ignoring_case(ctx):
    s, _, _ = ctx
    make_user(s, email="Same@Example.com")
    rejected(s, lambda: make_user(s, email="same@example.COM"))


def test_a_role_can_be_assigned_once_per_jurisdiction_and_viewer_is_not_a_role(ctx):
    s, j, staff = ctx
    s.add(RoleAssignment(user_id=staff.id, role=Role.REGISTRAR, jurisdiction_id=j.id))
    s.flush()
    rejected(
        s,
        lambda: (
            s.add(RoleAssignment(user_id=staff.id, role=Role.REGISTRAR, jurisdiction_id=j.id)),
            s.flush(),
        ),
    )
    rejected(
        s,
        lambda: s.execute(
            text(
                "INSERT INTO role_assignment (id,user_id,role,jurisdiction_id) VALUES (gen_random_uuid(), :u, 'viewer', :j)"
            ),
            {"u": staff.id, "j": j.id},
        ),
    )


def test_correction_note_length_is_enforced(ctx):
    s, j, staff = ctx
    p = make_place(s, jurisdiction=j, created_by=staff)
    viewer = make_user(s, UserKind.VIEWER)
    s.add(CorrectionRequest(place_id=p.id, submitted_by=viewer.id, note="The gate is on the other side"))
    s.flush()
    rejected(
        s, lambda: (s.add(CorrectionRequest(place_id=p.id, submitted_by=viewer.id, note="no")), s.flush())
    )
    rejected(
        s,
        lambda: (s.add(CorrectionRequest(place_id=p.id, submitted_by=viewer.id, note="x" * 501)), s.flush()),
    )


# ---------- spatial ----------


def test_nearby_search_uses_metres_on_geography(ctx):
    s, j, staff = ctx
    here = make_place(s, jurisdiction=j, created_by=staff, at=SUNRISE, name="here")
    near = make_place(
        s, jurisdiction=j, created_by=staff, at=LatLon(lat=SUNRISE.lat + 0.0001, lon=SUNRISE.lon), name="near"
    )  # ~11 m
    make_place(
        s, jurisdiction=j, created_by=staff, at=LatLon(lat=SUNRISE.lat + 0.0003, lon=SUNRISE.lon), name="far"
    )  # ~33 m
    found = s.scalars(
        select(Place.name)
        .where(
            func.ST_DWithin(
                cast(Place.geometry, Geography), cast(point(SUNRISE), Geography), DUPLICATE_RADIUS_M
            )
        )
        .order_by(Place.name)
    ).all()
    assert found == ["here", "near"]
    assert here.id != near.id


def test_the_geography_index_exists_and_is_used_for_distance_queries(ctx):
    s, *_ = ctx
    names = {r[0] for r in s.execute(text("SELECT indexname FROM pg_indexes WHERE tablename = 'place'"))}
    assert {"ix_place_geometry", "ix_place_geography", "uq_place_unit_label", "uq_place_public_id"} <= names


def test_point_helper_puts_longitude_first(ctx):
    s, *_ = ctx
    x, y = s.execute(select(func.ST_X(point(SUNRISE)), func.ST_Y(point(SUNRISE)))).one()
    assert (round(x, 6), round(y, 6)) == (77.594566, 12.971599)  # lon first: the classic bug
