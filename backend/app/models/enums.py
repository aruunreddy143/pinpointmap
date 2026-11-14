from enum import Enum

import sqlalchemy as sa

from app.domain.state_machine import PlaceStatus

__all__ = [
    "CorrectionStatus",
    "JurisdictionLevel",
    "LocationSource",
    "OtpChannel",
    "PlaceStatus",
    "PlaceType",
    "Role",
    "UserKind",
    "Visibility",
    "enum_column_type",
]


class PlaceType(str, Enum):
    HOUSE = "house"
    BUILDING = "building"
    UNIT = "unit"
    LAND = "land"  # Phase 2. The schema allows it now so Phase 1 rows never need migrating.


class Visibility(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"


class LocationSource(str, Enum):
    GPS = "gps"
    MAP_CLICK = "map_click"
    SURVEY = "survey"


class UserKind(str, Enum):
    STAFF = "staff"
    VIEWER = "viewer"


class Role(str, Enum):
    """Roles that are ASSIGNED per jurisdiction. Viewers have no assignment (see rbac skill)."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    REGISTRAR = "registrar"
    VERIFIER = "verifier"
    PRINTER = "printer"
    AUDITOR = "auditor"


class JurisdictionLevel(str, Enum):
    STATE = "state"
    DISTRICT = "district"
    POSTAL_AREA = "postal_area"


class CorrectionStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class OtpChannel(str, Enum):
    SMS = "sms"
    EMAIL = "email"


def enum_column_type(enum_cls: type[Enum], name: str) -> sa.Enum:
    """Stored as text with a CHECK constraint (not a native Postgres enum), so adding a value is a
    simple migration. Values, not member names, are stored."""
    return sa.Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )
