from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import Actor, get_session, require_permission
from app.core.permissions import Permission
from app.schemas.admin import AuditPage
from app.services import admin_read

router = APIRouter(prefix="/audit", tags=["audit"])
CAN_READ_AUDIT = Depends(require_permission(Permission.AUDIT_READ))


@router.get("/events", response_model=AuditPage)
def list_events(
    action: str | None = Query(None, max_length=60),
    resource_type: str | None = Query(None, max_length=40),
    resource_id: str | None = Query(None, max_length=64),
    actor_id: uuid.UUID | None = None,
    before_id: int | None = Query(None, ge=1),
    limit: int = Query(50, ge=1, le=admin_read.AUDIT_PAGE_MAX),
    actor: Actor = CAN_READ_AUDIT,
    session: Session = Depends(get_session),
) -> AuditPage:
    """The audit log for the caller's jurisdictions, newest first."""
    return admin_read.list_audit_events(
        session,
        actor.access,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        actor_id=actor_id,
        before_id=before_id,
        limit=limit,
    )
