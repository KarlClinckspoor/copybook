"""LaTeX generation and XeLaTeX compilation.

Every page is drawn with an absolutely positioned TikZ overlay whose
coordinate system is millimetres from the top-left corner, y pointing down,
matching :mod:`copybook.geometry`. Only greyscale (``black!N``) is used.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from copybook import CopybookError
from copybook.geometry import Grid, grid_shapes
from copybook.settings import GridSettings, PageSettings

_SPECIAL = {
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\\": r"\textbackslash{}",
}


def escape(text: str) -> str:
    return "".join(_SPECIAL.get(ch, ch) for ch in str(text).replace("\n", " "))


def mm(value: float) -> str:
    return f"{value:.2f}"


def tex_path(path: Path) -> str:
    """A path LaTeX accepts: forward slashes, no backslashes."""
    return Path(path).resolve().as_posix()


# ---------------------------------------------------------------------------
# Grid drawing
# ---------------------------------------------------------------------------


def _shape(shape: tuple) -> str:
    kind, x1, y1, x2, y2 = shape
    joiner = "--" if kind == "line" else " rectangle "
    return f"({mm(x1)},{mm(y1)}){joiner}({mm(x2)},{mm(y2)})"


def grid_drawing(grid: Grid, style: GridSettings) -> str:
    """TikZ commands for the empty grid; each line style is a single path."""
    shapes = grid_shapes(grid, style)
    out = []
    for name, items in (
        ("cb guide", shapes.guides),
        ("cb box", shapes.boxes),
        ("cb line", shapes.lines),
        ("cb frame", shapes.frame),
    ):
        if items:
            out.append(f"\\draw[{name}] " + " ".join(_shape(i) for i in items) + ";")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


def _ink(ink: float) -> str:
    return "black" if ink >= 100 else f"black!{ink:g}"


def _font_command(font: str) -> str:
    path = Path(font)
    if path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
        if not path.is_file():
            raise CopybookError(f"Font file not found: {font}")
        return f"\\setCJKmainfont[Path={tex_path(path.parent)}/]{{{path.name}}}"
    return f"\\setCJKmainfont{{{font}}}"


class Document:
    """Accumulates pages and renders a complete XeLaTeX document."""

    def __init__(
        self,
        page: PageSettings,
        style: GridSettings,
        font: str,
        page_numbers: bool = True,
        extra_preamble: str = "",
        markers=None,  # copybook.markers.MarkerLayout; the page must already be adjusted for it
    ):
        self.page = page
        self.markers = markers
        self.files: dict[str, str] = {}  # extra files written next to main.tex
        self.grid_pages: list[dict] = []  # sidecar records, in page order
        self.has_cover = False
        if markers is not None:
            self.files["aruco.tex"] = markers.tex_definitions()
        self.style = style
        self.font = font
        self.page_numbers = page_numbers
        self.extra_preamble = extra_preamble
        self.grid_macros: dict[str, str] = {}
        self.body: list[str] = []
        self._has_front_matter = False

    # -- preamble ----------------------------------------------------------

    def define_grid(self, name: str, grid: Grid) -> str:
        """Register the drawing of ``grid`` as a macro; returns its call."""
        self.grid_macros[name] = grid_drawing(grid, self.style)
        return f"\\{name}"

    def preamble(self) -> str:
        w, h = self.page.size
        p, s = self.page, self.style
        bottom = p.border + p.footer
        footskip = max(p.footer / 2 + 1.0, 1.0)
        if self.markers is not None:  # page number baseline level with the bottom markers
            footskip = self.markers.footer_y + 1.2 - (h - bottom)
        grids = "\n".join(
            f"\\newcommand{{\\{name}}}{{%\n{body}\n}}" for name, body in self.grid_macros.items()
        )
        return rf"""\documentclass[twoside]{{article}}
\usepackage[paperwidth={mm(w)}mm,paperheight={mm(h)}mm,left={mm(p.border)}mm,right={mm(p.border)}mm,top={mm(p.border + p.header)}mm,bottom={mm(bottom)}mm,headheight=0pt,headsep=0pt,footskip={mm(footskip)}mm]{{geometry}}
\usepackage{{fontspec}}
\usepackage{{xeCJK}}
\usepackage{{xcolor}}
\usepackage{{graphicx}}
\usepackage{{multicol}}
\usepackage{{tikz}}
{_font_command(self.font)}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{0pt}}
\makeatletter
\def\ps@copybook{{\let\@oddhead\@empty\let\@evenhead\@empty
  \def\@oddfoot{{\hfil\small\thepage\hfil}}\let\@evenfoot\@oddfoot}}
\makeatother
\pagestyle{{{"copybook" if self.page_numbers else "empty"}}}
\tikzset{{
  cb frame/.style={{line width={s.frame_width}pt, {_ink(s.line_ink)}}},
  cb line/.style={{line width={s.line_width}pt, {_ink(s.line_ink)}}},
  cb guide/.style={{line width={s.guide_width}pt, black!{s.guide_ink:g}, dash pattern=on 1.2pt off 1.2pt}},
  cb box/.style={{line width={s.guide_width}pt, black!{s.guide_ink:g}}},
  cb glyph/.style={{inner sep=0pt, outer sep=0pt}},
}}
{grids}
{self.extra_preamble}{self.markers.tex_preamble() if self.markers is not None else ""}"""

    # -- pages -------------------------------------------------------------

    def add(self, tex: str) -> None:
        self.body.append(tex)

    def start_front_matter(self) -> None:
        self._has_front_matter = True
        self.add(r"\pagenumbering{roman}")

    def start_main_matter(self) -> None:
        # After front matter, start page 1 on a right-hand (odd) page.
        clear = r"\cleardoublepage" if self._has_front_matter else r"\clearpage"
        self.add(clear + r"\pagenumbering{arabic}")

    def overlay_page(self, commands: list[str], header: str = "", record: dict | None = None) -> None:
        """One page drawn entirely with absolutely positioned TikZ commands.

        ``record`` (grid area and cells) goes into the geometry sidecar.
        """
        w, _ = self.page.size
        if record is not None:
            self.grid_pages.append(record)
        parts = [
            r"\null",
            r"\begin{tikzpicture}[remember picture,overlay]",
            r"\begin{scope}[shift={(current page.north west)},x=1mm,y=-1mm]",
        ]
        if header and self.page.header > 0:
            size = self.page.header * 0.5
            y = self.page.border + self.page.header / 2
            if self.markers is not None:  # between the top markers, at their height
                size, y = min(size, 4.0), self.markers.header_y
            parts.append(
                f"\\node[cb glyph, font=\\fontsize{{{mm(size)}mm}}{{{mm(size * 1.2)}mm}}\\selectfont] "
                f"at ({mm(w / 2)},{mm(y)}) {{{header}}};"
            )
        parts += commands
        parts += [r"\end{scope}", r"\end{tikzpicture}", r"\clearpage"]
        self.add("\n".join(parts))

    def cover_page(self, commands: list[str]) -> None:
        """An unnumbered first page; page numbering restarts after it."""
        self.has_cover = True
        self.add(r"\thispagestyle{empty}")
        self.overlay_page(commands)
        self.add(r"\pagenumbering{arabic}")

    def render(self) -> str:
        return "\n".join([self.preamble(), r"\begin{document}", *self.body, r"\end{document}", ""])


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------


def compile_pdf(
    tex: str, build_dir: Path, output: Path, passes: int = 2, files: dict[str, str] | None = None
) -> Path:
    """Write ``main.tex`` into ``build_dir``, run XeLaTeX and copy the PDF to ``output``.

    Two passes are needed: TikZ overlays learn their position on the page
    from the ``.aux`` file written by the first pass.
    """
    if shutil.which("xelatex") is None:
        raise CopybookError("xelatex not found. Install TeX Live, MiKTeX or MacTeX.")

    build_dir = Path(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    (build_dir / "main.tex").write_text(tex, encoding="utf-8")
    for name, content in (files or {}).items():
        (build_dir / name).write_text(content, encoding="utf-8")
    pdf = build_dir / "main.pdf"
    pdf.unlink(missing_ok=True)

    for _ in range(passes):
        proc = subprocess.run(
            ["xelatex", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
            cwd=build_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            log = build_dir / "main.log"
            text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else proc.stdout
            start = text.find("\n!")  # TeX error messages start with "!"
            excerpt = "\n".join(text[start:].splitlines()[:12]) if start >= 0 else text[-3000:]
            raise CopybookError(f"XeLaTeX failed (full log: {log}):\n{excerpt.strip()}")

    if not pdf.is_file():
        raise CopybookError("XeLaTeX finished but produced no PDF")

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(pdf, output)
    return output
