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
COLOR_BACKGROUND_RGB = (0x0A, 0x0A, 0x0A)
COLOR_PRIMARY_RGB = (0x3D, 0xFF, 0x7A)
COLOR_SECONDARY_RGB = (0xFF, 0xB2, 0x38)
COLOR_UNSYNCED_RGB = (0xFF, 0x4D, 0x4D)


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
FONT_MONTH = "month"
FONT_WEEKDAY = "weekday"
FONT_DAY = "day"

# 5×7 bitmap cell metrics (matches src.device.display.font)
FONT_CELL_WIDTH = 6
FONT_CELL_HEIGHT = 8

# Integer scales near UX ~88/~30/~14/~10 px; time=9 so HH:MM+gap+SS fits in 320.
# Calendar: month ~16px, weekday ~11px, day ~14px (nearest integer scales).
FONT_SCALE_TIME = 9  # 72 px (~88; scale 11 overflows 320 with SS)
FONT_SCALE_SECONDS = 4  # 32 px (~30)
FONT_SCALE_DATE = 2  # 16 px (~14)
FONT_SCALE_BADGE = 1  # 8 px (~10)
FONT_SCALE_MONTH = 2  # 16 px
FONT_SCALE_WEEKDAY = 1  # 8 px (~11)
FONT_SCALE_DAY = 2  # 16 px (~14)

FONT_SCALES = {
    FONT_TIME: FONT_SCALE_TIME,
    FONT_SECONDS: FONT_SCALE_SECONDS,
    FONT_DATE: FONT_SCALE_DATE,
    FONT_BADGE: FONT_SCALE_BADGE,
    FONT_MONTH: FONT_SCALE_MONTH,
    FONT_WEEKDAY: FONT_SCALE_WEEKDAY,
    FONT_DAY: FONT_SCALE_DAY,
}

# Clock layout metrics (320×240 landscape)
CLOCK_SS_GAP_PX = 8
CLOCK_DATE_GAP_PX = 14
CLOCK_LUNAR_GAP_PX = 6
CLOCK_PLACEHOLDER_HHMM = "--:--"

# Calendar layout metrics (320×240 landscape) — pad Y/X, cell gap, label gaps
CALENDAR_PAD_Y = 10
CALENDAR_PAD_X = 12
CALENDAR_GAP = 2
CALENDAR_LABEL_GAP = 6
CALENDAR_HEADER_GAP = 4

# Unsynced badge — fixed top-right, no reserved slot when hidden
BADGE_TEXT = "UNSYNCED"
BADGE_MARGIN_TOP = 8
BADGE_MARGIN_RIGHT = 10
BADGE_PADDING_X = 7
BADGE_PADDING_Y = 2

# Timing defaults (milliseconds)
BOOT_CHECKPOINT_DWELL_MS = 1_200
CLOCK_DWELL_MS = 30_000
CALENDAR_DWELL_MS = 8_000
CLOCK_REDRAW_MS = 1000
# Production App NTP retry cadence after each terminal sync consume (v1 = 1 h).
NTP_RETRY_MS = 3_600_000

# SyncCommand deadline budget for bounded worker ops (AD-8)
SYNC_COMMAND_DEADLINE_MS = 15_000
# Numeric address deliberately avoids a synchronous DNS lookup in the render loop.
NTP_SERVER_ADDRESS = ("129.6.15.28", 123)

# Wi-Fi setup AP and settings record (non-secret constants only; AD-3/AD-9)
SETUP_AP_SSID = "PiCalendar-Setup"
SETUP_AP_GATEWAY = "192.168.4.1"
SETTINGS_BASENAME = ".settings-v1"
ADMIN_PBKDF2_ITERATIONS = 500

# Station recovery (story 1.3): three terminal fails → SETUP_AP; persistent IP status
STATION_FAILURE_LIMIT = 3
# Keep the assigned address visible so users can reconnect later; this status
# strip is drawn after, and outside the centered clock content.
STATION_IP_DISPLAY_MS = None
# Gap before the next store-credential reconnect attempt after a terminal fail.
STATION_RECONNECT_GAP_MS = 1_000

# Bounded local HTTP limits (AD-4 / story 1.2); join reuses SYNC_COMMAND_DEADLINE_MS
HTTP_MAX_REQUEST_LINE = 256
HTTP_MAX_HEADERS_BYTES = 1024
HTTP_MAX_BODY_BYTES = 1024
HTTP_MAX_CLIENTS = 2
HTTP_PER_TICK_BYTES = 512
HTTP_LISTEN_PORT = 80
HTTP_LISTEN_BACKLOG = 1
# Retry web construction/listening cooperatively; no sleep or busy loop.
HTTP_RETRY_MS = 2_000
# Bound the coordinator-owned decoded scan cache; raw WLAN rows never escape
# the scan operation.
HTTP_SCAN_CACHE_MAX = 24
# Opt-in serial checkpoints for flashed heap evidence only.
WEB_HEAP_CHECKPOINTS = False

# Config auth / sessions (AD-5 / story 2.1)
SESSION_IDLE_MS = 900_000
SESSION_MAX = 4
SESSION_COOKIE_NAME = "pc_session"
# Maximum round allowance remains compatible with the host/coordinator contract;
# the coordinator additionally enforces KDF_MAX_STEP_MS on the Pico.
KDF_ROUNDS_PER_TICK = 200
KDF_MAX_STEP_MS = 5

# Story 1.4 flashable proof harness (src/device/network/proof.py)
NETWORK_PROOF_MODE = False
PROOF_RESULT_TIMEOUT_MS = 10_000
PROOF_BUSY_OP_MS = 500
PROOF_RENDER_POLL_MS = 10
PROOF_RENDER_MIN_POLLS = 10
PROOF_SUSTAINED_ITERATIONS = 50

# Fixed local offset for Asia/Ho_Chi_Minh (no DST)
LOCAL_UTC_OFFSET_HOURS = 7
