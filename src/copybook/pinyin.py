"""Pinyin parsing, display and collation.

Make Me a Hanzi stores readings with tone marks ("xué", "le liǎo"), but tone
numbers ("xue2", "lv4") are accepted everywhere as well.
"""

from __future__ import annotations

import re
import unicodedata

# Combining marks produced by NFD decomposition of tone-marked vowels.
_TONE_MARKS = {
    "̄": 1,  # macron      ā
    "́": 2,  # acute       á
    "̌": 3,  # caron       ǎ
    "̀": 4,  # grave       à
}
_DIAERESIS = "̈"  # ü = u + U+0308

NEUTRAL_TONE = 5

_MARKED_VOWELS = {
    "a": "āáǎà",
    "e": "ēéěè",
    "i": "īíǐì",
    "o": "ōóǒò",
    "u": "ūúǔù",
    "ü": "ǖǘǚǜ",
}


def parse_syllable(syllable: str) -> tuple[str, int]:
    """Split one syllable into an ASCII collation base and a tone (1-5).

    ``ü`` becomes ``v`` in the base so that lü sorts after lu, luan and luo.

    >>> parse_syllable("xué")
    ('xue', 2)
    >>> parse_syllable("lv4")
    ('lv', 4)
    >>> parse_syllable("nǚ")
    ('nv', 3)
    >>> parse_syllable("de")
    ('de', 5)
    """
    s = syllable.strip().lower().replace("u:", "ü")
    tone = NEUTRAL_TONE

    numbered = re.fullmatch(r"(.*?)([1-5])", s)
    if numbered:
        s, tone = numbered.group(1), int(numbered.group(2))

    letters: list[str] = []
    for ch in unicodedata.normalize("NFD", s):
        if ch in _TONE_MARKS:
            tone = _TONE_MARKS[ch]
        elif ch == _DIAERESIS:
            if letters and letters[-1] == "u":
                letters[-1] = "v"
        elif unicodedata.category(ch) != "Mn":
            letters.append(ch)

    base = "".join(c for c in "".join(letters) if "a" <= c <= "z")
    return base, tone


def first_reading(readings: str) -> str:
    """The first of several space-separated readings ("le liǎo" -> "le")."""
    parts = readings.split()
    return parts[0] if parts else ""


def _mark_numbered(syllable: str) -> str:
    """Convert "xue2" to "xué"; anything without a tone number is returned as-is."""
    s = syllable.strip()
    m = re.fullmatch(r"(.*?)([1-5])", s)
    if not m:
        return s

    base = m.group(1).lower().replace("u:", "ü").replace("v", "ü")
    tone = int(m.group(2))
    if tone == NEUTRAL_TONE or not base:
        return base

    # Standard placement: a or e takes the mark; in "ou" the o does; otherwise
    # the last vowel (which covers iu -> u and ui -> i).
    if "a" in base:
        idx = base.index("a")
    elif "e" in base:
        idx = base.index("e")
    elif "ou" in base:
        idx = base.index("o")
    else:
        idx = max((base.rfind(v) for v in "aeiouü"), default=-1)

    if idx < 0:
        return base
    return base[:idx] + _MARKED_VOWELS[base[idx]][tone - 1] + base[idx + 1 :]


def to_display(readings: str) -> str:
    """Tone-marked display form of one or more readings."""
    return " ".join(_mark_numbered(part) for part in readings.split())


def sort_key(readings: str) -> tuple[str, int]:
    """Collation key of the first reading: (base, tone)."""
    return parse_syllable(first_reading(readings))


def initial(readings: str) -> str:
    """Upper-case index letter for a reading ("ü" files under its consonant)."""
    base, _ = sort_key(readings)
    return base[0].upper() if base else "#"
