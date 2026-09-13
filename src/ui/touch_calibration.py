"""Map raw XPT2046 samples onto screen pixel coordinates.

TouchPort deliberately returns raw, uncalibrated ADC values (see its
docstring); this module is the one place that knows the physical panel is
mounted rotated relative to the display, so raw X tracks screen Y and raw Y
tracks screen X.
"""

from src import config


def _scale(value, raw_min, raw_max, screen_max):
    if raw_max == raw_min:
        return 0
    scaled = (value - raw_min) * screen_max // (raw_max - raw_min)
    if scaled < 0:
        return 0
    if scaled > screen_max:
        return screen_max
    return scaled


def calibrate_touch_point(raw_x, raw_y):
    """Return ``(screen_x, screen_y)`` for a raw ``(x, y)`` touch sample."""
    screen_x = _scale(
        raw_y, config.TOUCH_RAW_Y_MIN, config.TOUCH_RAW_Y_MAX, config.SCREEN_WIDTH - 1
    )
    screen_y = _scale(
        raw_x, config.TOUCH_RAW_X_MIN, config.TOUCH_RAW_X_MAX, config.SCREEN_HEIGHT - 1
    )
    return screen_x, screen_y


class CalibratedTouchPort:
    """Wrap a raw TouchPort, translating its samples to screen pixels."""

    def __init__(self, touch_port):
        self._touch_port = touch_port

    def read(self):
        edge_down, x, y = self._touch_port.read()
        if x is not None and y is not None:
            x, y = calibrate_touch_point(x, y)
        return edge_down, x, y
