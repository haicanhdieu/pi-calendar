"""Pure RGB565 packing shared by the display driver and boot renderer."""


def color565(red, green, blue):
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
