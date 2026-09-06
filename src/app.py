"""Single-writer App loop: AppState, Clock snapshots, tick deadlines (story 1.3)."""

from src import config
from src import ticks as default_ticks
from src.time.model import TRUST_UNSYNCED
from src.time.service import make_snapshot
from src.ui.compositor import UiCompositor

VIEW_CLOCK = "clock"


class AppState:
    """Mutable product state owned exclusively by App."""

    __slots__ = (
        "trust",
        "utc_valid",
        "active_view",
        "redraw_deadline",
        "retry_deadline",
        "freshness_deadline",
        "view_deadline",
        "sync_age_ms",
    )

    def __init__(self):
        self.trust = TRUST_UNSYNCED
        self.utc_valid = False
        self.active_view = VIEW_CLOCK
        self.redraw_deadline = 0
        self.retry_deadline = 0
        self.freshness_deadline = 0
        self.view_deadline = 0
        self.sync_age_ms = None


class App:
    """
    Sole writer of AppState.

    Reads advancing UTC only through an injected ClockPort, derives immutable
    TimeSnapshots via pure time logic, and schedules work with ticks helpers.
    """

    def __init__(
        self,
        clock_port,
        clock_view,
        ticks_module=None,
        log=None,
        compositor=None,
    ):
        self._clock = clock_port
        self._view = clock_view
        self._ticks = ticks_module if ticks_module is not None else default_ticks
        self._log = log if log is not None else print
        if compositor is None:
            compositor = UiCompositor(clock_view._display)
        self._compositor = compositor
        self.state = AppState()
        self._booted = False
        self._last_snapshot = None

    def boot(self):
        """Enter Clock as the active view and arm tick deadlines."""
        t = self._ticks
        now = t.ticks_ms()
        self.state.active_view = VIEW_CLOCK
        self.state.trust = TRUST_UNSYNCED
        self.state.utc_valid = False
        self.state.sync_age_ms = None
        # Due immediately so the first step paints Clock.
        self.state.redraw_deadline = now
        self.state.retry_deadline = t.ticks_add(now, config.NTP_RETRY_MS)
        self.state.freshness_deadline = t.ticks_add(now, config.NTP_RETRY_MS)
        self.state.view_deadline = t.ticks_add(now, config.CLOCK_DWELL_MS)
        if hasattr(self._view, "invalidate"):
            self._view.invalidate()
        self._booted = True

    def report_time_source_failure(self, reason):
        """
        Soft-fail path for expected sync/credential problems.

        Marks trust unsynced, emits a concise diagnostic, and returns without
        raising or blocking the loop.
        """
        self.state.trust = TRUST_UNSYNCED
        self._log("time-source: unsynced — %s" % (reason,))

    def step(self, now_ticks=None):
        """
        One non-blocking loop iteration.

        When ``now_ticks`` is omitted, uses ``ticks_ms()``. Host tests inject
        fake ticks and advance FakeClockPort without sleeping.
        """
        if not self._booted:
            self.boot()

        t = self._ticks
        if now_ticks is None:
            now = t.ticks_ms()
        else:
            now = int(now_ticks) & (default_ticks.PERIOD - 1)

        if t.ticks_diff(self.state.redraw_deadline, now) <= 0:
            self._refresh_clock(now)

        # Retry / freshness / view deadlines are armed with ticks_* only.
        # Story 1.3 does not perform NTP or Calendar rotation; expiry is a no-op
        # beyond re-arming so scheduling stays wrap-safe and tested.
        if t.ticks_diff(self.state.retry_deadline, now) <= 0:
            self.state.retry_deadline = t.ticks_add(now, config.NTP_RETRY_MS)

        if t.ticks_diff(self.state.freshness_deadline, now) <= 0:
            self.state.freshness_deadline = t.ticks_add(now, config.NTP_RETRY_MS)

        if t.ticks_diff(self.state.view_deadline, now) <= 0:
            # Stay on Clock (no Calendar rotation in epic 1 / story 1.3).
            self.state.active_view = VIEW_CLOCK
            self.state.view_deadline = t.ticks_add(now, config.CLOCK_DWELL_MS)

    def _refresh_clock(self, now):
        t = self._ticks
        # Advancing UTC only via ClockPort; FakeClockPort non-None values are
        # usable for host "valid RTC" snapshots. utc_valid stays App-owned for
        # first successful NTP (story 1.5) and is not flipped here.
        utc = self._clock.read_utc()
        snapshot = make_snapshot(utc, self.state.trust, self.state.sync_age_ms)
        self._last_snapshot = snapshot
        self._compositor.render(self._view, snapshot)
        self.state.redraw_deadline = t.ticks_add(now, config.CLOCK_REDRAW_MS)

    def run_forever(self, sleep_ms_fn=None):
        """Device loop: step + short sleep. Not used by host tests."""
        if sleep_ms_fn is None:
            from time import sleep_ms as sleep_ms_fn

        if not self._booted:
            self.boot()
        while True:
            self.step()
            sleep_ms_fn(10)
