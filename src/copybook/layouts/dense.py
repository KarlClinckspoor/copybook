"""(b) Dense reference book: every cell holds a character, sorted by pinyin."""

from __future__ import annotations

from copybook.entries import Entry, page_range
from copybook.geometry import plan_page
from copybook.layouts.common import (
    INDEX_PREAMBLE,
    Cover,
    GlyphPainter,
    cell_record,
    cover_commands,
    page_record,
    render_index,
)
from copybook.settings import ContentSettings, GlyphSettings, GridSettings, PageSettings
from copybook.tex import Document, escape


def chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def start_book(
    page: PageSettings,
    grid: GridSettings,
    glyphs: GlyphSettings,
    markers,
    cover: Cover | None,
) -> Document:
    doc = Document(page, grid, glyphs.font, page_numbers=True, extra_preamble=INDEX_PREAMBLE, markers=markers)
    if cover is not None:
        doc.cover_page(cover_commands(cover, page.size[0]))
    return doc


def add_index(doc: Document, pages: list[list[Entry]], content: ContentSettings) -> None:
    """Front-matter index (roman page numbers); the body then starts on a right-hand page at 1."""
    if content.index:
        doc.start_front_matter()
        located = [(entry, number) for number, page in enumerate(pages, start=1) for entry in page]
        doc.add(render_index(located, content.index_title, content.index_columns))
    doc.start_main_matter()


def running_head(entries: list[Entry], content: ContentSettings) -> str:
    """"ā -- bàn" for pinyin-ordered books; nothing when the order is arbitrary."""
    if content.order != "pinyin":
        return ""
    first, last = page_range(entries)
    if first == last:
        return escape(first)
    # A TeX en dash: a Unicode "–" would be typeset by the CJK font.
    return f"{escape(first)}\\enspace--\\enspace{{}}{escape(last)}"


def dense_document(
    entries: list[Entry],
    page: PageSettings,
    grid: GridSettings,
    glyphs: GlyphSettings,
    content: ContentSettings,
    painter: GlyphPainter,
    markers=None,
    cover: Cover | None = None,
) -> Document:
    page, layout = plan_page("dense", page, grid, markers)
    pages = chunk(entries, layout.cells_per_page)

    doc = start_book(page, grid, glyphs, markers, cover)
    draw_grid = doc.define_grid("cbgrid", layout)
    add_index(doc, pages, content)

    for page_entries in pages:
        commands = [draw_grid]
        cells = []
        for i in range(layout.cells_per_page):
            row, col = layout.cell_at(i)
            if i < len(page_entries):
                entry = page_entries[i]
                cx, cy = layout.cell_center(row, col)
                commands.append(painter.glyph(entry, cx, cy, layout.cell, shade=glyphs.shade))
                cells.append(cell_record(layout, row, col, entry.char, entry.reading, ink=100))
            else:
                cells.append(cell_record(layout, row, col))
        doc.overlay_page(commands, header=running_head(page_entries, content), record=page_record(layout, cells))
    return doc
