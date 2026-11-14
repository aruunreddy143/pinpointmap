---
name: pinpoint-rbac-audit
description: Roles, jurisdiction-scoped permissions and audit rules for the staff-operated PINPOINT system. Use when adding any endpoint, UI action or background job that creates, edits, verifies, prints or reads place data, or when touching authentication.
---

# Roles, permissions, audit

PINPOINT is **staff-operated**. There is no public sign-up. Admins create users and assign roles; roles are scoped to a **jurisdiction**.

## Roles

| Role | Can do |
|---|---|
| `super_admin` | Everything, including managing admins and system config. Few people. |
| `admin` | Manage users and role assignments, plus all registrar/verifier/auditor powers, within their jurisdiction. |
| `registrar` | Create and edit places (houses, buildings, units), add units, move pins, request merges. Within jurisdiction. |
| `verifier` | Verify places and approve merges, splits and retirements, and visibility changes to `public`. Cannot create places. |
| `printer` | Generate and print labels. |
| `auditor` | Read-only access to places, history and audit log. |
| `api_client` | Machine access for partner systems, read-only, granted scopes only, rate-limited. |
| `viewer` | **Normal user, read-only.** Signs in or self-registers with **a mobile number (+91) OR an email address**, confirmed by a one-time code (no password, no TOTP). The same person using either identifier is one account only if both are verified and linked; otherwise they are separate accounts. Can search, scan and open places that are `public` or shared with them, open a place in a map app, and submit "Report a problem" (`correction:request`). Has no jurisdiction. Cannot see private places, history, audit or staff screens. The UI shows no edit controls, and the API rejects every write except `correction:request`. |

A user may hold several roles. Permissions are named `resource:action` (`place:create`, `place:update`, `place:verify`, `place:retire`, `place:print`, `place:read_private`, `user:manage`). Roles map to permission sets in **one place**, `app/core/permissions.py`. Do not scatter `if role == ...` checks.

## Jurisdiction

- A role assignment is `(user, role, jurisdiction)`, where jurisdiction is a state, district or postal PIN area, stored as an id from a reference table.
- Every place has `state`, `district` and `postal_pin`, filled at creation. A permission check passes only if the place lies in a jurisdiction where the user holds a role granting the action.
- Jurisdiction is enforced **in the query** (filter), not after fetching, so out-of-scope rows are never loaded.

## Enforcement rules

1. Authorization is a FastAPI dependency (`require_permission("place:update")`) that resolves the user and jurisdiction. Services receive an `Actor` object and re-check jurisdiction, so a service called from a job is protected too.
2. Default deny. A new endpoint with no permission dependency fails a test that scans all routes.
3. Authentication: staff log in with email + password and a second factor (TOTP). Short-lived access tokens, rotating refresh tokens. Lock out after repeated failures. Never log tokens or passwords.
4. **Four-eyes** for risky actions: merge, split, retire and making a place `public` need a `verifier` different from the requester.
5. 6. `viewer` accounts are self-service sign-up (OTP by SMS or email). OTP codes expire in 5 minutes, allow 5 wrong tries, and requests are rate-limited per identifier and per IP. "Request code" and "forgot password" answer identically whether or not the account exists (no account enumeration). Staff accounts are created only by invite from an admin (set password + authenticator app on first use) but carry only `place:read_public` and `correction:request`. Rate-limit lookups per account and per IP to prevent enumeration. Viewer responses use a separate, smaller response model that never includes private fields.
7. Role changes themselves are audited and need `admin` or higher; nobody can grant a role above their own.

## Audit

- Table `audit_event(id, at, actor_id, action, resource_type, resource_id, jurisdiction, ip, request_id, detail JSONB)`. Append-only: the app DB user has INSERT and SELECT only. Place-level changes also go to `place_event` (see `pinpoint-domain-model`).
- Written in the **same transaction** as the change. If the audit write fails, the change fails.
- Log reads of private places by staff (`place:read_private`) as audit events. Log denied attempts too.
- Never put secrets or full personal data in `detail`. Store ids and changed field names, with values only where `place_event` needs them.

## Tests required

A permission matrix test (every role x every endpoint), a jurisdiction-boundary test (user in district A cannot touch district B), the four-eyes rule, the route-scan test for missing permission dependencies, and audit rows written on success and on denial.
