---
name: pinpoint-privacy-india
description: Visibility model and data-protection rules for PINPOINT under India's DPDP Act 2023. Use when deciding what data an endpoint, QR scan, API client, log or export may expose, or when handling personal data.
---

# Privacy and visibility (India, DPDP Act 2023)

A place registry ties **locations to people**. Treat it as sensitive. This skill is a engineering guide, not legal advice; the owner should confirm compliance with counsel.

## Visibility levels (`place.visibility`)

| Level | Anonymous scan / lookup may see | Default |
|---|---|---|
| `private` | Only "registered PINPOINT place". No location, name, address or ID details. | **Yes, for every new place.** |
| `shared` | Basic details for holders of a valid, scoped, expiring access grant. | |
| `public` | ID, label, locality, coordinates. Requires owner consent recorded and verifier approval. | |

- **Normal users (`viewer`, signed in by mobile OTP) see the same as an anonymous scan plus search:** `public` places in full (ID, label, locality, coordinates, units), `shared` places only with a valid grant, and nothing for `private` or `restricted` places. Search by ID or text returns only `public` places. A viewer's mobile number or email is personal data: store it hashed where possible, state its purpose in `docs/data-inventory.md`, and never show it to other users.
- Staff see more than anonymous users, but only inside their jurisdiction and through the audited `place:read_private` path.
- A **public** flag needs a recorded consent (who consented, when, for which fields). No consent record, no public.
- Sensitive places (shelters, safe houses, officials' residences) get a `restricted` flag. They are never public, never in `api_client` results, and need `admin` to view.

## Rules

1. **The ID leaks location** to about 4 m (see `pinpoint-id-format`). Therefore never list or echo IDs of non-public places in any public response, log line, error message, analytics event or URL outside the resolver.
2. **No enumeration:** no public "nearby places" query, no bulk export, no sequential lookups; rate-limit and monitor the resolver.
3. **Minimize personal data.** Store only what the operating model needs (staff accounts; owner/occupant contact only if a feature requires it, with a stated purpose). No Aadhaar numbers. Do not collect or store them even if offered. Do not add personal fields without asking the owner.
4. **Consent and purpose:** every personal-data field has a documented purpose in `docs/data-inventory.md`. Update it in the same change that adds the field.
5. **Access grants** (`shared`) are scoped to fields, expire, are revocable, and every use is logged.
6. **Correction and erasure:** a person can request correction or removal. Place history is kept for audit, so on erasure, **pseudonymize personal fields** inside `place_event` and `audit_event` instead of deleting rows. Document the retention period.
7. **Security basics:** TLS everywhere, encryption at rest for the database and backups, secrets only in env/secret manager (never in `VITE_` variables), no personal data in URLs or query strings, no personal data in logs.
8. **Breach readiness:** keep the audit log intact and exportable so an incident can be scoped quickly.
9. **Data residency:** host the database and backups in India unless the owner says otherwise.

## Tests required

A visibility matrix test (anonymous / grant holder / staff in jurisdiction / staff outside / `api_client`) across the resolver and every read endpoint; a test that private IDs never appear in public responses or logs; a consent-required test for `public`; and a pseudonymization test for erasure.
