"""Printable labels: a QR code of the resolver URL plus a Code 128 barcode of the canonical ID.

Pure functions (no database, no web framework). The label is laid out once, in millimetres, as plain
rectangles and text; SVG, PDF and PNG are three renderers of that one layout, so they cannot disagree.
See .claude/skills/pinpoint-qr-label: QR error correction Q, quiet zone of 4 modules, black on white,
no logo. The QR carries the URL only (never coordinates or names).

Limits, on purpose (no extra dependencies): the PDF uses the built-in Helvetica font, so characters
outside Latin-1 (for example Kannada) print as "?"; the PNG has the codes only, no text."""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

import segno
from barcode import Code128

from app.domain.place_id import format_display

QR_QUIET_MODULES = 4
BARCODE_QUIET_MODULES = 10
PNG_PX_PER_MM = 12  # about 300 dpi

SIZES_MM: dict[str, tuple[float, float]] = {"50x25": (50, 25), "a6": (105, 148)}
MEDIA_TYPES = {"svg": "image/svg+xml", "png": "image/png", "pdf": "application/pdf"}


def resolver_url(public_base_url: str, public_id: str) -> str:
    return f"{public_base_url.rstrip('/')}/p/{public_id}"


def qr_matrix(url: str) -> list[list[int]]:
    """Dark = 1. Error correction Q. The quiet zone is added by the layout, not here."""
    return [list(row) for row in segno.make(url, error="q", micro=False).matrix]


def barcode_modules(public_id: str) -> str:
    """Code 128 of the canonical ID as a string of '1' (bar) and '0' (space) modules."""
    return Code128(public_id).build()[0]


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class Text:
    x: float
    y: float  # baseline
    size: float  # mm
    value: str
    bold: bool = False
    anchor: str = "start"  # start | middle


@dataclass
class Layout:
    width: float
    height: float
    bars: list[Rect] = field(default_factory=list)  # everything drawn black, QR and barcode
    texts: list[Text] = field(default_factory=list)


def _runs(bits: list[int]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    start: int | None = None
    for i, bit in enumerate([*bits, 0]):
        if bit and start is None:
            start = i
        elif not bit and start is not None:
            out.append((start, i - start))
            start = None
    return out


def _qr_rects(matrix: list[list[int]], x: float, y: float, box: float) -> list[Rect]:
    n = len(matrix)
    m = box / (n + 2 * QR_QUIET_MODULES)
    rects = []
    for r, row in enumerate(matrix):
        for start, length in _runs(row):
            rects.append(
                Rect(x + (QR_QUIET_MODULES + start) * m, y + (QR_QUIET_MODULES + r) * m, length * m, m)
            )
    return rects


def _barcode_rects(modules: str, x: float, y: float, width: float, height: float) -> list[Rect]:
    m = width / (len(modules) + 2 * BARCODE_QUIET_MODULES)
    return [
        Rect(x + (BARCODE_QUIET_MODULES + start) * m, y, length * m, height)
        for start, length in _runs([int(c) for c in modules])
    ]


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build_layout(public_id: str, url: str, name: str, locality: str, size: str) -> Layout:
    w, h = SIZES_MM[size]
    layout = Layout(w, h)
    matrix = qr_matrix(url)
    modules = barcode_modules(public_id)
    display = format_display(public_id)
    if size == "a6":
        qr_box = 80.0
        layout.bars += _qr_rects(matrix, (w - qr_box) / 2, 10, qr_box)
        layout.bars += _barcode_rects(modules, 8, 98, w - 16, 18)
        layout.texts += [
            Text(w / 2, 10, 4.5, "PINPOINT", bold=True, anchor="middle"),
            Text(w / 2, 125, 5.2, display, anchor="middle"),
            Text(w / 2, 135, 5.5, _clip(name, 34), bold=True, anchor="middle"),
            Text(w / 2, 142, 4, _clip(locality, 44), anchor="middle"),
        ]
    else:  # 50 x 25 mm
        qr_box = 22.0
        layout.bars += _qr_rects(matrix, 1.5, 1.5, qr_box)
        layout.bars += _barcode_rects(modules, 24.5, 3, 24.5, 9)
        layout.texts += [
            Text(36.75, 15.5, 1.9, display, anchor="middle"),
            Text(25, 19.5, 2.2, _clip(name, 24), bold=True),
            Text(25, 23, 1.8, _clip(locality, 30)),
        ]
    return layout


# ---------- renderers ----------
def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def render_svg(layout: Layout) -> bytes:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(layout.width)}mm" height="{_fmt(layout.height)}mm" '
        f'viewBox="0 0 {_fmt(layout.width)} {_fmt(layout.height)}" shape-rendering="crispEdges">',
        '<rect width="100%" height="100%" fill="#fff"/>',
        '<path fill="#000" d="'
        + "".join(f"M{_fmt(r.x)} {_fmt(r.y)}h{_fmt(r.w)}v{_fmt(r.h)}h-{_fmt(r.w)}z" for r in layout.bars)
        + '"/>',
    ]
    for t in layout.texts:
        weight = "700" if t.bold else "400"
        parts.append(
            f'<text x="{_fmt(t.x)}" y="{_fmt(t.y)}" font-family="Helvetica, Arial, sans-serif" '
            f'font-size="{_fmt(t.size)}" font-weight="{weight}" text-anchor="{t.anchor}" fill="#000">{escape(t.value)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts).encode("utf-8")


_PT_PER_MM = 72 / 25.4
_HELVETICA_WIDTH = 0.55  # rough average glyph width in em, used only to centre text


def _pdf_escape(text: str) -> bytes:
    raw = text.encode("latin-1", errors="replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def render_pdf(layout: Layout) -> bytes:
    w, h = layout.width * _PT_PER_MM, layout.height * _PT_PER_MM
    ops = [b"0 g"]
    for r in layout.bars:
        ops.append(
            f"{r.x * _PT_PER_MM:.2f} {h - (r.y + r.h) * _PT_PER_MM:.2f} {r.w * _PT_PER_MM:.2f} {r.h * _PT_PER_MM:.2f} re f".encode()
        )
    for t in layout.texts:
        size = t.size * _PT_PER_MM
        x = t.x * _PT_PER_MM
        if t.anchor == "middle":
            x -= len(t.value) * size * _HELVETICA_WIDTH / 2
        font = "F2" if t.bold else "F1"
        ops.append(
            f"BT /{font} {size:.2f} Tf {x:.2f} {h - t.y * _PT_PER_MM:.2f} Td (".encode()
            + _pdf_escape(t.value)
            + b") Tj ET"
        )
    stream = b"\n".join(ops)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w:.2f} {h:.2f}] /Contents 4 0 R "
        f"/Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> >>".encode(),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def render_png(layout: Layout) -> bytes:
    """Greyscale PNG of the QR and barcode (no text), about 300 dpi."""
    width, height = round(layout.width * PNG_PX_PER_MM), round(layout.height * PNG_PX_PER_MM)
    rows = [bytearray(b"\xff" * width) for _ in range(height)]
    for r in layout.bars:
        x0, x1 = (
            round(r.x * PNG_PX_PER_MM),
            max(round((r.x + r.w) * PNG_PX_PER_MM), round(r.x * PNG_PX_PER_MM) + 1),
        )
        y0, y1 = (
            round(r.y * PNG_PX_PER_MM),
            max(round((r.y + r.h) * PNG_PX_PER_MM), round(r.y * PNG_PX_PER_MM) + 1),
        )
        for y in range(y0, min(y1, height)):
            rows[y][x0 : min(x1, width)] = b"\x00" * (min(x1, width) - x0)
    raw = b"".join(b"\x00" + bytes(row) for row in rows)

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def render_label(
    public_id: str, url: str, name: str, locality: str, fmt: str, size: str
) -> tuple[bytes, str]:
    layout = build_layout(public_id, url, name, locality, size)
    renderer = {"svg": render_svg, "pdf": render_pdf, "png": render_png}[fmt]
    return renderer(layout), MEDIA_TYPES[fmt]
