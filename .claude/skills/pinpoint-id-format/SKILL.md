---
name: pinpoint-id-format
description: The PINPOINT place ID format (geo cell + unique suffix + check character), how to generate, parse and validate it. Use whenever code creates, parses, displays, stores or validates a place ID, or touches ID-related tests.
---

# PINPOINT ID format

## Shape

```
PP1-<GEO>-<SEQ>-<C>
PP1-FC98-J327-K456-LMPT   (illustrative layout only)
```

| Part | Meaning |
|---|---|
| `PP1` | Format version. A future format becomes `PP2`; `PP1` IDs stay valid forever. |
| `GEO` | The 10-character **DIGIPIN** of the pin at registration time (about 4 m cell). |
| `SEQ` | 4 characters, random, unique within that GEO cell. |
| `C` | 1 check character over `GEO+SEQ`. |

Display grouping is cosmetic. Store and compare the **canonical form without hyphens**; accept hyphens, spaces and lower case on input and normalize.

## Alphabet

DIGIPIN's 16-symbol alphabet: `F C 9 8 J 3 2 7 K 4 5 6 L M P T`. It has no vowels and no 0/1/O/I, so it is unambiguous when read aloud or misprinted. Use the same alphabet for `SEQ` and the check character.

## Rules

1. **The ID is immutable.** If a pin is later corrected, the ID does **not** change. The `GEO` segment records the *registration cell* only. The authoritative location is the `geometry` column on `place`. Never derive location from the ID after registration. Never "fix" an ID to match a moved pin.
2. **Uniqueness:** unique constraint on the canonical ID. Generate `SEQ` with `secrets` (never `random`), retry on collision, and fail loudly after N retries instead of looping forever.
3. **Units share the building's GEO.** Apartment units get their own ID with the building's `GEO` and their own `SEQ`. Hierarchy lives in `parent_id`, not in the ID.
4. **Check character:** Luhn mod-N (N = 16) over the 14 payload characters. `validate_id()` must reject any single-character typo and adjacent transposition. Test this exhaustively.
5. **GEO must be a valid DIGIPIN** inside the India bounds. Implement against the official DIGIPIN specification and its test vectors. Do not invent the grid. Pin the reference vectors in `tests/test_digipin.py` so a drift fails CI.
6. **Never reuse an ID**, even after retire/merge/split. Retired IDs resolve to a tombstone or a redirect to the successor.
7. IDs contain **no personal data**.
8. The ID reveals the location to about 4 m. Treat the ID of a non-public place as location-sensitive. See `pinpoint-privacy-india`.

## Where the code lives

One module, `backend/app/domain/place_id.py`, with pure functions: `encode_geo(lat, lon)`, `decode_geo(geo)`, `generate(lat, lon, taken: Callable)`, `normalize(text)`, `validate(text)`, `format_display(canonical)`. No DB or web imports. The frontend validates with a small mirror of the same check, covered by shared test vectors. Do not hand-roll ID logic anywhere else.

## Tests required

Round-trip encode/decode within cell size, official DIGIPIN vectors, rejection of out-of-India coordinates, single-char typo detection, transposition detection, normalization of messy input, collision-retry behavior, and the immutability rule (moving a pin leaves the ID unchanged).
