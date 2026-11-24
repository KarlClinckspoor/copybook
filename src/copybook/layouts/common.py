"""Pieces shared by the character layouts: glyph placement and the index."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path

from copybook.entries import Entry
from copybook.geometry import Grid
from copybook.glyphs import GlyphCache
from copybook.settings import GlyphSettings
from copybook.tex import escape, mm

# Ideographic em box of the CJK font relative to the baseline (KaiTi: ascent
# 220/256, descent 36/256; most CJK fonts are close to 0.88/0.12). Giving the
# node exactly that box centres the em square on the anchor. Absolute lengths
# are required: "em" in TikZ's text height refers to the surrounding font.
_FONT_ASCENT = 0.86
_FONT_DESCENT = 0.14
# Typeface glyphs fill more of their em than Make Me a Hanzi outlines do;
# shrinking them keeps font fallbacks the same size as their neighbours.
_FONT_SIZE = 0.9


class GlyphPainter:
    """Emits TikZ nodes that draw characters, from stroke data or the font."""

    def __init__(self, settings: GlyphSettings, cache_dir: Path, build_dir: Path):
        self.settings = settings
        self.build_dir = Path(build_dir)
        self.cache = GlyphCache(Path(cache_dir) / "glyphs", settings.align)

    def _uses_strokes(self, entry: Entry) -> bool:
        return self.settings.source == "strokes" and entry.strokes is not None

    def _include(self, path: Path, options: str) -> str:
        rel = Path(os.path.relpath(path.resolve(), self.build_dir.resolve())).as_posix()
        return f"\\includegraphics[{options}]{{{rel}}}"

    def _font_node(self, entry: Entry, cx: float, cy: float, size: float, ink: float) -> str:
        colour = "" if ink >= 100 else f", text=black!{ink:g}"
        return (
            f"\\node[cb glyph, font=\\fontsize{{{mm(size)}mm}}{{{mm(size)}mm}}\\selectfont, "
            f"text height={mm(size * _FONT_ASCENT)}mm, text depth={mm(size * _FONT_DESCENT)}mm{colour}] "
            f"at ({mm(cx)},{mm(cy)}) {{{escape(entry.char)}}};"
        )

    def glyph(self, entry: Entry, cx: float, cy: float, cell: float, ink: float = 100.0, shade: bool = False) -> str:
        """A character centred on (cx, cy) in a cell of side ``cell``."""
        size = cell * self.settings.scale
        if not self._uses_strokes(entry):
            return self._font_node(entry, cx, cy, size * _FONT_SIZE, ink)
        if shade:
            path = self.cache.shaded(entry.char, entry.strokes, self.settings.shade_step, self.settings.shade_min_ink)
        else:
            path = self.cache.solid(entry.char, entry.strokes, ink)
        return f"\\node[cb glyph] at ({mm(cx)},{mm(cy)}) {{{self._include(path, f'width={mm(size)}mm')}}};"

    def stroke_order(self, entry: Entry, height: float, max_width: float) -> str:
        """Inline graphic of the stroke-by-stroke build-up ("" without stroke data)."""
        if entry.strokes is None:
            return ""
        path = self.cache.stroke_order(entry.char, entry.strokes)
        return self._include(path, f"height={mm(height)}mm,width={mm(max_width)}mm,keepaspectratio")


# ---------------------------------------------------------------------------
# Geometry sidecar records and the cover page
# ---------------------------------------------------------------------------


def cell_record(grid: Grid, row: int, col: int, char: str | None = None, pinyin: str | None = None, **extra) -> dict:
    x, y = grid.cell_origin(row, col)
    return {
        "row": row,
        "col": col,
        "x": round(x, 3),
        "y": round(y, 3),
        "size": round(grid.cell, 3),
        "char": char,
        "pinyin": pinyin,
        **extra,
    }


def page_record(grid: Grid, cells: list[dict]) -> dict:
    """Sidecar entry for one grid page: the cells' bounding box and every cell."""
    left, top = grid.x0, grid.row_top(0)
    right, bottom = grid.x0 + grid.width, grid.row_top(grid.rows - 1) + grid.cell
    area = [[left, top], [right, top], [right, bottom], [left, bottom]]
    return {"grid_area": [[round(v, 3) for v in p] for p in area], "cells": cells}


@dataclass(frozen=True)
class Cover:
    title: str
    subtitle: str
    qr_payload: str


def cover_commands(cover: Cover, page_width: float, qr_size: float = 20.0) -> list[str]:
    from copybook.markers import qr_tikz

    cx = page_width / 2
    return [
        f"\\node[cb glyph, font=\\fontsize{{9mm}}{{11mm}}\\selectfont] at ({mm(cx)},60) {{{escape(cover.title)}}};",
        f"\\node[cb glyph, font=\\fontsize{{3.5mm}}{{4.5mm}}\\selectfont] at ({mm(cx)},74) {{{escape(cover.subtitle)}}};",
        qr_tikz(cover.qr_payload, cx - qr_size / 2, 90, qr_size),
    ]


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

INDEX_PREAMBLE = r"""
\newcommand{\cbindexletter}[1]{\par\addvspace{1.4ex}{\large\bfseries #1}\par\nobreak\addvspace{0.3ex}}
\newcommand{\cbindexentry}[3]{\par\hangindent=1.5em\hangafter=1\noindent
  #1\enspace{}#2\nobreak\dotfill\nobreak#3}
"""


def render_index(located: Iterable[tuple[Entry, int]], title: str, columns: int) -> str:
    """Dictionary-style index: one line per reading and page, grouped by initial letter.

    ``ān  安按案 .... 1`` - characters sharing a reading on the same page are
    listed together, which roughly halves the length of the index.
    """
    items = sorted(located, key=lambda item: item[0].sort_key())
    out = [
        r"\begin{center}{\fontsize{6mm}{7mm}\selectfont " + escape(title) + r"}\end{center}",
        r"\vspace{1mm}",
        r"{\fontsize{3.3mm}{4.3mm}\selectfont",
        r"\setlength{\columnsep}{5mm}",
        f"\\begin{{multicols}}{{{columns}}}",
        r"\raggedcolumns",
    ]
    for letter, by_letter in groupby(items, key=lambda item: item[0].initial if item[0].readings else "?"):
        out.append(f"\\cbindexletter{{{escape(letter)}}}")
        for (reading, page), group in groupby(by_letter, key=lambda item: (item[0].reading, item[1])):
            chars = "".join(escape(entry.char) for entry, _ in group)
            out.append(f"\\cbindexentry{{{escape(reading)}}}{{{chars}}}{{{page}}}")
    out += [r"\end{multicols}", "}", r"\clearpage"]
    return "\n".join(out)
