"""End-to-end builds. Need XeLaTeX, the KaiTi font and `copybook data`."""

import shutil
from pathlib import Path

import pytest
from pypdf import PdfReader

from copybook.cli import main

DATA = Path("data/makemeahanzi/graphics.sqlite3")

pytestmark = [
    pytest.mark.latex,
    pytest.mark.skipif(shutil.which("xelatex") is None, reason="xelatex not installed"),
]


def run(tmp_path, *args):
    out = tmp_path / "out.pdf"
    assert main([*args, "-o", str(out), "--build-dir", str(tmp_path / "build"), "--cache-dir", str(tmp_path / "cache")]) == 0
    return PdfReader(out)


@pytest.mark.parametrize("pattern", ["blank", "tian", "mi", "hui", "hui-tall"])
def test_practice(tmp_path, pattern):
    assert len(run(tmp_path, "practice", "--pages", "2", "--pattern", pattern).pages) == 3  # cover + 2


@pytest.mark.skipif(not DATA.is_file(), reason="run `copybook data` first")
@pytest.mark.parametrize("kind", ["dense", "rows"])
def test_books(tmp_path, kind):
    reader = run(tmp_path, kind, "--chars", "学习书法永")
    # index page, blank verso so page 1 is a recto, then the character pages
    assert len(reader.pages) >= 3
    assert all(page.get_contents() is not None for page in reader.pages[2:])
