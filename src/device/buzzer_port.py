from machine import Pin

INIT_OK = "ok"
INIT_FAILED = "init_fail"
NOT_INITIALIZED = "not_ready"
HIGH_STARTED = "high_start"
HIGH_ENDED = "high_end"
LOW_ENDED = "low_end"
WAITING = "wait"
SILENCED = "silent"
DRIVE_HIGH_FAILED = "high_fail"
DRIVE_LOW_FAILED = "low_fail"


class BuzzerPort:
    __slots__ = (
        "_pin",
        "_high_ms",
        "_low_ms",
        "_active_high",
        "_ticks",
        "_initialized",
        "_phase_high",
        "_deadline",
        "init_result",
    )

    def __init__(
        self,
        signal_pin,
        high_ms,
        low_ms,
        active_high=True,
        ticks_module=None,
        pin_factory=None,
    ):
        if pin_factory is None:
            pin_factory = Pin
        if hasattr(signal_pin, "value"):
            self._pin = signal_pin
        else:
            self._pin = pin_factory(signal_pin, Pin.OUT)
        self._high_ms = int(high_ms)
        self._low_ms = int(low_ms)
        self._active_high = bool(active_high)
        if ticks_module is None:
            from src import ticks as ticks_module
        self._ticks = ticks_module
        self._initialized = False
        self._phase_high = False
        self._deadline = None
        self.init_result = self.initialize()

    def _level(self, high):
        return 1 if bool(high) == self._active_high else 0

    def _best_effort_low(self):
        try:
            self._pin.value(self._level(False))
        except Exception:
            pass

    def _drive(self, high):
        try:
            self._pin.value(self._level(high))
            return None
        except Exception:
            self._initialized = False
            self._deadline = None
            self._best_effort_low()
            return DRIVE_HIGH_FAILED if high else DRIVE_LOW_FAILED

    def initialize(self):
        self._initialized = False
        self._phase_high = False
        self._deadline = None
        failure = self._drive(False)
        if failure is not None:
            self.init_result = INIT_FAILED
            return INIT_FAILED
        self._initialized = True
        self.init_result = INIT_OK
        return INIT_OK

    def tick(self, now, sounding):
        if not self._initialized:
            return NOT_INITIALIZED
        now = int(now)
        if not sounding:
            return self.silence()
        if self._deadline is None:
            failure = self._drive(True)
            if failure is not None:
                return failure
            self._phase_high = True
            self._deadline = self._ticks.ticks_add(now, self._high_ms)
            return HIGH_STARTED
        if self._ticks.ticks_diff(now, self._deadline) < 0:
            return WAITING
        next_high = not self._phase_high
        failure = self._drive(next_high)
        if failure is not None:
            return failure
        self._phase_high = next_high
        duration = self._high_ms if next_high else self._low_ms
        self._deadline = self._ticks.ticks_add(now, duration)
        return LOW_ENDED if not next_high else HIGH_ENDED

    def silence(self):
        if not self._initialized:
            return NOT_INITIALIZED
        if not self._phase_high:
            self._phase_high = False
            self._deadline = None
            return SILENCED
        failure = self._drive(False)
        if failure is not None:
            return failure
        self._phase_high = False
        self._deadline = None
        return SILENCED
