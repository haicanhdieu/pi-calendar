"""Wrap-safe millisecond tick helpers (AD-5).

Pure add/diff are host-testable without ``machine``. ``ticks_ms`` prefers
MicroPython ``time.ticks_ms`` when present; otherwise uses a monotonic host
clock masked to the same 32-bit period.
"""

PERIOD = 2**32
_HALF = PERIOD // 2
_MASK = PERIOD - 1


def ticks_ms():
    """Current millisecond tick, wrap-safe within PERIOD."""
    import time as _time

    native = getattr(_time, "ticks_ms", None)
    if callable(native):
        return native() & _MASK
    # CPython / host: monotonic seconds → ms, masked like MicroPython.
    return int(_time.monotonic() * 1000) & _MASK


def ticks_add(ticks, delta_ms):
    """Return ``ticks + delta_ms`` modulo PERIOD (delta may be negative)."""
    return (int(ticks) + int(delta_ms)) & _MASK


def ticks_diff(ticks1, ticks2):
    """
    Signed wrap-safe difference ``ticks1 - ticks2``.

    Result is in ``[-PERIOD/2, PERIOD/2)``, matching MicroPython semantics.
    """
    diff = (int(ticks1) - int(ticks2)) & _MASK
    if diff >= _HALF:
        diff -= PERIOD
    return diff
