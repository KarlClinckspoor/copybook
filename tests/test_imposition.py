from pypdf import PdfReader, PdfWriter

from copybook.glyphs import minimal_pdf
from copybook.imposition import impose, signature_sides


def test_single_sheet_order():
    assert list(signature_sides(4, 1)) == [(4, 1), (2, 3)]


def test_two_sheet_signature():
    assert list(signature_sides(8, 2)) == [(8, 1), (2, 7), (6, 3), (4, 5)]


def test_padding_to_full_signature():
    sides = list(signature_sides(5, 1))
    assert len(sides) == 4  # two sheets of four pages
    assert sides[2] == (8, 5)


def test_every_page_used_once():
    used = sorted(n for side in signature_sides(32, 8) for n in side)
    assert used == list(range(1, 33))


def test_imposed_sheets_have_content(tmp_path):
    # Regression: pages were transformed then merged with merge_page, which
    # produced completely blank sheets with pypdf 6.
    page = tmp_path / "page.pdf"
    w, h = 148.5 / 25.4 * 72, 210 / 25.4 * 72
    page.write_bytes(minimal_pdf(w / 0.1, h / 0.1, "0 g 0 0 100 100 re f"))
    writer = PdfWriter()
    for _ in range(4):
        writer.append(str(page))
    source = tmp_path / "source.pdf"
    writer.write(source)

    out = impose(source, tmp_path / "booklet.pdf", sheets_per_signature=1)
    pages = PdfReader(out).pages
    assert len(pages) == 2
    for sheet in pages:
        assert sheet.get_contents() is not None
        assert len(sheet.get_contents().get_data()) > 0
