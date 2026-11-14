---
name: pinpoint-geo-conventions
description: Spatial conventions for PINPOINT, covering SRID, axis order, India bounds, PostGIS queries, accuracy handling and the MapLibre map. Use for any code that stores, queries, validates or displays coordinates.
---

# Geo conventions

## Coordinates

- Store everything in **SRID 4326** (WGS 84).
- **Axis order is the #1 bug source.** APIs, GeoJSON, PostGIS `ST_MakePoint` and MapLibre use **(longitude, latitude)**. Humans, Google Maps links and DIGIPIN docs say "lat, lon". Rule: in code, always use named fields `{lat, lon}` in Pydantic schemas and function signatures, and convert to (lon, lat) only at the PostGIS and GeoJSON boundary, in one helper (`app/core/geo.py`). Never pass bare tuples around.
- Round stored coordinates to 7 decimal places (about 1 cm). Never display more than 6.

## India bounds

- Reject any point outside the DIGIPIN India bounding box (lat 2.5 to 38.5, lon 63.5 to 99.5) with a 422 and a clear message.
- The box is a coarse filter. Optionally add a PostGIS check against an India boundary polygon later; don't rely on the box alone to prove a point is in India.

## PostGIS

- Columns use `geometry(Geometry, 4326)` with a **GiST index**. Use GeoAlchemy2.
- Distance and area must use **geography** (`::geography`) or `ST_DistanceSphere`, never degrees. `area_sqm` is computed in PostGIS.
- Nearby search: `ST_DWithin(geometry::geography, point::geography, meters)`. Always cap the radius and the result count.
- Never compute distances in Python with flat-earth math.
- Duplicate guard radius is 15 m (see `pinpoint-domain-model`). Keep it as a named constant.

## Capturing a pin

- Record `location_accuracy_m` and `location_source`. If device GPS accuracy is worse than 20 m, warn the staff member and ask them to confirm on the satellite layer.
- Staff drag the pin on a satellite basemap. Show the accuracy circle. Show the entrance point as a separate marker.
- Show the computed DIGIPIN and the reverse-geocoded locality live as the pin moves, so the registrar can see what will be recorded.

## Map frontend

- MapLibre GL only (no Google Maps JS). The tile and imagery provider is configured through env vars (`VITE_MAP_STYLE_URL`), never hard-coded. Tile keys are public, so use domain-restricted keys.
- Check provider terms before storing geocoding results (Google forbids it). Prefer OSM-based providers for geocoding and store results only from sources that allow it.
- Keep map components in `frontend/src/features/map/`. They take `{lat, lon}` props, not GeoJSON arrays.
- Every map has a keyboard-accessible alternative (a coordinates form), a loading skeleton and an error state.

## Tests

Axis-order regression test (a known Indian landmark round-trips through API, DB and DIGIPIN unchanged), out-of-bounds rejection, `ST_DWithin` meters check, and an area computation against a known polygon.
