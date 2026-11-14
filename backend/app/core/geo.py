"""Spatial conventions (see .claude/skills/pinpoint-geo-conventions).

Axis order is the classic bug: people say (lat, lon); PostGIS, GeoJSON and MapLibre use (lon, lat).
Everywhere in this codebase a position is a `LatLon` with NAMED fields, and the swap to (lon, lat)
happens in exactly one place: `point()`.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.sql.elements import ColumnElement

from app.domain.digipin import MAX_LAT, MAX_LON, MIN_LAT, MIN_LON, in_bounds

SRID = 4326
DUPLICATE_RADIUS_M = 15  # registration duplicate guard
PIN_MOVE_NEEDS_VERIFIER_M = 50
GOOD_ACCURACY_M = 20


class LatLon(BaseModel, frozen=True):
    lat: float
    lon: float

    @field_validator("lon")
    @classmethod
    def _inside_india(cls, lon: float, info) -> float:  # noqa: ANN001
        lat = info.data.get("lat")
        if lat is not None and not in_bounds(lat, lon):
            raise ValueError("The point is outside India")
        return lon

    def rounded(self) -> LatLon:
        """Stored coordinates are rounded to 7 decimals (about 1 cm)."""
        return LatLon(lat=round(self.lat, 7), lon=round(self.lon, 7))


def point(ll: LatLon) -> ColumnElement:
    """SQL point for a LatLon. THE place where (lat, lon) becomes (lon, lat)."""
    r = ll.rounded()
    return func.ST_SetSRID(func.ST_MakePoint(r.lon, r.lat), SRID)


def india_envelope() -> ColumnElement:
    return func.ST_MakeEnvelope(MIN_LON, MIN_LAT, MAX_LON, MAX_LAT, SRID)
