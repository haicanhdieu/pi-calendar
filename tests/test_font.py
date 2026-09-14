"""Glyph-level regression guard for the packed 5x7 font.

The lit-pixel coordinates below were captured from the previous
dict-of-strings ``FONT_5X7`` table before it was repacked into a ``bytes``
blob (see ``src/device/display/font.py``).  They pin the rendered output so
the memory representation can change again without silently altering a
pixel.
"""

import pytest

from src.device.display import font


class RecordingDisplay:
    width = 320
    height = 240

    def __init__(self):
        self.ops = []

    def fill_rect(self, x, y, w, h, color):
        self.ops.append((x, y, w, h, color))


# char -> lit pixel (x, y) offsets at scale 1, origin (0, 0).
GOLDEN = {
    ' ': [],
    '.': [(1, 5), (2, 5), (1, 6), (2, 6)],
    '·': [(2, 2), (1, 3), (2, 3), (3, 3), (2, 4)],
    '-': [(0, 3), (1, 3), (2, 3), (3, 3), (4, 3)],
    '/': [(4, 0), (3, 1), (2, 2), (1, 3), (0, 4)],
    '+': [(2, 1), (2, 2), (0, 3), (1, 3), (2, 3), (3, 3), (4, 3), (2, 4), (2, 5)],
    ':': [(1, 1), (2, 1), (1, 2), (2, 2), (1, 4), (2, 4), (1, 5), (2, 5)],
    '0': [(1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (0, 2), (3, 2), (4, 2), (0, 3), (2, 3), (4, 3), (0, 4), (1, 4), (4, 4), (0, 5), (4, 5), (1, 6), (2, 6), (3, 6)],
    '1': [(2, 0), (1, 1), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (1, 6), (2, 6), (3, 6)],
    '2': [(1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (4, 2), (3, 3), (2, 4), (1, 5), (0, 6), (1, 6), (2, 6), (3, 6), (4, 6)],
    '3': [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (3, 1), (2, 2), (3, 3), (4, 4), (0, 5), (4, 5), (1, 6), (2, 6), (3, 6)],
    '4': [(3, 0), (2, 1), (3, 1), (1, 2), (3, 2), (0, 3), (3, 3), (0, 4), (1, 4), (2, 4), (3, 4), (4, 4), (3, 5), (3, 6)],
    '5': [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (0, 1), (0, 2), (1, 2), (2, 2), (3, 2), (4, 3), (4, 4), (0, 5), (4, 5), (1, 6), (2, 6), (3, 6)],
    '6': [(2, 0), (3, 0), (1, 1), (0, 2), (0, 3), (1, 3), (2, 3), (3, 3), (0, 4), (4, 4), (0, 5), (4, 5), (1, 6), (2, 6), (3, 6)],
    '7': [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (4, 1), (3, 2), (2, 3), (1, 4), (1, 5), (1, 6)],
    '8': [(1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (0, 2), (4, 2), (1, 3), (2, 3), (3, 3), (0, 4), (4, 4), (0, 5), (4, 5), (1, 6), (2, 6), (3, 6)],
    '9': [(1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (0, 2), (4, 2), (1, 3), (2, 3), (3, 3), (4, 3), (4, 4), (3, 5), (1, 6), (2, 6)],
    '?': [(1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (4, 2), (3, 3), (2, 4), (2, 6)],
    'A': [(1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (0, 2), (4, 2), (0, 3), (1, 3), (2, 3), (3, 3), (4, 3), (0, 4), (4, 4), (0, 5), (4, 5), (0, 6), (4, 6)],
    'B': [(0, 0), (1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (0, 2), (4, 2), (0, 3), (1, 3), (2, 3), (3, 3), (0, 4), (4, 4), (0, 5), (4, 5), (0, 6), (1, 6), (2, 6), (3, 6)],
    'C': [(1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (0, 2), (0, 3), (0, 4), (0, 5), (4, 5), (1, 6), (2, 6), (3, 6)],
    'D': [(0, 0), (1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (0, 2), (4, 2), (0, 3), (4, 3), (0, 4), (4, 4), (0, 5), (4, 5), (0, 6), (1, 6), (2, 6), (3, 6)],
    'E': [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (0, 1), (0, 2), (0, 3), (1, 3), (2, 3), (3, 3), (0, 4), (0, 5), (0, 6), (1, 6), (2, 6), (3, 6), (4, 6)],
    'F': [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (0, 1), (0, 2), (0, 3), (1, 3), (2, 3), (3, 3), (0, 4), (0, 5), (0, 6)],
    'G': [(1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (0, 2), (0, 3), (2, 3), (3, 3), (4, 3), (0, 4), (4, 4), (0, 5), (4, 5), (1, 6), (2, 6), (3, 6)],
    'H': [(0, 0), (4, 0), (0, 1), (4, 1), (0, 2), (4, 2), (0, 3), (1, 3), (2, 3), (3, 3), (4, 3), (0, 4), (4, 4), (0, 5), (4, 5), (0, 6), (4, 6)],
    'I': [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (0, 6), (1, 6), (2, 6), (3, 6), (4, 6)],
    'J': [(2, 0), (3, 0), (4, 0), (3, 1), (3, 2), (3, 3), (3, 4), (0, 5), (3, 5), (1, 6), (2, 6)],
    'K': [(0, 0), (4, 0), (0, 1), (3, 1), (0, 2), (2, 2), (0, 3), (1, 3), (0, 4), (2, 4), (0, 5), (3, 5), (0, 6), (4, 6)],
    'L': [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (0, 6), (1, 6), (2, 6), (3, 6), (4, 6)],
    'M': [(0, 0), (4, 0), (0, 1), (1, 1), (3, 1), (4, 1), (0, 2), (2, 2), (4, 2), (0, 3), (4, 3), (0, 4), (4, 4), (0, 5), (4, 5), (0, 6), (4, 6)],
    'N': [(0, 0), (4, 0), (0, 1), (1, 1), (4, 1), (0, 2), (2, 2), (4, 2), (0, 3), (3, 3), (4, 3), (0, 4), (4, 4), (0, 5), (4, 5), (0, 6), (4, 6)],
    'O': [(1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (0, 2), (4, 2), (0, 3), (4, 3), (0, 4), (4, 4), (0, 5), (4, 5), (1, 6), (2, 6), (3, 6)],
    'P': [(0, 0), (1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (0, 2), (4, 2), (0, 3), (1, 3), (2, 3), (3, 3), (0, 4), (0, 5), (0, 6)],
    'R': [(0, 0), (1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (0, 2), (4, 2), (0, 3), (1, 3), (2, 3), (3, 3), (0, 4), (2, 4), (0, 5), (3, 5), (0, 6), (4, 6)],
    'S': [(1, 0), (2, 0), (3, 0), (4, 0), (0, 1), (0, 2), (1, 3), (2, 3), (3, 3), (4, 4), (4, 5), (0, 6), (1, 6), (2, 6), (3, 6)],
    'T': [(0, 0), (1, 0), (2, 0), (3, 0), (4, 0), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6)],
    'U': [(0, 0), (4, 0), (0, 1), (4, 1), (0, 2), (4, 2), (0, 3), (4, 3), (0, 4), (4, 4), (0, 5), (4, 5), (1, 6), (2, 6), (3, 6)],
    'V': [(0, 0), (4, 0), (0, 1), (4, 1), (0, 2), (4, 2), (0, 3), (4, 3), (0, 4), (4, 4), (1, 5), (3, 5), (2, 6)],
    'W': [(0, 0), (4, 0), (0, 1), (4, 1), (0, 2), (4, 2), (0, 3), (2, 3), (4, 3), (0, 4), (2, 4), (4, 4), (0, 5), (2, 5), (4, 5), (1, 6), (3, 6)],
    'Y': [(0, 0), (4, 0), (0, 1), (4, 1), (1, 2), (3, 2), (2, 3), (2, 4), (2, 5), (2, 6)],
}


@pytest.mark.parametrize("char", sorted(GOLDEN))
def test_glyph_pixels_match_pre_packing_table(char):
    display = RecordingDisplay()
    font.draw_glyph(display, 0, 0, char, 1, 0xF81F)
    assert [(x, y) for x, y, _w, _h, _c in display.ops] == GOLDEN[char]


@pytest.mark.parametrize("char", sorted(GOLDEN))
def test_glyph_cells_are_scale_sized_and_coloured(char):
    display = RecordingDisplay()
    font.draw_glyph(display, 3, 5, char, 4, 0x07E0)
    for x, y, w, h, color in display.ops:
        assert (w, h, color) == (4, 4, 0x07E0)
        assert (x - 3) % 4 == 0 and (y - 5) % 4 == 0


@pytest.mark.parametrize("unknown", ["~", "\x00", "Q", "X", "Z", "a", "\u03a9"])
def test_unknown_characters_render_the_question_mark_glyph(unknown):
    missing = RecordingDisplay()
    fallback = RecordingDisplay()
    font.draw_glyph(missing, 0, 0, unknown, 1, 1)
    font.draw_glyph(fallback, 0, 0, "?", 1, 1)
    assert missing.ops == fallback.ops


def test_lowercase_is_folded_to_uppercase_by_draw_text():
    lower = RecordingDisplay()
    upper = RecordingDisplay()
    font.draw_text(lower, "abc-9", 0, 0, 2, 7)
    font.draw_text(upper, "ABC-9", 0, 0, 2, 7)
    assert lower.ops == upper.ops


def test_middot_keeps_its_own_glyph_and_is_not_uppercased():
    dot = RecordingDisplay()
    font.draw_text(dot, "\u00b7", 0, 0, 1, 1)
    pixels = [(x, y) for x, y, _w, _h, _c in dot.ops]
    assert pixels == GOLDEN["\u00b7"] and pixels != []
    assert pixels != GOLDEN["?"]


def test_newline_resets_cursor_and_advances_a_row():
    wrapped = RecordingDisplay()
    font.draw_text(wrapped, "A\nA", 10, 20, 3, 1)
    half = len(wrapped.ops) // 2
    first, second = wrapped.ops[:half], wrapped.ops[half:]
    assert [(x, y - 8 * 3) for x, y, _w, _h, _c in second] == [
        (x, y) for x, y, _w, _h, _c in first
    ]


def test_blank_glyph_emits_nothing():
    display = RecordingDisplay()
    font.draw_glyph(display, 0, 0, " ", 9, 1)
    assert display.ops == []


@pytest.mark.parametrize(
    "text, scale, expected",
    [("", 1, 0), ("", 9, 0), ("A", 1, 5), ("A", 3, 15), ("AB", 1, 11)],
)
def test_text_width(text, scale, expected):
    assert font.text_width(text, scale) == expected


def test_centered_text_centres_on_display_width():
    display = RecordingDisplay()
    font.centered_text(display, "AB", 0, 1, 1)
    expected_x = (display.width - font.text_width("AB", 1)) // 2
    assert min(x for x, _y, _w, _h, _c in display.ops) == expected_x


def test_glyph_blob_is_a_single_allocation_of_the_expected_size():
    # Guards the memory fix itself: one bytes object, seven bytes per glyph.
    assert isinstance(font._GLYPHS, bytes)
    assert len(font._GLYPHS) == len(font._CHARS) * font.GLYPH_ROWS
    assert max(font._GLYPHS) < 1 << font.GLYPH_COLS
