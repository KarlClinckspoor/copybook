"""Booklet imposition: two pages side by side per sheet side, in signatures.

Print the result double-sided (flip on the short edge), fold each signature
in half and nest/sew the signatures in order.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from pypdf import PageObject, PdfReader, PdfWriter, Transformation

from copybook import CopybookError

MM_TO_PT = 72.0 / 25.4


def signature_sides(page_count: int, sheets_per_signature: int) -> Iterator[tuple[int, int]]:
    """Yield (left, right) 1-based page numbers for every printed side, front then back.

    Page numbers above ``page_count`` are blanks used to complete the last signature.

    >>> list(signature_sides(4, 1))
    [(4, 1), (2, 3)]
    """
    if sheets_per_signature < 1:
        raise CopybookError("sheets per signature must be at least 1")
    per_signature = 4 * sheets_per_signature
    padded = -(-page_count // per_signature) * per_signature

    for start in range(0, padded, per_signature):
        last = start + per_signature
        for sheet in range(sheets_per_signature):
            yield last - 2 * sheet, start + 2 * sheet + 1  # front
            yield start + 2 * sheet + 2, last - 2 * sheet - 1  # back


def impose(
    source: Path,
    destination: Path,
    sheets_per_signature: int = 8,
    sheet_size: tuple[float, float] = (297.0, 210.0),
) -> Path:
    """Impose ``source`` onto landscape sheets (A4 by default) and write ``destination``."""
    source = Path(source)
    if not source.is_file():
        raise CopybookError(f"PDF not found: {source}")

    reader = PdfReader(source)
    count = len(reader.pages)
    if count == 0:
        raise CopybookError(f"{source} has no pages")

    page_w = float(reader.pages[0].mediabox.width)
    page_h = float(reader.pages[0].mediabox.height)
    sheet_w, sheet_h = sheet_size[0] * MM_TO_PT, sheet_size[1] * MM_TO_PT
    if 2 * page_w > sheet_w + 1 or page_h > sheet_h + 1:
        raise CopybookError("Two pages do not fit side by side on the sheet")

    x_left = (sheet_w - 2 * page_w) / 2
    y = (sheet_h - page_h) / 2

    writer = PdfWriter()
    for left, right in signature_sides(count, sheets_per_signature):
        sheet: PageObject = writer.add_blank_page(width=sheet_w, height=sheet_h)
        for number, x in ((left, x_left), (right, x_left + page_w)):
            if number <= count:
                # merge_transformed_page keeps the content; transforming the
                # source page and then calling merge_page silently drops it
                # with current pypdf versions (blank sheets).
                sheet.merge_transformed_page(reader.pages[number - 1], Transformation().translate(x, y))

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "wb") as f:
        writer.write(f)
    return destination
