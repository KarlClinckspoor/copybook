"""Desktop front-end for copybook (standard library only: tkinter).

  uv run copybook-gui

Set every option on tabs, see the page update live on the right, then build.
Each build runs the ``copybook`` command line in a subprocess, so the PDF is
identical to the CLI's; the equivalent command is printed in the log and can
be copied. Settings are remembered in ``~/.copybook-gui.json``.

The preview is drawn from the same geometry code that writes the PDF (grid,
markers, header and footer positions, and the Make Me a Hanzi outlines), so
what you see is what XeLaTeX will print, except for text fonts.
"""

from __future__ import annotations

import json
import math
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from dataclasses import fields
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont
from tkinter.scrolledtext import ScrolledText

from copybook import CopybookError
from copybook.geometry import Grid, grid_shapes, plan_page
from copybook.glyphs import EM, ink_to_hex, outline_polygons, placement
from copybook.hanzi import collect_characters
from copybook.markers import MODULES, MarkerLayout, marker_id, patterns
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
    PageSettings,
    RowsSettings,
)

SETTINGS_FILE = Path.home() / ".copybook-gui.json"
WIN = sys.platform == "win32"
_NOWINDOW = 0x08000000 if WIN else 0  # CREATE_NO_WINDOW
# Frozen by PyInstaller (tools/build_exe.py): the exe carries copybook itself and runs the
# command line as "copybook-gui.exe --run-cli <args>" so builds stay separate processes.
FROZEN = getattr(sys, "frozen", False)
PY = [sys.executable, "--run-cli"] if FROZEN else [sys.executable, "-m", "copybook"]
KINDS = ("practice", "dense", "rows")
PT = 25.4 / 72  # mm per point


# ---------------------------------------------------------------------------
# Options: one table drives the widgets, the saved settings and the command line
# ---------------------------------------------------------------------------


def _d(cls, name):
    return {f.name: f.default for f in fields(cls)}[name]


# key, CLI flag, type, default, commands that accept it
# types: str, num, int, flag (store_true), noflag (on by default; the flag turns it off)
OPTIONS: list[tuple[str, str, str, object, tuple[str, ...]]] = [
    ("pages", "--pages", "int", 16, ("practice",)),
    ("page_numbers", "--page-numbers", "flag", False, ("practice",)),
    ("chars", "--chars", "str", "", ("dense", "rows")),
    ("keep_duplicates", "--keep-duplicates", "flag", False, ("dense", "rows")),
    ("order", "--order", "str", _d(ContentSettings, "order"), ("dense", "rows")),
    ("missing", "--missing", "str", _d(ContentSettings, "missing"), ("dense", "rows")),
    ("index", "--no-index", "noflag", True, ("dense", "rows")),
    ("index_title", "--index-title", "str", _d(ContentSettings, "index_title"), ("dense", "rows")),
    ("index_columns", "--index-columns", "int", _d(ContentSettings, "index_columns"), ("dense", "rows")),
    ("traces", "--traces", "int", _d(RowsSettings, "traces"), ("rows",)),
    ("trace_ink", "--trace-ink", "num", _d(GlyphSettings, "trace_ink"), ("rows",)),
    ("band", "--band", "num", _d(RowsSettings, "band"), ("rows",)),
    ("stroke_order", "--no-stroke-order", "noflag", True, ("rows",)),
    ("paper", "--paper", "str", _d(PageSettings, "paper"), KINDS),
    ("landscape", "--landscape", "flag", False, KINDS),
    ("page_width", "--page-width", "num", "", KINDS),
    ("page_height", "--page-height", "num", "", KINDS),
    ("border", "--border", "num", _d(PageSettings, "border"), KINDS),
    ("header", "--header", "num", _d(PageSettings, "header"), KINDS),
    ("footer", "--footer", "num", _d(PageSettings, "footer"), KINDS),
    ("pattern", "--pattern", "str", _d(GridSettings, "pattern"), KINDS),
    ("cell", "--cell", "num", _d(GridSettings, "cell"), KINDS),
    ("fit", "--fit", "str", _d(GridSettings, "fit"), KINDS),
    ("hui_scale", "--hui-scale", "num", _d(GridSettings, "hui_scale"), KINDS),
    ("tall_width", "--tall-width", "num", _d(GridSettings, "tall_width"), KINDS),
    ("tall_height", "--tall-height", "num", _d(GridSettings, "tall_height"), KINDS),
    ("guide_ink", "--guide-ink", "num", _d(GridSettings, "guide_ink"), KINDS),
    ("line_ink", "--line-ink", "num", _d(GridSettings, "line_ink"), KINDS),
    ("frame_width", "--frame-width", "num", _d(GridSettings, "frame_width"), KINDS),
    ("line_width", "--line-width", "num", _d(GridSettings, "line_width"), KINDS),
    ("guide_width", "--guide-width", "num", _d(GridSettings, "guide_width"), KINDS),
    ("glyphs", "--glyphs", "str", _d(GlyphSettings, "source"), ("dense", "rows")),
    ("font", "--font", "str", _d(GlyphSettings, "font"), ("dense", "rows")),
    ("align", "--align", "str", _d(GlyphSettings, "align"), ("dense", "rows")),
    ("glyph_scale", "--glyph-scale", "num", _d(GlyphSettings, "scale"), ("dense", "rows")),
    ("shade_strokes", "--shade-strokes", "flag", False, ("dense",)),
    ("shade_step", "--shade-step", "num", _d(GlyphSettings, "shade_step"), ("dense",)),
    ("shade_min_ink", "--shade-min-ink", "num", _d(GlyphSettings, "shade_min_ink"), ("dense",)),
    ("markers", "--no-markers", "noflag", True, KINDS),
    ("marker_size", "--marker-size", "num", _d(MarkerSettings, "size"), KINDS),
    ("marker_quiet", "--marker-quiet", "num", _d(MarkerSettings, "quiet"), KINDS),
    ("marker_outer_margin", "--marker-outer-margin", "num", _d(MarkerSettings, "outer_margin"), KINDS),
    ("marker_gutter_margin", "--marker-gutter-margin", "num", _d(MarkerSettings, "gutter_margin"), KINDS),
    ("book_qr", "--no-book-qr", "noflag", True, KINDS),
    ("book_id", "--book-id", "str", "", KINDS),
    ("title", "--title", "str", "", KINDS),
    ("output", "--output", "str", "", KINDS),
    ("impose", "--impose", "flag", False, KINDS),
    ("sheets_per_signature", "--sheets-per-signature", "int", 8, KINDS),
]
OPTION = {o[0]: o for o in OPTIONS}
GUI_ONLY = {"kind": "dense", "files": [], "open_after": True}


def _same(value: str, default) -> bool:
    if isinstance(default, bool):
        return value == default
    if isinstance(default, (int, float)) and str(value).strip():
        try:
            return float(value) == float(default)
        except ValueError:
            return False
    return str(value).strip() == str(default)


def command_args(values: dict) -> list[str]:
    """The ``copybook`` arguments for these GUI values (options left at their default are omitted)."""
    kind = values["kind"]
    args = [kind]
    if kind != "practice":
        for path in values.get("files", []):
            args += ["--file", rel(Path(path))]
    for key, flag, typ, default, kinds in OPTIONS:
        if kind not in kinds:
            continue
        value = values[key]
        if typ == "flag":
            if value:
                args.append(flag)
        elif typ == "noflag":
            if not value:
                args.append(flag)
        elif key == "chars":
            text = " ".join(str(value).split())
            if text:
                args += [flag, *text.split()]
        elif not _same(value, default) and str(value).strip():
            args += [flag, str(value).strip()]
    return args


def is_workdir(p: Path) -> bool:
    return (p / "data" / "makemeahanzi").is_dir() or (p / "src" / "copybook").is_dir()


def find_root() -> Path | None:
    if not FROZEN:
        return Path(__file__).resolve().parents[2]
    start = Path(sys.executable).resolve().parent
    for p in (start, *start.parents, Path.cwd()):
        if is_workdir(p):
            return p
    try:
        saved = Path(json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))["project_dir"])
        return saved if saved.is_dir() else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


ROOT = find_root() or Path.cwd()


# ---------------------------------------------------------------------------
# Preview data
# ---------------------------------------------------------------------------


class PreviewData:
    """Characters with readings and outlines for the preview, looked up lazily."""

    def __init__(self):
        self._data = None
        self._failed = False
        self._key = None
        self.entries: list = []
        self.polys: dict[tuple, list] = {}

    def _db(self):
        if self._data is None and not self._failed:
            try:
                from copybook.data import HanziData

                self._data = HanziData(ROOT / "data" / "makemeahanzi")
            except Exception:
                self._failed = True
        return self._data

    def update(self, chars: list[str], order: str, missing: str) -> str:
        key = (tuple(chars), order, missing)
        if key == self._key:
            return ""
        self._key = key
        db = self._db()
        if db is None:
            from copybook.entries import Entry

            self.entries = [Entry(ch, "", None) for ch in chars]
            return "no Make Me a Hanzi data (Download data): preview uses the font, unsorted"
        import contextlib
        import io

        from copybook.entries import build_entries

        try:
            with contextlib.redirect_stderr(io.StringIO()):
                self.entries = build_entries(chars, db, order, missing) if chars else []
        except CopybookError as e:
            self.entries = []
            return str(e)
        return ""

    def outlines(self, entry, align: str) -> list[list[tuple[float, float]]]:
        """Flattened polygons in em-square units (y up, 0..1024)."""
        key = (entry.char, align)
        if key not in self.polys:
            dx, dy = placement(entry.strokes, align)
            self.polys[key] = [
                [[(x + dx, y + dy) for x, y in poly] for poly in outline_polygons(d)] for d in entry.strokes
            ]
        return self.polys[key]


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("copybook – calligraphy sheets and copybooks")
        self.geometry("1280x860")
        self.minsize(1040, 700)
        self.v: dict[str, tk.Variable] = {}
        self.files: list[str] = []
        self.q: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.proc: subprocess.Popen | None = None
        self.stop_flag = threading.Event()
        self.last_pdf: Path | None = None
        self.preview_data = PreviewData()
        self._redraw_pending: str | None = None

        saved = {}
        try:
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        for key, _, typ, default, _ in OPTIONS:
            val = saved.get(key, default)
            self.v[key] = tk.BooleanVar(value=bool(val)) if typ in ("flag", "noflag") else tk.StringVar(value=str(val))
        self.v["kind"] = tk.StringVar(value=saved.get("kind", GUI_ONLY["kind"]))
        self.v["open_after"] = tk.BooleanVar(value=saved.get("open_after", True))
        self.v["side"] = tk.StringVar(value="recto")
        self.v["preview_page"] = tk.StringVar(value="1")
        default_file = ROOT / "input" / "learned_chars.txt"
        self.files = [f for f in saved.get("files", [str(default_file)] if default_file.is_file() else []) if Path(f).exists()]

        self._build_ui()
        for var in self.v.values():
            var.trace_add("write", lambda *_: self.schedule_preview())
        self.after(50, self.update_preview)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self._poll)

    # -- UI --------------------------------------------------------------------

    def _build_ui(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Hint.TLabel", foreground="#666")
        style.configure("Err.TLabel", foreground="#b00020")

        panes = ttk.PanedWindow(self, orient="vertical")
        panes.pack(fill="both", expand=True, padx=8, pady=8)
        top = ttk.PanedWindow(panes, orient="horizontal")
        panes.add(top, weight=4)

        left = ttk.Frame(top)
        top.add(left, weight=2)
        kinds = ttk.LabelFrame(left, text="Output", padding=6)
        kinds.pack(fill="x")
        for kind, text in (
            ("practice", "(a) Practice sheets"),
            ("dense", "(b) Dense reference book"),
            ("rows", "(c) One character per row"),
        ):
            ttk.Radiobutton(kinds, text=text, value=kind, variable=self.v["kind"]).pack(side="left", padx=(0, 12))

        nb = ttk.Notebook(left)
        nb.pack(fill="both", expand=True, pady=(6, 0))
        self._content_tab(nb)
        self._page_tab(nb)
        self._glyph_tab(nb)
        self._marker_tab(nb)
        self._output_tab(nb)

        right = ttk.LabelFrame(top, text="Preview", padding=6)
        top.add(right, weight=3)
        bar = ttk.Frame(right)
        bar.pack(fill="x")
        ttk.Radiobutton(bar, text="Right-hand page", value="recto", variable=self.v["side"]).pack(side="left")
        ttk.Radiobutton(bar, text="Left-hand page", value="verso", variable=self.v["side"]).pack(side="left", padx=8)
        ttk.Label(bar, text="Page").pack(side="left", padx=(16, 4))
        self.page_spin = ttk.Spinbox(bar, from_=1, to=1, width=5, textvariable=self.v["preview_page"])
        self.page_spin.pack(side="left")
        self.info = ttk.Label(right, text="", justify="left")
        self.info.pack(fill="x", pady=(4, 4))
        self.canvas = tk.Canvas(right, background="#d9d9d9", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda e: self.schedule_preview())

        bottom = ttk.Frame(panes)
        panes.add(bottom, weight=1)
        bar = ttk.Frame(bottom)
        bar.pack(fill="x")
        self.build_btn = ttk.Button(bar, text="Build PDF", command=self.build)
        self.build_btn.pack(side="left")
        self.stop_btn = ttk.Button(bar, text="Stop", command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=4)
        ttk.Button(bar, text="Copy command", command=self.copy_command).pack(side="left", padx=(12, 4))
        ttk.Button(bar, text="Open last PDF", command=self.open_last).pack(side="left")
        ttk.Button(bar, text="Open output folder", command=lambda: open_path(ROOT / "output")).pack(side="left", padx=4)
        ttk.Button(bar, text="Download data", command=self.download_data).pack(side="left", padx=(12, 4))
        ttk.Button(bar, text="Reset options", command=self.reset).pack(side="left")
        ttk.Button(bar, text="Clear log", command=lambda: self.log.delete("1.0", "end")).pack(side="right")
        self.status = ttk.Label(bar, text="")
        self.status.pack(side="left", padx=12)
        self.log = ScrolledText(bottom, height=8, font=("Consolas", 9), wrap="word")
        self.log.pack(fill="both", expand=True, pady=(6, 0))
        self.log.tag_configure("cmd", foreground="#2255aa")
        self.log.tag_configure("err", foreground="#b00020")
        self.log.tag_configure("ok", foreground="#1a7f37")

    def _tab(self, nb, title) -> ttk.Frame:
        f = ttk.Frame(nb, padding=8)
        nb.add(f, text=title)
        f.columnconfigure(2, weight=1)
        return f

    def _row(self, parent, r, label, widget, hint=""):
        ttk.Label(parent, text=label).grid(row=r, column=0, sticky="w", pady=2, padx=(0, 8))
        widget.grid(row=r, column=1, sticky="w", pady=2)
        if hint:
            ttk.Label(parent, text=hint, style="Hint.TLabel").grid(row=r, column=2, sticky="w", padx=6)

    def _num(self, parent, key, lo=0.0, hi=999.0, step=0.5, width=7):
        return ttk.Spinbox(parent, textvariable=self.v[key], from_=lo, to=hi, increment=step, width=width)

    def _combo(self, parent, key, values, width=10):
        return ttk.Combobox(parent, textvariable=self.v[key], values=list(values), width=width, state="readonly")

    def _check(self, parent, key, text):
        return ttk.Checkbutton(parent, text=text, variable=self.v[key])

    def _content_tab(self, nb):
        f = self._tab(nb, "Content")
        ttk.Label(f, text="Characters (any text; non-Chinese is ignored)").grid(row=0, column=0, columnspan=3, sticky="w")
        self.chars_text = tk.Text(f, height=4, width=50, wrap="char", font=("KaiTi", 12))
        self.chars_text.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(2, 6))
        self.chars_text.insert("1.0", self.v["chars"].get())
        self.chars_text.bind("<<Modified>>", self._chars_changed)
        ttk.Label(f, text="Character files").grid(row=2, column=0, sticky="nw")
        self.file_list = tk.Listbox(f, height=3, width=50)
        self.file_list.grid(row=2, column=1, columnspan=2, sticky="ew")
        buttons = ttk.Frame(f)
        buttons.grid(row=3, column=1, columnspan=2, sticky="w", pady=(2, 6))
        ttk.Button(buttons, text="Add…", command=self.add_file).pack(side="left")
        ttk.Button(buttons, text="Remove", command=self.remove_file).pack(side="left", padx=4)
        self._refresh_files()
        self.char_count = ttk.Label(f, style="Hint.TLabel")
        self.char_count.grid(row=4, column=0, columnspan=3, sticky="w")
        r = 5
        self._row(f, r, "Order", self._combo(f, "order", ORDERS)); r += 1
        self._row(f, r, "No reading found", self._combo(f, "missing", MISSING_POLICIES), "warn keeps it under “?”"); r += 1
        self._row(f, r, "", self._check(f, "keep_duplicates", "Keep repeated characters")); r += 1
        self._row(f, r, "", self._check(f, "index", "Index at the front")); r += 1
        self._row(f, r, "Index title", ttk.Entry(f, textvariable=self.v["index_title"], width=10)); r += 1
        self._row(f, r, "Index columns", self._num(f, "index_columns", 1, 6, 1)); r += 1
        ttk.Separator(f).grid(row=r, column=0, columnspan=3, sticky="ew", pady=6); r += 1
        ttk.Label(f, text="Rows book (c)").grid(row=r, column=0, sticky="w"); r += 1
        self._row(f, r, "Tracing copies", self._num(f, "traces", 0, 20, 1)); r += 1
        self._row(f, r, "Tracing ink", self._num(f, "trace_ink", 0, 100, 2), "0 white … 100 black"); r += 1
        self._row(f, r, "Label band", self._num(f, "band", 0, 20, 0.5), "mm above each row"); r += 1
        self._row(f, r, "", self._check(f, "stroke_order", "Stroke-order strip")); r += 1
        ttk.Separator(f).grid(row=r, column=0, columnspan=3, sticky="ew", pady=6); r += 1
        ttk.Label(f, text="Practice sheets (a)").grid(row=r, column=0, sticky="w"); r += 1
        self._row(f, r, "Pages", self._num(f, "pages", 1, 999, 1)); r += 1
        self._row(f, r, "", self._check(f, "page_numbers", "Page numbers")); r += 1

    def _page_tab(self, nb):
        f = self._tab(nb, "Page & grid")
        r = 0
        self._row(f, r, "Paper", self._combo(f, "paper", sorted(PAPER_SIZES)), "A5 = 148.5 × 210 mm"); r += 1
        self._row(f, r, "", self._check(f, "landscape", "Landscape")); r += 1
        self._row(f, r, "Custom width", self._num(f, "page_width"), "mm, with height; overrides paper"); r += 1
        self._row(f, r, "Custom height", self._num(f, "page_height")); r += 1
        self._row(f, r, "Border", self._num(f, "border"), "mm, every side"); r += 1
        self._row(f, r, "Header band", self._num(f, "header"), "mm"); r += 1
        self._row(f, r, "Footer band", self._num(f, "footer"), "mm"); r += 1
        ttk.Separator(f).grid(row=r, column=0, columnspan=3, sticky="ew", pady=6); r += 1
        self._row(f, r, "Pattern", self._combo(f, "pattern", PATTERNS)); r += 1
        self._row(f, r, "Cell", self._num(f, "cell", 5, 40, 0.5), "mm"); r += 1
        self._row(f, r, "Fit", self._combo(f, "fit", FIT_MODES), "fill grows cells to use the page"); r += 1
        self._row(f, r, "Hui box", self._num(f, "hui_scale", 0.1, 0.95, 0.05), "fraction of the cell"); r += 1
        self._row(f, r, "Tall box width", self._num(f, "tall_width", 0.1, 0.95, 0.05)); r += 1
        self._row(f, r, "Tall box height", self._num(f, "tall_height", 0.1, 0.95, 0.05)); r += 1
        self._row(f, r, "Line ink", self._num(f, "line_ink", 0, 100, 5), "frame and cell lines, 0–100"); r += 1
        self._row(f, r, "Guide ink", self._num(f, "guide_ink", 0, 100, 5), "dashed guides, 0–100"); r += 1
        self._row(f, r, "Frame width", self._num(f, "frame_width", 0, 5, 0.1), "pt"); r += 1
        self._row(f, r, "Line width", self._num(f, "line_width", 0, 5, 0.1), "pt"); r += 1
        self._row(f, r, "Guide width", self._num(f, "guide_width", 0, 5, 0.1), "pt"); r += 1

    def _glyph_tab(self, nb):
        f = self._tab(nb, "Glyphs")
        r = 0
        self._row(f, r, "Source", self._combo(f, "glyphs", GLYPH_SOURCES), "strokes: Make Me a Hanzi; font: typeset"); r += 1
        self._row(f, r, "Font", ttk.Entry(f, textvariable=self.v["font"], width=22), "name or .ttf/.otf path"); r += 1
        self._row(f, r, "Alignment", self._combo(f, "align", ALIGNMENTS), "design: typeface placement"); r += 1
        self._row(f, r, "Glyph scale", self._num(f, "glyph_scale", 0.3, 1.2, 0.02), "em size / cell"); r += 1
        self._row(f, r, "", self._check(f, "shade_strokes", "Shade strokes (dense book)")); r += 1
        self._row(f, r, "Shade step", self._num(f, "shade_step", 1, 50, 1), "ink per stroke"); r += 1
        self._row(f, r, "Lightest stroke", self._num(f, "shade_min_ink", 0, 100, 5), "ink 0–100"); r += 1

    def _marker_tab(self, nb):
        f = self._tab(nb, "Markers")
        r = 0
        self._row(f, r, "", self._check(f, "markers", "ArUco markers + geometry sidecar (for the checker)")); r += 1
        self._row(f, r, "Size", self._num(f, "marker_size", 6, 12, 0.5), "mm"); r += 1
        self._row(f, r, "Quiet zone", self._num(f, "marker_quiet", 0, 10, 0.5), "mm of white around each"); r += 1
        self._row(f, r, "Outer margin", self._num(f, "marker_outer_margin", 0, 30, 0.5), "mm to top, bottom, fore-edge"); r += 1
        self._row(f, r, "Gutter margin", self._num(f, "marker_gutter_margin", 0, 30, 0.5), "mm to the fold"); r += 1
        self._row(f, r, "", self._check(f, "book_qr", "Cover page with book QR code")); r += 1
        self._row(f, r, "Book id", ttk.Entry(f, textvariable=self.v["book_id"], width=12), "empty = random"); r += 1
        self._row(f, r, "Cover title", ttk.Entry(f, textvariable=self.v["title"], width=22), "empty = automatic"); r += 1

    def _output_tab(self, nb):
        f = self._tab(nb, "Output")
        r = 0
        out = ttk.Frame(f)
        ttk.Entry(out, textvariable=self.v["output"], width=36).pack(side="left")
        ttk.Button(out, text="…", width=3, command=self.choose_output).pack(side="left", padx=4)
        self._row(f, r, "PDF", out); r += 1
        ttk.Label(f, text="empty = output/<book>_<paper>.pdf", style="Hint.TLabel").grid(row=r, column=1, sticky="w"); r += 1
        self._row(f, r, "", self._check(f, "impose", "Also write an A4 booklet")); r += 1
        self._row(f, r, "Sheets per signature", self._num(f, "sheets_per_signature", 1, 32, 1)); r += 1
        self._row(f, r, "", self._check(f, "open_after", "Open the PDF after building")); r += 1
        ttk.Label(f, text=f"Working folder: {ROOT}", style="Hint.TLabel", wraplength=420).grid(
            row=r, column=0, columnspan=3, sticky="w", pady=(12, 0)
        )

    # -- values ----------------------------------------------------------------

    def _chars_changed(self, _event=None):
        if self.chars_text.edit_modified():
            self.v["chars"].set(self.chars_text.get("1.0", "end").strip())
            self.chars_text.edit_modified(False)

    def values(self) -> dict:
        vals = {k: var.get() for k, var in self.v.items()}
        vals["files"] = list(self.files)
        return vals

    def _refresh_files(self):
        self.file_list.delete(0, "end")
        for f in self.files:
            self.file_list.insert("end", rel(Path(f)))

    def add_file(self):
        for p in filedialog.askopenfilenames(parent=self, initialdir=ROOT / "input", filetypes=[("Text", "*.txt"), ("All", "*.*")]):
            if p not in self.files:
                self.files.append(p)
        self._refresh_files()
        self.schedule_preview()

    def remove_file(self):
        for i in reversed(self.file_list.curselection()):
            del self.files[i]
        self._refresh_files()
        self.schedule_preview()

    def choose_output(self):
        p = filedialog.asksaveasfilename(parent=self, initialdir=ROOT / "output", defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if p:
            self.v["output"].set(p)

    def reset(self):
        if not messagebox.askyesno("Reset", "Reset every option to its default?", parent=self):
            return
        for key, _, typ, default, _ in OPTIONS:
            if key != "chars":
                self.v[key].set(default if typ in ("flag", "noflag") else str(default))

    def save_settings(self):
        data = {k: v.get() for k, v in self.v.items() if k not in ("side", "preview_page")}
        data["files"] = self.files
        data["project_dir"] = str(ROOT)
        try:
            SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    def settings_objects(self, vals: dict):
        """Settings dataclasses for the preview (validated like a real build)."""

        def num(key):
            text = str(vals[key]).strip()
            return float(text) if text else None

        page = PageSettings(
            paper=vals["paper"], landscape=vals["landscape"], width=num("page_width"), height=num("page_height"),
            border=num("border"), header=num("header"), footer=num("footer"),
        )
        grid = GridSettings(
            cell=num("cell"), fit=vals["fit"], pattern=vals["pattern"], hui_scale=num("hui_scale"),
            tall_width=num("tall_width"), tall_height=num("tall_height"), guide_ink=num("guide_ink"),
            line_ink=num("line_ink"), frame_width=num("frame_width"), line_width=num("line_width"),
            guide_width=num("guide_width"),
        )
        glyphs = GlyphSettings(
            source=vals["glyphs"], font=vals["font"], align=vals["align"], scale=num("glyph_scale"),
            shade=vals["shade_strokes"], shade_step=num("shade_step"), shade_min_ink=num("shade_min_ink"),
            trace_ink=num("trace_ink"),
        )
        markers = MarkerSettings(
            enabled=vals["markers"], size=num("marker_size"), quiet=num("marker_quiet"),
            outer_margin=num("marker_outer_margin"), gutter_margin=num("marker_gutter_margin"),
            book_qr=vals["book_qr"], book_id=vals["book_id"].strip() or None,
        )
        rows = RowsSettings(traces=int(float(vals["traces"])), band=num("band"), stroke_order=vals["stroke_order"])
        for s in (page, grid, glyphs, markers, rows):
            s.validate()
        return page, grid, glyphs, markers, rows

    # -- preview ---------------------------------------------------------------

    def schedule_preview(self):
        if self._redraw_pending:
            self.after_cancel(self._redraw_pending)
        self._redraw_pending = self.after(150, self.update_preview)

    def update_preview(self):
        self._redraw_pending = None
        vals = self.values()
        kind = vals["kind"]
        c = self.canvas
        c.delete("all")
        try:
            page, grid, glyphs, msettings, rows = self.settings_objects(vals)
            mlayout = MarkerLayout(msettings, page.size) if msettings.enabled else None
            eff, layout = plan_page(kind, page, grid, mlayout, rows.band, page_numbers=vals["page_numbers"] if kind == "practice" else True)
        except (CopybookError, ValueError, TypeError) as e:
            self.info.config(text=f"⚠ {e}", style="Err.TLabel")
            return

        note, entries, per_page = "", [], layout.cells_per_page if kind == "dense" else layout.rows
        if kind != "practice":
            try:
                chars = collect_characters([vals["chars"]], [Path(f) for f in self.files], vals["keep_duplicates"])
            except CopybookError as e:
                chars, note = [], str(e)
            note = self.preview_data.update(chars, vals["order"], vals["missing"]) or note
            entries = self.preview_data.entries
            self.char_count.config(text=f"{len(chars)} characters")
        pages = max(1, math.ceil(len(entries) / per_page)) if kind != "practice" else max(1, int(float(vals["pages"] or 1)))
        self.page_spin.config(to=pages)
        try:
            index = min(max(int(self.v["preview_page"].get()), 1), pages) - 1
        except ValueError:
            index = 0
        shown = entries[index * per_page : (index + 1) * per_page]

        w, h = eff.size
        lines = [f"{w:g} × {h:g} mm · {layout.columns} × {layout.rows} cells of {layout.cell:.2f} mm"]
        if kind == "practice":
            lines[0] += f" · {pages} pages"
        else:
            lines[0] += f" · {per_page} {'characters' if kind == 'dense' else 'rows'} per page · {pages} pages + index"
        if mlayout:
            lines.append("markers on: cover page with QR, geometry sidecar next to the PDF")
        if note:
            lines.append(note)
        self.info.config(text="\n".join(lines), style="Err.TLabel" if note and not entries else "TLabel")
        self.draw_page(eff, grid, layout, glyphs, rows, mlayout, kind, shown, index, vals)

    def draw_page(self, page, style, layout: Grid, glyphs, rows, mlayout, kind, entries, index, vals):
        c = self.canvas
        cw, ch = max(c.winfo_width(), 50), max(c.winfo_height(), 50)
        w, h = page.size
        s = min((cw - 24) / w, (ch - 24) / h)
        ox, oy = (cw - w * s) / 2, (ch - h * s) / 2

        def X(x):
            return ox + x * s

        def Y(y):
            return oy + y * s

        def width(pt):
            return max(1, pt * PT * s)

        c.create_rectangle(X(0) + 3, Y(0) + 3, X(w) + 3, Y(h) + 3, fill="#9a9a9a", outline="")
        c.create_rectangle(X(0), Y(0), X(w), Y(h), fill="white", outline="#777")

        shapes = grid_shapes(layout, style)
        guide = ink_to_hex(style.guide_ink)
        line = ink_to_hex(style.line_ink)
        for kind_, x1, y1, x2, y2 in shapes.guides:
            c.create_line(X(x1), Y(y1), X(x2), Y(y2), fill=guide, width=width(style.guide_width), dash=(2, 2))
        for _, x1, y1, x2, y2 in shapes.boxes:
            c.create_rectangle(X(x1), Y(y1), X(x2), Y(y2), outline=guide, width=width(style.guide_width))
        for _, x1, y1, x2, y2 in shapes.lines:
            c.create_line(X(x1), Y(y1), X(x2), Y(y2), fill=line, width=width(style.line_width))
        for _, x1, y1, x2, y2 in shapes.frame:
            c.create_rectangle(X(x1), Y(y1), X(x2), Y(y2), outline=line, width=width(style.frame_width))

        # characters
        if kind == "dense":
            for i, entry in enumerate(entries):
                cx, cy = layout.cell_center(*layout.cell_at(i))
                self.draw_glyph(entry, cx, cy, layout.cell, glyphs, X, Y, s, shade=glyphs.shade)
        elif kind == "rows":
            traces = min(rows.traces, layout.columns - 1)
            for r, entry in enumerate(entries):
                if rows.band > 0:
                    self.draw_band(entry, layout, r, rows, glyphs, X, Y, s)
                for col in range(1 + traces):
                    cx, cy = layout.cell_center(r, col)
                    self.draw_glyph(entry, cx, cy, layout.cell, glyphs, X, Y, s, ink=100 if col == 0 else glyphs.trace_ink)

        # running head and page number
        text_px = max(6, int(3.4 * s))
        if kind != "practice" and entries and page.header > 0 and vals["order"] == "pinyin":
            first, last = entries[0].reading, entries[-1].reading
            y = mlayout.header_y if mlayout else page.border + page.header / 2
            c.create_text(X(w / 2), Y(y), text=first if first == last else f"{first} – {last}", font=("Times New Roman", -text_px))
        if kind != "practice" or vals["page_numbers"]:
            y = mlayout.footer_y if mlayout else h - page.border - page.footer / 2
            c.create_text(X(w / 2), Y(y), text=str(index + 1), font=("Times New Roman", -max(6, int(2.9 * s))))

        if mlayout:
            page_index = 0 if self.v["side"].get() == "recto" else 1
            for box in mlayout.boxes(self.v["side"].get()):
                self.draw_marker(marker_id(page_index, box.corner), box, mlayout.settings.quiet, X, Y, s)

    def draw_glyph(self, entry, cx, cy, cell, glyphs, X, Y, s, ink=100.0, shade=False):
        size = cell * glyphs.scale
        if glyphs.source == "strokes" and entry.strokes:
            from copybook.glyphs import shade_inks

            inks = shade_inks(len(entry.strokes), glyphs.shade_step, glyphs.shade_min_ink) if shade else [ink] * len(entry.strokes)
            k = size / EM
            left, top = cx - size / 2, cy + size / 2  # em square, y up from its bottom edge
            for polys, stroke_ink in zip(self.preview_data.outlines(entry, glyphs.align), inks):
                for poly in polys:
                    pts = [v for x, y in poly for v in (X(left + x * k), Y(top - y * k))]
                    if len(pts) >= 6:
                        self.canvas.create_polygon(pts, fill=ink_to_hex(stroke_ink), outline="")
        else:
            px = max(4, int(size * 0.9 * s))
            self.canvas.create_text(X(cx), Y(cy), text=entry.char, fill=ink_to_hex(ink), font=(glyphs.font, -px))

    def draw_band(self, entry, layout, row, rows, glyphs, X, Y, s):
        top = layout.y0 + row * layout.row_pitch
        baseline = top + rows.band * 0.82
        text_px = max(5, int(rows.band * 0.55 * s))
        label = entry.all_readings + (f"  {entry.stroke_count}画" if entry.stroke_count else "")
        item = self.canvas.create_text(X(layout.x0), Y(baseline), text=label, anchor="sw", font=("Times New Roman", -text_px))
        if not (rows.stroke_order and entry.strokes):
            return
        x = (self.canvas.bbox(item)[2] - X(0)) / s + 3
        size = rows.band * 0.72
        room = layout.x0 + layout.width - x
        n = len(entry.strokes)
        pitch = min(size * 1.2, room / max(n, 1))
        size = min(size, pitch / 1.2)
        polys = self.preview_data.outlines(entry, glyphs.align)
        k = size / EM
        for i in range(n):
            left = x + i * pitch
            for j in range(i + 1):
                colour = ink_to_hex(100 if j == i else 30)
                for poly in polys[j]:
                    pts = [v for px, py in poly[::2] for v in (X(left + px * k), Y(baseline - py * k))]
                    if len(pts) >= 6:
                        self.canvas.create_polygon(pts, fill=colour, outline="")

    def draw_marker(self, mid, box, quiet, X, Y, s):
        c = self.canvas
        q = quiet
        c.create_rectangle(X(box.x - q), Y(box.y - q), X(box.x + box.size + q), Y(box.y + box.size + q), fill="white", outline="")
        c.create_rectangle(X(box.x), Y(box.y), X(box.x + box.size), Y(box.y + box.size), fill="black", outline="")
        m = box.size / MODULES
        for i, bit in enumerate(patterns()[mid]):
            if bit == "1":
                x, y = box.x + (1 + i % 4) * m, box.y + (1 + i // 4) * m
                c.create_rectangle(X(x), Y(y), X(x + m), Y(y + m), fill="white", outline="")

    # -- commands --------------------------------------------------------------

    def command(self) -> list[str]:
        return command_args(self.values())

    def copy_command(self):
        text = subprocess.list2cmdline(["copybook", *self.command()]) if WIN else " ".join(["copybook", *self.command()])
        self.clipboard_clear()
        self.clipboard_append(text)
        self.write(text + "\n", "cmd")
        self.status.config(text="command copied")

    def build(self):
        if self.busy():
            return
        vals = self.values()
        if vals["kind"] != "practice" and not vals["chars"].strip() and not self.files:
            messagebox.showinfo("Build", "Type some characters or add a character file first.", parent=self)
            return
        try:
            self.settings_objects(vals)
        except (CopybookError, ValueError, TypeError) as e:
            messagebox.showerror("Build", str(e), parent=self)
            return
        self.save_settings()
        self.start([*PY, *self.command()], open_after=vals["open_after"])

    def download_data(self):
        if not self.busy():
            self.start([*PY, "data"], open_after=False)

    def busy(self) -> bool:
        return self.worker is not None and self.worker.is_alive()

    def start(self, cmd: list[str], open_after: bool):
        self.stop_flag.clear()
        self.build_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status.config(text="running …")
        self.worker = threading.Thread(target=self._worker, args=(cmd, open_after), daemon=True)
        self.worker.start()

    def _worker(self, cmd: list[str], open_after: bool):
        shown = ["copybook", *cmd[len(PY):]]
        self.q.put(("log", ("$ " + subprocess.list2cmdline(shown) + "\n", "cmd")))
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        pdf = None
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", env=env, creationflags=_NOWINDOW,
            )
            for line in self.proc.stdout:
                tag = "err" if re.match(r"(error|Traceback)", line) else ("ok" if line.startswith("Wrote") else None)
                self.q.put(("log", (line, tag)))
                m = re.match(r"Wrote (.+\.pdf)$", line.strip())
                if m and pdf is None:
                    pdf = Path(m.group(1))
            rc = self.proc.wait()
        except OSError as e:
            self.q.put(("log", (f"could not start: {e}\n", "err")))
            rc = -1
        self.proc = None
        stopped = self.stop_flag.is_set()
        msg = "stopped" if stopped else ("done" if rc == 0 else f"failed (exit code {rc})")
        self.q.put(("log", (msg + "\n\n", "ok" if rc == 0 else "err")))
        self.q.put(("status", msg))
        if pdf is not None and rc == 0:
            pdf = pdf if pdf.is_absolute() else ROOT / pdf
            self.q.put(("pdf", (pdf, open_after)))
        self.q.put(("done", None))

    def stop(self):
        self.stop_flag.set()
        p = self.proc
        if p and p.poll() is None:
            if WIN:  # the build spawns xelatex; kill the whole tree
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, creationflags=_NOWINDOW)
            else:
                p.terminate()

    def _poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "log":
                    self.write(*data)
                elif kind == "status":
                    self.status.config(text=data)
                elif kind == "done":
                    self.build_btn.config(state="normal")
                    self.stop_btn.config(state="disabled")
                    self.preview_data = PreviewData()  # pick up freshly downloaded data
                    self.schedule_preview()
                elif kind == "pdf":
                    self.last_pdf, open_after = data
                    if open_after:
                        open_path(self.last_pdf)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def write(self, text: str, tag: str | None = None):
        self.log.insert("end", text, tag or ())
        self.log.see("end")

    def open_last(self):
        if self.last_pdf and self.last_pdf.exists():
            open_path(self.last_pdf)
        else:
            self.status.config(text="nothing built yet in this session")

    def on_close(self):
        if self.busy():
            if not messagebox.askyesno("Quit", "A build is running. Stop it and quit?", parent=self):
                return
            self.stop()
        self.save_settings()
        self.destroy()


def rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def open_path(p: Path):
    try:
        p.mkdir(parents=True, exist_ok=True) if p.suffix == "" else None
        if WIN:
            os.startfile(p)  # noqa: S606 - opens with the user's default viewer
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(p)])
    except OSError as e:
        messagebox.showerror("Open", str(e))


def run_cli(argv: list[str]) -> int:
    """Frozen mode: behave like the ``copybook`` command line."""
    if sys.stdout is None:  # windowed exe: use the pipe handles the GUI passed us
        sys.stdout = open(1, "w", encoding="utf-8", errors="replace", closefd=False)
        sys.stderr = open(2, "w", encoding="utf-8", errors="replace", closefd=False)
    if WIN:  # this process has no console, so stop xelatex from opening one
        original = subprocess.Popen.__init__

        def quiet_init(self, *a, **kw):
            kw["creationflags"] = kw.get("creationflags", 0) | _NOWINDOW
            original(self, *a, **kw)

        subprocess.Popen.__init__ = quiet_init
    from copybook.cli import main as cli_main

    return cli_main(argv)


def main() -> None:
    global ROOT
    if len(sys.argv) > 1 and sys.argv[1] == "--run-cli":
        sys.exit(run_cli(sys.argv[2:]))
    if FROZEN and find_root() is None:
        hidden = tk.Tk()
        hidden.withdraw()
        d = filedialog.askdirectory(parent=hidden, title="Choose a working folder (data/ and output/ go there)")
        hidden.destroy()
        if not d:
            return
        ROOT = Path(d)
    os.chdir(ROOT)
    App().mainloop()


if __name__ == "__main__":
    main()
