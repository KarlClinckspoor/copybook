"""Make Me a Hanzi data: downloading, converting to SQLite and querying.

Two files from https://github.com/skishore/makemeahanzi are used:

* ``dictionary.txt`` - readings (pinyin) per character
* ``graphics.txt``   - stroke outlines and medians, in stroke order

Both are JSON-lines files. They are converted once into SQLite databases so
look-ups during a build are fast.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from copybook import CopybookError

DEFAULT_DATA_DIR = Path("data/makemeahanzi")

_BASE_URLS = (
    "https://raw.githubusercontent.com/skishore/makemeahanzi/master",
    "https://raw.githubusercontent.com/skritter/makemeahanzi/master",
)


@dataclass(frozen=True)
class Dataset:
    name: str
    source: str  # file name in the upstream repository
    table: str

    def jsonl(self, data_dir: Path) -> Path:
        return data_dir / f"{self.name}.jsonl"

    def sqlite(self, data_dir: Path) -> Path:
        return data_dir / f"{self.name}.sqlite3"

    def urls(self) -> list[str]:
        return [f"{base}/{self.source}" for base in _BASE_URLS]


DICTIONARY = Dataset("dictionary", "dictionary.txt", "entries")
GRAPHICS = Dataset("graphics", "graphics.txt", "graphics")


# ---------------------------------------------------------------------------
# Preparation
# ---------------------------------------------------------------------------


def _download(urls: list[str], destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(destination.name + ".part")
    errors = []
    for url in urls:
        print(f"Downloading {url}")
        try:
            with urllib.request.urlopen(url, timeout=60) as response, open(tmp, "wb") as f:
                while chunk := response.read(1 << 20):
                    f.write(chunk)
            tmp.replace(destination)
            return
        except Exception as exc:  # noqa: BLE001 - try the next mirror
            errors.append(f"{url}: {exc}")
            tmp.unlink(missing_ok=True)
    raise CopybookError("Download failed:\n  " + "\n  ".join(errors))


def _iter_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _reading(obj: dict) -> str:
    value = obj.get("pinyin")
    if isinstance(value, list):
        return " ".join(str(v).strip() for v in value if str(v).strip())
    if isinstance(value, str):
        return value.strip()
    return ""


def _build_dictionary(jsonl: Path, db: Path) -> int:
    conn = sqlite3.connect(db)
    with conn:
        conn.execute(
            "CREATE TABLE entries (hanzi TEXT PRIMARY KEY, pinyin TEXT NOT NULL, definition TEXT)"
        )
        rows = (
            (obj.get("character"), _reading(obj), str(obj.get("definition") or ""))
            for obj in _iter_jsonl(jsonl)
        )
        conn.executemany(
            "INSERT OR REPLACE INTO entries VALUES (?, ?, ?)",
            (r for r in rows if isinstance(r[0], str) and len(r[0]) == 1 and r[1]),
        )
    count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
    conn.close()
    return count


def _build_graphics(jsonl: Path, db: Path) -> int:
    conn = sqlite3.connect(db)
    with conn:
        conn.execute(
            "CREATE TABLE graphics (hanzi TEXT PRIMARY KEY, strokes TEXT NOT NULL, medians TEXT)"
        )
        rows = (
            (
                obj.get("character"),
                json.dumps(obj.get("strokes")),
                json.dumps(obj.get("medians")) if obj.get("medians") else None,
            )
            for obj in _iter_jsonl(jsonl)
            if isinstance(obj.get("character"), str)
            and len(obj["character"]) == 1
            and isinstance(obj.get("strokes"), list)
            and obj["strokes"]
        )
        conn.executemany("INSERT OR REPLACE INTO graphics VALUES (?, ?, ?)", rows)
    count = conn.execute("SELECT COUNT(*) FROM graphics").fetchone()[0]
    conn.close()
    return count


def _row_count(db: Path, table: str) -> int:
    if not db.is_file():
        return 0
    try:
        with sqlite3.connect(db) as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.Error:
        return 0


def prepare(data_dir: Path = DEFAULT_DATA_DIR, force_download: bool = False, force_build: bool = False) -> None:
    """Download both datasets (if missing) and build their SQLite databases."""
    builders = {DICTIONARY: _build_dictionary, GRAPHICS: _build_graphics}
    for dataset, build in builders.items():
        jsonl, db = dataset.jsonl(data_dir), dataset.sqlite(data_dir)

        if force_download or not jsonl.is_file() or jsonl.stat().st_size == 0:
            _download(dataset.urls(), jsonl)
        else:
            print(f"Using existing {jsonl}")

        if force_build or force_download or _row_count(db, dataset.table) == 0:
            db.unlink(missing_ok=True)
            count = build(jsonl, db)
            if count == 0:
                db.unlink(missing_ok=True)
                raise CopybookError(f"{jsonl} produced no rows; is it the right file?")
            print(f"Built {db} ({count} characters)")
        else:
            print(f"Using existing {db} ({_row_count(db, dataset.table)} characters)")


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


class HanziData:
    """Read-only access to readings and stroke graphics."""

    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR):
        self._conns: dict[str, sqlite3.Connection] = {}
        for dataset in (DICTIONARY, GRAPHICS):
            db = dataset.sqlite(Path(data_dir))
            if _row_count(db, dataset.table) == 0:
                raise CopybookError(
                    f"Missing or empty database: {db}\nRun `copybook data` to download and build it."
                )
            self._conns[dataset.name] = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        self.readings = lru_cache(maxsize=None)(self._readings)
        self.strokes = lru_cache(maxsize=None)(self._strokes)

    def _readings(self, char: str) -> str | None:
        """Space-separated tone-marked readings, or None if unknown."""
        row = self._conns["dictionary"].execute(
            "SELECT pinyin FROM entries WHERE hanzi = ?", (char,)
        ).fetchone()
        return row[0] if row else None

    def _strokes(self, char: str) -> tuple[str, ...] | None:
        """SVG path data per stroke in writing order, or None if unknown."""
        row = self._conns["graphics"].execute(
            "SELECT strokes FROM graphics WHERE hanzi = ?", (char,)
        ).fetchone()
        return tuple(json.loads(row[0])) if row else None

    def close(self) -> None:
        for conn in self._conns.values():
            conn.close()

    def __enter__(self) -> HanziData:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
