import pytest

from copybook import CopybookError
from copybook.geometry import Rect, content_area, fit_grid
from copybook.settings import GridSettings, PageSettings


def test_content_area_a5():
    area = content_area(PageSettings())
    assert area == Rect(5.0, 13.0, 138.5, 210.0 - 13.0 - 11.0)
    assert content_area(PageSettings(), header=False, footer=False).height == 200.0


def test_exact_grid_is_centred_both_ways():
    area = Rect(5, 5, 138.5, 200)
    grid = fit_grid(area, GridSettings(cell=15))
    assert (grid.columns, grid.rows, grid.cell) == (9, 13, 15)
    # Leftover space is split evenly (it used to all go to the bottom).
    assert grid.x0 - area.x == pytest.approx(area.x + area.width - (grid.x0 + grid.width))
    assert grid.y0 - area.y == pytest.approx(area.y + area.height - (grid.y0 + grid.height))


def test_fill_grows_cells():
    grid = fit_grid(Rect(0, 0, 100, 100), GridSettings(cell=15, fit="fill"))
    assert (grid.columns, grid.rows) == (6, 6)
    assert grid.cell == pytest.approx(100 / 6)


def test_band_rows():
    grid = fit_grid(Rect(0, 0, 150, 100), GridSettings(cell=15), band=5)
    assert grid.rows == 5  # 100 / (15 + 5)
    assert grid.row_top(0) == pytest.approx(5)  # cells start below the first band
    assert grid.cell_center(1, 0) == pytest.approx((7.5, 20 + 5 + 7.5))


def test_cell_too_big():
    with pytest.raises(CopybookError):
        fit_grid(Rect(0, 0, 10, 10), GridSettings(cell=15))


def test_paper_sizes():
    assert PageSettings(paper="a4").size == (210.0, 297.0)
    assert PageSettings(paper="a4", landscape=True).size == (297.0, 210.0)
    assert PageSettings(width=100, height=120).size == (100, 120)
