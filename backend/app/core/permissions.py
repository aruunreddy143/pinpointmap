"""Role -> permission map. One place only; never scatter `if role == ...` checks.
Mirrors frontend/src/lib/permissions.ts (a test compares the two)."""

from __future__ import annotations

from enum import Enum

from app.models.enums import Role


class Permission(str, Enum):
    PLACE_READ = "place:read"
    PLACE_READ_PUBLIC = "place:read_public"
    PLACE_CREATE = "place:create"
    PLACE_UPDATE = "place:update"
    PLACE_VERIFY = "place:verify"
    PLACE_PRINT = "place:print"
    USER_MANAGE = "user:manage"
    AUDIT_READ = "audit:read"
    CORRECTION_REQUEST = "correction:request"


P = Permission

_STAFF_ALL = frozenset(
    {P.PLACE_READ, P.PLACE_CREATE, P.PLACE_UPDATE, P.PLACE_VERIFY, P.PLACE_PRINT, P.USER_MANAGE, P.AUDIT_READ}
)

ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    Role.SUPER_ADMIN.value: _STAFF_ALL,
    Role.ADMIN.value: _STAFF_ALL,
    Role.REGISTRAR.value: frozenset({P.PLACE_READ, P.PLACE_CREATE, P.PLACE_UPDATE}),
    Role.VERIFIER.value: frozenset({P.PLACE_READ, P.PLACE_VERIFY}),
    Role.PRINTER.value: frozenset({P.PLACE_READ, P.PLACE_PRINT}),
    Role.AUDITOR.value: frozenset({P.PLACE_READ, P.AUDIT_READ}),
    # Normal users have no assignment; they are granted this fixed set by account kind.
    "viewer": frozenset({P.PLACE_READ_PUBLIC, P.CORRECTION_REQUEST}),
}


def role_can(role: str, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
