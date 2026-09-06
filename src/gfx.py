"""Neutral geometry helpers shared by UI and device display layers."""

from src import config


def measure_font_text(text, font_id):
    """Return (width, height) for a stable font_id using config cell metrics."""
    scale = config.FONT_SCALES[font_id]
    height = config.FONT_CELL_HEIGHT * scale
    if not text:
        return (0, height)
    width = (len(text) * config.FONT_CELL_WIDTH - 1) * scale
    return (width, height)


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
