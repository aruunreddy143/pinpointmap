"""Importing this package registers every table on Base.metadata (Alembic and tests rely on it)."""

from app.models.audit import AuditEvent
from app.models.place import ConsentRecord, CorrectionRequest, Place, PlaceEvent
from app.models.user import AppUser, Invite, Jurisdiction, OtpChallenge, RefreshToken, RoleAssignment

__all__ = [
    "AppUser",
    "AuditEvent",
    "ConsentRecord",
    "CorrectionRequest",
    "Invite",
    "Jurisdiction",
    "OtpChallenge",
    "Place",
    "PlaceEvent",
    "RefreshToken",
    "RoleAssignment",
]
