---
name: pinpoint-qr-label
description: QR code and barcode spec for PINPOINT places, the scan resolver endpoint, and printable labels. Use when generating codes, building the scan/resolve flow, label printing, or the mobile scan UI.
---

# QR / barcode labels

Every place has exactly one canonical scan payload, a QR code, and a linear barcode of the same ID.

## Payload

- **QR content is a URL, never raw data:** `https://<PUBLIC_BASE_URL>/p/<CANONICAL_ID>`. `PUBLIC_BASE_URL` comes from config; never hard-code a domain.
- No coordinates, names or other personal data in the code. The ID is the only thing encoded.
- **Barcode:** Code 128 of the canonical ID (no hyphens), for handheld linear scanners.
- QR: error correction level **Q**, quiet zone of at least 4 modules, black on white. No logo overlays. Minimum printed size 2.5 cm.

## Generation

- Python: `segno` for QR (SVG and PNG), `python-barcode` for Code 128 (SVG). Generate on demand and cache by ID. IDs are immutable, so caching is safe.
- Endpoint: `GET /places/{id}/label?format=svg|png|pdf`, restricted to roles with `place:print`. Return the code and a printable label (QR, barcode, display-form ID, short place name, locality) at A6 and 50x25 mm sizes.
- Printing a label is an audit event.

## Resolver: `GET /p/{id}` (the scan target)

1. Normalize and validate the ID with `pinpoint-id-format`. An invalid check character returns 404 with a "check the code" message, with no database lookup.
2. **Resolution depends on who scans:**
   - Anonymous: only what the place's visibility allows (see `pinpoint-privacy-india`). A private place returns a minimal "this is a registered PINPOINT place" page and nothing else.
   - Authenticated staff: full details within their jurisdiction (see `pinpoint-rbac-audit`).
3. Retired, merged or split places answer with a tombstone and a redirect to the successor.
4. Rate-limit this endpoint per IP. It must not allow enumeration.
5. Anonymous scans are logged in aggregate only, with no IP stored beyond rate-limiting.

## Frontend

- Staff app has an in-browser scanner (camera, `BarcodeDetector` with a JS fallback). It also has a manual-entry field that validates the check character live.
- Scanning inside the staff app opens the place directly; scanning with a phone camera hits the public resolver.
- Provide a "Print label" action on the place page, and a bulk print sheet for all units in a building.

## Tests

QR payload round-trip, barcode decodes to the canonical ID, resolver visibility matrix (anonymous / staff in jurisdiction / staff outside it), tombstone redirect, bad-check-digit rejection, and rate limiting.
