"""Non-secret hardware and product defaults (AD-9)."""

# TFT wiring — SPI0 (docs/hardware_configuration.md)
TFT_MISO = 16
TFT_CS = 17
TFT_SCK = 18
TFT_MOSI = 19
TFT_DC = 20
TFT_RST = 21

# Display geometry and SPI
SCREEN_WIDTH = 320
SCREEN_HEIGHT = 240
SPI_BAUDRATE = 40_000_000
SPI_POLARITY = 0
SPI_PHASE = 0
MADCTL = 0xA8

# Instrument-panel palette seeds (RGB888); convert at the display boundary.
COLOR_BACKGROUND_RGB = (0x03, 0x14, 0x06)
COLOR_PRIMARY_RGB = (0x3D, 0xFF, 0x7A)
COLOR_SECONDARY_RGB = (0x1C, 0x6B, 0x38)
COLOR_UNSYNCED_RGB = (0xFF, 0x6B, 0x3D)


def rgb888_to_rgb565(red, green, blue):
    """Pack an RGB888 triple into a high-byte-first RGB565 integer."""
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)


COLOR_BACKGROUND = rgb888_to_rgb565(*COLOR_BACKGROUND_RGB)
COLOR_PRIMARY = rgb888_to_rgb565(*COLOR_PRIMARY_RGB)
COLOR_SECONDARY = rgb888_to_rgb565(*COLOR_SECONDARY_RGB)
COLOR_UNSYNCED = rgb888_to_rgb565(*COLOR_UNSYNCED_RGB)

# Stable DisplayPort font identifiers (AD-11)
FONT_TIME = "time"
FONT_SECONDS = "seconds"
FONT_DATE = "date"
FONT_BADGE = "badge"

# 5×7 bitmap cell metrics (matches src.device.display.font)
FONT_CELL_WIDTH = 6
FONT_CELL_HEIGHT = 8

# Integer scales near UX ~88/~30/~14/~10 px; time=9 so HH:MM+gap+SS fits in 320.
FONT_SCALE_TIME = 9  # 72 px (~88; scale 11 overflows 320 with SS)
FONT_SCALE_SECONDS = 4  # 32 px (~30)
FONT_SCALE_DATE = 2  # 16 px (~14)
FONT_SCALE_BADGE = 1  # 8 px (~10)

FONT_SCALES = {
    FONT_TIME: FONT_SCALE_TIME,
    FONT_SECONDS: FONT_SCALE_SECONDS,
    FONT_DATE: FONT_SCALE_DATE,
    FONT_BADGE: FONT_SCALE_BADGE,
}

# Clock layout metrics (320×240 landscape)
CLOCK_SS_GAP_PX = 8
CLOCK_DATE_GAP_PX = 14
CLOCK_PLACEHOLDER_HHMM = "--:--"

# Unsynced badge — fixed top-right, no reserved slot when hidden
BADGE_TEXT = "UNSYNCED"
BADGE_MARGIN_TOP = 8
BADGE_MARGIN_RIGHT = 10
BADGE_PADDING_X = 7
BADGE_PADDING_Y = 2

# Timing defaults (milliseconds)
CLOCK_DWELL_MS = 30_000
CALENDAR_DWELL_MS = 8_000
CLOCK_REDRAW_MS = 1000
NTP_RETRY_MS = 3_600_000

# Fixed local offset for Asia/Ho_Chi_Minh (no DST)
LOCAL_UTC_OFFSET_HOURS = 7
