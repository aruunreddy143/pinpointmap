# PINPOINT backend plan (Phase 1)

Goal: replace `frontend/src/mocks/` with a real FastAPI + PostGIS backend, with no screen changes. The mock layer already encodes the rules (visibility, four-eyes, 404 vs 403, OTP limits), so the mocks and their tests are the behavioural reference.

Stack (see `CLAUDE.md`): Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy 2 + GeoAlchemy2, Alembic, PostgreSQL + PostGIS, pytest (real PostGIS test DB), Ruff.
Extra libraries: `argon2-cffi` (passwords), `pyotp` (authenticator codes), `PyJWT` (tokens), `segno` (QR), `python-barcode` (Code 128), `pydantic-settings`, `httpx` (provider calls, tests).

Layout (thin routers, services never import FastAPI):

```
backend/
  pyproject.toml  docker-compose.yml  alembic.ini
  app/
    main.py  core/{settings,db,security,permissions,deps,errors}.py
    domain/{place_id,digipin,units,state_machine}.py     # pure, no DB / web imports
    models/    schemas/    services/    api/
    providers/{sms,email}.py                             # interfaces + console/dev backends
  migrations/   tests/
```

## Milestones (in order)

> Status: M0, M1 and M2 are done and tested. Next: M3 (auth and permissions).

### M0. Scaffold (small)
- `docker compose up db` (PostGIS), settings from env, app factory, `/health`, Alembic wired, Ruff config, pytest fixtures (real DB, per-test transaction rollback).
- GitHub Actions: ruff, pytest, frontend lint/test/build. **Ask before pushing or enabling CI.**
- Done when: `pytest` and `ruff` pass on an empty app; `alembic upgrade head` works on a fresh DB.

### M1. Pure domain code (can run in parallel with M0)
- `domain/digipin.py`: encode/decode a lat/lon to the 10-character cell. **Blocked on the official DIGIPIN specification and test vectors** (open question 1). Do not ship from memory.
- `domain/place_id.py`: generate (`secrets`, collision retry), normalize, validate, format. Same Luhn mod-16 as `frontend/src/lib/placeId.ts`.
- `domain/units.py` (range expansion), `domain/state_machine.py` (legal status transitions).
- **Shared test vectors file** `tests/vectors/place_ids.json` consumed by both pytest and the frontend's vitest, so the two implementations cannot drift.
- Done when: exhaustive single-typo and transposition tests pass; official DIGIPIN vectors pass; out-of-India points rejected.

### M2. Data model and migrations (DONE: migration `0002`, 29 schema tests)
Tables: `jurisdiction`, `app_user` (kind: staff | viewer; email and/or mobile hash), `role_assignment (user, role, jurisdiction)`, `place` (single table, `type`, `parent_id`, `geometry(Geometry,4326)` + GiST, `status`, `visibility`, `public_id` unique, address fields), `place_event` (append-only), `audit_event` (append-only; app DB role has INSERT/SELECT only), `consent_record`, `correction_request`, `otp_challenge`, `invite`, `refresh_token`.
- Postgres check constraints for Phase 1 shape (house/building need a point and no parent; unit needs a building parent).
- Done when: migrations apply and roll back; a test proves `UPDATE`/`DELETE` on `audit_event` is refused.

### M3. Auth and permissions
- `core/permissions.py`: the role to permission map (mirror of `frontend/src/lib/permissions.ts`; one test compares them).
- Staff: password (argon2) then authenticator code; lockout after 5 failures; unknown email and wrong password give the same answer; refresh-token rotation. Invites (single-use, expiring), password reset (same response whether or not the account exists).
- Viewer: OTP by SMS or email (`providers/` interface; console provider in dev), 5-minute expiry, 5 tries, 3 requests per identifier, per-IP limit; identifier stored hashed.
- `require_permission(...)` dependency + a test that scans every route and fails if one has no permission dependency (public routes are an explicit allow-list).
- Tokens: short-lived access token; refresh in an httpOnly, Secure, SameSite cookie (plus CSRF protection). Never put secrets in `VITE_` variables.
- Done when: the auth cases in `frontend/src/mocks/auth.test.ts` pass against the real API.

### M4. Places and verification (the core)
- Create draft, duplicate guard (`ST_DWithin` on `geography`, 15 m), submit (ID issued here, never earlier), bulk units, patch, `place_event` + `audit_event` in the same transaction.
- Verify, reject, merge, split, retire with four-eyes; pin move over 50 m needs a verifier; going public needs a consent record plus a verifier.
- Every query filters by the caller's jurisdiction; out-of-scope returns 404.
- Done when: the rules in `frontend/src/mocks/api.test.ts` pass against the real API, plus: audit write failure rolls the change back, concurrent submits never produce a duplicate ID.

### M5. Resolver, public view, labels
- `GET /p/{id}`: check character first (no DB hit on a bad ID), then the visibility matrix (anonymous / viewer / staff in jurisdiction / staff outside); tombstone redirect for retired, merged and split places.
- `GET /public/places?q=` and `/public/places/{id}` return only public, active places using a smaller response model. `POST /places/{id}/corrections` (5 per day per user).
- `GET /places/{id}/label?format=svg|png|pdf` (QR of the resolver URL, Code 128, audited).
- Rate limits on the resolver and search so IDs and places cannot be enumerated.

### M6. Admin and review
- Review queue (new / changes / merges, nearest-place distance), users and roles endpoints, audit-events listing.

### M7. Contract and frontend switch-over
- Generate `openapi.json`, then TypeScript types with `openapi-typescript` (`api-contract-sync` skill). Replace `mocks/api.ts` and `mocks/auth.ts` with a small API client; keep the mocks only for tests and demos.
- Playwright end-to-end: register building, add units, verify as a second user, print label, scan as a viewer.

### M8. Hardening and release
- `security-review` and `code-review` passes; `docs/data-inventory.md` (purpose of each personal field); backups and retention; India data residency; `devops-release` agent for Docker, CI and deploy config (proposals only; no hosted changes without approval).

## Testing strategy
- Real PostGIS database for integration tests; mock only external providers (SMS, email).
- Matrices as tests: role x endpoint permission, visibility (anonymous / viewer / staff in and out of jurisdiction), state-machine transitions.
- Regression tests for every bug fix (project rule).

## Open decisions (need an owner answer)
1. Official DIGIPIN specification and test vectors (blocks M1 sign-off).
2. SMS provider (India sender / DLT registration) and email provider (SMTP or API).
3. Jurisdiction reference data source (state, district, PIN areas) and who loads it.
4. Map and geocoding provider (reverse geocoding for locality; storage terms).
5. Hosting in India, secrets management, and where rate-limit counters live (Postgres first; Redis if needed).
6. First `super_admin` seeding method (CLI command assumed).
7. Whether the cell part of the ID stays 10 characters (about 4 m) or is coarsened (privacy trade-off).
