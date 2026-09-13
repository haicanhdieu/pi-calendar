"""Host coverage for raw-touch-to-screen-pixel calibration."""

from src import config
from src.ui.touch_calibration import CalibratedTouchPort, calibrate_touch_point


def test_corners_map_to_screen_bounds():
    assert calibrate_touch_point(config.TOUCH_RAW_X_MIN, config.TOUCH_RAW_Y_MIN) == (
        0,
        0,
    )
    assert calibrate_touch_point(config.TOUCH_RAW_X_MIN, config.TOUCH_RAW_Y_MAX) == (
        config.SCREEN_WIDTH - 1,
        0,
    )
    assert calibrate_touch_point(config.TOUCH_RAW_X_MAX, config.TOUCH_RAW_Y_MIN) == (
        0,
        config.SCREEN_HEIGHT - 1,
    )
    assert calibrate_touch_point(config.TOUCH_RAW_X_MAX, config.TOUCH_RAW_Y_MAX) == (
        config.SCREEN_WIDTH - 1,
        config.SCREEN_HEIGHT - 1,
    )


def test_out_of_range_raw_values_clamp_to_screen_bounds():
    assert calibrate_touch_point(0, 0) == (0, 0)
    assert calibrate_touch_point(4095, 4095) == (
        config.SCREEN_WIDTH - 1,
        config.SCREEN_HEIGHT - 1,
    )


class FakeTouchPort:
    def __init__(self, samples):
        self._samples = iter(samples)

    def read(self):
        return next(self._samples)


def test_calibrated_wrapper_translates_edge_samples():
    port = CalibratedTouchPort(
        FakeTouchPort([(True, config.TOUCH_RAW_X_MAX, config.TOUCH_RAW_Y_MAX)])
    )
    assert port.read() == (True, config.SCREEN_WIDTH - 1, config.SCREEN_HEIGHT - 1)


def test_calibrated_wrapper_passes_through_no_contact():
    port = CalibratedTouchPort(FakeTouchPort([(False, None, None)]))
    assert port.read() == (False, None, None)
