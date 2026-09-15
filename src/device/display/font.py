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
    """Draw one glyph cell at ``scale`` (int or float, e.g. 1.5).

    Each pixel's rect is the gap between two rounded boundary positions
    (``round(i * scale)``) rather than a fixed ``scale``x``scale`` square.
    For integer ``scale`` this collapses to the original exact grid (every
    boundary gap equals ``scale``). For a fractional ``scale`` it spreads
    the fractional pixel across the glyph as an even mix of smaller/larger
    pixels instead of rounding every pixel the same way -- e.g. scale=1.5
    renders as a mix of 1px and 2px pixels that average out to 1.5px.
    fill_rect is always called with plain ints (framebuf requires it).
    """
    base = _CHARS.find(char)
    base = _FALLBACK if base < 0 else base * GLYPH_ROWS
    # Column boundaries (6 of them, bounding GLYPH_COLS=5 pixels), computed
    # once per glyph and reused across rows.
    col_bounds = [round(c * scale) for c in range(GLYPH_COLS + 1)]
    for row_index in range(GLYPH_ROWS):
        row_bits = _GLYPHS[base + row_index]
        if not row_bits:
            continue
        row_y0 = round(row_index * scale)
        row_h = round((row_index + 1) * scale) - row_y0
        py = y + row_y0
        for col_index in range(GLYPH_COLS):
            if row_bits & (0x10 >> col_index):
                col_x0 = col_bounds[col_index]
                col_w = col_bounds[col_index + 1] - col_x0
                display.fill_rect(
                    x + col_x0,
                    py,
                    col_w,
                    row_h,
                    color,
                )


def draw_text(display, text, x, y, scale, color):
    """Draw ``text`` at ``scale`` (int or float).

    Per-character/per-line offsets are recomputed from the character/line
    index (``round(index * step)``) rather than accumulated by repeated
    float addition, so cursor position never drifts and always lands on an
    int -- draw_glyph (and fill_rect beneath it) never sees a float x/y.
    """
    step = 6 * scale
    line_step = 8 * scale
    cursor_x = x
    line_y = y
    col = 0
    line = 0
    for char in text:
        if char == "\n":
            line += 1
            line_y = y + round(line * line_step)
            cursor_x = x
            col = 0
            continue
        # Preserve middot; uppercase ASCII letters/digits for glyph lookup.
        if char == "·":
            glyph = char
        else:
            glyph = char.upper()
        draw_glyph(display, cursor_x, line_y, glyph, scale, color)
        col += 1
        cursor_x = x + round(col * step)


def text_width(text, scale):
    if not text:
        return 0
    return round((len(text) * 6 - 1) * scale)


def centered_text(display, text, y, scale, color):
    x = (display.width - text_width(text, scale)) // 2
    draw_text(display, text, x, y, scale, color)
