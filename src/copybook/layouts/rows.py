"""(c) One character per row: model, tracing copies, then empty cells.

A narrow band above each row shows the reading, the stroke count and the
stroke order, built up one stroke at a time.
"""

from __future__ import annotations

from copybook.entries import Entry
from copybook.geometry import Grid, plan_page
from copybook.layouts.common import Cover, GlyphPainter, cell_record, page_record
from copybook.layouts.dense import add_index, chunk, running_head, start_book
from copybook.settings import ContentSettings, GlyphSettings, GridSettings, PageSettings, RowsSettings
from copybook.tex import Document, escape, mm

LABEL_WIDTH = 32.0  # mm reserved for the reading before the stroke-order strip


def _band(entry: Entry, layout: Grid, row: int, rows: RowsSettings, painter: GlyphPainter) -> str:
    band_top = layout.y0 + row * layout.row_pitch
    baseline = band_top + rows.band * 0.82
    text_size = rows.band * 0.55

    label = escape(entry.all_readings)
    if entry.stroke_count:
        label += f"\\enspace{{\\color{{black!60}}{entry.stroke_count}画}}"
    if rows.stroke_order:
        strip = painter.stroke_order(entry, rows.band * 0.72, layout.width - LABEL_WIDTH)
        if strip:
            label += f"\\quad{strip}"

    return (
        f"\\node[cb glyph, anchor=base west, font=\\fontsize{{{mm(text_size)}mm}}{{{mm(text_size)}mm}}\\selectfont] "
        f"at ({mm(layout.x0)},{mm(baseline)}) {{{label}}};"
    )


def rows_document(
    entries: list[Entry],
    page: PageSettings,
    grid: GridSettings,
    glyphs: GlyphSettings,
    content: ContentSettings,
    rows: RowsSettings,
    painter: GlyphPainter,
    markers=None,
    cover: Cover | None = None,
) -> Document:
    page, layout = plan_page("rows", page, grid, markers, band=rows.band)
    pages = chunk(entries, layout.rows)

    doc = start_book(page, grid, glyphs, markers, cover)
    draw_grid = doc.define_grid("cbgrid", layout)
    add_index(doc, pages, content)

    traces = min(rows.traces, layout.columns - 1)
    for page_entries in pages:
        commands = [draw_grid]
        cells = []
        for row in range(layout.rows):
            entry = page_entries[row] if row < len(page_entries) else None
            if entry is not None and rows.band > 0:
                commands.append(_band(entry, layout, row, rows, painter))
            for col in range(layout.columns):
                if entry is None:
                    cells.append(cell_record(layout, row, col, target=None))
                elif col <= traces:
                    ink = 100.0 if col == 0 else glyphs.trace_ink
                    cx, cy = layout.cell_center(row, col)
                    commands.append(painter.glyph(entry, cx, cy, layout.cell, ink=ink))
                    cells.append(cell_record(layout, row, col, entry.char, entry.reading, ink=ink, target=entry.char))
                else:  # empty practice cell: the character to write is the row's
                    cells.append(cell_record(layout, row, col, target=entry.char))
        doc.overlay_page(commands, header=running_head(page_entries, content), record=page_record(layout, cells))
    return doc
