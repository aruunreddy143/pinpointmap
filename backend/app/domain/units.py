"""Expand unit label input such as "101-110, 201-204, 2B" (mirror of frontend/src/lib/units.ts)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_UNITS = 500
_RANGE = re.compile(r"^(\d+)\s*-\s*(\d+)$")


@dataclass(frozen=True)
class UnitParse:
    labels: list[str] = field(default_factory=list)
    error: str | None = None


def parse_unit_labels(text: str) -> UnitParse:
    """Only purely numeric A-B tokens are ranges; anything else ('2B', 'Ground-rear') is one label.
    Labels are unique per building, ignoring case."""
    labels: list[str] = []
    for token in (t.strip() for t in re.split(r"[,\n]", text)):
        if not token:
            continue
        m = _RANGE.match(token)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                return UnitParse(error=f'"{token}" runs backwards. Write it as {b}-{a}.')
            if len(labels) + (b - a + 1) > MAX_UNITS:
                return UnitParse(error=f"A building can have at most {MAX_UNITS} units in one go.")
            labels.extend(str(n) for n in range(a, b + 1))
        else:
            labels.append(token)
    seen: set[str] = set()
    dupes: list[str] = []
    for label in labels:
        key = label.lower()
        if key in seen and label not in dupes:
            dupes.append(label)
        seen.add(key)
    if dupes:
        return UnitParse(error=f"Repeated unit labels: {', '.join(dupes)}.")
    if len(labels) > MAX_UNITS:
        return UnitParse(error=f"A building can have at most {MAX_UNITS} units in one go.")
    return UnitParse(labels=labels)
