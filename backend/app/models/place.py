from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.geo import SRID
from app.models.enums import (
    CorrectionStatus,
    LocationSource,
    PlaceStatus,
    PlaceType,
    Visibility,
    enum_column_type,
)
from app.models.user import NOW

# Phase 1 shape rules live in the database so no code path can break them.
_INDIA = "ST_MakeEnvelope(63.5, 2.5, 99.5, 38.5, 4326)"
_ACTIVE_STATUSES = "('draft','pending_verification','active')"


class Place(Base):
    """One table for house, building, unit (and land in Phase 2). See pinpoint-domain-model skill."""

    __tablename__ = "place"
    __table_args__ = (
        sa.CheckConstraint(
            "type NOT IN ('house','building') OR (parent_id IS NULL AND GeometryType(geometry) = 'POINT')",
            name="top_level_is_a_point",
        ),
        sa.CheckConstraint(
            "type <> 'unit' OR (parent_id IS NOT NULL AND GeometryType(geometry) = 'POINT')",
            name="unit_has_building_parent",
        ),
        sa.CheckConstraint("type <> 'land' OR GeometryType(geometry) = 'POLYGON'", name="land_is_a_polygon"),
        sa.CheckConstraint(f"ST_CoveredBy(geometry, {_INDIA})", name="inside_india"),
        sa.CheckConstraint("status = 'draft' OR public_id IS NOT NULL", name="id_issued_after_draft"),
        sa.CheckConstraint(
            "public_id IS NULL OR public_id ~ '^PP1[FC98J327K456LMPT]{15}$'", name="public_id_format"
        ),
        sa.CheckConstraint("accuracy_m IS NULL OR accuracy_m >= 0", name="accuracy_not_negative"),
        sa.CheckConstraint("NOT restricted OR visibility = 'private'", name="restricted_is_private"),
        sa.Index("ix_place_geometry", "geometry", postgresql_using="gist"),
        sa.Index(
            "uq_place_unit_label",
            "parent_id",
            sa.text("lower(label)"),
            unique=True,
            postgresql_where=sa.text(
                f"parent_id IS NOT NULL AND label IS NOT NULL AND status IN {_ACTIVE_STATUSES}"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    public_id: Mapped[str | None] = mapped_column(sa.String(18), unique=True)  # null until submit
    type: Mapped[PlaceType] = mapped_column(enum_column_type(PlaceType, "place_type"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("place.id"), index=True)
    label: Mapped[str | None] = mapped_column(sa.String(60))  # free text: "101", "2B", "Ground-rear"
    name: Mapped[str] = mapped_column(sa.String(160))
    geometry: Mapped[Any] = mapped_column(Geometry("GEOMETRY", srid=SRID, spatial_index=False))
    accuracy_m: Mapped[float | None] = mapped_column(sa.Numeric(7, 2))
    location_source: Mapped[LocationSource] = mapped_column(
        enum_column_type(LocationSource, "location_source")
    )
    entrance_point: Mapped[Any | None] = mapped_column(Geometry("POINT", srid=SRID, spatial_index=False))
    address_text: Mapped[str] = mapped_column(sa.String(240), default="")
    landmark: Mapped[str] = mapped_column(sa.String(160), default="")
    locality: Mapped[str] = mapped_column(sa.String(120), default="")
    district: Mapped[str] = mapped_column(sa.String(120), default="")
    state: Mapped[str] = mapped_column(sa.String(120), default="")
    postal_pin: Mapped[str] = mapped_column(sa.String(6), default="")
    jurisdiction_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("jurisdiction.id"), index=True)
    status: Mapped[PlaceStatus] = mapped_column(
        enum_column_type(PlaceStatus, "place_status"), index=True, default=PlaceStatus.DRAFT
    )
    visibility: Mapped[Visibility] = mapped_column(
        enum_column_type(Visibility, "visibility"), default=Visibility.PRIVATE, server_default="private"
    )
    restricted: Mapped[bool] = mapped_column(default=False, server_default=sa.false())
    successor_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    created_by: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("app_user.id"))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=NOW)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("app_user.id"))
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=NOW)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("app_user.id"))
    verified_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class PlaceEvent(Base):
    """Append-only history of a place (the database refuses UPDATE, DELETE and TRUNCATE)."""

    __tablename__ = "place_event"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    place_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("place.id"), index=True)
    type: Mapped[str] = mapped_column(sa.String(40))
    actor_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("app_user.id"))
    at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=NOW)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(sa.String(500))


class ConsentRecord(Base):
    """Recorded consent from an owner before a place (or some of its fields) becomes public."""

    __tablename__ = "consent_record"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    place_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("place.id"), index=True)
    given_by_name: Mapped[str] = mapped_column(sa.String(120))
    fields: Mapped[list[str]] = mapped_column(ARRAY(sa.String(40)))
    recorded_by: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("app_user.id"))
    recorded_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=NOW)
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


class CorrectionRequest(Base):
    """A "Report a problem" note from a normal user. The only write a viewer can make."""

    __tablename__ = "correction_request"
    __table_args__ = (sa.CheckConstraint("char_length(note) BETWEEN 5 AND 500", name="note_length"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    place_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("place.id"), index=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("app_user.id"))
    note: Mapped[str] = mapped_column(sa.String(500))
    status: Mapped[CorrectionStatus] = mapped_column(
        enum_column_type(CorrectionStatus, "correction_status"),
        default=CorrectionStatus.OPEN,
        server_default="open",
    )
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=NOW)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("app_user.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
