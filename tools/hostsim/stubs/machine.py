"""Host stand-in for the Pico's ``machine`` module.

Only enough surface for the import graph to load and for constructors to run.
Nothing here models real hardware behaviour; the simulation measures heap
occupancy, not device I/O.
"""


class Pin:
    OUT = 1
    IN = 0
    PULL_UP = 2
    IRQ_FALLING = 4

    def __init__(self, *args, **kwargs):
        self._value = 0

    def value(self, *args):
        if args:
            self._value = args[0]
        return self._value

    def on(self):
        self._value = 1

    def off(self):
        self._value = 0

    def irq(self, *args, **kwargs):
        return None


class SPI:
    MSB = 0

    def __init__(self, *args, **kwargs):
        pass

    def init(self, *args, **kwargs):
        pass

    def write(self, _buf):
        pass

    def readinto(self, buf, _write=0):
        for i in range(len(buf)):
            buf[i] = 0

    def write_readinto(self, _tx, rx):
        for i in range(len(rx)):
            rx[i] = 0


class RTC:
    def __init__(self, *args, **kwargs):
        self._datetime = (2026, 1, 1, 0, 0, 0, 0, 0)

    def datetime(self, *args):
        if args:
            self._datetime = args[0]
        return self._datetime


def reset():
    raise SystemExit("machine.reset() in simulation")


def soft_reset():
    raise SystemExit("machine.soft_reset() in simulation")


def bootloader():
    raise SystemExit("machine.bootloader() in simulation")
