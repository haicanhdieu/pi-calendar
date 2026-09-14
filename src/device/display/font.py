"""5x7 bitmap font, packed as a single ``bytes`` blob.

The glyph table was a ``dict`` of tuples of ``"01010"`` strings.  That is
~400 separate objects on the Pico heap -- one per row string, plus a tuple
and a dict entry per glyph -- and measured 24,544 bytes that are allocated
at import and never released.  The same pixels as one byte-per-row blob
cost two objects and 1,664 bytes, which is most of the contiguous headroom
the station web surface needs on first request.

Layout: ``_CHARS[i]`` owns ``_GLYPHS[i * 7 : i * 7 + 7]``, one byte per row,
top row first.  Within a row the low five bits are the columns, leftmost
column in bit 4.  Unknown characters fall back to ``?``.
"""

GLYPH_ROWS = 7
GLYPH_COLS = 5

_CHARS = ' .·-/+:0123456789?ABCDEFGHIJKLMNOPRSTUVWY'
_GLYPHS = (
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0c\x0c\x00\x00'
    b'\x04\x0e\x04\x00\x00\x00\x00\x00\x1f\x00\x00\x00\x01\x02\x04\x08'
    b'\x10\x00\x00\x00\x04\x04\x1f\x04\x04\x00\x00\x0c\x0c\x00\x0c\x0c'
    b'\x00\x0e\x11\x13\x15\x19\x11\x0e\x04\x0c\x04\x04\x04\x04\x0e\x0e'
    b'\x11\x01\x02\x04\x08\x1f\x1f\x02\x04\x02\x01\x11\x0e\x02\x06\n'
    b'\x12\x1f\x02\x02\x1f\x10\x1e\x01\x01\x11\x0e\x06\x08\x10\x1e\x11'
    b'\x11\x0e\x1f\x01\x02\x04\x08\x08\x08\x0e\x11\x11\x0e\x11\x11\x0e'
    b'\x0e\x11\x11\x0f\x01\x02\x0c\x0e\x11\x01\x02\x04\x00\x04\x0e\x11'
    b'\x11\x1f\x11\x11\x11\x1e\x11\x11\x1e\x11\x11\x1e\x0e\x11\x10\x10'
    b'\x10\x11\x0e\x1e\x11\x11\x11\x11\x11\x1e\x1f\x10\x10\x1e\x10\x10'
    b'\x1f\x1f\x10\x10\x1e\x10\x10\x10\x0e\x11\x10\x17\x11\x11\x0e\x11'
    b'\x11\x11\x1f\x11\x11\x11\x1f\x04\x04\x04\x04\x04\x1f\x07\x02\x02'
    b'\x02\x02\x12\x0c\x11\x12\x14\x18\x14\x12\x11\x10\x10\x10\x10\x10'
    b'\x10\x1f\x11\x1b\x15\x11\x11\x11\x11\x11\x19\x15\x13\x11\x11\x11'
    b'\x0e\x11\x11\x11\x11\x11\x0e\x1e\x11\x11\x1e\x10\x10\x10\x1e\x11'
    b'\x11\x1e\x14\x12\x11\x0f\x10\x10\x0e\x01\x01\x1e\x1f\x04\x04\x04'
    b'\x04\x04\x04\x11\x11\x11\x11\x11\x11\x0e\x11\x11\x11\x11\x11\n'
    b'\x04\x11\x11\x11\x15\x15\x15\n\x11\x11\n\x04\x04\x04\x04'
)
_FALLBACK = _CHARS.index("?") * GLYPH_ROWS


def draw_glyph(display, x, y, char, scale, color):
    base = _CHARS.find(char)
    base = _FALLBACK if base < 0 else base * GLYPH_ROWS
    for row_index in range(GLYPH_ROWS):
        row_bits = _GLYPHS[base + row_index]
        if not row_bits:
            continue
        py = y + (row_index * scale)
        for col_index in range(GLYPH_COLS):
            if row_bits & (0x10 >> col_index):
                display.fill_rect(
                    x + (col_index * scale),
                    py,
                    scale,
                    scale,
                    color,
                )


def draw_text(display, text, x, y, scale, color):
    cursor_x = x
    step = 6 * scale
    for char in text:
        if char == "\n":
            y += 8 * scale
            cursor_x = x
            continue
        # Preserve middot; uppercase ASCII letters/digits for glyph lookup.
        if char == "·":
            glyph = char
        else:
            glyph = char.upper()
        draw_glyph(display, cursor_x, y, glyph, scale, color)
        cursor_x += step


def text_width(text, scale):
    if not text:
        return 0
    return (len(text) * 6 - 1) * scale


def centered_text(display, text, y, scale, color):
    x = (display.width - text_width(text, scale)) // 2
    draw_text(display, text, x, y, scale, color)
