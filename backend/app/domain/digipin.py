"""DIGIPIN: India Post's 10-character grid code for a point (about 4 m x 4 m cell).

VERIFICATION STATUS (read before relying on this):
- The bounding box and the Dak Bhawan example (28.622788, 77.213033 -> 39J49LL8T4) are
  taken from published descriptions of the standard (see tests/test_digipin.py).
- The 4x4 label grid below and the cell-boundary rules were NOT checked against India Post's
  technical document (the host was unreachable when this was written). The Dak Bhawan vector
  passing is strong evidence, but one vector cannot prove the whole grid. Before launch, add
  the official document's vectors to tests/vectors/digipin.json and confirm they pass.
"""

from __future__ import annotations

from dataclasses import dataclass

LEVELS = 10
MIN_LAT, MAX_LAT = 2.5, 38.5
MIN_LON, MAX_LON = 63.5, 99.5

# Row 0 is the NORTHERN row, column 0 the WESTERN column.
GRID: tuple[tuple[str, ...], ...] = (
    ("F", "C", "9", "8"),
    ("J", "3", "2", "7"),
    ("K", "4", "5", "6"),
    ("L", "M", "P", "T"),
)
ALPHABET = "".join("".join(row) for row in GRID)  # 'FC98J327K456LMPT'

_POSITION = {ch: (r, c) for r, row in enumerate(GRID) for c, ch in enumerate(row)}


class OutsideIndiaError(ValueError):
    """The point is outside the DIGIPIN bounding box."""


class InvalidDigipinError(ValueError):
    """The text is not a valid 10-character DIGIPIN."""


@dataclass(frozen=True)
class Cell:
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float

    @property
    def center(self) -> tuple[float, float]:
        return (self.lat_min + self.lat_max) / 2, (self.lon_min + self.lon_max) / 2


def in_bounds(lat: float, lon: float) -> bool:
    return MIN_LAT <= lat <= MAX_LAT and MIN_LON <= lon <= MAX_LON


def encode(lat: float, lon: float) -> str:
    """Return the 10-character code (no hyphens). A point exactly on the north or east edge
    of the box belongs to the last cell in that direction."""
    if not in_bounds(lat, lon):
        raise OutsideIndiaError(f"({lat}, {lon}) is outside the DIGIPIN area")
    lat_min, lat_max, lon_min, lon_max = MIN_LAT, MAX_LAT, MIN_LON, MAX_LON
    out: list[str] = []
    for _ in range(LEVELS):
        lat_step = (lat_max - lat_min) / 4
        lon_step = (lon_max - lon_min) / 4
        lat_idx = min(3, int((lat - lat_min) // lat_step))
        lon_idx = min(3, int((lon - lon_min) // lon_step))
        out.append(GRID[3 - lat_idx][lon_idx])
        lat_min, lat_max = lat_min + lat_step * lat_idx, lat_min + lat_step * (lat_idx + 1)
        lon_min, lon_max = lon_min + lon_step * lon_idx, lon_min + lon_step * (lon_idx + 1)
    return "".join(out)


def normalize(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def is_valid(code: str) -> bool:
    c = normalize(code)
    return len(c) == LEVELS and all(ch in _POSITION for ch in c)


def decode(code: str) -> Cell:
    """Return the cell a code denotes."""
    c = normalize(code)
    if not is_valid(c):
        raise InvalidDigipinError(f"Not a valid DIGIPIN: {code!r}")
    lat_min, lat_max, lon_min, lon_max = MIN_LAT, MAX_LAT, MIN_LON, MAX_LON
    for ch in c:
        row, col = _POSITION[ch]
        lat_idx = 3 - row
        lat_step = (lat_max - lat_min) / 4
        lon_step = (lon_max - lon_min) / 4
        lat_min, lat_max = lat_min + lat_step * lat_idx, lat_min + lat_step * (lat_idx + 1)
        lon_min, lon_max = lon_min + lon_step * col, lon_min + lon_step * (col + 1)
    return Cell(lat_min, lat_max, lon_min, lon_max)


def format_display(code: str) -> str:
    """39J49LL8T4 -> 39J-49L-L8T4"""
    c = normalize(code)
    return f"{c[:3]}-{c[3:6]}-{c[6:]}"
