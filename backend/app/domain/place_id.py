"""PINPOINT place ID: PP1 + 10-char geo cell + 4-char suffix + 1 check character.

See .claude/skills/pinpoint-id-format. Pure functions only (no database, no web framework).
The same check-character algorithm lives in frontend/src/lib/placeId.ts; both are tested
against shared/test-vectors/place_ids.json so they cannot drift.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from app.domain import digipin
from app.domain.digipin import ALPHABET

PREFIX = "PP1"
GEO_LEN = digipin.LEVELS  # 10
SEQ_LEN = 4
CANONICAL_LEN = len(PREFIX) + GEO_LEN + SEQ_LEN + 1  # 18
_N = len(ALPHABET)  # 16
MAX_ATTEMPTS = 20


class IdProblem(str, Enum):
    INCOMPLETE = "incomplete"
    PREFIX = "prefix"
    CHARACTERS = "characters"
    CHECKSUM = "checksum"


@dataclass(frozen=True)
class IdCheck:
    ok: bool
    canonical: str | None = None
    problem: IdProblem | None = None


class IdGenerationError(RuntimeError):
    """Could not find a free suffix in this cell after several tries."""


def check_char(payload: str) -> str:
    """Luhn mod-16 over the payload (geo + seq). Detects any single-character error
    and any swap of two adjacent different characters."""
    factor = 2
    total = 0
    for ch in reversed(payload):
        code = ALPHABET.index(ch)  # ValueError for a character outside the alphabet
        addend = factor * code
        factor = 1 if factor == 2 else 2
        total += addend // _N + addend % _N
    return ALPHABET[(_N - total % _N) % _N]


def make_id(geo: str, seq: str) -> str:
    if len(geo) != GEO_LEN or len(seq) != SEQ_LEN:
        raise ValueError("geo must be 10 characters and seq 4 characters")
    payload = geo + seq
    return PREFIX + payload + check_char(payload)


def normalize(text: str) -> str:
    """Upper-case and drop separators: 'pp1-fc98 ...' -> 'PP1FC98...'."""
    return "".join(ch for ch in text.upper() if ch.isalnum())


def validate(text: str) -> IdCheck:
    c = normalize(text)
    if len(c) < CANONICAL_LEN:
        return IdCheck(False, problem=IdProblem.INCOMPLETE)
    if len(c) > CANONICAL_LEN or not c.startswith(PREFIX):
        return IdCheck(False, problem=IdProblem.PREFIX)
    body = c[len(PREFIX) :]
    if any(ch not in ALPHABET for ch in body):
        return IdCheck(False, problem=IdProblem.CHARACTERS)
    if check_char(body[:-1]) != body[-1]:
        return IdCheck(False, problem=IdProblem.CHECKSUM)
    return IdCheck(True, canonical=c)


def format_display(canonical: str) -> str:
    """PP1-FC98J327K4-56LM-T"""
    c = normalize(canonical)
    return f"{c[:3]}-{c[3:13]}-{c[13:17]}-{c[17:]}"


def geo_cell(canonical: str) -> str:
    """The registration cell recorded in the ID. NOT the place's current location."""
    c = normalize(canonical)
    return c[len(PREFIX) : len(PREFIX) + GEO_LEN]


def generate(
    lat: float,
    lon: float,
    exists: Callable[[str], bool],
    *,
    rng: Callable[[int], int] = secrets.randbelow,
) -> str:
    """Issue an ID for a point. `exists(canonical)` reports whether an ID is taken; the database
    unique constraint is still the final guard (callers must retry on a conflict).
    Uses `secrets`, never `random`. Raises OutsideIndiaError outside the DIGIPIN area."""
    geo = digipin.encode(lat, lon)
    for _ in range(MAX_ATTEMPTS):
        seq = "".join(ALPHABET[rng(_N)] for _ in range(SEQ_LEN))
        candidate = make_id(geo, seq)
        if not exists(candidate):
            return candidate
    raise IdGenerationError(f"No free suffix found in cell {geo} after {MAX_ATTEMPTS} attempts")
