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

# Timing defaults (milliseconds)
CLOCK_DWELL_MS = 30_000
CALENDAR_DWELL_MS = 8_000
NTP_RETRY_MS = 3_600_000

# Fixed local offset for Asia/Ho_Chi_Minh (no DST)
LOCAL_UTC_OFFSET_HOURS = 7
