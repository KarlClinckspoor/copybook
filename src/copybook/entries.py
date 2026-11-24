"""Turning a list of characters into ordered copybook entries."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from copybook import CopybookError, pinyin
from copybook.data import HanziData


@dataclass(frozen=True)
class Entry:
    char: str
    readings: str  # every reading, tone-marked, space separated; "" if unknown
    strokes: tuple[str, ...] | None  # stroke outlines, None if Make Me a Hanzi lacks the character

    @property
    def reading(self) -> str:
        """The reading used for sorting, headers and the index."""
        return pinyin.to_display(pinyin.first_reading(self.readings)) or "?"

    @property
    def all_readings(self) -> str:
        return pinyin.to_display(self.readings) or "?"

    @property
    def stroke_count(self) -> int | None:
        return len(self.strokes) if self.strokes else None

    @property
    def initial(self) -> str:
        return pinyin.initial(self.readings) if self.readings else "#"

    def sort_key(self) -> tuple:
        """Pinyin, then tone, then stroke count, then code point; unknown readings last."""
        base, tone = pinyin.sort_key(self.readings)
        return (not self.readings, base, tone, self.stroke_count or 999, ord(self.char))


def warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def build_entries(chars: list[str], data: HanziData, order: str = "pinyin", missing: str = "warn") -> list[Entry]:
    """Look up every character; apply the missing-reading policy and the order."""
    entries: list[Entry] = []
    no_graphics: list[str] = []

    for ch in chars:
        readings = data.readings(ch) or ""
        if not readings:
            if missing == "error":
                raise CopybookError(f"No reading found for {ch} (U+{ord(ch):04X})")
            if missing == "skip":
                warn(f"skipping {ch}: no reading found")
                continue
            warn(f"no reading found for {ch}; it is listed under '?'")

        strokes = data.strokes(ch)
        if strokes is None:
            no_graphics.append(ch)
        entries.append(Entry(ch, readings, strokes))

    if no_graphics:
        warn(
            f"{len(no_graphics)} character(s) have no stroke data and will be typeset "
            f"with the font instead: {''.join(no_graphics)}"
        )

    if not entries:
        raise CopybookError("No characters left after looking up readings")

    if order == "pinyin":
        entries.sort(key=Entry.sort_key)
    return entries


def page_range(entries: list[Entry]) -> tuple[str, str]:
    """Dictionary-style running head: the first and last reading on a page."""
    return entries[0].reading, entries[-1].reading
