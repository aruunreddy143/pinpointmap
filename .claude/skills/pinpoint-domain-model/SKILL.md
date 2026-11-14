---
name: pinpoint-domain-model
description: The PINPOINT data model, the single Place table with hierarchy, geometry, lifecycle status and history. Use when adding or changing tables, migrations, services or endpoints for places, buildings, units or land.
---

# Domain model

## One table, many types

Do **not** create separate House, Building, Unit and Land tables. There is one `place` table. Type-specific data goes in nullable columns or a typed JSONB `attributes` column validated by Pydantic.

| Column | Notes |
|---|---|
| `id` (UUID, PK) | Internal. Never exposed as the public identifier. |
| `public_id` (text, unique) | Canonical PINPOINT ID. See `pinpoint-id-format`. Immutable. |
| `type` (enum) | `house`, `building`, `unit` in Phase 1. `land` in Phase 2. Add values by migration only. |
| `parent_id` (FK to `place.id`, nullable) | Unit's parent is a building. Supports nesting such as community, tower, unit later. |
| `label` (text, nullable) | Door number or unit label as **free text** ("101", "2B", "Ground-rear"). Unique per parent among active places. |
| `geometry` | PostGIS `geometry(Geometry, 4326)`. A **Point** in Phase 1, a **Polygon** for land in Phase 2. Same column, so Phase 2 needs no schema change. |
| `location_accuracy_m`, `location_source` | How the pin was captured: `gps`, `map_click`, `survey`. |
| `entrance_point` | Optional second point for the access/entrance location. |
| `address_text`, `landmark`, `locality`, `district`, `state`, `postal_pin` | Human-readable bridge to normal addresses. Reverse-geocoded or staff-entered. |
| `status` (enum) | `active`, `retired`, `merged`, `split`. |
| `successor_ids` | For merged and split places. Retired IDs point to successors. |
| `visibility` (enum) | `private`, `shared`, `public`. Default `private`. See `pinpoint-privacy-india`. |
| `created_at`, `created_by`, `updated_at`, `updated_by` | Staff user IDs. |

## Rules

1. **Units inherit the building's location.** A unit stores no geometry of its own, or stores the same point. Moving the building moves its units. Do not let a unit diverge silently.
2. **Phase 1 validation:** `house` and `building` must have a Point and no parent. `unit` must have a `building` parent. Enforce in the service layer and with a DB check constraint where possible.
3. **Phase 2 readiness:** `land` is a Polygon with computed `area_sqm` (calculate in PostGIS with `geography`, not in Python). A building or house may sit inside a land parcel via `parent_id`. Do not build land features in Phase 1. Do keep nothing in the schema that blocks them.
4. **No hard deletes.** Retire, merge or split. IDs are never reused.
5. **Merge and split** are explicit service operations that run in one transaction: set statuses, write successor links, write history events, and re-parent children.
6. **History is append-only:** table `place_event(id, place_id, type, actor_id, at, before JSONB, after JSONB, reason)`. Every create, edit, pin move, visibility change, status change, merge, split and label print writes one. Written in the same transaction as the change.
7. **Duplicate guard:** on create, query active places within 15 m and with a similar label or type. If any exist, return them to the staff member, who must choose "this is a different place" (with a reason) or open the existing one. Never silently create a near-duplicate.
8. Spatial indexes: GiST on `geometry`; B-tree on `public_id`, `parent_id`, `status`. Keep the schema Postgres/PostGIS-portable and migrate only through Alembic.

## Layering

Routers in `app/api`, logic in `app/services` (no FastAPI imports), SQLAlchemy models in `app/models`, Pydantic schemas in `app/schemas`. Use the `python-api-endpoint` skill for new endpoints and `api-contract-sync` after response changes.
