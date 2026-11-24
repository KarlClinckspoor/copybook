import pytest

from copybook import pinyin


@pytest.mark.parametrize(
    "syllable, expected",
    [
        ("xué", ("xue", 2)),
        ("zhōng", ("zhong", 1)),
        ("nǚ", ("nv", 3)),
        ("lǜ", ("lv", 4)),
        ("lüè", ("lve", 4)),
        ("de", ("de", 5)),
        ("xue2", ("xue", 2)),
        ("lv4", ("lv", 4)),
        ("lu:4", ("lv", 4)),
        ("ZHANG3", ("zhang", 3)),
    ],
)
def test_parse_syllable(syllable, expected):
    assert pinyin.parse_syllable(syllable) == expected


def test_tone_marks_sort_by_tone():
    # Regression: tone-marked readings used to be treated as toneless.
    readings = ["ào", "áo", "āo", "ǎo"]
    assert sorted(readings, key=pinyin.sort_key) == ["āo", "áo", "ǎo", "ào"]


def test_u_umlaut_sorts_after_u():
    readings = ["lǚ", "luó", "lù", "luàn"]
    assert sorted(readings, key=pinyin.sort_key) == ["lù", "luàn", "luó", "lǚ"]


def test_neutral_tone_sorts_last():
    assert sorted(["ma", "mà", "mā"], key=pinyin.sort_key) == ["mā", "mà", "ma"]


def test_first_reading_is_used():
    assert pinyin.sort_key("le liǎo") == ("le", 5)
    assert pinyin.first_reading("le liǎo") == "le"


@pytest.mark.parametrize(
    "numbered, marked",
    [
        ("xue2", "xué"),
        ("zhong1", "zhōng"),
        ("lv4", "lǜ"),
        ("gou3", "gǒu"),
        ("liu2", "liú"),
        ("gui4", "guì"),
        ("guo2", "guó"),
        ("de5", "de"),
        ("xué", "xué"),
    ],
)
def test_to_display(numbered, marked):
    assert pinyin.to_display(numbered) == marked


def test_initial():
    assert pinyin.initial("nǚ") == "N"
    assert pinyin.initial("ài") == "A"
    assert pinyin.initial("") == "#"
