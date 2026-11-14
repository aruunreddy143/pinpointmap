from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent


@dataclass(frozen=True)
class ClientInfo:
    ip: str | None = None
    request_id: str | None = None


def record(
    session: Session,
    *,
    action: str,
    resource_type: str,
    actor_id: uuid.UUID | None = None,
    resource_id: str | None = None,
    jurisdiction_id: uuid.UUID | None = None,
    client: ClientInfo | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditEvent:
    """Add an audit row in the caller's transaction. It commits or rolls back with the change it records.
    `detail` holds ids and field names only, never personal data (no emails, numbers or codes)."""
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        jurisdiction_id=jurisdiction_id,
        ip=client.ip if client else None,
        request_id=client.request_id if client else None,
        detail=detail,
    )
    session.add(event)
    return event
