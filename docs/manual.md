# Manual

copybook makes printable Chinese calligraphy material in greyscale:

- **Practice sheets**: empty grids (blank, 田 tian, 米 mi, 回 hui, tall 回).
- **Dense reference book**: every cell holds one of your characters, sorted by pinyin, with an index.
- **Rows book**: one character per row, with its pinyin, stroke count and stroke order above, a model,
  grey copies to trace over, and empty cells to write in.

## 1. Install

You need, in every case:

- **XeLaTeX**: [MiKTeX](https://miktex.org/) (Windows) or TeX Live / MacTeX. MiKTeX installs missing
  packages on first use; allow it to.
- **A Chinese font.** KaiTi (楷体) comes with Windows and is the default. On other systems install a
  Kai font such as [LXGW WenKai](https://github.com/lxgw/LxgwWenKai) and pass its name with `--font`.

Then choose one:

- **Desktop app (Windows)**: download `copybook-gui.exe` from the
  [latest release](https://github.com/KarlClinckspoor/copybook/releases/latest) and put it in an empty folder, for example `Documents\copybook`.
  No Python needed.
- **From source**: install Python 3.11+ and [uv](https://docs.astral.sh/uv/), then
  ```bash
  git clone https://github.com/KarlClinckspoor/copybook.git
  cd copybook
  uv sync
  ```

## 2. Download the character data (once)

Readings and stroke outlines come from [Make Me a Hanzi](https://github.com/skishore/makemeahanzi)
(about 35 MB).

- Desktop app: click **Download data**. The data goes into `data/` next to the exe.
- Command line: `uv run copybook data`

Practice sheets work without the data; the two character books need it.

## 3. Using the desktop app

Start `copybook-gui.exe` (or `uv run copybook-gui`).

1. **Choose the output** at the top left: (a) Practice sheets, (b) Dense reference book or (c) One character per row.
2. **Content tab** (character books only): type characters into the box and/or add text files.
   Anything that isn't a Chinese character is ignored, so you can paste whole sentences.
   Choose pinyin order or the order you gave. This tab also holds the number of pages for practice
   sheets and the tracing copies for the rows book.
3. **Page & grid tab**: paper size, cell size in mm, grid pattern, and how dark the lines and guides are.
4. **Glyphs tab**: font, character size and alignment.
5. **Markers tab**: corner markers for the calligraphy checker app. Untick **ArUco markers** for
   plain pages.
6. **Output tab**: file name, and **Also write an A4 booklet** for a version to fold (see section 5).

The preview on the right updates as you change settings. Use the page arrows and the right/left page
switch to look through the book. The line above the preview tells you how many cells fit and how many
pages the book will have, or what is wrong with a setting.

Click **Build PDF**. A rows book of a few hundred characters takes several minutes; the log shows
progress. **Open last PDF** opens the result. Settings are remembered between sessions.

## 4. Using the command line

Every option in the app is also a command-line flag, and **Copy command** in the app gives you
the command for the current settings. Run `uv run copybook <command> --help` for the full list.

```bash
# 8 pages of tian grids, 18 mm cells, no markers
uv run copybook practice --pattern tian --cell 18 --pages 8 --no-markers

# Reference book of a text file
uv run copybook dense --file my_characters.txt

# Rows book in the order the characters appear in the text
uv run copybook rows --file examples/lanting.txt --order input
```

PDFs are written to `output/`. More recipes are in [`examples/`](../examples/README.md).

### Character files

Plain UTF-8 text. Lines starting with `#` are comments. Each character is used once, however often
it appears.

## 5. Printing

- Print at **100 % / actual size**. Turn off "fit to page", or the cell sizes and marker positions change.
- A5 pages print fine on A5 paper, or two to a sheet with the booklet option:
  - **Booklet** (`--impose`) also writes `<name>_booklet.pdf`: two A5 pages per A4 side, grouped into
    signatures of 8 sheets.
  - Print it **double-sided, flipping on the short edge**. Fold each signature in half and stack them in order.
- Everything is greyscale; colour printers are not needed.

## 6. Page markers

With markers on (the default), every page has a small black square pattern (ArUco code) in each corner,
the first page carries a QR code, and a `.geometry.json` file is written next to the PDF. These let the
calligraphy checker app find the page and each cell in a photo. If you don't use the checker, turn them off:
you get one more row per page.

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| "xelatex not found" | Install MiKTeX or TeX Live and reopen the app, so it sees the updated PATH. |
| Build stops at a missing `.sty` package | Open the MiKTeX Console and enable installing missing packages, or install the package. |
| Characters show as boxes | The font lacks them. Pass another installed font with `--font` (the Font field on the Glyphs tab). |
| "no reading" warnings | The character isn't in Make Me a Hanzi (often radicals or rare forms). Use `--missing skip`. |
| The app asks for a folder on start | It looks for `data/` next to the exe. Choose any folder; **Download data** fills it. |
| Cells come out the wrong size on paper | Turn off "fit to page" / scaling in the print dialog. |
