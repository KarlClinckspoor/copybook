import json

import pytest

from copybook import CopybookError
from copybook.hanzi import collect_characters, extract_hanzi, is_hanzi
from copybook.learned import learned_characters


def test_is_hanzi():
    assert is_hanzi("学")
    assert is_hanzi("㐫")  # Extension A
    assert is_hanzi("𡗗")  # Extension B
    for ch in "⺀㇑，。！a1 ":
        assert not is_hanzi(ch), ch


def test_extract_keeps_order_and_duplicates():
    assert extract_hanzi("我是，我。abc 学") == ["我", "是", "我", "学"]


def test_collect_dedupes_and_reads_files(tmp_path):
    f = tmp_path / "chars.txt"
    f.write_text("# comment 不要\n学习\n学生\n", encoding="utf-8")
    assert collect_characters(["书学"], [f]) == ["书", "学", "习", "生"]
    assert collect_characters(["学学"], keep_duplicates=True) == ["学", "学"]


def test_missing_file(tmp_path):
    with pytest.raises(CopybookError):
        collect_characters(files=[tmp_path / "nope.txt"])


def test_learned_characters(tmp_path):
    export = tmp_path / "export.json"
    export.write_text(
        json.dumps({"学习": {}, "学习_reverse": {}, "“好”": {}, "⺀": {}, "囧": {}}),
        encoding="utf-8",
    )
    # Sorted by code point, reverse cards and non-hanzi ignored, exclusions applied.
    assert learned_characters(export, exclude="囧") == sorted("学习好")
