"""Print a label for a verified place. Printing is itself recorded (audit + place history)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.core.permissions import Permission
from app.models.enums import PlaceStatus
from app.services import labels, places
from app.services.access import Access
from app.services.audit import ClientInfo


def print_label(
    session: Session,
    who: Access,
    id_: uuid.UUID,
    *,
    fmt: str,
    size: str,
    public_base_url: str,
    client: ClientInfo,
) -> tuple[bytes, str]:
    place = places.load(session, who, id_, Permission.PLACE_PRINT)
    if place.status is not PlaceStatus.ACTIVE or not place.public_id:
        raise Conflict("Labels can only be printed for verified (active) places.")
    content, media_type = labels.render_label(
        place.public_id,
        labels.resolver_url(public_base_url, place.public_id),
        place.name,
        place.locality,
        fmt,
        size,
    )
    with places.atomic(session):
        places.record_event(session, place, "label_printed", who.user_id, after={"format": fmt, "size": size})
        places.record_audit(
            session, "place.label_print", place, who.user_id, client, {"format": fmt, "size": size}
        )
    return content, media_type
