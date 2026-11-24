"""Extracting the characters you have studied from a flashcard progress export.

The export is a JSON object whose keys are the studied items (characters,
words or sentences). Keys ending in ``_reverse`` are the reverse cards of the
same items and are ignored.
"""

from __future__ import annotations

import json
from pathlib import Path

from copybook import CopybookError
from copybook.hanzi import extract_hanzi


def learned_characters(export: Path, exclude: str = "") -> list[str]:
    """Unique characters from the export, in code-point order (stable between runs)."""
    export = Path(export)
    if not export.is_file():
        raise CopybookError(f"Progress export not found: {export}")
    try:
        progress = json.loads(export.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CopybookError(f"{export} is not valid JSON: {exc}") from exc

    excluded = set(extract_hanzi(exclude))
    chars = {
        ch
        for key in progress
        if not key.endswith("_reverse")
        for ch in extract_hanzi(key)
        if ch not in excluded
    }
    return sorted(chars)
