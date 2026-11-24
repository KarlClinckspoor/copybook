import pytest

from copybook import CopybookError
from copybook.entries import build_entries
from copybook.geometry import Grid
from copybook.layouts.common import render_index
from copybook.settings import GridSettings
from copybook.tex import escape, grid_drawing


class FakeData:
    READINGS = {"奥": "ào", "熬": "áo", "凹": "āo", "袄": "ǎo", "了": "le liǎo"}

    def readings(self, ch):
        return self.READINGS.get(ch)

    def strokes(self, ch):
        return ("M 0 0 L 1 1 Z",) if ch != "袄" else None


def test_entries_sorted_by_pinyin_and_tone():
    entries = build_entries(list("奥熬凹袄"), FakeData())
    assert [e.char for e in entries] == list("凹熬袄奥")


def test_input_order_kept():
    entries = build_entries(list("奥熬"), FakeData(), order="input")
    assert [e.char for e in entries] == list("奥熬")


def test_missing_policies(capsys):
    assert [e.char for e in build_entries(list("学奥"), FakeData(), missing="skip")] == ["奥"]
    warned = build_entries(list("学奥"), FakeData(), missing="warn")
    assert [e.char for e in warned] == ["奥", "学"]  # unknown readings sort last
    assert warned[-1].reading == "?"
    with pytest.raises(CopybookError):
        build_entries(list("学"), FakeData(), missing="error")
    assert "学" in capsys.readouterr().err


def test_entry_readings():
    (entry,) = build_entries(["了"], FakeData())
    assert entry.reading == "le"
    assert entry.all_readings == "le liǎo"


def test_index_groups_by_letter_and_reading():
    entries = build_entries(list("奥了凹熬"), FakeData())
    pages = {"凹": 1, "熬": 1, "奥": 2, "了": 2}
    tex = render_index([(e, pages[e.char]) for e in entries], "索引", 3)
    assert r"\begin{multicols}{3}" in tex
    assert tex.index(r"\cbindexletter{A}") < tex.index(r"\cbindexletter{L}")
    assert r"\cbindexentry{āo}{凹}{1}" in tex
    assert r"\cbindexentry{ào}{奥}{2}" in tex


def test_index_merges_same_reading_on_same_page():
    class Same(FakeData):
        READINGS = {"安": "ān", "按": "ān", "案": "ān"}

    entries = build_entries(list("安按案"), Same())
    tex = render_index([(e, 1 if e.char != "案" else 2) for e in entries], "索引", 3)
    assert r"\cbindexentry{ān}{安按}{1}" in tex
    assert r"\cbindexentry{ān}{案}{2}" in tex


GRID = Grid(cell=10, columns=3, rows=2, x0=0, y0=0)


def test_blank_pattern_has_no_guides():
    tex = grid_drawing(GRID, GridSettings(pattern="blank"))
    assert "cb guide" not in tex and "cb frame" in tex


def test_mi_pattern_has_diagonals():
    tex = grid_drawing(GRID, GridSettings(pattern="mi"))
    assert "(0.00,0.00)--(10.00,10.00)" in tex


def test_hui_patterns_have_inner_boxes():
    assert "cb box" in grid_drawing(GRID, GridSettings(pattern="hui"))
    assert "cb box" in grid_drawing(GRID, GridSettings(pattern="hui-tall"))
    assert "cb box" not in grid_drawing(GRID, GridSettings(pattern="tian"))


def test_shared_edges_drawn_once():
    tex = grid_drawing(GRID, GridSettings(pattern="blank"))
    line = next(row for row in tex.splitlines() if row.startswith(r"\draw[cb line]"))
    assert line.count("--") == (3 - 1) + (2 - 1)


def test_escape():
    assert escape("a_b & 50%") == r"a\_b \& 50\%"
