"""Who is asking, as plain data. Services take this instead of the web layer's Actor, so they never
import the web framework. Built from the signed-in user's role assignments (see core/deps.py)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.permissions import ROLE_PERMISSIONS, Permission, role_can
from app.models.enums import Role
from app.services import jurisdictions


@dataclass(frozen=True)
class Access:
    user_id: uuid.UUID
    is_staff: bool
    name: str = ""
    grants: tuple[tuple[str, uuid.UUID], ...] = field(default_factory=tuple)  # (role, jurisdiction_id)

    def can(self, permission: Permission) -> bool:
        if not self.is_staff:
            return permission in ROLE_PERMISSIONS["viewer"]
        return any(role_can(role, permission) for role, _ in self.grants)

    @property
    def is_super_admin(self) -> bool:
        return any(role == Role.SUPER_ADMIN.value for role, _ in self.grants)

    def scope(self, session: Session, permission: Permission) -> set[uuid.UUID]:
        """Every jurisdiction where this person may use `permission`: the granted areas PLUS all their
        sub-areas (a state grant covers its districts and PIN areas). Queries filter by this set."""
        if not self.is_staff:
            return set()
        granted = {jid for role, jid in self.grants if role_can(role, permission)}
        return jurisdictions.expand(session, granted)
