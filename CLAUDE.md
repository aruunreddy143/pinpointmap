# PINPOINT: Geographical Identity System (India)

A unique, permanent digital identity for every physical place (house, apartment building, apartment unit, later land), tied to a map pinpoint and carrying a scannable QR/barcode label.
Architecture reference: `requirements/PINPOINT Geographical Identity System Architecture.png`.

## Decisions already made (do not change without asking the owner)

- **Country:** India only. Coordinates must fall inside the India bounding box (see `pinpoint-geo-conventions`).
- **Operating model:** staff-operated. Only admins and users an admin has assigned a role to can create or edit places. There is **no public self-registration of places**. A **normal user** (role `viewer`) has a **read-only** view: they can search, scan and view only what visibility allows (`public` places, or places shared with them). They sign in and self-register with **either a mobile number (India, +91) or an email address**, confirmed by a one-time code. They cannot create, edit, verify or print. The only write a viewer has is "Report a problem" on a place, which creates a correction request for staff.
- **ID:** unique, permanent, **contains the geo location** (DIGIPIN cell) plus a unique suffix and a check character. See `pinpoint-id-format`.
- **Every place has a QR code and a Code 128 barcode** that resolve to the place. See `pinpoint-qr-label`.
- **Phases:** Phase 1 = House, Building, Apartment Unit. Phase 2 = Land (polygon). The schema must already allow Phase 2 with no migration of existing rows.

## Stack (from the architecture diagram; overrides global defaults where they differ)

- Frontend: React + TypeScript (strict), Vite, Tailwind, MapLibre GL, React Router, Vitest + RTL, Playwright.
- Backend: Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy 2 + GeoAlchemy2, Alembic, pytest, Ruff.
- Database: **PostgreSQL + PostGIS** (not SQLite; spatial queries need PostGIS). Use Docker for dev and tests. Tests use a real PostGIS database.
- Contract: Pydantic response models are the source of truth; generate TS types with openapi-typescript.
- Global UI quality bar in `~/.claude/CLAUDE.md` still applies (design tokens, light/dark, every state designed). Tailwind should consume the tokens.

## Project skills (read the relevant one before touching that area)

| Area | Skill |
|---|---|
| Place table, hierarchy, lifecycle, history | `pinpoint-domain-model` |
| ID generation, validation, check character | `pinpoint-id-format` |
| QR/barcode generation, scan resolver, labels | `pinpoint-qr-label` |
| Roles, jurisdictions, permissions, audit | `pinpoint-rbac-audit` |
| SRID, axis order, PostGIS, India bounds, map | `pinpoint-geo-conventions` |
| Visibility, DPDP Act, data handling | `pinpoint-privacy-india` |
| Register, verify, merge, split, retire, bulk import | `pinpoint-registration-workflow` |
| Frontend screens, tokens, theming, components | `pinpoint-ui-design` |

## Conventions

- Endpoints are thin: parse, call a service, return a response model. Services never import FastAPI.
- Never return ORM objects from endpoints. Request and response schemas are separate from ORM models.
- **No hard deletes of places.** Retire, merge or split with a status change and a history event.
- **Every mutation writes an audit event** in the same transaction.
- Every bug fix gets a regression test that fails without the fix.
- Ask before pushing, opening PRs, deploying, or changing anything hosted. Never `--no-verify` or force-push.

## Commands (fill in as the project is scaffolded)

- Backend (M0 scaffold + M1 domain code done): `cd backend`, `py -3.11 -m venv .venv`, `.venv\Scripts\python -m pip install -e ".[dev]"`, then `.venv\Scripts\python -m pytest`, `.venv\Scripts\python -m ruff check . && .venv\Scripts\python -m ruff format --check .`. Plan: `docs/backend-plan.md`.
- Schema rules live in the database (migration `0002`): place shape (house/building = point with no parent, unit = point with a building parent, land = polygon), points inside India, ID format and uniqueness, unique unit labels per building, and triggers that make `audit_event` and `place_event` append-only and forbid deleting places. Tests in `backend/tests/test_schema.py` and `test_migrations.py` run against the real migrated PostGIS database. After changing a model, add a migration; `test_models_and_migrations_agree` fails otherwise.
- The postgis Docker image installs a US "tiger" geocoder with its own `place` table; `backend/docker/init-test-db.sql` removes it on first start.
- Auth (M3): every route must use `require_permission(...)` / `require_authenticated` or be on the public allow-list in `backend/tests/test_route_permissions.py` (a test fails otherwise). Role permissions are defined once in `backend/app/core/permissions.py`; a test checks they match `frontend/src/lib/permissions.ts`. Notifications go through `app/providers/notify.py` (console in dev, outbox in tests; production fails loudly until a real SMS/email provider is configured).
- ID vectors shared by backend and frontend tests: `shared/test-vectors/place_ids.json`. DIGIPIN grid is NOT yet verified against India Post's official document (see `backend/app/domain/digipin.py`).
- Frontend (built, mock data): `cd frontend && npm run dev` (http://localhost:5173), `npm test`, `npm run lint`, `npx tsc --noEmit`, `npm run build`
- Frontend mock layer: `frontend/src/mocks/` (data + in-memory API with the real visibility, four-eyes and 404 rules). Demo sign-in at `/` picks a role. Replace `mocks/api.ts` with the generated API client when the backend exists; screens should not need to change.
- Map tiles: `VITE_MAP_STYLE_URL` (falls back to OSM raster tiles, development only). QR base URL: `VITE_PUBLIC_BASE_URL`.
- Database (PostGIS 16 in Docker; start Docker Desktop first): `cd backend && docker compose up -d db`, `.venv\Scripts\python -m alembic upgrade head`. Dev DB `pinpoint`, test DB `pinpoint_test` (created by `backend/docker/init-test-db.sql` on first start).
- Contract: regenerate TS types after any response-model change (`api-contract-sync` skill).
