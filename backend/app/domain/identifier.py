"""A normal user signs in with an Indian mobile number OR an email address (mirror of
frontend/src/lib/identifier.ts)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
_MOBILE = re.compile(r"^[6-9]\d{9}$")


@dataclass(frozen=True)
class Identifier:
    kind: Literal["email", "mobile"]
    value: str  # normalized: lower-case email, or +91XXXXXXXXXX


def parse_identifier(text: str) -> Identifier | None:
    t = text.strip()
    if not t:
        return None
    if "@" in t:
        return Identifier("email", t.lower()) if _EMAIL.match(t) else None
    digits = re.sub(r"[\s\-().]", "", t)
    if not re.fullmatch(r"\+?\d+", digits):
        return None
    digits = digits.lstrip("+")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return Identifier("mobile", f"+91{digits}") if _MOBILE.match(digits) else None
