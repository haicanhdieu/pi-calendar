from machine import Pin, SPI
from time import sleep_ms


# Pico W TFT wiring from the handoff doc.
TFT_MISO = 16
TFT_CS = 17
TFT_SCK = 18
TFT_MOSI = 19
TFT_DC = 20
TFT_RST = 21

SCREEN_WIDTH = 320
SCREEN_HEIGHT = 240


def color565(red, green, blue):
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)


BLACK = color565(0, 0, 0)
NAVY = color565(0, 18, 38)
CYAN = color565(0, 210, 255)
WHITE = color565(255, 255, 255)


FONT_5X7 = {
    " ": (
        "00000",
        "00000",
        "00000",
        "00000",
        "00000",
        "00000",
        "00000",
    ),
    "?": (
        "01110",
        "10001",
        "00001",
        "00010",
        "00100",
        "00000",
        "00100",
    ),
    "D": (
        "11110",
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "11110",
    ),
    "E": (
        "11111",
        "10000",
        "10000",
        "11110",
        "10000",
        "10000",
        "11111",
    ),
    "F": (
        "11111",
        "10000",
        "10000",
        "11110",
        "10000",
        "10000",
        "10000",
    ),
    "H": (
        "10001",
        "10001",
        "10001",
        "11111",
        "10001",
        "10001",
        "10001",
    ),
    "I": (
        "11111",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
        "11111",
    ),
    "K": (
        "10001",
        "10010",
        "10100",
        "11000",
        "10100",
        "10010",
        "10001",
    ),
    "L": (
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "11111",
    ),
    "O": (
        "01110",
        "10001",
        "10001",
        "10001",
        "10001",
        "10001",
        "01110",
    ),
    "P": (
        "11110",
        "10001",
        "10001",
        "11110",
        "10000",
        "10000",
        "10000",
    ),
    "R": (
        "11110",
        "10001",
        "10001",
        "11110",
        "10100",
        "10010",
        "10001",
    ),
    "T": (
        "11111",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
        "00100",
    ),
    "W": (
        "10001",
        "10001",
        "10001",
        "10101",
        "10101",
        "10101",
        "01010",
    ),
}


class ILI9341:
    CMD_SWRESET = 0x01
    CMD_SLPOUT = 0x11
    CMD_DISPON = 0x29
    CMD_CASET = 0x2A
    CMD_PASET = 0x2B
    CMD_RAMWR = 0x2C
    CMD_MADCTL = 0x36
    CMD_COLMOD = 0x3A

    def __init__(self, spi, dc, rst, cs, width=SCREEN_WIDTH, height=SCREEN_HEIGHT):
        self.spi = spi
        self.dc = Pin(dc, Pin.OUT)
        self.rst = Pin(rst, Pin.OUT)
        self.cs = Pin(cs, Pin.OUT)
        self.width = width
        self.height = height

        self.cs.value(1)
        self.dc.value(1)
        self.rst.value(1)
        self._init_display()

    def _select(self):
        self.cs.value(0)

    def _deselect(self):
        self.cs.value(1)

    def _command(self, command, data=None):
        self._select()
        self.dc.value(0)
        self.spi.write(bytes((command,)))
        if data:
            self.dc.value(1)
            self.spi.write(data)
        self._deselect()

    def _reset(self):
        self.rst.value(1)
        sleep_ms(10)
        self.rst.value(0)
        sleep_ms(50)
        self.rst.value(1)
        sleep_ms(120)

    def _madctl(self):
        # Landscape rotation, RGB order, with normal orientation.
        return 0xA8

    def _init_display(self):
        self._reset()
        self._command(self.CMD_SWRESET)
        sleep_ms(150)
        self._command(self.CMD_SLPOUT)
        sleep_ms(150)
        self._command(self.CMD_COLMOD, b"\x55")
        self._command(self.CMD_MADCTL, bytes((self._madctl(),)))
        self._command(0xB1, b"\x00\x18")
        self._command(0xB6, b"\x0A\xA2")
        self._command(0xC0, b"\x10")
        self._command(0xC1, b"\x10")
        self._command(0xC5, b"\x3E\x28")
        self._command(0xC7, b"\x86")
        self._command(0xE0, b"\x0F\x31\x2B\x0C\x0E\x08\x4E\xF1\x37\x07\x10\x03\x0E\x09\x00")
        self._command(0xE1, b"\x00\x0E\x14\x03\x11\x07\x31\xC1\x48\x08\x0F\x0C\x31\x36\x0F")
        self._command(0x13)
        sleep_ms(10)
        self._command(self.CMD_DISPON)
        sleep_ms(120)

    def set_window(self, x0, y0, x1, y1):
        self._command(self.CMD_CASET, bytes((x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF)))
        self._command(self.CMD_PASET, bytes((y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF)))
        self._select()
        self.dc.value(0)
        self.spi.write(bytes((self.CMD_RAMWR,)))
        self.dc.value(1)

    def fill_rect(self, x, y, w, h, color):
        if w <= 0 or h <= 0:
            return

        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.width - 1, x + w - 1)
        y1 = min(self.height - 1, y + h - 1)

        if x1 < x0 or y1 < y0:
            return

        self.set_window(x0, y0, x1, y1)
        hi = (color >> 8) & 0xFF
        lo = color & 0xFF
        row = bytes((hi, lo)) * (x1 - x0 + 1)
        for _ in range(y1 - y0 + 1):
            self.spi.write(row)
        self._deselect()

    def fill(self, color):
        self.fill_rect(0, 0, self.width, self.height, color)


def draw_glyph(display, x, y, char, scale, color):
    bitmap = FONT_5X7.get(char, FONT_5X7["?"])
    for row_index, row_bits in enumerate(bitmap):
        py = y + (row_index * scale)
        for col_index, bit in enumerate(row_bits):
            if bit == "1":
                display.fill_rect(
                    x + (col_index * scale),
                    py,
                    scale,
                    scale,
                    color,
                )


def draw_text(display, text, x, y, scale, color):
    cursor_x = x
    step = 6 * scale
    for char in text:
        if char == "\n":
            y += 8 * scale
            cursor_x = x
            continue
        draw_glyph(display, cursor_x, y, char.upper(), scale, color)
        cursor_x += step


def text_width(text, scale):
    if not text:
        return 0
    return (len(text) * 6 - 1) * scale


def centered_text(display, text, y, scale, color):
    x = (display.width - text_width(text, scale)) // 2
    draw_text(display, text, x, y, scale, color)


def splash_screen(display):
    display.fill(NAVY)
    display.fill_rect(0, 0, display.width, 18, BLACK)
    display.fill_rect(0, display.height - 18, display.width, 18, BLACK)

    top_y = 88
    bottom_y = 160
    centered_text(display, "HELLO", top_y, 6, WHITE)
    centered_text(display, "WORLD", bottom_y, 6, CYAN)


def main():
    led = Pin("LED", Pin.OUT)
    led.value(1)

    print("Initializing SPI0 TFT demo")
    spi = SPI(
        0,
        baudrate=40_000_000,
        polarity=0,
        phase=0,
        sck=Pin(TFT_SCK),
        mosi=Pin(TFT_MOSI),
        miso=Pin(TFT_MISO),
    )

    display = ILI9341(
        spi=spi,
        dc=TFT_DC,
        rst=TFT_RST,
        cs=TFT_CS,
    )

    print("Drawing hello world splash")
    splash_screen(display)
    led.value(0)
    print("Splash shown; leaving the board alive")

    while True:
        sleep_ms(1000)


try:
    main()
except Exception as exc:
    print("TFT demo failed:", exc)
    led = Pin("LED", Pin.OUT)
    while True:
        led.value(1)
        sleep_ms(150)
        led.value(0)
        sleep_ms(150)
