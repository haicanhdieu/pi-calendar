from machine import Pin
from time import sleep_ms

from src import config


def color565(red, green, blue):
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)


class ILI9341:
    CMD_SWRESET = 0x01
    CMD_SLPOUT = 0x11
    CMD_DISPON = 0x29
    CMD_CASET = 0x2A
    CMD_PASET = 0x2B
    CMD_RAMWR = 0x2C
    CMD_MADCTL = 0x36
    CMD_COLMOD = 0x3A

    def __init__(
        self,
        spi,
        dc,
        rst,
        cs,
        width=config.SCREEN_WIDTH,
        height=config.SCREEN_HEIGHT,
    ):
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
        return config.MADCTL

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
