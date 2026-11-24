import io

import pytest
from pypdf import PdfReader

from copybook import glyphs

SQUARE = ("M 100 0 L 300 0 L 300 200 L 100 200 Z",)


def test_quadratic_becomes_cubic():
    ops = glyphs.path_operators("M 0 0 Q 30 60 90 0 Z")
    assert ops.splitlines() == ["0 0 m", "20 40 50 40 90 0 c", "h"]


def test_unsupported_command():
    with pytest.raises(ValueError):
        glyphs.path_operators("M 0 0 A 1 1 0 0 1 5 5")


def test_design_alignment_uses_the_900_baseline():
    # Source y = -124 (em bottom) must land on the page bottom.
    assert glyphs.placement(SQUARE, "design") == (0.0, 124.0)


def test_center_alignment_centres_the_ink():
    dx, dy = glyphs.placement(SQUARE, "center")
    assert (200 + dx, 100 + dy) == (512, 512)


def test_shade_inks():
    assert glyphs.shade_inks(3, 20, 35) == [100, 80, 60]
    many = glyphs.shade_inks(20, 20, 35)
    assert many[0] == 100 and many[-1] == pytest.approx(35)
    assert all(a > b for a, b in zip(many, many[1:]))  # still distinguishable


def test_glyph_pdf_is_valid():
    reader = PdfReader(io.BytesIO(glyphs.glyph_pdf(SQUARE, "design", [100])))
    box = reader.pages[0].mediabox
    assert float(box.width) == pytest.approx(102.4)
    assert b" g\n" in reader.pages[0].get_contents().get_data()  # DeviceGray fill


def test_stroke_order_strip_width():
    pdf = glyphs.stroke_order_pdf(SQUARE * 3, "design")
    width = float(PdfReader(io.BytesIO(pdf)).pages[0].mediabox.width)
    assert width == pytest.approx((1024 * 1.2 * 2 + 1024) * glyphs.PDF_SCALE, abs=0.1)


def test_cache_key_changes_with_settings(tmp_path):
    cache = glyphs.GlyphCache(tmp_path, "design")
    a = cache.shaded("学", SQUARE * 4, step=20, min_ink=35)
    b = cache.shaded("学", SQUARE * 4, step=10, min_ink=35)
    assert a != b and a.is_file() and b.is_file()
    assert cache.shaded("学", SQUARE * 4, step=20, min_ink=35) == a
