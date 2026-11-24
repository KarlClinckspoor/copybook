"""(a) Practice sheets: empty grids in the chosen pattern."""

from __future__ import annotations

from copybook.geometry import plan_page
from copybook.layouts.common import Cover, cell_record, cover_commands, page_record
from copybook.settings import GridSettings, PageSettings
from copybook.tex import Document


def practice_document(
    page: PageSettings,
    grid: GridSettings,
    pages: int,
    font: str,
    page_numbers: bool = False,
    markers=None,
    cover: Cover | None = None,
) -> Document:
    page, layout = plan_page("practice", page, grid, markers, page_numbers=page_numbers)

    doc = Document(page, grid, font, page_numbers=page_numbers, markers=markers)
    if cover is not None:
        doc.cover_page(cover_commands(cover, page.size[0]))
    draw_grid = doc.define_grid("cbgrid", layout)
    cells = [cell_record(layout, r, c) for r in range(layout.rows) for c in range(layout.columns)]
    for _ in range(pages):
        doc.overlay_page([draw_grid], record=page_record(layout, cells))
    return doc
