"""DisplayPort contract and host FakeDisplayPort (AD-11)."""

from src import config
from src.gfx import clip_half_open, measure_font_text


class FakeDisplayPort:
    """Host test surface: records clipped ops; no pixel framebuffer."""

    def __init__(self, width=config.SCREEN_WIDTH, height=config.SCREEN_HEIGHT):
        self.width = width
        self.height = height
        self.ops = []

    def clear_ops(self):
        self.ops = []

    def fill_rect(self, x, y, w, h, color):
        clipped = clip_half_open(x, y, w, h, self.width, self.height)
        if clipped is None:
            return
        cx, cy, cw, ch = clipped
        self.ops.append(("fill_rect", cx, cy, cw, ch, color))

    def measure_text(self, text, font_id):
        return measure_font_text(text, font_id)

    def draw_text(self, text, x, y, font_id, color):
        self.ops.append(("draw_text", text, x, y, font_id, color))
