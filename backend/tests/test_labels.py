"""Labels: the QR carries the resolver URL, the barcode carries the canonical ID, printing is audited."""

import re
import struct
import zlib

import pytest
import segno
from barcode import Code128
from sqlalchemy import select

from app.core.settings import get_settings
from app.domain.place_id import format_display
from app.models import AuditEvent, PlaceEvent
from app.models.enums import Role
from app.services import labels
from tests.world import active_place, register

pytestmark = pytest.mark.db


def svg_rects(svg: str) -> list[tuple[float, float, float, float]]:
    d = re.search(r'<path fill="#000" d="([^"]*)"', svg).group(1)
    return [
        tuple(float(v) for v in m) for m in re.findall(r"M([\d.]+) ([\d.]+)h([\d.]+)v([\d.]+)h-[\d.]+z", d)
    ]


def test_the_qr_decodes_to_the_resolver_url_and_the_barcode_to_the_canonical_id(client, world):
    p = active_place(client, world, name="Label Court", locality="Indiranagar")
    r = client.get(f"/places/{p['id']}/label", params={"format": "svg"}, headers=world.h("printer"))
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    assert r.headers["cache-control"] == "private, no-store"
    svg = r.text
    rects = svg_rects(svg)

    # QR: rebuild the module grid from the drawn squares and compare with an independent QR of the URL.
    url = f"{get_settings().public_base_url}/p/{p['public_id']}"
    expected = segno.make(url, error="q", micro=False)
    n = len(expected.matrix)
    box = 22.0
    m = box / (n + 2 * labels.QR_QUIET_MODULES)
    grid = [[0] * n for _ in range(n)]
    for x, y, w, _h in (r_ for r_ in rects if r_[0] < 24):
        row = round((y - 1.5) / m) - labels.QR_QUIET_MODULES
        col = round((x - 1.5) / m) - labels.QR_QUIET_MODULES
        for c in range(col, col + round(w / m)):
            grid[row][c] = 1
    assert grid == [list(row) for row in expected.matrix]
    assert expected.error == "Q"

    # Barcode: bars map back to the Code 128 module string of the canonical ID (no hyphens).
    modules = Code128(p["public_id"]).build()[0]
    mw = 24.5 / (len(modules) + 2 * labels.BARCODE_QUIET_MODULES)
    rebuilt = ["0"] * len(modules)
    for x, _, w, _ in (r_ for r_ in rects if r_[0] >= 24):
        start = round((x - 24.5) / mw) - labels.BARCODE_QUIET_MODULES
        for i in range(start, start + round(w / mw)):
            rebuilt[i] = "1"
    assert "".join(rebuilt) == modules
    assert Code128(p["public_id"]).get_fullcode() == p["public_id"]

    # Printed text: display-form ID, name, locality. The QR payload has no name or coordinates.
    assert format_display(p["public_id"]) in svg and "Label Court" in svg and "Indiranagar" in svg
    assert "12.97" not in svg


def test_every_format_and_size_renders(client, world):
    p = active_place(client, world)
    h = world.h("printer")
    for size, (w_mm, h_mm) in labels.SIZES_MM.items():
        png = client.get(f"/places/{p['id']}/label", params={"format": "png", "size": size}, headers=h)
        assert png.headers["content-type"] == "image/png" and png.content[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", png.content[16:24])
        assert (width, height) == (round(w_mm * 12), round(h_mm * 12))
        idat = png.content[png.content.index(b"IDAT") + 4 :]
        raw = zlib.decompress(
            idat[
                : struct.unpack(
                    ">I", png.content[png.content.index(b"IDAT") - 4 : png.content.index(b"IDAT")]
                )[0]
            ]
        )
        assert len(raw) == height * (width + 1) and 0 in raw[1:] and 255 in raw
        pdf = client.get(f"/places/{p['id']}/label", params={"format": "pdf", "size": size}, headers=h)
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF-1.4") and pdf.content.rstrip().endswith(b"%%EOF")
        assert b"Helvetica" in pdf.content and format_display(p["public_id"]).encode() in pdf.content
    assert client.get(f"/places/{p['id']}/label", params={"format": "gif"}, headers=h).status_code == 422
    assert client.get(f"/places/{p['id']}/label", params={"size": "huge"}, headers=h).status_code == 422


def test_printing_is_audited_and_recorded_in_history(client, world, db_session):
    p = active_place(client, world, unit_labels=["1"])
    client.get(f"/places/{p['id']}/label", params={"format": "pdf"}, headers=world.h("printer"))
    audit = db_session.scalars(select(AuditEvent).where(AuditEvent.action == "place.label_print")).one()
    assert audit.actor_id == world.printer.id and audit.detail == {"format": "pdf", "size": "50x25"}
    ev = db_session.scalars(select(PlaceEvent).where(PlaceEvent.type == "label_printed")).one()
    assert ev.place_id.hex == p["id"].replace("-", "")
    titles = [e["title"] for e in client.get(f"/places/{p['id']}/history", headers=world.h("admin")).json()]
    assert titles[0] == "Label printed"


def test_only_printers_and_admins_print_and_only_verified_places(client, world, db_session):
    active = active_place(client, world, 0)
    pending = register(client, world.h("registrar"), 3)
    url = f"/places/{active['id']}/label"
    for role in ("registrar", "verifier", "auditor"):
        assert client.get(url, headers=world.h(role)).status_code == 403
    for role in ("printer", "admin"):
        assert client.get(url, headers=world.h(role)).status_code == 200
    assert client.get(f"/places/{pending['id']}/label", headers=world.h("printer")).status_code == 409
    from tests.factories import make_staff
    from tests.world import auth

    mys_printer, _ = make_staff(db_session, Role.PRINTER, world.mys)
    assert client.get(url, headers=auth(mys_printer)).status_code == 404  # outside: it does not exist
    assert client.get(url).status_code == 401


def test_a_unit_label_prints_like_a_place(client, world):
    p = active_place(client, world, unit_labels=["101"])
    unit = client.get(f"/places/{p['id']}/units", headers=world.h("printer")).json()[0]
    r = client.get(f"/places/{unit['id']}/label", headers=world.h("printer"))
    assert r.status_code == 200 and format_display(unit["public_id"]) in r.text


def test_long_names_are_clipped_and_pdf_text_is_escaped():
    layout = labels.build_layout(
        "PP1FC98J327K456LMT"[:18], "http://x/p/1", "A (very) long \\ name " * 5, "Somewhere", "50x25"
    )
    pdf = labels.render_pdf(layout)
    assert b"\\(very\\)" in pdf or b"(very)" not in pdf
    assert max(len(t.value) for t in layout.texts) <= 30
