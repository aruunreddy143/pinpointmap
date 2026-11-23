# API contract notes (M4 to M6)

The Pydantic response models in `backend/app/schemas/` are the source of truth (`/openapi.json`). The API is **snake_case**; the frontend's `frontend/src/lib/types.ts` is camelCase. This file lists the mapping and the places where the real API differs from `frontend/src/mocks/api.ts`.

Errors are `{ "error": "<code>", "message": "<text to show>" }` with a real status: 401 not signed in, 403 not allowed, 404 missing **or outside your jurisdiction**, 409 conflict (including `duplicate_suspect`), 422 invalid input (FastAPI validation errors use its default `detail` list), 429 rate limited.

## Place (`PlaceOut`) to `Place`

| Frontend `Place` | API field | Note |
|---|---|---|
| `id` | `id` | internal UUID, used in staff URLs |
| `publicId` | `public_id` | null only before submit (never for places made through this API) |
| `type`, `parentId`, `label`, `name` | `type`, `parent_id`, `label`, `name` | |
| `geo` | `geo` | `{lat, lon}`, same shape |
| `accuracyM` | `accuracy_m` | may be null |
| `source` | `source` | `gps` / `map_click` / `survey` |
| `address` | `address` | |
| `landmark`, `locality`, `district`, `state` | same | district and state come from the jurisdiction tree |
| `postalPin` | `postal_pin` | |
| `status`, `visibility` | same | |
| `createdBy` | `created_by_name` | `created_by` is the user id |
| `createdAt`, `verifiedAt` | `created_at`, `verified_at` | ISO timestamps (the mock used dates) |
| (none) | `jurisdiction_id`, `unit_count` | extra; `unit_count` is set for houses and buildings, not retired units |

## History (`PlaceEventOut`) to `PlaceEvent`

`id`, `placeId` = `place_id`, `title`, `actor` = `actor_name` (viewers show as "Normal user"), `at` (ISO timestamp, format it in the UI), `tone`. Also `type` and `reason`. Newest first, like the mock.

## Review (`ReviewItemOut`) to `ReviewItem`

`id`, `placeId` = `place_id`, `kind`, `submittedBy` = `submitted_by`, `ageLabel` = format `submitted_at` ("2 days", "5 hours"), `nearestM` = `nearest_m` (**null** when there is no other active place), `duplicateSuspect` = `duplicate_suspect`, `checks` (`title`, `detail`, `ok`), and `place` (a full `PlaceOut`), exactly the `ReviewItem & { place }` that `listReview` returned. `kind=new` is submitted places, `kind=change` is verified buildings with new units waiting, `kind=merge` is always empty for now.

## Resolver (`GET /p/{code}`) to `Resolution`

Always a `ResolveOut` with a `kind`:

| API `kind` | HTTP | Frontend `Resolution` |
|---|---|---|
| `invalid` | 404 | `{kind:'invalid'}` |
| `not_found` | 404 | `{kind:'not_found'}` |
| `minimal` | 200 | `{kind:'minimal', publicId: public_id}` |
| `public` | 200 | `{kind:'public', place: place, units: units}` (`PublicPlaceOut`, see below) |
| `staff` | 200 | `{kind:'staff', place: staff_place, units: staff_units}` (`PlaceOut`) |
| `tombstone` | 200 | new: `status` (`retired`/`merged`/`split`) and `successor_ids` (public IDs of public successors). Show "this place was retired" and link to the successors. |

The 404 bodies still carry `kind`, so read the body whatever the status. Staff outside the place's jurisdiction are treated as anonymous. Send the bearer token if signed in; a missing or bad token is just anonymous.

## Public and viewer views (`PublicPlaceOut`)

Used by `/public/places`, `/public/places/{ref}` and the resolver's `public` kind. Smaller than `Place`: `id`, `public_id`, `type`, `parent_id`, `label`, `name`, `geo`, `address`, `landmark`, `locality`, `district`, `state`, `postal_pin`. No `created_by`, `status`, `visibility`, `accuracy_m`, dates. When filling a frontend `Place` from this, use `status:'active'`, `visibility:'public'`, empty strings and `null` for the rest.

`{ref}` is the internal id or the PINPOINT ID. Public detail lists only **active** units (the mock also showed pending ones).

## Endpoints

| Mock function | Real endpoint | Permission |
|---|---|---|
| `listPlaces({q,status})` | `GET /places?q=&status=` | `place:read` |
| `getPlace` | `GET /places/{id}` | `place:read` |
| `listUnits` | `GET /places/{id}/units` | `place:read` |
| `listHistory` | `GET /places/{id}/history` | `place:read` |
| `listReview(kind)` | `GET /review?kind=new\|change\|merge` | `place:verify` |
| `findNearby(geo, radius)` | `GET /places/nearby?lat=&lon=&radius_m=15` (adds `distance_m`) | `place:read` |
| `createAndSubmit` | `POST /places` | `place:create` |
| `decide(id, approve\|reject, reason)` | `POST /places/{id}/decision` `{decision, reason}` | `place:verify` |
| `setVisibility` | `PUT /places/{id}/visibility` `{visibility, consent_given_by?}` | signed-in staff; the service needs verify for public, update or verify for private |
| `publicSearch(q)` | `GET /public/places?q=` | public, 60 per minute per IP |
| `getPublicPlace(id)` | `GET /public/places/{ref}` | public |
| `submitCorrection` | `POST /places/{ref}/corrections` `{note}` | `correction:request` (viewers; 5 per day) |
| `resolve(input, role)` | `GET /p/{code}` | public, 60 per minute per IP |
| (new) edit | `PATCH /places/{id}` | `place:update` |
| (new) add units later | `POST /places/{id}/units` `{labels}` | `place:update` |
| (new) fix and resubmit | `POST /places/{id}/resubmit` | `place:update` |
| (new) label | `GET /places/{id}/label?format=svg\|png\|pdf&size=50x25\|a6` | `place:print` |
| `listStaff` | `GET /admin/staff` | `user:manage` |
| (new) | `GET /admin/jurisdictions` | `user:manage` |
| `inviteStaff` | `POST /admin/invites` (existing, M3) | `user:manage` |
| (new) | `GET /audit/events?action=&resource_type=&resource_id=&actor_id=&before_id=&limit=` | `audit:read` |

## Where the real API is stricter than the mock

- **Duplicate guard is enforced.** `POST /places` within 15 m of an active or pending place in your jurisdiction answers 409 `duplicate_suspect` unless the body has `different_place_reason` (5 to 500 characters). The register screen should show the `/places/nearby` list and send the reason when the registrar says it is a different place.
- **Four-eyes** is a 403 with the message to show. The person who submitted a place (or added its pending units) cannot approve or reject it. Rejecting needs a non-empty `reason` (422).
- **Going public** needs `place:verify` in the place's area, a verifier who did not register the place, an active place, and `consent_given_by` (422 without it). The mock let anyone toggle it. Registrars can only set a place back to private.
- **Pin move over 50 m** needs `place:verify` (403 otherwise). The ID never changes when a pin moves.
- **Jurisdiction:** out of scope is 404 on every place route, never 403. A state or district grant covers every area below it.
- **Units** are created with the building, with their own IDs, `pending_verification`, following the building's visibility. Units added to an already verified building wait for a verifier (`kind=change` in the review queue).
- **Units in the list:** `GET /places` returns houses and buildings only, like the mock. A unit's own page and label use its `id`.
- Not built yet: merge, split, retire, bulk import, `GET /places/{id}/corrections` (staff view of reports).

## Labels

`GET /places/{id}/label` returns the file itself (`image/svg+xml`, `image/png` or `application/pdf`), not JSON. The QR encodes `{PUBLIC_BASE_URL}/p/{public_id}` (error correction Q, 4-module quiet zone); the barcode is Code 128 of the canonical ID without hyphens. The PNG has the codes only (no text) and the PDF uses Helvetica, so non-Latin characters in a name print as `?`. Printing writes an audit event and a "Label printed" history entry. Only active places can be printed (409 otherwise).

## Admin reads

- `GET /admin/staff` returns one row per role assignment plus pending invites: `id`, `user_id` (null for invites), `email`, `name`, `role`, `jurisdiction_id`, `jurisdiction_name`, `status` (`active` or `invited`), `invite_token`, `invite_expires_at`. `invite_token` is set only for the person who created that invite and never in production. The frontend's `StaffRow.district` is `jurisdiction_name`; `inviteToken` is `invite_token`. The invite link is `{origin}/invite/{token}`.
- `GET /admin/jurisdictions` lists the areas you manage, including everything below your grants, for the invite form (`id`, `name`, `code`, `level`, `parent_id`).
- `POST /admin/invites` now accepts any jurisdiction below your grant (it used to need an exact match).
- Invite tokens are now derived from the invite id and the server key (still stored only as a hash), so a link can be shown again after a page reload in development.

## Audit events

Newest first, 50 per page (max 200). Pass `next_before_id` as `before_id` for the next page. You see events whose jurisdiction is inside your `audit:read` areas; events with no jurisdiction (sign-ins, for example) are for `super_admin` only. IP addresses are not returned. A normal user's name is shown as "Normal user".
