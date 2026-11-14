import json
from pathlib import Path

import pytest

from app.domain import digipin, place_id
from app.domain.digipin import ALPHABET
from app.domain.place_id import IdProblem

SHARED = json.loads(
    (Path(__file__).parents[2] / "shared" / "test-vectors" / "place_ids.json").read_text(encoding="utf-8")
)
VALID = SHARED["valid"]


@pytest.mark.parametrize("v", VALID, ids=lambda v: v["id"])
def test_shared_vectors_make_and_validate(v):
    assert place_id.make_id(v["geo"], v["seq"]) == v["id"]
    assert place_id.format_display(v["id"]) == v["display"]
    assert place_id.validate(v["display"]) == place_id.IdCheck(True, canonical=v["id"])


@pytest.mark.parametrize("case", SHARED["invalid"], ids=lambda c: c["reason"] + ":" + c["input"][:8])
def test_shared_invalid_inputs(case):
    result = place_id.validate(case["input"])
    assert not result.ok
    assert result.problem == IdProblem(case["reason"])


@pytest.mark.parametrize("case", SHARED["normalize"])
def test_shared_normalize(case):
    assert place_id.normalize(case["input"]) == case["canonical"]


def test_every_single_character_typo_is_detected():
    for v in VALID:
        ident = v["id"]
        for pos in range(len(place_id.PREFIX), len(ident)):
            for ch in ALPHABET:
                if ch == ident[pos]:
                    continue
                bad = ident[:pos] + ch + ident[pos + 1 :]
                assert not place_id.validate(bad).ok, bad


def test_every_adjacent_transposition_of_different_characters_is_detected():
    for v in VALID:
        ident = v["id"]
        for pos in range(len(place_id.PREFIX), len(ident) - 1):
            if ident[pos] == ident[pos + 1]:
                continue
            bad = ident[:pos] + ident[pos + 1] + ident[pos] + ident[pos + 2 :]
            assert not place_id.validate(bad).ok, bad


def test_check_char_rejects_characters_outside_the_alphabet():
    with pytest.raises(ValueError):
        place_id.check_char("FC98J327K4O")


def test_geo_cell_is_recorded_in_the_id_but_is_not_the_location():
    ident = place_id.make_id("FC98J327K4", "56LM")
    assert place_id.geo_cell(ident) == "FC98J327K4"


def test_generate_uses_the_registration_cell_and_a_valid_id():
    lat, lon = 28.622788, 77.213033
    ident = place_id.generate(lat, lon, exists=lambda _: False)
    assert place_id.validate(ident).ok
    assert place_id.geo_cell(ident) == digipin.encode(lat, lon) == "39J49LL8T4"


def test_generate_retries_on_collision():
    calls: list[str] = []

    def exists(candidate: str) -> bool:
        calls.append(candidate)
        return len(calls) < 4  # first three are taken

    ident = place_id.generate(28.622788, 77.213033, exists=exists)
    assert len(calls) == 4 and calls[-1] == ident
    assert len(set(calls)) == 4  # a different suffix each time (overwhelmingly likely)


def test_generate_fails_loudly_instead_of_looping_forever():
    with pytest.raises(place_id.IdGenerationError):
        place_id.generate(28.622788, 77.213033, exists=lambda _: True)


def test_generate_rejects_points_outside_india():
    with pytest.raises(digipin.OutsideIndiaError):
        place_id.generate(51.5, -0.12, exists=lambda _: False)


def test_generate_uses_the_injected_rng():
    ident = place_id.generate(28.622788, 77.213033, exists=lambda _: False, rng=lambda n: 0)
    assert ident[13:17] == ALPHABET[0] * 4
