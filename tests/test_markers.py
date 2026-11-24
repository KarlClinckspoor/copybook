"""Page markers, book QR and geometry sidecar (acceptance tests from the page marker spec).

Rendered checks need XeLaTeX, pdftoppm and OpenCV; they render pages at 300 dpi
and detect markers with ``cv2.aruco.ArucoDetector``.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from copybook.cli import main
from copybook.markers import MarkerLayout, marker_id, patterns, side
from copybook.settings import GridSettings, MarkerSettings, PageSettings

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

DPI = 300
PX_PER_MM = DPI / 25.4
DATA = Path("data/makemeahanzi/graphics.sqlite3")
_missing_tools = shutil.which("xelatex") is None or shutil.which("pdftoppm") is None


def needs_latex(test):
    test = pytest.mark.skipif(_missing_tools, reason="needs xelatex and pdftoppm")(test)
    return pytest.mark.latex(test)


# ---------------------------------------------------------------------------
# Unit checks (no LaTeX)
# ---------------------------------------------------------------------------


def test_table_matches_opencv():
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_1000)
    for mid in (0, 1, 17, 500, 999):
        image = dictionary.generateImageMarker(mid, 6)
        assert "".join("1" if v > 127 else "0" for v in image[1:5, 1:5].flatten()) == patterns()[mid]


def test_marker_ids():
    assert [marker_id(4, c) for c in range(4)] == [16, 17, 18, 19]
    assert marker_id(250, 0) == 0 and marker_id(249, 3) == 999
    assert side(0) == "recto" and side(1) == "verso"


def test_gutter_side_per_page():
    layout = MarkerLayout(MarkerSettings(), (148.5, 210.0))
    recto, verso = layout.boxes("recto"), layout.boxes("verso")
    assert recto[0].x == 10 and recto[1].x + 8 == 148.5 - 7  # fold on the left
    assert verso[0].x == 7 and verso[1].x + 8 == 148.5 - 10  # fold on the right
    assert recto[0].y == 7 and recto[3].y + 8 == 210 - 7


def _overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


@pytest.mark.parametrize("pattern", ["blank", "tian", "mi", "hui", "hui-tall"])
@pytest.mark.parametrize("cell", [7, 15, 25])
def test_no_overlap(pattern, cell):
    from copybook.layouts.practice import practice_document

    settings = MarkerSettings()
    page = PageSettings()
    layout = MarkerLayout(settings, page.size)
    doc = practice_document(page, GridSettings(cell=cell, pattern=pattern), 2, "KaiTi", True, layout)
    (x0, y0), _, (x1, y1), _ = doc.grid_pages[0]["grid_area"]
    grid = (x0 - 0.2, y0 - 0.2, x1 + 0.2, y1 + 0.2)  # frame line width
    left, right = layout.text_span()
    for page_side in ("recto", "verso"):
        for box in layout.boxes(page_side):
            q = settings.quiet
            quiet = (box.x - q, box.y - q, box.x + box.size + q, box.y + box.size + q)
            assert not _overlaps(grid, quiet)
            # header and page number boxes (generous: 40 mm wide, 5 mm high) between the markers
            for y in (layout.header_y, layout.footer_y):
                text = (148.5 / 2 - 20, y - 2.5, 148.5 / 2 + 20, y + 2.5)
                assert not _overlaps(text, quiet) and not _overlaps(text, grid)
    assert left < 148.5 / 2 - 20 and right > 148.5 / 2 + 20


# ---------------------------------------------------------------------------
# Rendered checks
# ---------------------------------------------------------------------------


def _render(pdf: Path, page: int, out_dir: Path):
    prefix = out_dir / f"{pdf.stem}-{page}"
    subprocess.run(
        ["pdftoppm", "-r", str(DPI), "-gray", "-png", "-singlefile", "-f", str(page + 1), "-l", str(page + 1), str(pdf), str(prefix)],
        check=True,
    )
    return cv2.imread(str(prefix) + ".png", cv2.IMREAD_GRAYSCALE)


def _detect(image):
    detector = cv2.aruco.ArucoDetector(
        cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_1000), cv2.aruco.DetectorParameters()
    )
    corners, ids, _ = detector.detectMarkers(image)
    if ids is None:
        return {}
    # pixel centres -> mm (pixel i spans [i, i+1) / PX_PER_MM)
    return {int(i): (c.reshape(4, 2) + 0.5) / PX_PER_MM for i, c in zip(ids.flatten(), corners)}


def _build(tmp_path, *args):
    out = tmp_path / "book.pdf"
    argv = [*args, "-o", str(out), "--build-dir", str(tmp_path / "build"), "--cache-dir", str(tmp_path / "cache"), "--book-id", "abc12345"]
    assert main(argv) == 0
    sidecar = json.loads((tmp_path / "book.abc12345.geometry.json").read_text(encoding="utf-8"))
    return out, sidecar


@pytest.fixture(scope="module")
def practice_book(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("practice")
    return tmp, *_build(tmp, "practice", "--pages", "3", "--pattern", "mi", "--impose", "--sheets-per-signature", "1")


@needs_latex
def test_every_page_has_four_correct_markers(practice_book):
    tmp, pdf, sidecar = practice_book
    assert len(sidecar["pages"]) == 4  # cover + 3 sheets
    for record in sidecar["pages"]:
        found = _detect(_render(pdf, record["page_index"], tmp))
        expected = {m["id"]: m for m in record["markers"]}
        assert set(found) == set(expected) == {marker_id(record["page_index"], c) for c in range(4)}
        for mid, corners in found.items():
            assert np.abs(corners - np.array(expected[mid]["corners"])).max() < 0.15


@needs_latex
def test_cells_land_on_grid_lines(practice_book):
    tmp, pdf, sidecar = practice_book
    record = sidecar["pages"][1]
    image = _render(pdf, 1, tmp)
    found = _detect(image)
    src = np.array([c for m in record["markers"] for c in m["corners"]], dtype=np.float32)
    dst = np.array([found[m["id"]] for m in record["markers"]], dtype=np.float32).reshape(-1, 2) * PX_PER_MM - 0.5
    homography, _ = cv2.findHomography(src, dst)
    radius = int(round(0.2 * PX_PER_MM)) + 1
    for cell in record["cells"]:
        x, y, s = cell["x"], cell["y"], cell["size"]
        points = np.array([[[x, y]], [[x + s, y]], [[x + s, y + s]], [[x, y + s]]], dtype=np.float32)
        for px, py in cv2.perspectiveTransform(points, homography).reshape(-1, 2):
            window = image[int(py) - radius : int(py) + radius + 1, int(px) - radius : int(px) + radius + 1]
            assert window.min() < 100, (cell["row"], cell["col"])


@needs_latex
def test_quiet_zones_are_white(practice_book):
    tmp, pdf, sidecar = practice_book
    margin = 0.25  # mm of anti-aliasing allowed next to the marker and at the zone edge
    for record in sidecar["pages"]:
        image = _render(pdf, record["page_index"], tmp)
        q = sidecar["marker"]["quiet_zone_mm"]
        for m in record["markers"]:
            (x0, y0), _, (x1, y1), _ = m["corners"]

            def px(v):
                return int(round(v * PX_PER_MM))

            # the ring between the marker (plus margin) and the quiet-zone edge (minus margin)
            top, bottom = px(y0 - q + margin), px(y1 + q - margin)
            left, right = px(x0 - q + margin), px(x1 + q - margin)
            ring = image[top:bottom, left:right].copy()
            ring[px(y0 - margin) - top : px(y1 + margin) - top, px(x0 - margin) - left : px(x1 + margin) - left] = 255
            assert ring.min() > 230, (record["page_index"], m["corner"])


@needs_latex
def test_imposed_sheets(practice_book):
    tmp, pdf, sidecar = practice_book
    booklet = pdf.with_name("book_booklet.pdf")
    width_mm, fold = 297.0, 148.5
    for sheet in range(2):  # 4 pages, 1 sheet per signature: front and back
        image = _render(booklet, sheet, tmp)
        found = _detect(image)
        assert len(found) == 8
        for corners in found.values():
            xs, ys = corners[:, 0], corners[:, 1]
            assert xs.min() >= 5 and ys.min() >= 5 and xs.max() <= width_mm - 5 and ys.max() <= 210 - 5
            distance_to_fold = min(abs(xs.min() - fold), abs(xs.max() - fold))
            assert distance_to_fold >= 10 - 0.15


@needs_latex
def test_book_qr(practice_book):
    tmp, pdf, sidecar = practice_book
    text, _, _ = cv2.QRCodeDetector().detectAndDecode(_render(pdf, 0, tmp))
    assert text == "cc1;abc12345;mi;15"
    assert sidecar["pages"][0]["kind"] == "cover"


@needs_latex
def test_no_markers(tmp_path):
    out = tmp_path / "plain.pdf"
    assert main(["practice", "--pages", "2", "--no-markers", "-o", str(out), "--build-dir", str(tmp_path / "b")]) == 0
    assert not list(tmp_path.glob("*.geometry.json"))
    tex = (tmp_path / "b" / "main.tex").read_text(encoding="utf-8")
    assert "cbmarker" not in tex and "aruco" not in tex
    assert _detect(_render(out, 0, tmp_path)) == {}


@needs_latex
@pytest.mark.skipif(not DATA.is_file(), reason="run `copybook data` first")
def test_reference_book_sidecar(tmp_path):
    pdf, sidecar = _build(tmp_path, "rows", "--chars", "永和九年")
    grid_pages = [p for p in sidecar["pages"] if p["kind"] == "grid"]
    cells = grid_pages[0]["cells"]
    models = [c for c in cells if c["col"] == 0 and c["char"]]
    assert {c["char"] for c in models} == set("永和九年")
    blanks = [c for c in cells if c["char"] is None and c["target"]]
    assert blanks and all(c["target"] in "永和九年" for c in blanks)
    assert sidecar["glyph"]["align"] == "design"
    # every page, including cover, index and blank verso, carries its markers
    for record in sidecar["pages"]:
        assert len(_detect(_render(pdf, record["page_index"], tmp_path))) == 4
