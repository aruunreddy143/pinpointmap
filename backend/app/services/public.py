"""What anonymous people, normal users (viewers) and staff outside a place's jurisdiction may see.

The visibility matrix (pinpoint-privacy-india):
- private place: anonymous and viewer get a minimal "registered place" answer, nothing else.
- public + active place: everyone gets the small public view.
- staff inside the place's jurisdiction: the full view (private reads are audited).
- retired / merged / split public place: a tombstone that points to its public successors.
Private places never appear in search, and their IDs never appear in any public answer except as the
ID the caller already typed or scanned."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFound, RateLimited
from app.core.geo import LatLon
from app.core.permissions import Permission
from app.domain import place_id
from app.models import CorrectionRequest, Place
from app.models.enums import PlaceStatus, PlaceType, Visibility
from app.schemas.places import CorrectionOut, PublicPlaceDetail, PublicPlaceOut, ResolveOut
from app.services import audit, places
from app.services.access import Access
from app.services.audit import ClientInfo

SEARCH_LIMIT = 25
CORRECTIONS_PER_DAY = 5
_PUBLIC_VISIBLE = (Place.visibility == Visibility.PUBLIC, Place.status == PlaceStatus.ACTIVE)


def _public_select() -> Any:
    return select(Place, places._lat().label("lat"), places._lon().label("lon"))


def _to_public(row: Any) -> PublicPlaceOut:
    p: Place = row[0]
    return PublicPlaceOut(
        id=p.id,
        public_id=p.public_id or "",  # public places are active, so they always have an ID
        type=p.type,
        parent_id=p.parent_id,
        label=p.label,
        name=p.name,
        geo=LatLon(lat=row.lat, lon=row.lon),
        address=p.address_text,
        landmark=p.landmark,
        locality=p.locality,
        district=p.district,
        state=p.state,
        postal_pin=p.postal_pin,
    )


def _public_units(session: Session, parent_id: uuid.UUID) -> list[PublicPlaceOut]:
    rows = session.execute(
        _public_select()
        .where(Place.parent_id == parent_id, *_PUBLIC_VISIBLE)
        .order_by(Place.label)
        .limit(500)
    )
    return [_to_public(r) for r in rows]


def resolve(session: Session, who: Access | None, text: str, client: ClientInfo) -> tuple[ResolveOut, int]:
    """The scan target. Returns the answer and the HTTP status to send."""
    check = place_id.validate(text)
    if not check.ok:  # a mistyped or damaged code never reaches the database
        return ResolveOut(
            kind="invalid", message="Check the code. A character may be mistyped or damaged."
        ), 404
    canonical = check.canonical or ""
    row = session.execute(places.place_select().where(Place.public_id == canonical)).first()
    if row is None:
        return ResolveOut(kind="not_found", message="No place is registered with this code."), 404
    place: Place = row[0]

    if (
        who is not None
        and who.is_staff
        and place.jurisdiction_id in who.scope(session, Permission.PLACE_READ)
    ):
        if place.visibility is Visibility.PRIVATE:
            places.record_audit(
                session, "place.read_private", place, who.user_id, client, {"via": "resolver"}
            )
            session.commit()
        units = session.execute(
            places.place_select()
            .where(Place.parent_id == place.id, Place.status != PlaceStatus.RETIRED)
            .order_by(Place.label)
            .limit(500)
        )
        return (
            ResolveOut(
                kind="staff",
                public_id=canonical,
                staff_place=places.to_place_out(row),
                staff_units=[places.to_place_out(r) for r in units],
            ),
            200,
        )

    if place.visibility is Visibility.PUBLIC and place.status is PlaceStatus.ACTIVE:
        public_row = session.execute(_public_select().where(Place.id == place.id)).one()
        return (
            ResolveOut(
                kind="public",
                public_id=canonical,
                place=_to_public(public_row),
                units=_public_units(session, place.id),
            ),
            200,
        )
    if place.visibility is Visibility.PUBLIC and place.status in places.TERMINAL:
        successors: list[str] = []
        if place.successor_ids:
            successors = list(
                session.scalars(
                    select(Place.public_id).where(Place.id.in_(place.successor_ids), *_PUBLIC_VISIBLE)
                )
            )
        return (
            ResolveOut(kind="tombstone", public_id=canonical, status=place.status, successor_ids=successors),
            200,
        )
    return ResolveOut(kind="minimal", public_id=canonical), 200


def search(session: Session, q: str) -> list[PublicPlaceOut]:
    """Public, active houses and buildings only. Capped, so it cannot be used to dump the registry."""
    term = q.strip()
    if not term:
        return []
    stmt = (
        _public_select()
        .where(Place.type != PlaceType.UNIT, *_PUBLIC_VISIBLE, places.text_match(term))
        .order_by(Place.name)
        .limit(SEARCH_LIMIT)
    )
    return [_to_public(r) for r in session.execute(stmt)]


def _find_public(session: Session, ref: str) -> Any:
    """A public, active place by its internal id or by its PINPOINT ID; otherwise 404."""
    cond = None
    try:
        cond = Place.id == uuid.UUID(ref)
    except ValueError:
        check = place_id.validate(ref)
        if check.ok:
            cond = Place.public_id == check.canonical
    if cond is None:
        raise NotFound("Place not found.")
    row = session.execute(_public_select().where(cond, *_PUBLIC_VISIBLE)).first()
    if row is None:
        raise NotFound("Place not found.")
    return row


def public_place(session: Session, ref: str) -> PublicPlaceDetail:
    row = _find_public(session, ref)
    return PublicPlaceDetail(place=_to_public(row), units=_public_units(session, row[0].id))


def submit_correction(
    session: Session, who: Access, ref: str, note: str, client: ClientInfo
) -> CorrectionOut:
    """ "Report a problem": the one write a normal user can make. Only about places they can see."""
    row = _find_public(session, ref)
    place: Place = row[0]
    since = datetime.now(timezone.utc) - timedelta(days=1)
    recent = session.scalar(
        select(func.count()).where(
            CorrectionRequest.submitted_by == who.user_id, CorrectionRequest.created_at > since
        )
    )
    if (recent or 0) >= CORRECTIONS_PER_DAY:
        raise RateLimited(f"You can send {CORRECTIONS_PER_DAY} reports a day. Please try again tomorrow.")
    with places.atomic(session):
        correction = CorrectionRequest(place_id=place.id, submitted_by=who.user_id, note=note.strip())
        session.add(correction)
        session.flush()
        places.record_event(session, place, "correction_requested", who.user_id)
        audit.record(
            session,
            action="correction.submit",
            resource_type="correction",
            actor_id=who.user_id,
            resource_id=str(correction.id),
            jurisdiction_id=place.jurisdiction_id,
            client=client,
            detail={"place_id": str(place.id)},
        )
    return CorrectionOut(id=correction.id, status=correction.status.value, created_at=correction.created_at)
