"""High-level build functions: settings in, PDF (and geometry sidecar) out."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pypdf import PdfReader

from copybook import CopybookError
from copybook.data import HanziData
from copybook.entries import build_entries
from copybook.imposition import impose
from copybook.layouts.common import Cover, GlyphPainter
from copybook.layouts.dense import dense_document
from copybook.layouts.practice import practice_document
from copybook.layouts.rows import rows_document
from copybook.markers import MarkerLayout, new_book_id, qr_payload, sidecar_path, write_sidecar
from copybook.settings import (
    ContentSettings,
    GlyphSettings,
    GridSettings,
    MarkerSettings,
    OutputSettings,
    PageSettings,
    RowsSettings,
)
from copybook.tex import Document, compile_pdf

PATTERN_NAMES = {"blank": "方格", "tian": "田字格", "mi": "米字格", "hui": "回宫格", "hui-tall": "长回宫格"}
DEFAULT_TITLES = {"practice": "{pattern}练习", "dense": "字帖", "rows": "字帖 · 逐字练习"}


class _Book:
    """Marker layout, book id and cover for one build (all None without markers)."""

    def __init__(self, kind: str, page: PageSettings, grid: GridSettings, markers: MarkerSettings | None, detail: str):
        self.kind = kind
        self.layout = self.book_id = self.cover = None
        if markers is None or not markers.enabled:
            return
        markers.validate()
        self.layout = MarkerLayout(markers, page.size)
        self.book_id = markers.book_id or new_book_id()
        if markers.book_qr:
            pattern = PATTERN_NAMES[grid.pattern]
            title = markers.title or DEFAULT_TITLES[kind].format(pattern=pattern)
            subtitle = f"{pattern} · {grid.cell:g} mm · {detail}{date.today().isoformat()}"
            self.cover = Cover(title, subtitle, qr_payload(self.book_id, grid.pattern, grid.cell))

    def sidecar_header(self, grid: GridSettings, glyphs: GlyphSettings | None, actual_cell: float) -> dict:
        header = {
            "book_id": self.book_id,
            "book_type": self.kind,
            "grid": {
                "type": grid.pattern,
                "square_mm": round(actual_cell, 3),
                "line_gray": grid.line_ink / 100,
                "guide_gray": grid.guide_ink / 100,
                # Inner guide boxes as fractions of the cell (cells themselves stay square).
                "hui_scale": grid.hui_scale if grid.pattern == "hui" else None,
                "tall_box": [grid.tall_width, grid.tall_height] if grid.pattern == "hui-tall" else None,
            },
            "glyph": None,
        }
        if glyphs is not None:
            header["glyph"] = {
                "source": "makemeahanzi" if glyphs.source == "strokes" else "font",
                "font": glyphs.font,
                "align": glyphs.align,
                # Em square side as a fraction of the cell, centred on the cell. With
                # "design", Make Me a Hanzi's em box (y -124..900) maps onto that square.
                "scale": glyphs.scale,
            }
        return header


def _finish(doc: Document, output: OutputSettings, book: _Book, header: dict) -> list[Path]:
    pdf = compile_pdf(doc.render(), output.build_dir, output.output, files=doc.files)
    written = [pdf]
    if book.layout is not None:
        total = len(PdfReader(pdf).pages)
        path = sidecar_path(pdf, book.book_id)
        written.append(write_sidecar(path, header, book.layout, total, doc.grid_pages, doc.has_cover))
    if output.impose:
        booklet = pdf.with_name(f"{pdf.stem}_booklet.pdf")
        written.append(impose(pdf, booklet, output.sheets_per_signature))
    return written


def _cell(doc: Document) -> float:
    return doc.grid_pages[0]["cells"][0]["size"] if doc.grid_pages else 0.0


def build_practice(
    page: PageSettings,
    grid: GridSettings,
    output: OutputSettings,
    pages: int = 16,
    page_numbers: bool = False,
    font: str = "KaiTi",
    markers: MarkerSettings | None = None,
) -> list[Path]:
    if pages < 1:
        raise CopybookError("--pages must be at least 1")
    page.validate()
    grid.validate()
    book = _Book("practice", page, grid, markers, f"{pages} pages · ")
    doc = practice_document(page, grid, pages, font, page_numbers, book.layout, book.cover)
    return _finish(doc, output, book, book.sidecar_header(grid, None, _cell(doc)) if book.layout else {})


def build_book(
    kind: str,
    page: PageSettings,
    grid: GridSettings,
    glyphs: GlyphSettings,
    content: ContentSettings,
    output: OutputSettings,
    rows: RowsSettings | None = None,
    markers: MarkerSettings | None = None,
) -> list[Path]:
    """Build a ``dense`` reference book or a ``rows`` copybook."""
    for settings in (page, grid, glyphs, content, rows):
        if settings is not None:
            settings.validate()

    with HanziData(output.data_dir) as data:
        entries = build_entries(content.characters, data, content.order, content.missing)

    book = _Book(kind, page, grid, markers, f"{len(entries)} 字 · ")
    print(f"{len(entries)} characters; rendering glyphs ...")
    painter = GlyphPainter(glyphs, output.cache_dir, output.build_dir)
    if kind == "dense":
        doc = dense_document(entries, page, grid, glyphs, content, painter, book.layout, book.cover)
    elif kind == "rows":
        doc = rows_document(entries, page, grid, glyphs, content, rows or RowsSettings(), painter, book.layout, book.cover)
    else:
        raise CopybookError(f"Unknown book kind {kind!r}")
    print("Typesetting with XeLaTeX ...")
    return _finish(doc, output, book, book.sidecar_header(grid, glyphs, _cell(doc)) if book.layout else {})
