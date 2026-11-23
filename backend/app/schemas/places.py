"""Request and response models for places, history, review and the public/resolver views.

Names are snake_case; docs/api-contract.md maps them to the frontend's camelCase Place, PlaceEvent and
ReviewItem. Positions are always a named {lat, lon} (see core/geo.py)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.geo import LatLon
from app.models.enums import LocationSource, PlaceStatus, PlaceType, Visibility

# ---------- staff views ----------


class PlaceOut(BaseModel):
    id: uuid.UUID
    public_id: str | None
    type: PlaceType
    parent_id: uuid.UUID | None
    label: str | None
    name: str
    geo: LatLon
    accuracy_m: float | None
    source: LocationSource
    address: str
    landmark: str
    locality: str
    district: str
    state: str
    postal_pin: str
    status: PlaceStatus
    visibility: Visibility
    jurisdiction_id: uuid.UUID
    created_by: uuid.UUID
    created_by_name: str
    created_at: datetime
    verified_at: datetime | None
    unit_count: int | None = None  # buildings only (units that are not retired)


class PlaceNearbyOut(PlaceOut):
    distance_m: int


class PlaceEventOut(BaseModel):
    id: uuid.UUID
    place_id: uuid.UUID
    type: str
    title: str
    actor_name: str
    at: datetime
    tone: Literal["ok", "accent", "warn", "muted"]
    reason: str | None = None


class NewPlace(BaseModel):
    type: Literal["house", "building"]
    name: str = Field(min_length=1, max_length=160)
    geo: LatLon
    accuracy_m: float = Field(ge=0, le=1000)
    source: LocationSource = LocationSource.GPS
    address: str = Field(default="", max_length=240)
    landmark: str = Field(default="", max_length=160)
    locality: str = Field(default="", max_length=120)
    postal_pin: str = Field(default="", pattern=r"^(\d{6})?$")
    unit_labels: list[str] = Field(default_factory=list, max_length=500)
    # Where the place lies. Optional when the caller can create places in exactly one area.
    jurisdiction_id: uuid.UUID | None = None
    # The duplicate guard refuses a place within 15 m of another unless the registrar says why it differs.
    different_place_reason: str | None = Field(default=None, min_length=5, max_length=500)


class PlacePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    address: str | None = Field(default=None, max_length=240)
    landmark: str | None = Field(default=None, max_length=160)
    locality: str | None = Field(default=None, max_length=120)
    postal_pin: str | None = Field(default=None, pattern=r"^(\d{6})?$")
    geo: LatLon | None = None
    accuracy_m: float | None = Field(default=None, ge=0, le=1000)
    reason: str | None = Field(default=None, max_length=500)


class AddUnits(BaseModel):
    labels: list[str] = Field(min_length=1, max_length=500)


class VisibilityChange(BaseModel):
    visibility: Visibility
    # Going public needs the owner's consent on record: who gave it, and for which fields.
    consent_given_by: str | None = Field(default=None, min_length=2, max_length=120)
    consent_fields: list[Literal["name", "address", "location", "units"]] = Field(
        default_factory=lambda: ["name", "address", "location"]
    )


class Decision(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(default="", max_length=500)


class ReviewCheck(BaseModel):
    title: str
    detail: str
    ok: bool


class ReviewItemOut(BaseModel):
    id: str
    place_id: uuid.UUID
    kind: Literal["new", "change", "merge"]
    submitted_by: str
    submitted_at: datetime
    nearest_m: int | None
    duplicate_suspect: bool
    checks: list[ReviewCheck]
    place: PlaceOut


# ---------- public, viewer and resolver views (smaller; never any private field) ----------


class PublicPlaceOut(BaseModel):
    id: uuid.UUID
    public_id: str
    type: PlaceType
    parent_id: uuid.UUID | None
    label: str | None
    name: str
    geo: LatLon
    address: str
    landmark: str
    locality: str
    district: str
    state: str
    postal_pin: str


class PublicPlaceDetail(BaseModel):
    place: PublicPlaceOut
    units: list[PublicPlaceOut]


class ResolveOut(BaseModel):
    """What a scan of /p/{id} shows. `kind`: invalid | not_found | minimal | public | tombstone | staff.
    `invalid` and `not_found` are sent with HTTP 404; the rest with 200."""

    kind: Literal["invalid", "not_found", "minimal", "public", "tombstone", "staff"]
    message: str | None = None
    public_id: str | None = None  # minimal and tombstone: the canonical ID that was scanned
    place: PublicPlaceOut | None = None  # kind=public
    staff_place: PlaceOut | None = None  # kind=staff
    units: list[PublicPlaceOut] = Field(default_factory=list)
    staff_units: list[PlaceOut] = Field(default_factory=list)
    status: PlaceStatus | None = None  # tombstone: retired | merged | split
    successor_ids: list[str] = Field(default_factory=list)  # tombstone: public IDs of public successors


class CorrectionIn(BaseModel):
    note: str = Field(min_length=5, max_length=500)


class CorrectionOut(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime
