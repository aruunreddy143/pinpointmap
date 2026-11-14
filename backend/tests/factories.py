"""Small helpers to build valid rows. Defaults are valid; tests override only what they test."""

from __future__ import annotations

import itertools
import uuid

from sqlalchemy.orm import Session

from app.core.geo import LatLon, point
from app.domain.digipin import ALPHABET
from app.domain.place_id import make_id
from app.models import AppUser, Jurisdiction, Place
from app.models.enums import (
    JurisdictionLevel,
    LocationSource,
    PlaceStatus,
    PlaceType,
    UserKind,
    Visibility,
)

_counter = itertools.count(1)
SUNRISE = LatLon(lat=12.971599, lon=77.594566)


def unique_public_id() -> str:
    """A valid, never-repeating ID (the suffix counts up in base 16)."""
    n = next(_counter)
    seq = "".join(ALPHABET[(n >> shift) & 15] for shift in (12, 8, 4, 0))
    return make_id("FC98J327K4", seq)


def make_jurisdiction(session: Session, **kw) -> Jurisdiction:
    n = next(_counter)
    j = Jurisdiction(
        level=kw.pop("level", JurisdictionLevel.DISTRICT),
        name=f"District {n}",
        code=f"D{n}-{uuid.uuid4().hex[:6]}",
        **kw,
    )
    session.add(j)
    session.flush()
    return j


def make_user(session: Session, kind: UserKind = UserKind.STAFF, **kw) -> AppUser:
    n = next(_counter)
    defaults: dict = {"kind": kind, "name": f"User {n}"}
    if kind is UserKind.STAFF:
        defaults |= {"email": f"staff{n}-{uuid.uuid4().hex[:6]}@pinpoint.test", "password_hash": "x"}
    else:
        defaults |= {"email": f"viewer{n}-{uuid.uuid4().hex[:6]}@example.com"}
    user = AppUser(**(defaults | kw))
    session.add(user)
    session.flush()
    return user


def make_place(
    session: Session,
    *,
    jurisdiction: Jurisdiction,
    created_by: AppUser,
    type: PlaceType = PlaceType.BUILDING,  # noqa: A002
    at: LatLon = SUNRISE,
    parent: Place | None = None,
    label: str | None = None,
    status: PlaceStatus = PlaceStatus.ACTIVE,
    visibility: Visibility = Visibility.PRIVATE,
    public_id: str | None = "auto",
    **kw,
) -> Place:
    n = next(_counter)
    place = Place(
        type=type,
        parent_id=parent.id if parent else None,
        label=label,
        name=kw.pop("name", f"Place {n}"),
        geometry=kw.pop("geometry", point(at)),
        accuracy_m=4,
        location_source=LocationSource.GPS,
        jurisdiction_id=jurisdiction.id,
        status=status,
        visibility=visibility,
        public_id=unique_public_id() if public_id == "auto" else public_id,
        created_by=created_by.id,
        **kw,
    )
    session.add(place)
    session.flush()
    return place
