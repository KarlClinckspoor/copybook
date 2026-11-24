# Examples

Run these from the repository root after `uv sync` and `uv run copybook data`.
Each one writes a PDF to `output/`. Add `--no-markers` for plain pages without the corner codes.

## Practice sheets

```bash
# A5 mi grid, 16 pages (the defaults)
uv run copybook practice

# Large tian cells for beginners, page numbers on, A4
uv run copybook practice --pattern tian --cell 25 --paper a4 --page-numbers

# Tall hui cells, stretched to fill the page, fainter guides
uv run copybook practice --pattern hui-tall --fit fill --guide-ink 30

# 32 pages imposed as an A4 booklet for double-sided printing
uv run copybook practice --pages 32 --impose
```

## Books from a text

[`lanting.txt`](lanting.txt) holds the opening of the Lanting Xu (兰亭序).

```bash
# Rows book in reading order: model, three tracing copies, stroke order
uv run copybook rows --file examples/lanting.txt --order input

# More tracing copies, a bit darker
uv run copybook rows --file examples/lanting.txt --order input --traces 5 --trace-ink 25

# Dense reference book sorted by pinyin, strokes shaded to show their order
uv run copybook dense --file examples/lanting.txt --shade-strokes

# Characters straight from the command line, centred in the cell
uv run copybook rows --chars 春眠不觉晓 --align center
```

## Your own study list

```bash
# Turn a flashcard progress export into a character list, minus characters you want to skip
uv run copybook learned-chars my_export.json --exclude input/excluded_chars.txt -o input/learned_chars.txt

# Then make both books from it
uv run copybook dense --file input/learned_chars.txt --impose
uv run copybook rows --file input/learned_chars.txt
```

## Sample output

The [releases page](https://github.com/KarlClinckspoor/copybook/releases/latest) has PDFs made with these commands (with `--no-markers`).
