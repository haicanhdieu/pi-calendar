"""DisplayPort adapter over the existing ILI9341 driver (device layer only)."""

from src import config
from src.device.display.font import draw_text
from src.gfx import clip_half_open, measure_font_text


class Ili9341DisplayPort:
    """
    Maps half-open DisplayPort rects/text to ILI9341 inclusive windows.

    Owns no pin/MADCTL changes; reuses the wrapped driver's SPI path and
    fill_rect semantics. Glyph drawing still goes through font helpers that
    call fill_rect on the underlying controller.
    """

    def __init__(self, display):
        self._display = display
        self.width = display.width
        self.height = display.height

    def fill_rect(self, x, y, w, h, color):
        clipped = clip_half_open(x, y, w, h, self.width, self.height)
        if clipped is None:
            return
        cx, cy, cw, ch = clipped
        self._display.fill_rect(cx, cy, cw, ch, color)

    def measure_text(self, text, font_id):
        return measure_font_text(text, font_id)

    def draw_text(self, text, x, y, font_id, color):
        scale = config.FONT_SCALES[font_id]
        draw_text(self._display, text, x, y, scale, color)
