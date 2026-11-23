from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.models.enums import JurisdictionLevel, Role


class JurisdictionOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    level: JurisdictionLevel
    parent_id: uuid.UUID | None


class StaffRowOut(BaseModel):
    """One row per role assignment (a person with two roles appears twice) and one per pending invite."""

    id: uuid.UUID  # the role assignment id, or the invite id
    user_id: uuid.UUID | None  # null for an invite that has not been accepted
    email: str
    name: str
    role: Role
    jurisdiction_id: uuid.UUID
    jurisdiction_name: str
    status: Literal["active", "invited"]
    # Only for the person who created the invite, and never in production.
    invite_token: str | None = None
    invite_expires_at: datetime | None = None


class AuditEventOut(BaseModel):
    id: int
    at: datetime
    actor_id: uuid.UUID | None
    actor_name: str | None
    action: str
    resource_type: str
    resource_id: str | None
    jurisdiction_id: uuid.UUID | None
    request_id: str | None
    detail: dict[str, Any] | None


class AuditPage(BaseModel):
    items: list[AuditEventOut]
    next_before_id: int | None  # pass as ?before_id= to get the next (older) page
