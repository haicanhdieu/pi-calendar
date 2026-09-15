"""Neutral geometry helpers shared by UI and device display layers."""

from src import config
from src.device.display.font import text_width as _glyph_text_width


def measure_font_text(text, font_id):
    """Return (width, height) for a stable font_id using config cell metrics.

    ``scale`` may be a fractional value (e.g. 1.5); width delegates to
    ``font.text_width`` so layout math always matches what draw_text
    actually renders, and height is rounded the same way draw_text rounds
    a line's pixel height.
    """
    scale = config.FONT_SCALES[font_id]
    height = round(config.FONT_CELL_HEIGHT * scale)
    if not text:
        return (0, height)
    width = _glyph_text_width(text, scale)
    return (width, height)


def measure_spaced_font_text(text, font_id, letter_spacing_px):
    """Return (width, height) with extra pixel spacing between glyph cells."""
    scale = config.FONT_SCALES[font_id]
    height = round(config.FONT_CELL_HEIGHT * scale)
    if not text:
        return (0, height)
    width, _ = measure_font_text(text, font_id)
    if len(text) > 1:
        width += (len(text) - 1) * letter_spacing_px
    return (width, height)


def draw_spaced_text(display, text, x, y, font_id, color, letter_spacing_px):
    """Draw text with fixed extra spacing between characters."""
    scale = config.FONT_SCALES[font_id]
    cursor_x = x
    step = config.FONT_CELL_WIDTH * scale + letter_spacing_px
    for char in text:
        display.draw_text(char, cursor_x, y, font_id, color)
        cursor_x += step


def clip_half_open(x, y, w, h, width, height):
    """Clip a half-open rect to [0, width) × [0, height); return None if empty."""
    if w <= 0 or h <= 0:
        return None
    x0 = x if x > 0 else 0
    y0 = y if y > 0 else 0
    x1 = x + w
    y1 = y + h
    if x1 > width:
        x1 = width
    if y1 > height:
        y1 = height
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1 - x0, y1 - y0)
