from app.domain.units import MAX_UNITS, parse_unit_labels


def test_expands_ranges_and_keeps_free_text_labels():
    r = parse_unit_labels("101-103, 2B, Ground-rear")
    assert r.error is None
    assert r.labels == ["101", "102", "103", "2B", "Ground-rear"]


def test_repeated_labels_are_an_error_ignoring_case():
    r = parse_unit_labels("101-103, 102, 2b, 2B")
    assert r.labels == []
    assert r.error == "Repeated unit labels: 102, 2B."


def test_backwards_range_is_an_error():
    assert "backwards" in (parse_unit_labels("110-101").error or "")


def test_cap_on_units():
    assert "at most" in (parse_unit_labels(f"1-{MAX_UNITS + 1}").error or "")
    assert parse_unit_labels(f"1-{MAX_UNITS}").error is None


def test_empty_input_gives_nothing_and_no_error():
    r = parse_unit_labels("  ")
    assert r.labels == [] and r.error is None
