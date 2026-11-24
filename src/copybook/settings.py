"""Plain settings objects shared by the CLI (and later a web front-end).

All lengths are millimetres. Grey levels are given as *ink* percentages:
0 is white (no ink), 100 is solid black. Output is strictly greyscale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from copybook import CopybookError

# A5 is 148.5 mm wide here (exactly half of A4) so two pages tile an A4
# sheet without a gap when imposed as a booklet.
PAPER_SIZES: dict[str, tuple[float, float]] = {
    "a4": (210.0, 297.0),
    "a5": (148.5, 210.0),
    "a6": (105.0, 148.5),
    "b5": (176.0, 250.0),
    "letter": (215.9, 279.4),
}

PATTERNS = ("blank", "tian", "mi", "hui", "hui-tall")
FIT_MODES = ("exact", "fill")
ALIGNMENTS = ("design", "center")
GLYPH_SOURCES = ("strokes", "font")
ORDERS = ("pinyin", "input")
MISSING_POLICIES = ("warn", "skip", "error")


def _check(cond: bool, message: str) -> None:
    if not cond:
        raise CopybookError(message)


def _check_ink(name: str, value: float) -> None:
    _check(0 <= value <= 100, f"{name} must be between 0 and 100 (ink percent), got {value}")


@dataclass
class PageSettings:
    paper: str = "a5"
    landscape: bool = False
    width: float | None = None  # overrides the paper size when both are set
    height: float | None = None
    border: float = 5.0  # minimum blank margin on every side
    header: float = 8.0  # band at the top for the running head
    footer: float = 6.0  # band at the bottom for the page number

    @property
    def size(self) -> tuple[float, float]:
        if self.width and self.height:
            w, h = self.width, self.height
        else:
            _check(self.paper in PAPER_SIZES, f"Unknown paper size {self.paper!r}")
            w, h = PAPER_SIZES[self.paper]
        return (h, w) if self.landscape else (w, h)

    def validate(self) -> None:
        w, h = self.size
        _check(w > 0 and h > 0, "Page size must be positive")
        for name in ("border", "header", "footer"):
            _check(getattr(self, name) >= 0, f"--{name} cannot be negative")
        _check(2 * self.border < min(w, h), "Border is larger than the page")


@dataclass
class GridSettings:
    cell: float = 15.0
    fit: str = "exact"  # exact: keep the cell size; fill: grow cells to use the page
    pattern: str = "mi"
    hui_scale: float = 0.6  # inner square of the hui pattern, as a fraction of the cell
    tall_width: float = 0.5  # inner rectangle of the hui-tall pattern
    tall_height: float = 0.85
    frame_width: float = 0.8  # pt, outline of the whole grid or row
    line_width: float = 0.4  # pt, lines between cells
    guide_width: float = 0.3  # pt, dashed guides inside cells
    guide_ink: float = 45.0
    line_ink: float = 100.0  # frame and cell lines

    MIN_CELL = 5.0
    MAX_CELL = 40.0

    def validate(self) -> None:
        _check(
            self.MIN_CELL <= self.cell <= self.MAX_CELL,
            f"Cell size must be between {self.MIN_CELL} and {self.MAX_CELL} mm, got {self.cell}",
        )
        _check(self.fit in FIT_MODES, f"fit must be one of {FIT_MODES}")
        _check(self.pattern in PATTERNS, f"pattern must be one of {PATTERNS}")
        for name in ("hui_scale", "tall_width", "tall_height"):
            _check(0 < getattr(self, name) < 1, f"{name} must be between 0 and 1")
        _check_ink("guide ink", self.guide_ink)
        _check_ink("line ink", self.line_ink)


@dataclass
class GlyphSettings:
    source: str = "strokes"  # strokes: Make Me a Hanzi outlines; font: typeset with `font`
    font: str = "KaiTi"  # installed font name, or a path to a .ttf/.otf file
    align: str = "design"  # design: the typeface's own placement; center: centre the ink
    scale: float = 0.9  # em square as a fraction of the cell
    shade: bool = False  # dense book: lighten each successive stroke
    shade_step: float = 20.0  # ink lost per stroke when shading
    shade_min_ink: float = 35.0  # the lightest a shaded stroke may get
    trace_ink: float = 18.0  # rows book: tracing copies

    def validate(self) -> None:
        _check(self.source in GLYPH_SOURCES, f"glyph source must be one of {GLYPH_SOURCES}")
        _check(self.align in ALIGNMENTS, f"alignment must be one of {ALIGNMENTS}")
        _check(0.3 <= self.scale <= 1.2, "glyph scale must be between 0.3 and 1.2")
        _check(self.shade_step > 0, "shade step must be positive")
        _check_ink("shade minimum ink", self.shade_min_ink)
        _check_ink("trace ink", self.trace_ink)


@dataclass
class ContentSettings:
    characters: list[str] = field(default_factory=list)
    order: str = "pinyin"  # pinyin, or the order the characters were given in
    missing: str = "warn"  # characters without a reading: warn (keep), skip or error
    index: bool = True
    index_title: str = "索引"
    index_columns: int = 4

    def validate(self) -> None:
        _check(bool(self.characters), "No Chinese characters were given (use --chars or --file)")
        _check(self.order in ORDERS, f"order must be one of {ORDERS}")
        _check(self.missing in MISSING_POLICIES, f"missing policy must be one of {MISSING_POLICIES}")
        _check(1 <= self.index_columns <= 6, "index columns must be between 1 and 6")


@dataclass
class RowsSettings:
    traces: int = 3  # grey tracing copies after the model character
    band: float = 6.0  # label band above each row: reading, stroke count, stroke order
    stroke_order: bool = True

    def validate(self) -> None:
        _check(self.traces >= 0, "traces cannot be negative")
        _check(self.band >= 0, "band cannot be negative")


@dataclass
class MarkerSettings:
    """ArUco page markers and the geometry sidecar for the calligraphy checker."""

    enabled: bool = True
    size: float = 8.0  # marker side, mm (6 x 6 modules incl. border)
    quiet: float = 2.0  # white margin around each marker, mm
    outer_margin: float = 7.0  # marker edge to top, bottom and fore-edge, mm
    gutter_margin: float = 10.0  # marker edge to the fold, mm
    book_qr: bool = True  # cover page with a QR code identifying the book
    book_id: str | None = None  # default: random 8 hex digits per build
    title: str | None = None  # cover title; default depends on the book type

    def validate(self) -> None:
        _check(6 <= self.size <= 12, "marker size must be between 6 and 12 mm")
        _check(0 <= self.quiet <= 10, "marker quiet zone must be between 0 and 10 mm")
        _check(self.outer_margin >= 0 and self.gutter_margin >= 0, "marker margins cannot be negative")
        if self.book_id is not None:
            _check(
                self.book_id.isalnum() and 1 <= len(self.book_id) <= 16,
                "book id must be 1-16 letters or digits",
            )


@dataclass
class OutputSettings:
    output: Path = Path("output/copybook.pdf")
    build_dir: Path = Path("output/build")
    cache_dir: Path = Path("output/cache")
    data_dir: Path = Path("data/makemeahanzi")
    impose: bool = False  # also write an A4 booklet for duplex printing
    sheets_per_signature: int = 8
