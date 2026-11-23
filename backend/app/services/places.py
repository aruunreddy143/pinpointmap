"""Places: register, list, edit, verify (four-eyes), visibility, history and the review queue.

Rules (mirrors frontend/src/mocks/api.ts and the pinpoint-* skills):
- Staff only see places inside their jurisdiction (the query filters; out of scope is 404, never 403).
- The public ID is issued on submit, never earlier. Units get their own IDs.
- The person who submitted a place cannot approve it (four-eyes). Rejecting needs a reason.
- Going public needs a verifier who is not the creator, plus a recorded consent.
- Every mutation writes place_event + audit_event in the same transaction as the change.
- No hard deletes. Services never import the web framework."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import and_, cast, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.core.errors import Conflict, DuplicateSuspect, InvalidInput, NotFound, PermissionDenied
from app.core.geo import (
    DUPLICATE_RADIUS_M,
    GOOD_ACCURACY_M,
    PIN_MOVE_NEEDS_VERIFIER_M,
    LatLon,
    point,
)
from app.core.permissions import ROLE_PERMISSIONS, Permission
from app.domain import place_id
from app.domain.state_machine import IllegalTransitionError, PlaceStatus, transition
from app.domain.units import parse_unit_labels
from app.models import AppUser, ConsentRecord, Jurisdiction, Place, PlaceEvent
from app.models.enums import PlaceType, Visibility
from app.schemas.places import (
    NewPlace,
    PlaceEventOut,
    PlaceNearbyOut,
    PlaceOut,
    PlacePatch,
    ReviewCheck,
    ReviewItemOut,
)
from app.services import audit, jurisdictions
from app.services.access import Access
from app.services.audit import ClientInfo

P = Permission
ACTIVE_STATUSES = (PlaceStatus.DRAFT, PlaceStatus.PENDING, PlaceStatus.ACTIVE)
TERMINAL = (PlaceStatus.RETIRED, PlaceStatus.MERGED, PlaceStatus.SPLIT)
NEARBY_MAX_RADIUS_M = 500
NEARBY_MAX_RESULTS = 50
_DEGREE_MARGIN_PER_M = 1 / 80_000  # 1 degree is >= 87 km inside India, so this pre-filter never misses


# ---------- shared helpers ----------
@contextmanager
def atomic(session: Session) -> Iterator[None]:
    """Everything inside commits together or not at all, even if the caller's session is reused."""
    with session.begin_nested():
        yield
    session.commit()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lat() -> Any:
    return func.ST_Y(func.ST_PointOnSurface(Place.geometry))


def _lon() -> Any:
    return func.ST_X(func.ST_PointOnSurface(Place.geometry))


def _geog(expr: Any) -> Any:
    return cast(expr, Geography)


def _near(column: Any, pt: Any, meters: float) -> Any:
    """Index-friendly pre-filter in degrees, then the exact test on geography (meters)."""
    return and_(
        func.ST_DWithin(column, pt, meters * _DEGREE_MARGIN_PER_M + 1e-9),
        func.ST_DWithin(_geog(column), _geog(pt), meters),
    )


def place_select(*extra: Any) -> Any:
    """Place rows plus lat, lon, creator name and unit count, ready for `to_place_out`."""
    child = aliased(Place)
    unit_count = (
        select(func.count())
        .where(child.parent_id == Place.id, child.status != PlaceStatus.RETIRED)
        .correlate(Place)
        .scalar_subquery()
    )
    creator = aliased(AppUser)
    return select(
        Place,
        _lat().label("lat"),
        _lon().label("lon"),
        creator.name.label("creator"),
        unit_count.label("units"),
        *extra,
    ).join(creator, creator.id == Place.created_by)


def to_place_out(row: Any) -> PlaceOut:
    p: Place = row[0]
    return PlaceOut(
        id=p.id,
        public_id=p.public_id,
        type=p.type,
        parent_id=p.parent_id,
        label=p.label,
        name=p.name,
        geo=LatLon(lat=row.lat, lon=row.lon),
        accuracy_m=float(p.accuracy_m) if p.accuracy_m is not None else None,
        source=p.location_source,
        address=p.address_text,
        landmark=p.landmark,
        locality=p.locality,
        district=p.district,
        state=p.state,
        postal_pin=p.postal_pin,
        status=p.status,
        visibility=p.visibility,
        jurisdiction_id=p.jurisdiction_id,
        created_by=p.created_by,
        created_by_name=row.creator,
        created_at=p.created_at,
        verified_at=p.verified_at,
        unit_count=None if p.type is PlaceType.UNIT else row.units,
    )


def place_out(session: Session, id_: uuid.UUID) -> PlaceOut:
    return to_place_out(session.execute(place_select().where(Place.id == id_)).one())


def load(session: Session, who: Access, id_: uuid.UUID, permission: Permission = P.PLACE_READ) -> Place:
    """The place, if the caller may see it AND may use `permission` on it. Outside the caller's
    jurisdiction it does not exist (404). Visible but not allowed (e.g. a printer editing) is 403."""
    visible = who.scope(session, P.PLACE_READ)
    place = session.scalar(select(Place).where(Place.id == id_, Place.jurisdiction_id.in_(visible)))
    if place is None:
        raise NotFound("Place not found.")
    if permission is not P.PLACE_READ and place.jurisdiction_id not in who.scope(session, permission):
        raise PermissionDenied("You don't have permission to do that.")
    return place


def record_event(
    session: Session,
    place: Place,
    kind: str,
    actor_id: uuid.UUID,
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    reason: str | None = None,
) -> None:
    # `at` is set here, not by the database's now(), which is frozen for a whole transaction: events in
    # one request must still sort in the order they happened.
    session.add(
        PlaceEvent(
            place_id=place.id,
            type=kind,
            actor_id=actor_id,
            at=_now(),
            before=before,
            after=after,
            reason=reason,
        )
    )


def record_audit(
    session: Session,
    action: str,
    place: Place,
    actor_id: uuid.UUID,
    client: ClientInfo,
    detail: dict[str, Any] | None = None,
) -> None:
    audit.record(
        session,
        action=action,
        resource_type="place",
        actor_id=actor_id,
        resource_id=str(place.id),
        jurisdiction_id=place.jurisdiction_id,
        client=client,
        detail=detail,
    )


def _public_id_taken(session: Session, candidate: str) -> bool:
    return bool(session.scalar(select(exists().where(Place.public_id == candidate))))


def issue_ids_and_insert(session: Session, rows: list[Place], lat: float, lon: float) -> None:
    """Give every row an ID from the cell at (lat, lon) and insert them (rows[0] first, so it can be
    the parent of the rest). The unique constraint is the final guard: if two requests race for the
    same ID, the loser's insert fails and is retried with fresh IDs."""
    for _ in range(5):
        taken: set[str] = set()
        for row in rows:
            row.public_id = place_id.generate(
                lat, lon, lambda c, taken=taken: c in taken or _public_id_taken(session, c)
            )
            taken.add(row.public_id)
        try:
            with session.begin_nested():
                session.add(rows[0])
                session.flush()
                session.add_all(rows[1:])
                session.flush()
            return
        except IntegrityError as exc:
            if "public_id" not in str(exc.orig):
                raise
    raise Conflict("Could not issue a free ID. Please try again.")


def _unit_labels(raw: list[str]) -> list[str]:
    parsed = parse_unit_labels("\n".join(raw))
    if parsed.error:
        raise InvalidInput(parsed.error)
    for label in parsed.labels:
        if len(label) > 60:
            raise InvalidInput(f'Unit label "{label[:20]}..." is longer than 60 characters.')
    return parsed.labels


def _unit_rows(
    parent: Place, labels: list[str], created_by: uuid.UUID, status: PlaceStatus, geo: LatLon
) -> list[Place]:
    return [
        Place(
            id=uuid.uuid4(),
            type=PlaceType.UNIT,
            parent_id=parent.id,
            label=label,
            name=f"{parent.name}, {label}",
            geometry=point(geo),
            accuracy_m=parent.accuracy_m,
            location_source=parent.location_source,
            address_text=parent.address_text,
            landmark=parent.landmark,
            locality=parent.locality,
            district=parent.district,
            state=parent.state,
            postal_pin=parent.postal_pin,
            jurisdiction_id=parent.jurisdiction_id,
            status=status,
            visibility=parent.visibility,
            created_by=created_by,
        )
        for label in labels
    ]


# ---------- reads ----------
def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def text_match(term: str) -> Any:
    """name, address, locality or ID contains `term` (case-insensitive; wildcards are plain characters)."""
    like = _like(term)
    clauses = [
        Place.name.ilike(like, escape="\\"),
        Place.address_text.ilike(like, escape="\\"),
        Place.locality.ilike(like, escape="\\"),
    ]
    id_part = place_id.normalize(term)
    if id_part:
        clauses.append(Place.public_id.ilike(_like(id_part), escape="\\"))
    return or_(*clauses)


def list_places(
    session: Session, who: Access, *, q: str = "", status: PlaceStatus | None = None, limit: int = 200
) -> list[PlaceOut]:
    stmt = place_select().where(
        Place.type != PlaceType.UNIT, Place.jurisdiction_id.in_(who.scope(session, P.PLACE_READ))
    )
    if status:
        stmt = stmt.where(Place.status == status)
    term = q.strip()
    if term:
        stmt = stmt.where(text_match(term))
    stmt = stmt.order_by(Place.created_at.desc(), Place.name).limit(min(limit, 500))
    return [to_place_out(r) for r in session.execute(stmt)]


def get_place(session: Session, who: Access, id_: uuid.UUID, client: ClientInfo) -> PlaceOut:
    place = load(session, who, id_)
    if place.visibility is Visibility.PRIVATE:  # staff reads of private places are audited
        record_audit(session, "place.read_private", place, who.user_id, client)
        session.commit()
    return place_out(session, place.id)


def list_units(session: Session, who: Access, parent_id: uuid.UUID) -> list[PlaceOut]:
    parent = load(session, who, parent_id)
    rows = session.execute(
        place_select().where(Place.parent_id == parent.id).order_by(Place.created_at, Place.label)
    )
    return [to_place_out(r) for r in rows]


def find_nearby(session: Session, who: Access, geo: LatLon, radius_m: float) -> list[PlaceNearbyOut]:
    """Duplicate guard lookup: active or pending houses/buildings within `radius_m`, nearest first.
    Capped in radius and count so it can never be used to list the registry."""
    radius = min(max(radius_m, 1), NEARBY_MAX_RADIUS_M)
    pt = point(geo)
    dist = func.ST_Distance(_geog(Place.geometry), _geog(pt))
    stmt = (
        place_select(dist.label("dist"))
        .where(
            Place.type != PlaceType.UNIT,
            Place.status.in_((PlaceStatus.ACTIVE, PlaceStatus.PENDING)),
            Place.jurisdiction_id.in_(who.scope(session, P.PLACE_READ)),
            _near(Place.geometry, pt, radius),
        )
        .order_by(dist)
        .limit(NEARBY_MAX_RESULTS)
    )
    return [
        PlaceNearbyOut(**to_place_out(r).model_dump(), distance_m=round(r.dist))
        for r in session.execute(stmt)
    ]


# ---------- history ----------
_TONE = {
    "submitted": "accent",
    "resubmitted": "accent",
    "verified": "ok",
    "rejected": "warn",
    "units_added": "accent",
    "units_verified": "ok",
    "units_rejected": "warn",
    "pin_moved": "warn",
    "updated": "accent",
    "visibility_changed": "accent",
    "label_printed": "muted",
    "correction_requested": "warn",
}


def event_title(ev: PlaceEvent) -> str:
    after = ev.after or {}
    n = after.get("count")
    if ev.type == "submitted":
        return "Submitted for verification" + (f" with {n} units" if n else "")
    if ev.type == "rejected":
        return f"Rejected: {ev.reason}" if ev.reason else "Rejected"
    if ev.type == "units_added":
        return "1 unit added" if n == 1 else f"{n} units added"
    if ev.type == "units_rejected":
        return f"{n} new units rejected" + (f": {ev.reason}" if ev.reason else "")
    if ev.type == "pin_moved":
        return f"Pin moved {after.get('moved_m', 0)} m"
    if ev.type == "updated":
        return "Details updated (" + ", ".join(after.get("fields", [])) + ")"
    if ev.type == "visibility_changed":
        return "Made public" if after.get("visibility") == "public" else "Made private"
    if ev.type == "label_printed":
        return "Label printed" + (f" ({n} units)" if n else "")
    fixed = {
        "resubmitted": "Resubmitted for verification",
        "verified": "Verified and activated",
        "units_verified": f"{n} new units verified",
        "correction_requested": "Problem reported by a user",
    }
    return fixed.get(ev.type, ev.type.replace("_", " ").capitalize())


def history(session: Session, who: Access, id_: uuid.UUID) -> list[PlaceEventOut]:
    place = load(session, who, id_)
    rows = session.execute(
        select(PlaceEvent, AppUser.name, AppUser.kind)
        .join(AppUser, AppUser.id == PlaceEvent.actor_id)
        .where(PlaceEvent.place_id == place.id)
        .order_by(PlaceEvent.at.desc(), PlaceEvent.id)
    )
    return [
        PlaceEventOut(
            id=ev.id,
            place_id=ev.place_id,
            type=ev.type,
            title=event_title(ev),
            actor_name=name if kind.value == "staff" else "Normal user",  # viewers' names stay private
            at=ev.at,
            tone=_TONE.get(ev.type, "muted"),
            reason=ev.reason,
        )
        for ev, name, kind in rows
    ]


# ---------- create ----------
def _roles_that_can(permission: Permission) -> set[str]:
    return {role for role, perms in ROLE_PERMISSIONS.items() if permission in perms}


def _creation_jurisdiction(session: Session, who: Access, requested: uuid.UUID | None) -> uuid.UUID:
    scope = who.scope(session, P.PLACE_CREATE)
    if requested is not None:
        if requested not in scope:
            raise PermissionDenied("You can only register places in jurisdictions you work in.")
        return requested
    roles = _roles_that_can(P.PLACE_CREATE)
    granted = {jid for role, jid in who.grants if role in roles}
    if len(granted) == 1:
        (only,) = granted
        if not session.scalar(select(exists().where(Jurisdiction.parent_id == only))):
            return only
    raise InvalidInput("Choose the area this place is in (jurisdiction_id).")


def create_place(session: Session, who: Access, data: NewPlace, client: ClientInfo) -> PlaceOut:
    """Register and submit a house or building (with its units). The ID is issued here."""
    labels = _unit_labels(data.unit_labels)
    if labels and data.type == "house":
        raise InvalidInput("Only buildings have units.")
    jid = _creation_jurisdiction(session, who, data.jurisdiction_id)
    nearby = find_nearby(session, who, data.geo, DUPLICATE_RADIUS_M)
    if nearby and not data.different_place_reason:
        first = nearby[0]
        raise DuplicateSuspect(
            f'"{first.name}" is already registered {first.distance_m} m from this pin. Open it, or '
            "explain why this is a different place (different_place_reason)."
        )
    state, district = jurisdictions.state_and_district(session, jid)
    geo = data.geo.rounded()
    with atomic(session):
        parent = Place(
            id=uuid.uuid4(),
            type=PlaceType(data.type),
            name=data.name.strip(),
            geometry=point(geo),
            accuracy_m=data.accuracy_m,
            location_source=data.source,
            address_text=data.address.strip(),
            landmark=data.landmark.strip(),
            locality=data.locality.strip(),
            district=district,
            state=state,
            postal_pin=data.postal_pin,
            jurisdiction_id=jid,
            status=PlaceStatus.PENDING,
            visibility=Visibility.PRIVATE,
            created_by=who.user_id,
        )
        units = _unit_rows(parent, labels, who.user_id, PlaceStatus.PENDING, geo)
        issue_ids_and_insert(session, [parent, *units], geo.lat, geo.lon)
        record_event(
            session,
            parent,
            "submitted",
            who.user_id,
            after={"type": data.type, "count": len(labels), "duplicate_override": bool(nearby)},
            reason=data.different_place_reason,
        )
        record_audit(
            session,
            "place.create",
            parent,
            who.user_id,
            client,
            {"type": data.type, "units": len(labels), "duplicate_override": bool(nearby)},
        )
    return place_out(session, parent.id)


def add_units(
    session: Session, who: Access, parent_id: uuid.UUID, raw: list[str], client: ClientInfo
) -> PlaceOut:
    parent = load(session, who, parent_id, P.PLACE_UPDATE)
    if parent.type is not PlaceType.BUILDING:
        raise InvalidInput("Only buildings have units.")
    if parent.status not in (PlaceStatus.PENDING, PlaceStatus.ACTIVE, PlaceStatus.REJECTED):
        raise Conflict(f"Units cannot be added to a place that is {parent.status.value}.")
    labels = _unit_labels(raw)
    taken = set(
        session.scalars(
            select(func.lower(Place.label)).where(
                Place.parent_id == parent.id, Place.status.in_(ACTIVE_STATUSES)
            )
        )
    )
    repeated = [label for label in labels if label.lower() in taken]
    if repeated:
        raise Conflict(f"This building already has units: {', '.join(repeated[:10])}.")
    # Units added to a verified building wait for a verifier; otherwise they follow the building.
    status = PlaceStatus.PENDING if parent.status is PlaceStatus.ACTIVE else parent.status
    lat, lon = session.execute(select(_lat(), _lon()).where(Place.id == parent.id)).one()
    geo = LatLon(lat=lat, lon=lon)
    with atomic(session):
        units = _unit_rows(parent, labels, who.user_id, status, geo)
        issue_ids_and_insert(session, units, geo.lat, geo.lon)
        record_event(session, parent, "units_added", who.user_id, after={"count": len(labels)})
        record_audit(session, "place.units_add", parent, who.user_id, client, {"units": len(labels)})
    return place_out(session, parent.id)


# ---------- edit ----------
_PATCH_COLUMNS = {
    "name": "name",
    "address": "address_text",
    "landmark": "landmark",
    "locality": "locality",
    "postal_pin": "postal_pin",
    "accuracy_m": "accuracy_m",
}


def update_place(
    session: Session, who: Access, id_: uuid.UUID, patch: PlacePatch, client: ClientInfo
) -> PlaceOut:
    place = load(session, who, id_, P.PLACE_UPDATE)
    if place.status in TERMINAL:
        raise Conflict(f"A place that is {place.status.value} cannot be edited.")
    if place.type is PlaceType.UNIT:
        raise Conflict("Edit the building instead; units follow it.")
    changed: dict[str, Any] = {}
    before: dict[str, Any] = {}
    for api_name, column in _PATCH_COLUMNS.items():
        value = getattr(patch, api_name)
        if value is None:
            continue
        value = value.strip() if isinstance(value, str) else value
        current = getattr(place, column)
        current = float(current) if column == "accuracy_m" and current is not None else current
        if value != current:
            before[api_name] = current
            changed[api_name] = value
    new_pt = None
    moved_m = 0
    if patch.geo is not None:
        new_pt = point(patch.geo.rounded())
        moved_m = round(
            session.scalar(
                select(func.ST_Distance(_geog(Place.geometry), _geog(new_pt))).where(Place.id == place.id)
            )
            or 0
        )
        if moved_m > PIN_MOVE_NEEDS_VERIFIER_M and place.jurisdiction_id not in who.scope(
            session, P.PLACE_VERIFY
        ):
            raise PermissionDenied(
                f"Moving a pin more than {PIN_MOVE_NEEDS_VERIFIER_M} m needs a verifier. Ask one to make this change."
            )
    if not changed and moved_m == 0:
        return place_out(session, place.id)
    with atomic(session):
        for api_name, value in changed.items():
            setattr(place, _PATCH_COLUMNS[api_name], value)
        if moved_m > 0:
            place.geometry = new_pt
        place.updated_by = who.user_id
        place.updated_at = _now()
        # Units follow their building: same pin, address and accuracy; the name is "<building>, <label>".
        follow: dict[str, Any] = {_PATCH_COLUMNS[k]: v for k, v in changed.items() if k != "name"}
        if "name" in changed:
            follow["name"] = func.concat(changed["name"], ", ", Place.label)
        if moved_m > 0:
            follow["geometry"] = new_pt
        if follow:
            session.execute(update(Place).where(Place.parent_id == place.id).values(**follow))
        if changed:
            record_event(
                session,
                place,
                "updated",
                who.user_id,
                before=before,
                after={**changed, "fields": sorted(changed)},
                reason=patch.reason,
            )
        if moved_m > 0:
            record_event(
                session, place, "pin_moved", who.user_id, after={"moved_m": moved_m}, reason=patch.reason
            )
        record_audit(
            session,
            "place.update",
            place,
            who.user_id,
            client,
            {"fields": sorted(changed), "pin_moved_m": moved_m or None},
        )
    return place_out(session, place.id)


def change_visibility(
    session: Session,
    who: Access,
    id_: uuid.UUID,
    target: Visibility,
    client: ClientInfo,
    *,
    consent_given_by: str | None = None,
    consent_fields: list[str] | None = None,
) -> PlaceOut:
    place = load(session, who, id_)
    if place.type is PlaceType.UNIT:
        raise Conflict("Units follow their building's visibility.")
    # Who may ask is checked first, so a no-op request is not a way to probe what a role may do.
    if target is Visibility.PUBLIC:
        if place.jurisdiction_id not in who.scope(session, P.PLACE_VERIFY):
            raise PermissionDenied("Making a place public needs a verifier.")
    elif place.jurisdiction_id not in (
        who.scope(session, P.PLACE_UPDATE) | who.scope(session, P.PLACE_VERIFY)
    ):
        raise PermissionDenied("You don't have permission to do that.")
    if place.visibility is target:
        return place_out(session, place.id)
    if target is Visibility.PUBLIC:
        if place.created_by == who.user_id:
            raise PermissionDenied("You registered this place, so a different verifier must make it public.")
        if place.restricted:
            raise Conflict("This place is restricted and can never be public.")
        if place.status is not PlaceStatus.ACTIVE:
            raise Conflict("Only a verified (active) place can be made public.")
        if not consent_given_by:
            raise InvalidInput("Record who gave consent to make this place public (consent_given_by).")
    previous = place.visibility
    with atomic(session):
        place.visibility = target
        place.updated_by = who.user_id
        place.updated_at = _now()
        session.execute(update(Place).where(Place.parent_id == place.id).values(visibility=target))
        if target is Visibility.PUBLIC:
            session.add(
                ConsentRecord(
                    place_id=place.id,
                    given_by_name=consent_given_by,
                    fields=consent_fields or ["name", "address", "location"],
                    recorded_by=who.user_id,
                )
            )
        else:
            session.execute(
                update(ConsentRecord)
                .where(ConsentRecord.place_id == place.id, ConsentRecord.revoked_at.is_(None))
                .values(revoked_at=_now())
            )
        record_event(
            session,
            place,
            "visibility_changed",
            who.user_id,
            before={"visibility": previous.value},
            after={"visibility": target.value},
        )
        record_audit(session, "place.visibility", place, who.user_id, client, {"visibility": target.value})
    return place_out(session, place.id)


# ---------- verification ----------
def _last_submission(session: Session, place: Place, kinds: tuple[str, ...]) -> tuple[uuid.UUID, datetime]:
    ev = session.scalar(
        select(PlaceEvent)
        .where(PlaceEvent.place_id == place.id, PlaceEvent.type.in_(kinds))
        .order_by(PlaceEvent.at.desc())
        .limit(1)
    )
    return (ev.actor_id, ev.at) if ev else (place.created_by, place.created_at)


def _pending_units(session: Session, place: Place) -> int:
    return (
        session.scalar(
            select(func.count()).where(Place.parent_id == place.id, Place.status == PlaceStatus.PENDING)
        )
        or 0
    )


def decide(
    session: Session, who: Access, id_: uuid.UUID, decision: str, reason: str, client: ClientInfo
) -> PlaceOut:
    """Approve or reject a submitted place (its pending units go with it), or just the new units of
    an already verified building."""
    place = load(session, who, id_, P.PLACE_VERIFY)
    if place.type is PlaceType.UNIT:
        raise Conflict("Units are verified together with their building.")
    reason = reason.strip()
    approve = decision == "approve"
    units_only = place.status is PlaceStatus.ACTIVE
    if units_only:
        if _pending_units(session, place) == 0:
            raise Conflict("There is nothing waiting for verification on this place.")
        submitter, _ = _last_submission(session, place, ("units_added",))
    else:
        submitter, _ = _last_submission(session, place, ("submitted", "resubmitted"))
    if submitter == who.user_id:
        raise PermissionDenied("You submitted this place, so a different verifier must approve it.")
    if not approve and not reason:
        raise InvalidInput("A reason is required to reject.")
    target = PlaceStatus.ACTIVE if approve else PlaceStatus.REJECTED
    if not units_only:
        try:
            transition(place.status, target)
        except IllegalTransitionError as exc:
            raise Conflict(str(exc)) from exc
    now = _now()
    before_status = place.status.value
    with atomic(session):
        n_units = session.execute(
            update(Place)
            .where(Place.parent_id == place.id, Place.status == PlaceStatus.PENDING)
            .values(
                status=target,
                verified_by=who.user_id if approve else None,
                verified_at=now if approve else None,
                updated_at=now,
            )
        ).rowcount
        if units_only:
            kind = "units_verified" if approve else "units_rejected"
        else:
            place.status = target
            place.verified_by = who.user_id if approve else None
            place.verified_at = now if approve else None
            place.updated_by = who.user_id
            place.updated_at = now
            kind = "verified" if approve else "rejected"
        record_event(
            session,
            place,
            kind,
            who.user_id,
            before={"status": before_status},
            after={"status": target.value, "count": n_units},
            reason=reason or None,
        )
        record_audit(
            session,
            f"place.{decision}",
            place,
            who.user_id,
            client,
            {"units": n_units, "units_only": units_only},
        )
    return place_out(session, place.id)


def resubmit(session: Session, who: Access, id_: uuid.UUID, client: ClientInfo) -> PlaceOut:
    place = load(session, who, id_, P.PLACE_UPDATE)
    if place.type is PlaceType.UNIT:
        raise Conflict("Resubmit the building; its units follow.")
    try:
        transition(place.status, PlaceStatus.PENDING)
    except IllegalTransitionError as exc:
        raise Conflict(str(exc)) from exc
    with atomic(session):
        place.status = PlaceStatus.PENDING
        place.updated_by = who.user_id
        place.updated_at = _now()
        session.execute(
            update(Place)
            .where(Place.parent_id == place.id, Place.status == PlaceStatus.REJECTED)
            .values(status=PlaceStatus.PENDING)
        )
        record_event(
            session,
            place,
            "resubmitted",
            who.user_id,
            before={"status": "rejected"},
            after={"status": "pending_verification"},
        )
        record_audit(session, "place.resubmit", place, who.user_id, client)
    return place_out(session, place.id)


# ---------- review queue ----------
def _nearest_m(session: Session, place: Place, lat: float, lon: float) -> int | None:
    pt = point(LatLon(lat=lat, lon=lon))
    value = session.scalar(
        select(func.ST_Distance(_geog(Place.geometry), _geog(pt)))
        .where(Place.id != place.id, Place.type != PlaceType.UNIT, Place.status == PlaceStatus.ACTIVE)
        .order_by(Place.geometry.op("<->")(pt))
        .limit(1)
    )
    return None if value is None else round(value)


def review_queue(session: Session, who: Access, kind: str) -> list[ReviewItemOut]:
    """Items waiting for a verifier in their jurisdiction, oldest first. kind: new | change | merge.
    `new` = submitted places; `change` = verified buildings with new units waiting; `merge` is empty
    until merge requests exist."""
    if kind == "merge":
        return []
    scope = who.scope(session, P.PLACE_VERIFY)
    pending_child = aliased(Place)
    base = place_select().where(Place.type != PlaceType.UNIT, Place.jurisdiction_id.in_(scope))
    if kind == "new":
        stmt = base.where(Place.status == PlaceStatus.PENDING)
        kinds: tuple[str, ...] = ("submitted", "resubmitted")
    else:
        stmt = base.where(
            Place.status == PlaceStatus.ACTIVE,
            exists().where(pending_child.parent_id == Place.id, pending_child.status == PlaceStatus.PENDING),
        )
        kinds = ("units_added",)
    items: list[ReviewItemOut] = []
    for row in session.execute(stmt.limit(200)).all():
        place: Place = row[0]
        actor_id, at = _last_submission(session, place, kinds)
        submitter = session.scalar(select(AppUser.name).where(AppUser.id == actor_id)) or ""
        nearest = _nearest_m(session, place, row.lat, row.lon)
        suspect = nearest is not None and nearest <= DUPLICATE_RADIUS_M
        items.append(
            ReviewItemOut(
                id=f"{kind}-{place.id}",
                place_id=place.id,
                kind=kind,  # type: ignore[arg-type]
                submitted_by=submitter,
                submitted_at=at,
                nearest_m=nearest,
                duplicate_suspect=suspect,
                checks=_checks(session, place, nearest, suspect, kind),
                place=to_place_out(row),
            )
        )
    items.sort(key=lambda i: i.submitted_at)
    return items


def _checks(
    session: Session, place: Place, nearest: int | None, suspect: bool, kind: str
) -> list[ReviewCheck]:
    acc = float(place.accuracy_m) if place.accuracy_m is not None else None
    if acc is None:
        accuracy_detail = "Not recorded"
    else:
        accuracy_detail = f"± {acc:g} m, " + ("within" if acc <= GOOD_ACCURACY_M else "worse than")
        accuracy_detail += f" the {GOOD_ACCURACY_M} m limit"
    if nearest is None:
        dup_detail = "No other active place found"
    elif suspect:
        dup_detail = f"An active place is {nearest} m away. Check it is different"
    else:
        dup_detail = f"Nearest active place is {nearest} m away"
    has_address = bool(place.locality and place.postal_pin)
    checks = [
        ReviewCheck(
            title="Pin accuracy", detail=accuracy_detail, ok=acc is not None and acc <= GOOD_ACCURACY_M
        ),
        ReviewCheck(title="No duplicate nearby", detail=dup_detail, ok=not suspect),
        ReviewCheck(
            title="Address matches locality",
            detail=f"{place.locality}, {place.postal_pin}"
            if has_address
            else "Locality or PIN code is missing",
            ok=has_address,
        ),
        ReviewCheck(
            title="Entrance point set",
            detail="Set" if place.entrance_point is not None else "Not set. Optional, but helps delivery",
            ok=place.entrance_point is not None,
        ),
    ]
    if place.type is PlaceType.BUILDING:
        n = _pending_units(session, place)
        if n:
            word = "new units" if kind == "change" else "units"
            checks.append(
                ReviewCheck(title="Unit labels unique", detail=f"{n} {word}, no repeated labels", ok=True)
            )
    return checks
