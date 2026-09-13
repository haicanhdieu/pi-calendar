"""Host coverage for TouchPort's bounded sampling and SPI0 ownership."""

from src import config
from src.device.touch_port import TouchPort


class FakePin:
    def __init__(self, name, events):
        self.name = name
        self.events = events

    def value(self, value):
        self.events.append((self.name, value))


class FakeSpi:
    def __init__(self, events):
        self.events = events

    def init(self, **kwargs):
        self.events.append(("spi.init", kwargs["baudrate"]))


def _port(samples, events=None):
    events = [] if events is None else events
    iterator = iter(samples)
    return (
        TouchPort(
            FakeSpi(events),
            FakePin("touch", events),
            FakePin("tft", events),
            sampler=lambda: next(iterator),
        ),
        events,
    )


def _stable(x=1234, y=2345, pressure=20):
    return [(x, y, pressure)] * config.TOUCH_SAMPLE_COUNT


def test_fresh_contact_emits_once_until_release_then_emits_again():
    port, _events = _port(_stable() + _stable() + [None] + _stable(1400, 2200))

    assert port.read() == (True, 1234, 2345)
    assert port.read() == (False, None, None)
    assert port.read() == (False, None, None)
    assert port.read() == (True, 1400, 2200)


def test_every_poll_hands_spi_to_touch_and_restores_tft():
    port, events = _port(_stable())

    assert port.read() == (True, 1234, 2345)
    assert events == [
        ("tft", 1),
        ("spi.init", config.TOUCH_SPI_BAUDRATE),
        ("touch", 0),
        ("spi.init", config.SPI_BAUDRATE),
        ("touch", 1),
        ("tft", 0),
    ]


def test_noisy_or_invalid_samples_never_emit_a_false_edge_and_remain_usable():
    noisy = [(100, 200, 20)] * (config.TOUCH_SAMPLE_COUNT - 1) + [(300, 200, 20)]
    invalid = [(100, 200, 0)]
    port, _events = _port(noisy + invalid + _stable(444, 555))

    assert port.read() == (False, None, None)
    assert port.read() == (False, None, None)
    assert port.read() == (True, 444, 555)


def test_sample_failure_restores_the_bus_and_does_not_create_an_edge():
    def failing_sampler():
        raise OSError("spi failed")

    events = []
    port = TouchPort(
        FakeSpi(events),
        FakePin("touch", events),
        FakePin("tft", events),
        sampler=failing_sampler,
    )

    assert port.read() == (False, None, None)
    assert events[-3:] == [
        ("spi.init", config.SPI_BAUDRATE),
        ("touch", 1),
        ("tft", 0),
    ]


def test_restore_failure_is_visible_and_keeps_tft_deselected():
    class RestoreFailingSpi(FakeSpi):
        def init(self, **kwargs):
            super().init(**kwargs)
            if kwargs["baudrate"] == config.SPI_BAUDRATE:
                raise OSError("restore failed")

    events = []
    port = TouchPort(
        RestoreFailingSpi(events),
        FakePin("touch", events),
        FakePin("tft", events),
        sampler=lambda: (10, 20, 10),
    )

    assert port.read() == (False, None, None)
    assert port.failure_code == "touch_restore_spi"
    assert ("tft", 0) not in events
