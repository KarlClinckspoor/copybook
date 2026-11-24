"""Grid geometry: how many cells fit on a page and where they go.

Coordinates are millimetres from the top-left corner of the page, with y
growing downwards.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

from copybook import CopybookError
from copybook.settings import GridSettings, PageSettings

_EPS = 1e-9


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class Grid:
    """A block of square cells; rows may carry a label band above them."""

    cell: float
    columns: int
    rows: int
    x0: float
    y0: float
    band: float = 0.0  # label band height above every row (0 = cells packed tightly)

    @property
    def width(self) -> float:
        return self.columns * self.cell

    @property
    def row_pitch(self) -> float:
        return self.band + self.cell

    @property
    def height(self) -> float:
        return self.rows * self.row_pitch

    @property
    def cells_per_page(self) -> int:
        return self.columns * self.rows

    def row_top(self, row: int) -> float:
        """Top edge of the cells in ``row`` (below its band)."""
        return self.y0 + row * self.row_pitch + self.band

    def cell_origin(self, row: int, col: int) -> tuple[float, float]:
        return self.x0 + col * self.cell, self.row_top(row)

    def cell_center(self, row: int, col: int) -> tuple[float, float]:
        x, y = self.cell_origin(row, col)
        return x + self.cell / 2, y + self.cell / 2

    def cell_at(self, index: int) -> tuple[int, int]:
        """(row, col) of the index-th cell, filling rows left to right."""
        return divmod(index, self.columns)


def content_area(page: PageSettings, header: bool = True, footer: bool = True) -> Rect:
    """The page minus its border and, optionally, the header and footer bands."""
    width, height = page.size
    top = page.border + (page.header if header else 0.0)
    bottom = page.border + (page.footer if footer else 0.0)
    area = Rect(page.border, top, width - 2 * page.border, height - top - bottom)
    if area.width <= 0 or area.height <= 0:
        raise CopybookError("Border, header and footer leave no room for the grid")
    return area


def fit_grid(area: Rect, grid: GridSettings, band: float = 0.0) -> Grid:
    """Fit as many cells as possible into ``area`` and centre the block.

    ``exact`` keeps the requested cell size; ``fill`` keeps the same number of
    rows and columns but enlarges the cells (up to the maximum size) so the
    block uses the available space.
    """
    cell = grid.cell
    columns = math.floor(area.width / cell + _EPS)
    rows = math.floor(area.height / (cell + band) + _EPS)
    if columns < 1 or rows < 1:
        raise CopybookError(
            f"A {cell} mm cell does not fit in the {area.width:.1f} x {area.height:.1f} mm grid area"
        )

    if grid.fit == "fill":
        cell = min(area.width / columns, area.height / rows - band, grid.MAX_CELL)

    block = Grid(cell=cell, columns=columns, rows=rows, x0=0.0, y0=0.0, band=band)
    return Grid(
        cell=cell,
        columns=columns,
        rows=rows,
        x0=area.x + (area.width - block.width) / 2,
        y0=area.y + (area.height - block.height) / 2,
        band=band,
    )


Shape = tuple  # ("line" | "rect", x1, y1, x2, y2)


@dataclass
class GridShapes:
    frame: list[Shape] = field(default_factory=list)  # outline of the grid (or of each row strip)
    lines: list[Shape] = field(default_factory=list)  # lines between cells
    guides: list[Shape] = field(default_factory=list)  # dashed centre cross and diagonals
    boxes: list[Shape] = field(default_factory=list)  # hui inner boxes


def grid_shapes(grid: Grid, style: GridSettings) -> GridShapes:
    """Every line of the empty grid, in mm. Used by the PDF writer and the GUI preview.

    Shared edges appear once. With a label band, every row is a separate strip.
    """
    c = grid.cell
    left, right = grid.x0, grid.x0 + grid.width
    blocks = (
        [(grid.row_top(0), grid.rows)]
        if grid.band == 0
        else [(grid.row_top(r), 1) for r in range(grid.rows)]
    )
    out = GridShapes()
    pattern = style.pattern

    for top, nrows in blocks:
        bottom = top + nrows * c
        out.frame.append(("rect", left, top, right, bottom))
        out.lines += [("line", left + i * c, top, left + i * c, bottom) for i in range(1, grid.columns)]
        out.lines += [("line", left, top + j * c, right, top + j * c) for j in range(1, nrows)]

        if pattern == "blank":
            continue

        # Centre cross: one continuous line per column and per row.
        out.guides += [("line", left + (i + 0.5) * c, top, left + (i + 0.5) * c, bottom) for i in range(grid.columns)]
        out.guides += [("line", left, top + (j + 0.5) * c, right, top + (j + 0.5) * c) for j in range(nrows)]

        for j in range(nrows):
            for i in range(grid.columns):
                x, y = left + i * c, top + j * c
                if pattern == "mi":
                    out.guides.append(("line", x, y, x + c, y + c))
                    out.guides.append(("line", x, y + c, x + c, y))
                elif pattern == "hui":
                    inset = c * (1 - style.hui_scale) / 2
                    out.boxes.append(("rect", x + inset, y + inset, x + c - inset, y + c - inset))
                elif pattern == "hui-tall":
                    dx = c * (1 - style.tall_width) / 2
                    dy = c * (1 - style.tall_height) / 2
                    out.boxes.append(("rect", x + dx, y + dy, x + c - dx, y + c - dy))
    return out


def plan_page(
    kind: str,
    page: PageSettings,
    grid: GridSettings,
    markers=None,  # copybook.markers.MarkerLayout
    band: float = 0.0,
    page_numbers: bool = True,
) -> tuple[PageSettings, Grid]:
    """The effective page settings and the grid for a ``practice``, ``dense`` or ``rows`` book."""
    if kind == "practice":
        # No running head on blank sheets; keep the footer band only for page numbers.
        page = replace(page, header=0.0, footer=page.footer if page_numbers else 0.0)
    if markers is not None:
        page = markers.adjust(page)
    return page, fit_grid(content_area(page), grid, band=band if kind == "rows" else 0.0)
