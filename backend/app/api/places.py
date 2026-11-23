"""Place endpoints for staff. Thin: parse, call a service, return a response model."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.deps import Actor, get_client, get_session, require_permission
from app.core.errors import InvalidInput
from app.core.geo import DUPLICATE_RADIUS_M, LatLon
from app.core.permissions import Permission
from app.core.settings import get_settings
from app.domain.digipin import in_bounds
from app.domain.state_machine import PlaceStatus
from app.schemas.places import (
    AddUnits,
    CorrectionIn,
    CorrectionOut,
    Decision,
    NewPlace,
    PlaceEventOut,
    PlaceNearbyOut,
    PlaceOut,
    PlacePatch,
    ReviewItemOut,
    VisibilityChange,
)
from app.services import label_service, places, public
from app.services.audit import ClientInfo

router = APIRouter(prefix="/places", tags=["places"])
review_router = APIRouter(prefix="/review", tags=["review"])

CAN_READ = Depends(require_permission(Permission.PLACE_READ))
CAN_CREATE = Depends(require_permission(Permission.PLACE_CREATE))
CAN_UPDATE = Depends(require_permission(Permission.PLACE_UPDATE))
CAN_VERIFY = Depends(require_permission(Permission.PLACE_VERIFY))
CAN_PRINT = Depends(require_permission(Permission.PLACE_PRINT))
CAN_REPORT = Depends(require_permission(Permission.CORRECTION_REQUEST))


@router.get("", response_model=list[PlaceOut])
def list_places(
    q: str = Query("", max_length=100),
    status: PlaceStatus | None = None,
    limit: int = Query(200, ge=1, le=500),
    actor: Actor = CAN_READ,
    session: Session = Depends(get_session),
) -> list[PlaceOut]:
    """Houses and buildings in the caller's jurisdiction (units come from /places/{id}/units)."""
    return places.list_places(session, actor.access, q=q, status=status, limit=limit)


@router.get("/nearby", response_model=list[PlaceNearbyOut])
def nearby(
    lat: float,
    lon: float,
    radius_m: float = Query(DUPLICATE_RADIUS_M, gt=0, le=places.NEARBY_MAX_RADIUS_M),
    actor: Actor = CAN_READ,
    session: Session = Depends(get_session),
) -> list[PlaceNearbyOut]:
    """The duplicate guard: active or pending places within `radius_m` of a pin, nearest first."""
    if not in_bounds(lat, lon):
        raise InvalidInput("The point is outside India.")
    return places.find_nearby(session, actor.access, LatLon(lat=lat, lon=lon), radius_m)


@router.post("", response_model=PlaceOut, status_code=201)
def create_place(
    body: NewPlace,
    actor: Actor = CAN_CREATE,
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> PlaceOut:
    return places.create_place(session, actor.access, body, client)


@router.get("/{place_id}", response_model=PlaceOut)
def get_place(
    place_id: uuid.UUID,
    actor: Actor = CAN_READ,
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> PlaceOut:
    return places.get_place(session, actor.access, place_id, client)


@router.patch("/{place_id}", response_model=PlaceOut)
def update_place(
    place_id: uuid.UUID,
    body: PlacePatch,
    actor: Actor = CAN_UPDATE,
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> PlaceOut:
    return places.update_place(session, actor.access, place_id, body, client)


@router.get("/{place_id}/units", response_model=list[PlaceOut])
def list_units(
    place_id: uuid.UUID, actor: Actor = CAN_READ, session: Session = Depends(get_session)
) -> list[PlaceOut]:
    return places.list_units(session, actor.access, place_id)


@router.post("/{place_id}/units", response_model=PlaceOut, status_code=201)
def add_units(
    place_id: uuid.UUID,
    body: AddUnits,
    actor: Actor = CAN_UPDATE,
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> PlaceOut:
    """Add units to a building. Returns the building (with its new unit count)."""
    return places.add_units(session, actor.access, place_id, body.labels, client)


@router.get("/{place_id}/history", response_model=list[PlaceEventOut])
def history(
    place_id: uuid.UUID, actor: Actor = CAN_READ, session: Session = Depends(get_session)
) -> list[PlaceEventOut]:
    return places.history(session, actor.access, place_id)


@router.put("/{place_id}/visibility", response_model=PlaceOut)
def set_visibility(
    place_id: uuid.UUID,
    body: VisibilityChange,
    actor: Actor = CAN_READ,  # the service decides: private needs update or verify, public needs verify
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> PlaceOut:
    return places.change_visibility(
        session,
        actor.access,
        place_id,
        body.visibility,
        client,
        consent_given_by=body.consent_given_by,
        consent_fields=list(body.consent_fields),
    )


@router.post("/{place_id}/decision", response_model=PlaceOut)
def decide(
    place_id: uuid.UUID,
    body: Decision,
    actor: Actor = CAN_VERIFY,
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> PlaceOut:
    """Approve or reject (four-eyes: not the person who submitted it; rejecting needs a reason)."""
    return places.decide(session, actor.access, place_id, body.decision, body.reason, client)


@router.post("/{place_id}/resubmit", response_model=PlaceOut)
def resubmit(
    place_id: uuid.UUID,
    actor: Actor = CAN_UPDATE,
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> PlaceOut:
    return places.resubmit(session, actor.access, place_id, client)


@router.get("/{place_id}/label")
def label(
    place_id: uuid.UUID,
    format: Literal["svg", "png", "pdf"] = "svg",  # noqa: A002 (the public query name)
    size: Literal["50x25", "a6"] = "50x25",
    actor: Actor = CAN_PRINT,
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> Response:
    """QR of the resolver URL plus Code 128 of the ID. Printing is audited."""
    content, media_type = label_service.print_label(
        session,
        actor.access,
        place_id,
        fmt=format,
        size=size,
        public_base_url=get_settings().public_base_url,
        client=client,
    )
    return Response(
        content,
        media_type=media_type,
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'inline; filename="label.{format}"',
        },
    )


@router.post("/{ref}/corrections", response_model=CorrectionOut, status_code=201)
def report_problem(
    ref: str,
    body: CorrectionIn,
    actor: Actor = CAN_REPORT,
    session: Session = Depends(get_session),
    client: ClientInfo = Depends(get_client),
) -> CorrectionOut:
    """A normal user's only write: tell staff something about a public place is wrong. 5 a day."""
    return public.submit_correction(session, actor.access, ref, body.note, client)


@review_router.get("", response_model=list[ReviewItemOut])
def review_queue(
    kind: Literal["new", "change", "merge"] = "new",
    actor: Actor = CAN_VERIFY,
    session: Session = Depends(get_session),
) -> list[ReviewItemOut]:
    return places.review_queue(session, actor.access, kind)
