import json
import random
from pathlib import Path

import pytest

from app.domain import digipin

VECTORS = json.loads((Path(__file__).parent / "vectors" / "digipin.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("v", VECTORS["encode"], ids=lambda v: v["name"])
def test_published_vectors_encode(v):
    assert digipin.encode(v["lat"], v["lon"]) == v["code"]


@pytest.mark.parametrize("v", VECTORS["encode"], ids=lambda v: v["name"])
def test_published_vectors_decode_to_a_cell_containing_the_point(v):
    cell = digipin.decode(v["code"])
    assert cell.lat_min <= v["lat"] <= cell.lat_max
    assert cell.lon_min <= v["lon"] <= cell.lon_max


def test_alphabet_has_16_distinct_unambiguous_symbols():
    assert len(digipin.ALPHABET) == 16
    assert len(set(digipin.ALPHABET)) == 16
    assert not set("0O1IAEU") & set(digipin.ALPHABET)


def test_round_trip_random_points_inside_india():
    rng = random.Random(42)  # noqa: S311 (a seeded generator for reproducible test data, not security)
    for _ in range(2000):
        lat = rng.uniform(digipin.MIN_LAT, digipin.MAX_LAT)
        lon = rng.uniform(digipin.MIN_LON, digipin.MAX_LON)
        code = digipin.encode(lat, lon)
        assert len(code) == 10 and digipin.is_valid(code)
        cell = digipin.decode(code)
        assert cell.lat_min <= lat <= cell.lat_max
        assert cell.lon_min <= lon <= cell.lon_max


def test_cell_is_about_four_metres():
    cell = digipin.decode(digipin.encode(28.622788, 77.213033))
    lat_m = (cell.lat_max - cell.lat_min) * 111_000
    assert 3.0 < lat_m < 4.5


def test_neighbouring_cells_differ_and_a_nearby_point_often_shares_a_cell():
    a = digipin.encode(28.622788, 77.213033)
    assert digipin.encode(28.622788 + 0.00001, 77.213033) in (a, digipin.encode(28.622798, 77.213033))
    assert digipin.encode(28.7, 77.2) != a


@pytest.mark.parametrize(
    "lat,lon", [(2.4999, 80), (38.5001, 80), (20, 63.4999), (20, 99.5001), (0, 0), (51.5, -0.12)]
)
def test_points_outside_the_area_are_rejected(lat, lon):
    with pytest.raises(digipin.OutsideIndiaError):
        digipin.encode(lat, lon)


def test_points_on_the_box_edge_are_accepted_and_use_the_last_cell():
    assert digipin.encode(digipin.MAX_LAT, digipin.MAX_LON) == digipin.GRID[0][3] * 10
    assert digipin.encode(digipin.MIN_LAT, digipin.MIN_LON) == digipin.GRID[3][0] * 10


@pytest.mark.parametrize("bad", ["", "39J49LL8T", "39J49LL8T44", "39J49LL8TO", "ABCDEFGHIJ"])
def test_decode_rejects_invalid_codes(bad):
    with pytest.raises(digipin.InvalidDigipinError):
        digipin.decode(bad)


def test_hyphenated_and_lowercase_input_is_accepted():
    assert digipin.decode("39j-49l-l8t4") == digipin.decode("39J49LL8T4")
    assert digipin.format_display("39J49LL8T4") == "39J-49L-L8T4"
