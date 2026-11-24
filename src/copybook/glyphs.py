"""Vector glyphs from Make Me a Hanzi stroke outlines, written as tiny PDFs.

Make Me a Hanzi outlines live in a 1024-unit em square, y pointing up, with
the em box spanning y = -124 ... 900 (upstream renders them with
``translate(0, 900) scale(1, -1)``). The previous code flipped around 1024
instead of 900, which pushed every character 124 units - about 12% of the
cell - too low.

The outlines only use absolute ``M``, ``L``, ``Q`` and ``Z`` commands, so they
are converted straight into PDF path operators: no Cairo or other native
library is needed, and fills use DeviceGray, so the output is pure greyscale.
"""

from __future__ import annotations

import hashlib
import re
import zlib
from pathlib import Path

EM = 1024.0
DESCENT = 124.0  # the em box bottom sits at y = -124 in source units
# PDF points per source unit. Keeps pages small: TeX cannot handle dimensions
# above ~16000 pt, which a long stroke-order strip at 1024 pt per frame exceeds.
PDF_SCALE = 0.1
_TOKEN = re.compile(r"[A-Za-z]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


# ---------------------------------------------------------------------------
# Outline geometry
# ---------------------------------------------------------------------------


def _num(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def path_operators(d: str) -> str:
    """Translate SVG path data (absolute M/L/Q/C/Z) into PDF path operators."""
    tokens = _TOKEN.findall(d)
    ops: list[str] = []
    cmd = ""
    cur = start = (0.0, 0.0)
    i = 0

    def take(n: int) -> list[float]:
        nonlocal i
        values = [float(t) for t in tokens[i : i + n]]
        i += n
        return values

    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                ops.append("h")
                cur = start
                continue
        if cmd == "M":
            cur = start = tuple(take(2))
            ops.append(f"{_num(cur[0])} {_num(cur[1])} m")
            cmd = "L"  # further pairs after M are line-tos
        elif cmd == "L":
            cur = tuple(take(2))
            ops.append(f"{_num(cur[0])} {_num(cur[1])} l")
        elif cmd == "Q":
            qx, qy, x, y = take(4)
            # Exact quadratic -> cubic conversion.
            c1 = (cur[0] + 2 / 3 * (qx - cur[0]), cur[1] + 2 / 3 * (qy - cur[1]))
            c2 = (x + 2 / 3 * (qx - x), y + 2 / 3 * (qy - y))
            ops.append(" ".join(_num(v) for v in (*c1, *c2, x, y)) + " c")
            cur = (x, y)
        elif cmd == "C":
            values = take(6)
            ops.append(" ".join(_num(v) for v in values) + " c")
            cur = (values[4], values[5])
        else:
            raise ValueError(f"Unsupported SVG path command {cmd!r} in {d[:40]}...")
    return "\n".join(ops)


def ink_to_hex(ink: float) -> str:
    """Screen grey for an ink percentage (100 = black, 0 = white)."""
    level = round(255 * (1 - max(0.0, min(100.0, ink)) / 100))
    return f"#{level:02x}{level:02x}{level:02x}"


def outline_polygons(d: str, steps: int = 6) -> list[list[tuple[float, float]]]:
    """Flatten SVG path data into polygons (curves as ``steps`` segments), for on-screen previews."""
    tokens = _TOKEN.findall(d)
    polys: list[list[tuple[float, float]]] = []
    cur = (0.0, 0.0)
    cmd = ""
    i = 0
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                continue
        n = {"M": 2, "L": 2, "Q": 4, "C": 6}.get(cmd)
        if n is None:
            raise ValueError(f"Unsupported SVG path command {cmd!r}")
        v = [float(t) for t in tokens[i : i + n]]
        i += n
        if cmd == "M":
            polys.append([(v[0], v[1])])
            cmd = "L"
        elif cmd == "L":
            polys[-1].append((v[0], v[1]))
        elif cmd == "Q":
            (x0, y0), (qx, qy, x, y) = cur, v
            for k in range(1, steps + 1):
                t = k / steps
                a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
                polys[-1].append((a * x0 + b * qx + c * x, a * y0 + b * qy + c * y))
        else:  # C
            (x0, y0), (c1x, c1y, c2x, c2y, x, y) = cur, v
            for k in range(1, steps + 1):
                t = k / steps
                a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t**3
                polys[-1].append((a * x0 + b * c1x + c * c2x + e * x, a * y0 + b * c1y + c * c2y + e * y))
        cur = polys[-1][-1]
    return polys


def outline_bbox(strokes: tuple[str, ...]) -> tuple[float, float, float, float]:
    """Approximate ink bounding box (min_x, min_y, max_x, max_y) in source units.

    Every number pair in the (absolute) path data is a point; including the
    Bézier control points errs slightly on the generous side.
    """
    nums = [float(t) for d in strokes for t in _TOKEN.findall(d) if not t.isalpha()]
    xs, ys = nums[0::2], nums[1::2]
    return min(xs), min(ys), max(xs), max(ys)


def placement(strokes: tuple[str, ...], align: str) -> tuple[float, float]:
    """Translation from source units into a 1024 x 1024 page (PDF, y up)."""
    if align == "center":
        min_x, min_y, max_x, max_y = outline_bbox(strokes)
        return EM / 2 - (min_x + max_x) / 2, EM / 2 - (min_y + max_y) / 2
    return 0.0, DESCENT


def shade_inks(count: int, step: float, min_ink: float) -> list[float]:
    """Ink per stroke when shading: first stroke black, then lighter, never below min_ink.

    The step shrinks for characters with many strokes so the sequence stays
    distinguishable all the way down to ``min_ink``.
    """
    if count <= 1:
        return [100.0] * count
    step = min(step, (100.0 - min_ink) / (count - 1))
    return [max(min_ink, 100.0 - i * step) for i in range(count)]


# ---------------------------------------------------------------------------
# PDF output
# ---------------------------------------------------------------------------


def minimal_pdf(width: float, height: float, content: str) -> bytes:
    """A single-page PDF of ``width`` x ``height`` source units (scaled by PDF_SCALE)."""
    content = f"{PDF_SCALE} 0 0 {PDF_SCALE} 0 0 cm\n{content}"
    width, height = width * PDF_SCALE, height * PDF_SCALE
    stream = zlib.compress(content.encode("ascii"))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_num(width)} {_num(height)}] "
        f"/Resources << >> /Contents 4 0 R >>".encode(),
        f"<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n".encode() + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def _strokes_content(strokes, inks, dx: float, dy: float) -> str:
    parts = [f"q 1 0 0 1 {_num(dx)} {_num(dy)} cm"]
    for d, ink in zip(strokes, inks):
        parts.append(f"{1 - ink / 100:.3f} g\n{path_operators(d)}\nf")
    parts.append("Q")
    return "\n".join(parts)


def glyph_pdf(strokes: tuple[str, ...], align: str, inks: list[float]) -> bytes:
    """One character, one ink level (0-100) per stroke."""
    dx, dy = placement(strokes, align)
    return minimal_pdf(EM, EM, _strokes_content(strokes, inks, dx, dy))


def stroke_order_pdf(strokes: tuple[str, ...], align: str, previous_ink: float = 30.0) -> bytes:
    """A strip of frames; frame i shows strokes 1..i with the newest one black."""
    dx, dy = placement(strokes, align)
    pitch = EM * 1.2  # frames are separated by a fifth of an em
    frames = [
        _strokes_content(strokes[: i + 1], [previous_ink] * i + [100.0], dx + i * pitch, dy)
        for i in range(len(strokes))
    ]
    return minimal_pdf(pitch * (len(strokes) - 1) + EM, EM, "\n".join(frames))


class GlyphCache:
    """Writes glyph PDFs on demand and reuses them across builds.

    File names hash the PDF bytes, i.e. everything that affects the drawing
    (outlines, alignment, ink levels), so a changed setting can never pick up
    a stale file.
    """

    def __init__(self, directory: Path, align: str):
        self.directory = Path(directory)
        self.align = align
        self.directory.mkdir(parents=True, exist_ok=True)

    def _store(self, char: str, kind: str, pdf: bytes) -> Path:
        digest = hashlib.sha1(pdf).hexdigest()[:10]
        path = self.directory / f"U{ord(char):05X}-{kind}-{digest}.pdf"
        if not path.is_file():
            tmp = path.with_suffix(".part")
            tmp.write_bytes(pdf)
            tmp.replace(path)
        return path

    def solid(self, char: str, strokes: tuple[str, ...], ink: float = 100.0) -> Path:
        kind = "solid" if ink >= 100 else f"ink{ink:g}"
        return self._store(char, kind, glyph_pdf(strokes, self.align, [ink] * len(strokes)))

    def shaded(self, char: str, strokes: tuple[str, ...], step: float, min_ink: float) -> Path:
        inks = shade_inks(len(strokes), step, min_ink)
        return self._store(char, "shaded", glyph_pdf(strokes, self.align, inks))

    def stroke_order(self, char: str, strokes: tuple[str, ...]) -> Path:
        return self._store(char, "order", stroke_order_pdf(strokes, self.align))
