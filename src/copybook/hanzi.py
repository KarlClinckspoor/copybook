"""Recognising and collecting Chinese characters from free text."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from copybook import CopybookError

# Unified ideographs and their extensions. Radical supplements, CJK strokes
# and punctuation are deliberately excluded: they are not practice characters.
HANZI_RANGES: tuple[tuple[int, int], ...] = (
    (0x3400, 0x4DBF),  # Extension A
    (0x4E00, 0x9FFF),  # Unified Ideographs
    (0xF900, 0xFAFF),  # Compatibility Ideographs
    (0x20000, 0x2EE5F),  # Extensions B-F, I
    (0x2F800, 0x2FA1F),  # Compatibility Supplement
    (0x30000, 0x323AF),  # Extensions G-H
)


def is_hanzi(ch: str) -> bool:
    if len(ch) != 1:
        return False
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in HANZI_RANGES)


def extract_hanzi(text: str) -> list[str]:
    """Return every Chinese character in ``text``, in order, duplicates kept."""
    return [ch for ch in text if is_hanzi(ch)]


def unique(chars: Iterable[str]) -> list[str]:
    """Drop repeated characters, keeping the first occurrence."""
    return list(dict.fromkeys(chars))


def read_character_file(path: Path) -> str:
    """Text of a UTF-8 character list, without lines starting with ``#``."""
    path = Path(path)
    if not path.is_file():
        raise CopybookError(f"Character file not found: {path}")
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def collect_characters(
    texts: Iterable[str] = (),
    files: Iterable[Path] = (),
    keep_duplicates: bool = False,
) -> list[str]:
    """Gather characters from command-line strings and character files."""
    chars: list[str] = []
    for text in texts:
        chars.extend(extract_hanzi(text))
    for path in files:
        chars.extend(extract_hanzi(read_character_file(path)))
    return chars if keep_duplicates else unique(chars)
