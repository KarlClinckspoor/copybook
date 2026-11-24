# copybook

Printable Chinese calligraphy practice material, typeset with XeLaTeX:

| Command    | Output                                                                                     |
|------------|--------------------------------------------------------------------------------------------|
| `practice` | **(a) Practice sheets**: empty grids in a blank, tian (田), mi (米), hui (回) or tall hui pattern |
| `dense`    | **(b) Dense reference book**: every cell holds a character, sorted by pinyin               |
| `rows`     | **(c) One character per row**: model, grey tracing copies, empty cells; the reading, stroke count and stroke order sit above each row |

The character books include a dictionary-style index (grouped by letter, with page numbers),
a running head with the pinyin range of each page ("ā – cè"), and page numbers.
Everything is greyscale, for printers without colour.

Any output can also be imposed as an A4 booklet for double-sided printing.

**Quick start on Windows:** download `copybook-gui.exe` and sample PDFs from the
[latest release](https://github.com/KarlClinckspoor/copybook/releases/latest), then read the
[manual](docs/manual.md). More command recipes are in [`examples/`](examples/README.md).

## Requirements

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- XeLaTeX (TeX Live, MiKTeX or MacTeX) with `xeCJK`, `tikz`, `multicol` and `geometry`
- A CJK font. The default is `KaiTi` (楷体, installed with Windows). Pass another installed
  font name, or a `.ttf`/`.otf` path, with `--font`. The font is used for page text and for
  characters that have no stroke data.

## Setup

```bash
uv sync
uv run copybook data
```

`copybook data` downloads [Make Me a Hanzi](https://github.com/skishore/makemeahanzi)
(readings and stroke outlines, about 35 MB) into `data/makemeahanzi/` and converts it to SQLite.

## Usage

```bash
# (a) 16 pages of mi-grid practice sheets, 15 mm cells
uv run copybook practice --pattern mi

# (b) reference book of every character in a file, plus an A4 booklet
uv run copybook dense --file input/learned_chars.txt --impose

# (c) one character per row
uv run copybook rows --chars 永和九年岁在癸丑
```

PDFs go to `output/<command>_<paper>.pdf` unless you pass `-o`. Run any command with
`--help` for every option. The most useful ones:

| Option                               | Meaning                                                                 |
|--------------------------------------|-------------------------------------------------------------------------|
| `--paper a4\|a5\|a6\|b5\|letter`, `--landscape` | Page size (A5 = 148.5 × 210 mm, half of A4)                      |
| `--pattern blank\|tian\|mi\|hui\|hui-tall` | Cell pattern                                                     |
| `--cell 15`, `--fit exact\|fill`     | Cell size in mm; `fill` enlarges cells to use the page                  |
| `--border`, `--header`, `--footer`   | Margin, running-head band and page-number band, in mm                   |
| `--guide-ink 45`                     | Darkness of the dashed guides (0 = white, 100 = black)                  |
| `--chars …`, `--file …`              | Characters to include. Text is filtered to Chinese characters, and files may contain `#` comment lines |
| `--order pinyin\|input`              | Sort by pinyin (then tone, then stroke count), or keep the given order  |
| `--missing warn\|skip\|error`        | What to do with characters that have no reading                         |
| `--glyphs strokes\|font`             | Make Me a Hanzi outlines (default), or typeset with `--font`            |
| `--align design\|center`             | `design` keeps the typeface's own placement (default); `center` centres the ink |
| `--glyph-scale 0.9`                  | Character size as a fraction of the cell                                |
| `--shade-strokes`                    | Dense book: each stroke lighter than the one before (shows the stroke order) |
| `--traces 3`, `--trace-ink 18`       | Rows book: number and darkness of the tracing copies                    |
| `--impose`, `--sheets-per-signature 8` | Also write `<output>_booklet.pdf`                                     |

Glyph PDFs are cached in `output/cache/glyphs`. Cache file names hash the drawing itself,
so changing a setting never reuses a stale glyph.

### Desktop app

```bash
uv run copybook-gui
```

A tkinter window with every option on tabs (Content, Page & grid, Glyphs, Markers, Output)
and a live preview of the page on the right. The preview draws the real geometry: the grid,
markers, running head and page number, and the Make Me a Hanzi outlines at their printed size and grey.
Only text fonts differ from the PDF. Switch between right- and left-hand pages and step through the
book's pages.

- **Build PDF** runs the `copybook` command line in a subprocess, so the result is identical to it.
  The log shows the exact command, and **Copy command** puts it on the clipboard.
- **Download data** runs `copybook data`.
- **Stop** kills the build, including XeLaTeX.
- Settings are kept in `~/.copybook-gui.json`.

To make a stand-alone `dist/copybook-gui.exe` (no Python needed):

```bash
uv run python tools/build_exe.py
```

The exe contains the whole package. It still needs XeLaTeX, the CJK font and a working folder for
`data/` and `output/`. It uses the folder it sits in, or a parent of it, that has
`data/makemeahanzi/`; otherwise it asks once.

### Page markers for the calligraphy checker

By default every page carries four ArUco markers (`DICT_4X4_1000`), one per corner, and each build writes
`<output>.<book_id>.geometry.json` next to the PDF. The sidecar gives the position in mm of every
marker and cell (and, in character books, which character is in each cell or should be written there).
A cover page holds a QR code with `cc1;<book_id>;<pattern>;<cell mm>`, so the checker can load the right sidecar.

- Marker IDs: `4 × (page_index mod 250) + corner`, corners 0–3 = top-left, top-right, bottom-right, bottom-left.
  `page_index` is the 0-based physical page; even pages are rectos (fold on the left).
- Markers are 8 mm with a 2 mm white quiet zone. They sit ≥ 7 mm from the outer edges and ≥ 10 mm from the fold.
  The grid shrinks to make room, which with 15 mm cells on A5 costs one row.
- The running head and page number sit between the markers.
- Options: `--no-markers` (exactly the plain output, no sidecar or cover), `--marker-size`, `--marker-quiet`,
  `--marker-outer-margin`, `--marker-gutter-margin`, `--no-book-qr`, `--book-id`, `--title`, and `--line-ink`
  to make the cell lines fainter.
- Print with toner saving and "fit to page" off.

`tools/make_aruco_table.py` regenerates the packaged marker table from OpenCV.

### Printing a booklet

`--impose` (or `copybook impose some.pdf`) places two A5 pages on each A4 landscape side,
in signatures of 8 sheets (32 pages). Print double-sided, flipping on the short edge.
Then fold each signature and stack the signatures in order. The last signature is padded with blank pages.

### Characters you have studied

```bash
uv run copybook learned-chars input/learning_progress_export.json \
    --exclude input/excluded_chars.txt -o input/learned_chars.txt
```

This reads a flashcard progress export (a JSON object whose keys are the studied items),
ignores `_reverse` cards and keeps each Chinese character once, in code-point order.

## Project layout

```
src/copybook/
  cli.py          command-line interface
  gui.py          tkinter desktop app with live preview
  build.py        settings in, PDF out
  settings.py     page / grid / glyph / content settings (shared with a future web UI)
  data.py         Make Me a Hanzi download, SQLite conversion and queries
  hanzi.py        recognising and collecting characters
  pinyin.py       tone parsing, display and collation
  entries.py      character lookup, ordering, missing-reading policy
  geometry.py     fitting and centring grids on the page
  glyphs.py       stroke outlines to small greyscale PDFs (no native libraries)
  tex.py          grid drawing, document assembly, XeLaTeX compilation
  imposition.py   A4 booklet imposition
  markers.py      ArUco markers, book QR code, geometry sidecar
  learned.py      progress export to character list
  layouts/        practice, dense and rows layouts, plus the shared index
tests/
docs/manual.md    user manual
examples/         example commands and a sample text
input/            your character lists
```

## Development

```bash
uv run pytest                 # everything, including real XeLaTeX builds
uv run pytest -m "not latex"  # fast unit tests only
```

`tests/test_markers.py` renders pages at 300 dpi and checks them with OpenCV's ArUco detector
(it needs `pdftoppm`, which ships with MiKTeX and Poppler).

## Data and licences

The code is released under the [MIT licence](LICENSE).

Make Me a Hanzi data is derived from Arphic PL fonts and released under the Arphic Public License
(graphics) and LGPL (dictionary). See the upstream repository. Fonts such as KaiTi are licensed
separately and are not part of this repository.
