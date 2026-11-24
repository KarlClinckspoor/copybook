"""The GUI turns its option values into exactly the command a user would type."""

import pytest

pytest.importorskip("tkinter")

from copybook import gui
from copybook.cli import build_parser


def defaults(**changes):
    values = {key: default for key, _, _, default, _ in gui.OPTIONS}
    values.update({"kind": "dense", "files": [], **changes})
    return values


def test_defaults_give_a_bare_command():
    assert gui.command_args(defaults()) == ["dense"]
    assert gui.command_args(defaults(kind="practice")) == ["practice"]


def test_changed_options_and_flags():
    args = gui.command_args(
        defaults(kind="rows", cell="18", pattern="tian", markers=False, stroke_order=False, impose=True, chars="永和 九年")
    )
    assert args[0] == "rows"
    assert ["--cell", "18"] == args[args.index("--cell") : args.index("--cell") + 2]
    assert "--no-markers" in args and "--no-stroke-order" in args and "--impose" in args
    assert args[args.index("--chars") + 1 : args.index("--chars") + 3] == ["永和", "九年"]


def test_numbers_equal_to_default_are_omitted():
    assert gui.command_args(defaults(cell="15.0", border="5")) == ["dense"]


def test_options_only_go_to_commands_that_accept_them():
    args = gui.command_args(defaults(kind="practice", traces="5", glyph_scale="0.8", pages="4", files=["x.txt"]))
    assert args == ["practice", "--pages", "4"]


@pytest.mark.parametrize("kind", ["practice", "dense", "rows"])
def test_every_generated_command_parses(kind):
    everything = defaults(
        kind=kind, files=["input/learned_chars.txt"], chars="学", pages="3", page_numbers=True, traces="2",
        index=False, book_qr=False, book_id="abc", title="T", shade_strokes=True, landscape=True,
        line_ink="50", output="out.pdf",
    )
    build_parser().parse_args(gui.command_args(everything))  # raises SystemExit on a bad flag
