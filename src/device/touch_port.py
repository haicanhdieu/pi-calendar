"""Bounded XPT2046-compatible touch polling over the TFT's shared SPI0 bus."""

from src import config


class TouchPort:
    """Return one raw touch edge per contact while safely handing off SPI0.

    The port intentionally does not use ``TOUCH_IRQ`` or calibrate coordinates.
    A caller may inject ``sampler`` for host tests; it must return ``(x, y,
    pressure)`` or ``None`` for no contact.
    """

    _CMD_X = 0xD0
    _CMD_Y = 0x90
    _CMD_Z1 = 0xB0

    def __init__(self, spi, touch_cs, tft_cs, sampler=None):
        self._spi = spi
        self._touch_cs = touch_cs
        self._tft_cs = tft_cs
        self._sampler = sampler if sampler is not None else self._sample_xpt2046
        self._down = False
        self.failure_code = None
        # Allocate fixed working storage at construction, not during each poll.
        self._xs = [0] * config.TOUCH_SAMPLE_COUNT
        self._ys = [0] * config.TOUCH_SAMPLE_COUNT
        self._write_buffer = bytearray(3)
        self._read_buffer = bytearray(3)

    def read(self):
        """Poll once, returning ``(edge_down, x, y)`` without blocking."""
        result = (False, None, None)
        try:
            self._begin_touch_transaction()
            for index in range(config.TOUCH_SAMPLE_COUNT):
                sample = self._sampler()
                if sample is None:
                    self._down = False
                    break
                x, y, pressure = sample
                if pressure is None or int(pressure) < config.TOUCH_PRESSURE_MIN:
                    self._down = False
                    break
                self._xs[index] = int(x)
                self._ys[index] = int(y)
            else:
                point = self._stable_point()
                if point is not None and not self._down:
                    self._down = True
                    result = (True, point[0], point[1])
        except (MemoryError, OSError, RuntimeError, ValueError, TypeError, AttributeError):
            # Preserve a held-contact state on transfer failure: a transient
            # error must not manufacture another edge for the same press.
            result = (False, None, None)
        finally:
            if not self._restore_tft_transaction():
                result = (False, None, None)
        return result

    def _begin_touch_transaction(self):
        self._tft_cs.value(1)
        self._spi.init(
            baudrate=config.TOUCH_SPI_BAUDRATE,
            polarity=config.SPI_POLARITY,
            phase=config.SPI_PHASE,
        )
        self._touch_cs.value(0)

    def _restore_tft_transaction(self):
        # Each operation is attempted independently so a failed sample cannot
        # strand the shared bus at touch speed or leave TFT deselected.
        restored = True
        try:
            self._spi.init(
                baudrate=config.SPI_BAUDRATE,
                polarity=config.SPI_POLARITY,
                phase=config.SPI_PHASE,
            )
        except (MemoryError, OSError, RuntimeError, ValueError, TypeError, AttributeError):
            # Keep the TFT deselected rather than allowing an unknown-speed
            # transaction. The next poll retries the normal handoff.
            self.failure_code = "touch_restore_spi"
            restored = False
        try:
            self._touch_cs.value(1)
        except (MemoryError, OSError, RuntimeError, ValueError, TypeError, AttributeError):
            pass
        if restored:
            try:
                self._tft_cs.value(0)
            except (MemoryError, OSError, RuntimeError, ValueError, TypeError, AttributeError):
                self.failure_code = "touch_restore_tft_cs"
                restored = False
        return restored

    def _sample_xpt2046(self):
        x = self._read_channel(self._CMD_X)
        y = self._read_channel(self._CMD_Y)
        z1 = self._read_channel(self._CMD_Z1)
        return x, y, z1

    def _read_channel(self, command):
        self._write_buffer[0] = command
        self._write_buffer[1] = 0
        self._write_buffer[2] = 0
        self._spi.write_readinto(self._write_buffer, self._read_buffer)
        return ((self._read_buffer[1] << 8) | self._read_buffer[2]) >> 3

    def _stable_point(self):
        if max(self._xs) - min(self._xs) > config.TOUCH_SAMPLE_MAX_SPREAD:
            return None
        if max(self._ys) - min(self._ys) > config.TOUCH_SAMPLE_MAX_SPREAD:
            return None
        self._xs.sort()
        self._ys.sort()
        middle = config.TOUCH_SAMPLE_COUNT // 2
        return self._xs[middle], self._ys[middle]
