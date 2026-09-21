import sys
import types


machine = types.ModuleType("machine")
machine.Pin = type("Pin", (), {"OUT": 1})
sys.modules["machine"] = machine

from src.device.buzzer_port import (
    BuzzerPort,
    DRIVE_HIGH_FAILED,
    DRIVE_LOW_FAILED,
    HIGH_ENDED,
    HIGH_STARTED,
    INIT_FAILED,
    INIT_OK,
    LOW_ENDED,
    NOT_INITIALIZED,
    SILENCED,
    WAITING,
)
from src import ticks

sys.modules.pop("machine", None)


class FakeTicks:
    ticks_add = staticmethod(ticks.ticks_add)
    ticks_diff = staticmethod(ticks.ticks_diff)


class FakePin:
    def __init__(self, fail_on=None):
        self.values = []
        self.fail_on = fail_on

    def value(self, value=None):
        if value is not None:
            self.values.append(value)
            if self.fail_on == len(self.values):
                raise RuntimeError("pin failure")
        return self.values[-1] if self.values else 0


def make_port(pin=None, active_high=True):
    return BuzzerPort(pin or FakePin(), 180, 220, active_high, FakeTicks)


def test_initializes_low_and_starts_high_immediately():
    pin = FakePin()
    port = make_port(pin)
    assert port.init_result == INIT_OK
    assert pin.values == [0]
    assert port.tick(1000, True) == HIGH_STARTED
    assert pin.values[-1] == 1
    assert port._deadline == 1180


def test_cadence_switches_high_to_low_to_high():
    pin = FakePin()
    port = make_port(pin)
    port.tick(1000, True)
    assert port.tick(1180, True) == LOW_ENDED
    assert pin.values[-1] == 0
    assert port._deadline == 1400
    assert port.tick(1400, True) == HIGH_ENDED
    assert pin.values[-1] == 1


def test_late_tick_emits_one_edge_and_resynchronizes():
    pin = FakePin()
    port = make_port(pin)
    port.tick(1000, True)
    assert port.tick(5000, True) == LOW_ENDED
    assert pin.values == [0, 1, 0]
    assert port._deadline == 5220


def test_wrap_safe_deadline():
    pin = FakePin()
    port = make_port(pin)
    start = 0xFFFFFFF0
    port.tick(start, True)
    assert port.tick(0x000000A4, True) == LOW_ENDED
    assert port._deadline == 0x00000180


def test_silence_is_idempotent_and_false_tick_cannot_reassert():
    pin = FakePin()
    port = make_port(pin)
    port.tick(10, True)
    assert port.silence() == SILENCED
    assert port.silence() == SILENCED
    values = list(pin.values)
    assert port.tick(10000, False) == SILENCED
    assert pin.values == values


def test_failed_edge_marks_port_unavailable_until_reinitialized():
    pin = FakePin(fail_on=2)
    port = make_port(pin)
    assert port.init_result == INIT_OK
    assert port.tick(10, True) == DRIVE_HIGH_FAILED
    assert port.tick(20, True) == NOT_INITIALIZED
    pin.fail_on = None
    assert port.initialize() == INIT_OK
    assert port.tick(30, True) == HIGH_STARTED


def test_failed_initialization_returns_named_result_and_can_retry():
    pin = FakePin(fail_on=1)
    port = make_port(pin)
    assert port.init_result == INIT_FAILED
    assert port.tick(10, True) == NOT_INITIALIZED
    pin.fail_on = None
    assert port.initialize() == INIT_OK


def test_active_low_configuration_inverts_levels():
    pin = FakePin()
    port = make_port(pin, active_high=False)
    assert pin.values == [1]
    port.tick(0, True)
    assert pin.values[-1] == 0
