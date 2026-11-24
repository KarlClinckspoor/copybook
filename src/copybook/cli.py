"""Command-line interface: ``copybook <command> [options]``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from copybook import CopybookError, __version__
from copybook.settings import (
    ALIGNMENTS,
    FIT_MODES,
    GLYPH_SOURCES,
    MISSING_POLICIES,
    ORDERS,
    PAPER_SIZES,
    PATTERNS,
    ContentSettings,
    GlyphSettings,
    GridSettings,
    MarkerSettings,
    OutputSettings,
    PageSettings,
    RowsSettings,
)

# ---------------------------------------------------------------------------
# Shared option groups
# ---------------------------------------------------------------------------


def _page_options(parser: argparse.ArgumentParser) -> None:
    d = PageSettings()
    g = parser.add_argument_group("page")
    g.add_argument("--paper", choices=sorted(PAPER_SIZES), default=d.paper, help="paper size (default: %(default)s)")
    g.add_argument("--landscape", action="store_true", help="rotate the paper")
    g.add_argument("--page-width", type=float, help="custom page width in mm (with --page-height)")
    g.add_argument("--page-height", type=float, help="custom page height in mm (with --page-width)")
    g.add_argument("--border", type=float, default=d.border, help="minimum margin in mm (default: %(default)s)")
    g.add_argument("--header", type=float, default=d.header, help="running-head band in mm (default: %(default)s)")
    g.add_argument("--footer", type=float, default=d.footer, help="page-number band in mm (default: %(default)s)")


def _grid_options(parser: argparse.ArgumentParser) -> None:
    d = GridSettings()
    g = parser.add_argument_group("grid")
    g.add_argument("--pattern", choices=PATTERNS, default=d.pattern, help="cell pattern (default: %(default)s)")
    g.add_argument("--cell", type=float, default=d.cell, help="cell size in mm (default: %(default)s)")
    g.add_argument(
        "--fit", choices=FIT_MODES, default=d.fit,
        help="exact: keep the cell size; fill: enlarge cells to use the page (default: %(default)s)",
    )
    g.add_argument("--hui-scale", type=float, default=d.hui_scale, help="hui inner square, fraction of the cell")
    g.add_argument("--tall-width", type=float, default=d.tall_width, help="hui-tall inner box width, fraction")
    g.add_argument("--tall-height", type=float, default=d.tall_height, help="hui-tall inner box height, fraction")
    g.add_argument("--guide-ink", type=float, default=d.guide_ink, help="guide darkness, 0-100 (default: %(default)s)")
    g.add_argument("--line-ink", type=float, default=d.line_ink, help="frame and cell line darkness, 0-100 (default: %(default)s)")
    g.add_argument("--frame-width", type=float, default=d.frame_width, help="outer frame line width in pt")
    g.add_argument("--line-width", type=float, default=d.line_width, help="cell line width in pt")
    g.add_argument("--guide-width", type=float, default=d.guide_width, help="guide line width in pt")


def _glyph_options(parser: argparse.ArgumentParser) -> None:
    d = GlyphSettings()
    g = parser.add_argument_group("glyphs")
    g.add_argument(
        "--glyphs", choices=GLYPH_SOURCES, default=d.source,
        help="strokes: Make Me a Hanzi outlines (font used as fallback); font: typeset (default: %(default)s)",
    )
    g.add_argument("--font", default=d.font, help="CJK font name or .ttf/.otf path (default: %(default)s)")
    g.add_argument(
        "--align", choices=ALIGNMENTS, default=d.align,
        help="design: typeface placement; center: centre the ink (default: %(default)s)",
    )
    g.add_argument("--glyph-scale", type=float, default=d.scale, help="em size as a fraction of the cell (default: %(default)s)")
    g.add_argument("--shade-strokes", action="store_true", help="dense book: lighten each successive stroke")
    g.add_argument("--shade-step", type=float, default=d.shade_step, help="ink lost per stroke when shading")
    g.add_argument("--shade-min-ink", type=float, default=d.shade_min_ink, help="lightest shaded stroke, 0-100")


def _content_options(parser: argparse.ArgumentParser) -> None:
    d = ContentSettings()
    g = parser.add_argument_group("characters")
    g.add_argument("--chars", nargs="+", default=[], metavar="TEXT", help="characters or words to include")
    g.add_argument("--file", type=Path, action="append", default=[], help="UTF-8 text file of characters (repeatable)")
    g.add_argument("--keep-duplicates", action="store_true", help="keep repeated characters")
    g.add_argument("--order", choices=ORDERS, default=d.order, help="pinyin, or as given (default: %(default)s)")
    g.add_argument(
        "--missing", choices=MISSING_POLICIES, default=d.missing,
        help="characters without a reading: warn and keep, skip, or error (default: %(default)s)",
    )
    g.add_argument("--no-index", action="store_true", help="leave out the index")
    g.add_argument("--index-title", default=d.index_title)
    g.add_argument("--index-columns", type=int, default=d.index_columns)


def _marker_options(parser: argparse.ArgumentParser) -> None:
    d = MarkerSettings()
    g = parser.add_argument_group("page markers (for the calligraphy checker)")
    g.add_argument("--no-markers", action="store_true", help="no ArUco markers, cover or geometry sidecar")
    g.add_argument("--marker-size", type=float, default=d.size, help="marker side in mm (default: %(default)s)")
    g.add_argument("--marker-quiet", type=float, default=d.quiet, help="white margin around markers in mm (default: %(default)s)")
    g.add_argument("--marker-outer-margin", type=float, default=d.outer_margin, help="marker to outer page edges in mm")
    g.add_argument("--marker-gutter-margin", type=float, default=d.gutter_margin, help="marker to the fold in mm")
    g.add_argument("--no-book-qr", action="store_true", help="no cover page with the book QR code")
    g.add_argument("--book-id", help="fixed book id instead of a random one")
    g.add_argument("--title", help="cover title")


def _output_options(parser: argparse.ArgumentParser, command: str) -> None:
    g = parser.add_argument_group("output")
    g.add_argument("-o", "--output", type=Path, help=f"PDF to write (default: output/{command}_<paper>.pdf)")
    g.add_argument("--build-dir", type=Path, default=Path("output/build") / command, help="LaTeX working directory")
    g.add_argument("--cache-dir", type=Path, default=Path("output/cache"), help="glyph cache directory")
    g.add_argument("--data-dir", type=Path, default=Path("data/makemeahanzi"), help="Make Me a Hanzi databases")
    g.add_argument("--impose", action="store_true", help="also write an A4 booklet (<output>_booklet.pdf)")
    g.add_argument("--sheets-per-signature", type=int, default=8, help="sheets folded together (default: %(default)s)")


# ---------------------------------------------------------------------------
# Settings from arguments
# ---------------------------------------------------------------------------


def _page(a) -> PageSettings:
    return PageSettings(
        paper=a.paper, landscape=a.landscape, width=a.page_width, height=a.page_height,
        border=a.border, header=a.header, footer=a.footer,
    )


def _grid(a) -> GridSettings:
    return GridSettings(
        cell=a.cell, fit=a.fit, pattern=a.pattern, hui_scale=a.hui_scale,
        tall_width=a.tall_width, tall_height=a.tall_height, guide_ink=a.guide_ink, line_ink=a.line_ink,
        frame_width=a.frame_width, line_width=a.line_width, guide_width=a.guide_width,
    )


def _markers(a) -> MarkerSettings:
    return MarkerSettings(
        enabled=not a.no_markers, size=a.marker_size, quiet=a.marker_quiet,
        outer_margin=a.marker_outer_margin, gutter_margin=a.marker_gutter_margin,
        book_qr=not a.no_book_qr, book_id=a.book_id, title=a.title,
    )


def _glyphs(a) -> GlyphSettings:
    return GlyphSettings(
        source=a.glyphs, font=a.font, align=a.align, scale=a.glyph_scale, shade=a.shade_strokes,
        shade_step=a.shade_step, shade_min_ink=a.shade_min_ink,
        trace_ink=getattr(a, "trace_ink", GlyphSettings.trace_ink),
    )


def _content(a) -> ContentSettings:
    from copybook.hanzi import collect_characters

    return ContentSettings(
        characters=collect_characters(a.chars, a.file, a.keep_duplicates),
        order=a.order, missing=a.missing, index=not a.no_index,
        index_title=a.index_title, index_columns=a.index_columns,
    )


def _output(a, command: str) -> OutputSettings:
    paper = "custom" if a.page_width and a.page_height else a.paper
    return OutputSettings(
        output=a.output or Path("output") / f"{command}_{paper}.pdf",
        build_dir=a.build_dir, cache_dir=a.cache_dir, data_dir=a.data_dir,
        impose=a.impose, sheets_per_signature=a.sheets_per_signature,
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def _report(paths: list[Path]) -> int:
    for path in paths:
        print(f"Wrote {path}")
    return 0


def cmd_data(a) -> int:
    from copybook.data import prepare

    prepare(a.data_dir, force_download=a.force_download, force_build=a.force_build)
    return 0


def cmd_practice(a) -> int:
    from copybook.build import build_practice

    return _report(
        build_practice(_page(a), _grid(a), _output(a, "practice"), a.pages, a.page_numbers, markers=_markers(a))
    )


def cmd_book(a) -> int:
    from copybook.build import build_book

    rows = None
    if a.command == "rows":
        rows = RowsSettings(traces=a.traces, band=a.band, stroke_order=not a.no_stroke_order)
    return _report(
        build_book(a.command, _page(a), _grid(a), _glyphs(a), _content(a), _output(a, a.command), rows, _markers(a))
    )


def cmd_impose(a) -> int:
    from copybook.imposition import impose

    output = a.output or a.input.with_name(f"{a.input.stem}_booklet.pdf")
    return _report([impose(a.input, output, a.sheets_per_signature)])


def cmd_learned(a) -> int:
    from copybook.hanzi import read_character_file
    from copybook.learned import learned_characters

    exclude = read_character_file(a.exclude) if a.exclude else ""
    chars = learned_characters(a.export, exclude)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text("".join(chars) + "\n", encoding="utf-8")
    print(f"Wrote {len(chars)} characters to {a.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="copybook", description=__doc__)
    parser.add_argument("--version", action="version", version=f"copybook {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    p = sub.add_parser("data", help="download Make Me a Hanzi and build the databases")
    p.add_argument("--data-dir", type=Path, default=Path("data/makemeahanzi"))
    p.add_argument("--force-download", action="store_true")
    p.add_argument("--force-build", action="store_true")
    p.set_defaults(func=cmd_data)

    p = sub.add_parser("practice", help="(a) blank practice sheets")
    p.add_argument("--pages", type=int, default=16, help="number of pages (default: %(default)s)")
    p.add_argument("--page-numbers", action="store_true", help="print page numbers")
    _page_options(p)
    _grid_options(p)
    _marker_options(p)
    _output_options(p, "practice")
    p.set_defaults(func=cmd_practice)

    p = sub.add_parser("dense", help="(b) dense reference book, characters sorted by pinyin")
    _content_options(p)
    _page_options(p)
    _grid_options(p)
    _glyph_options(p)
    _marker_options(p)
    _output_options(p, "dense")
    p.set_defaults(func=cmd_book)

    p = sub.add_parser("rows", help="(c) one character per row: model, tracing copies, practice")
    _content_options(p)
    rg = p.add_argument_group("rows")
    rd = RowsSettings()
    rg.add_argument("--traces", type=int, default=rd.traces, help="grey tracing copies (default: %(default)s)")
    rg.add_argument("--trace-ink", type=float, default=GlyphSettings.trace_ink, help="tracing copy darkness, 0-100")
    rg.add_argument("--band", type=float, default=rd.band, help="label band above each row in mm (0 = none)")
    rg.add_argument("--no-stroke-order", action="store_true", help="leave out the stroke-order strip")
    _page_options(p)
    _grid_options(p)
    _glyph_options(p)
    _marker_options(p)
    _output_options(p, "rows")
    p.set_defaults(func=cmd_book)

    p = sub.add_parser("impose", help="impose an existing A5 PDF as an A4 booklet")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path)
    p.add_argument("--sheets-per-signature", type=int, default=8)
    p.set_defaults(func=cmd_impose)

    p = sub.add_parser("learned-chars", help="extract studied characters from a progress export")
    p.add_argument("export", type=Path, help="JSON progress export")
    p.add_argument("-o", "--output", type=Path, default=Path("input/learned_chars.txt"))
    p.add_argument("--exclude", type=Path, help="file of characters to leave out")
    p.set_defaults(func=cmd_learned)

    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except CopybookError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
