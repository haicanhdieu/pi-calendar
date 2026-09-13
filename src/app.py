"""Single-writer App loop: snapshots, view rotation, tick deadlines."""

from src import config
from src import ticks as default_ticks
from src.calendar.gregorian import build_month_grid
from src.time.model import TRUST_SYNCED, TRUST_UNSYNCED
from src.time.service import make_snapshot
from src.ui.compositor import UiCompositor
from src.ui.touch_state import SURFACE_BAR, next_surface
from src.ui.view_state import (
    VIEW_CALENDAR,
    VIEW_CLOCK,
    classify_local_rollover,
    next_view_after_dwell,
)

# Re-export view constants for callers / tests.
__all__ = ("VIEW_CLOCK", "VIEW_CALENDAR", "AppState", "App")

# Duck-typed NetworkEvent kind strings (no src.device import — purity).
_EVENT_SETUP_STATUS = "setup_status"
_EVENT_STATION_STATUS = "station_status"
_MODE_STATION_ONLINE = "STATION_ONLINE"

_OVERLAY_SETUP = "setup"
_OVERLAY_STATION_IP = "station_ip"


class _SyncCommand:
    """Duck-typed SyncCommand so App never imports ``src.device``."""

    __slots__ = ("command_id", "deadline_ms")

    def __init__(self, command_id, deadline_ms):
        self.command_id = command_id
        self.deadline_ms = deadline_ms


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
        "active_surface",
        "surface_deadline",
        "settings_status_snapshot",
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
        self.active_surface = "rotation"
        self.surface_deadline = None
        self.settings_status_snapshot = None


class App:
    """
    Sole writer of AppState.

    Reads advancing UTC only through an injected ClockPort, derives immutable
    TimeSnapshots via pure time logic, and schedules work with ticks helpers.
    Loop order (AD-12): touch → adapter results → network events → snapshot →
    rollover → view deadline → base render → status overlays.
    """

    def __init__(
        self,
        clock_port,
        clock_view,
        calendar_view,
        ticks_module=None,
        log=None,
        compositor=None,
        mailbox=None,
        lock=None,
        sync_enabled=True,
        network_events=None,
        touch_port=None,
    ):
        self._clock = clock_port
        self._view = clock_view
        self._calendar_view = calendar_view
        self._ticks = ticks_module if ticks_module is not None else default_ticks
        self._log = log if log is not None else print
        if compositor is None:
            compositor = UiCompositor(clock_view._display)
        self._compositor = compositor
        self._mailbox = mailbox
        # Kept as a call-site compatibility argument while old proof fixtures
        # retire; the cooperative core-0 composition never uses a lock.
        del lock
        self._sync_enabled = bool(sync_enabled)
        self._network_events = network_events
        self._touch_port = touch_port
        self.state = AppState()
        self._booted = False
        self._last_snapshot = None
        self._last_local_ymd = None
        self._month_grid = None
        self._next_command_id = 1
        self._inflight_id = None
        self._inflight_deadline = None
        self._overlay_kind = None
        self._overlay_ssid = None
        self._overlay_ip = None
        self._overlay_clear_deadline = None
        self._bar_reveal_started = None
        self.state.active_surface = "rotation"
        self.state.surface_deadline = None

    def boot(self):
        """Enter Clock as the active view and arm tick deadlines."""
        t = self._ticks
        now = t.ticks_ms()
        self.state.active_view = VIEW_CLOCK
        self.state.trust = TRUST_UNSYNCED
        self.state.utc_valid = False
        self.state.sync_age_ms = None
        self._last_local_ymd = None
        self._month_grid = None
        self._inflight_id = None
        self._inflight_deadline = None
        self._overlay_kind = None
        self._overlay_ssid = None
        self._overlay_ip = None
        self._overlay_clear_deadline = None
        self._bar_reveal_started = None
        # Due immediately so the first step paints Clock.
        self.state.redraw_deadline = now
        # Sync retry due immediately so the first NTP attempt is not deferred.
        self.state.retry_deadline = now
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
        One non-blocking loop iteration (AD-12 event order).

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

        # 0. Poll touch once, then commit its pure surface transition before
        # later same-tick work (including synchronization).
        force_redraw = self._poll_touch(now)

        # 1. Consume adapter results (AD-8 mailbox), then maybe enqueue.
        self._consume_sync_result(now)
        self._maybe_enqueue_sync(now)

        # 1b. Drain coordinator NetworkEvents into retained network state.
        self._drain_network_events(now)
        self._expire_station_ip_overlay(now)

        # 2. Derive snapshot.
        utc = self._clock.read_utc()
        snapshot = make_snapshot(utc, self.state.trust, self.state.sync_age_ms)
        self._last_snapshot = snapshot

        # 3. Handle date / month rollover.
        force_redraw = self._handle_rollover(snapshot, now) or force_redraw

        if t.ticks_diff(self.state.freshness_deadline, now) <= 0:
            self.state.freshness_deadline = t.ticks_add(now, config.NTP_RETRY_MS)

        # 4. Handle view deadline.
        if (
            self.state.active_surface != SURFACE_BAR
            and t.ticks_diff(self.state.view_deadline, now) <= 0
        ):
            force_redraw = self._handle_view_deadline(snapshot, now) or force_redraw

        # 5–6. Render base view + UNSYNCED badge via compositor.
        if force_redraw or t.ticks_diff(self.state.redraw_deadline, now) <= 0:
            self._render(snapshot, now)
            self.state.redraw_deadline = self._next_redraw_deadline(now)

    def _poll_touch(self, now):
        """Read the optional touch port once and commit its surface decision."""
        edge_down = False
        if self._touch_port is not None:
            sample = self._touch_port.read()
            if sample:
                edge_down = bool(sample[0])
        previous = self.state.active_surface
        # Story 2.2 enters Bar from Rotation.  Story 2.3 wires the existing
        # Bar expiry decision and its fresh Rotation dwell deadline.
        if previous == "rotation":
            surface, deadline = next_surface(
                previous, self.state.surface_deadline, edge_down, now
            )
        else:
            surface, deadline = previous, self.state.surface_deadline
        self.state.active_surface = surface
        self.state.surface_deadline = deadline
        if surface != previous:
            self._bar_reveal_started = now if surface == SURFACE_BAR else None
            return True
        return False

    def _next_redraw_deadline(self, now):
        """Use the short cadence only while the Bar reveal is in progress."""
        if self.state.active_surface == SURFACE_BAR and self._bar_reveal_started is not None:
            elapsed = self._ticks.ticks_diff(now, self._bar_reveal_started)
            if elapsed < config.BAR_SLIDE_DURATION_MS:
                return self._ticks.ticks_add(now, config.BAR_ANIMATION_FRAME_MS)
        return self._ticks.ticks_add(now, config.CLOCK_REDRAW_MS)

    def _drain_network_events(self, now):
        events = self._network_events
        if events is None:
            return
        while events:
            event = events.pop(0)
            self._apply_network_event(event, now)

    def _apply_network_event(self, event, now):
        kind = getattr(event, "kind", None)
        mode = getattr(event, "mode", None)
        if kind == _EVENT_SETUP_STATUS:
            self._sync_enabled = False
            self._overlay_kind = _OVERLAY_SETUP
            self._overlay_ssid = getattr(event, "ssid", None) or config.SETUP_AP_SSID
            self._overlay_ip = getattr(event, "ip", None) or config.SETUP_AP_GATEWAY
            self._overlay_clear_deadline = None
            return
        if kind == _EVENT_STATION_STATUS and mode == _MODE_STATION_ONLINE:
            # NTP only after station is online (not while still connecting).
            self._sync_enabled = True
            # The boot retry deadline was armed while the station was still
            # connecting. Queue the first NTP attempt immediately now that
            # the online event has made synchronization eligible.
            self.state.retry_deadline = now
            ip = getattr(event, "ip", None)
            # Clear prior status; never retain a stale address.
            self._overlay_kind = None
            self._overlay_ssid = None
            self._overlay_ip = None
            self._overlay_clear_deadline = None
            if not ip:
                # Missing IP: never invent a false address.
                return
            self._overlay_kind = _OVERLAY_STATION_IP
            self._overlay_ssid = getattr(event, "ssid", None)
            self._overlay_ip = str(ip)
            display_ms = config.STATION_IP_DISPLAY_MS
            self._overlay_clear_deadline = (
                None
                if display_ms is None
                else self._ticks.ticks_add(now, display_ms)
            )

    def _expire_station_ip_overlay(self, now):
        if self._overlay_kind != _OVERLAY_STATION_IP:
            return
        deadline = self._overlay_clear_deadline
        if deadline is None:
            return
        if self._ticks.ticks_diff(now, deadline) >= 0:
            self._overlay_kind = None
            self._overlay_ssid = None
            self._overlay_ip = None
            self._overlay_clear_deadline = None

    def _network_status(self):
        """Immutable-ish retained network-status payload for Settings."""
        kind = self._overlay_kind
        if kind is None:
            return None
        return {
            "kind": kind,
            "ssid": self._overlay_ssid,
            "ip": self._overlay_ip,
        }

    def _result_is_expired(self, deadline_ms, now_ms):
        return self._ticks.ticks_diff(now_ms, deadline_ms) >= 0

    def _should_apply_result(self, result, expected_command_id, deadline_ms, now_ms):
        """Matching, non-expired gate (duck-typed; no ``src.device`` import)."""
        if result is None:
            return False
        if result.command_id != expected_command_id:
            return False
        if self._result_is_expired(deadline_ms, now_ms):
            return False
        return True

    def _consume_sync_result(self, now):
        mailbox = self._mailbox
        if mailbox is None:
            return

        result = mailbox.try_take_result()
        if result is None:
            return

        expected_id = self._inflight_id
        deadline = self._inflight_deadline
        self._inflight_id = None
        self._inflight_deadline = None

        apply = False
        if expected_id is not None and deadline is not None:
            apply = self._should_apply_result(result, expected_id, deadline, now)

        if apply and getattr(result, "ok", False) and result.utc is not None:
            self._clock.set_utc(result.utc)
            self.state.trust = TRUST_SYNCED
            self.state.utc_valid = True
            self.state.sync_age_ms = 0
        else:
            reason = "sync result discarded"
            if apply:
                err = getattr(result, "error_code", None)
                reason = "sync failed" if err is None else "sync failed: %s" % (err,)
            elif expected_id is None:
                reason = "stale sync result (no inflight)"
            elif result.command_id != expected_id:
                reason = "stale sync result (id mismatch)"
            elif deadline is not None and self._result_is_expired(deadline, now):
                reason = "expired sync result"
            self.report_time_source_failure(reason)

        self.state.retry_deadline = self._ticks.ticks_add(now, config.NTP_RETRY_MS)

    def _maybe_enqueue_sync(self, now):
        t = self._ticks
        if t.ticks_diff(self.state.retry_deadline, now) > 0:
            return

        if not self._sync_enabled or self._mailbox is None:
            self.state.retry_deadline = t.ticks_add(now, config.NTP_RETRY_MS)
            return

        command_id = self._next_command_id
        deadline_ms = t.ticks_add(now, config.SYNC_COMMAND_DEADLINE_MS)
        command = _SyncCommand(command_id, deadline_ms)

        accepted = self._mailbox.enqueue(command)
        if accepted:
            self._next_command_id = command_id + 1
            self._inflight_id = command_id
            self._inflight_deadline = deadline_ms
            self.state.retry_deadline = t.ticks_add(now, config.NTP_RETRY_MS)
        # Rejected (busy / result occupied): leave retry_deadline due.

    def _handle_rollover(self, snapshot, now):
        """Apply same-month today refresh or month-change cut; return force flag."""
        local = snapshot.local
        if local is None:
            return False

        ymd = (local.year, local.month, local.day)
        kind = classify_local_rollover(self._last_local_ymd, local)
        self._last_local_ymd = ymd

        if kind is None:
            return False

        t = self._ticks
        if kind == "day":
            if self.state.active_view == VIEW_CALENDAR:
                self._rebuild_month_grid(local)
                self._invalidate_calendar()
            return True

        # Month (or year) change.
        self._month_grid = None
        if self.state.active_view == VIEW_CALENDAR:
            self.state.active_view = VIEW_CLOCK
            self.state.view_deadline = t.ticks_add(now, config.CLOCK_DWELL_MS)
            if hasattr(self._view, "invalidate"):
                self._view.invalidate()
        return True

    def _handle_view_deadline(self, snapshot, now):
        """Rotate or re-arm dwell; return True when painted content changes."""
        t = self._ticks
        nxt = next_view_after_dwell(self.state.active_view, snapshot)
        if nxt == self.state.active_view:
            # Stay on Clock (invalid local) — re-arm Clock dwell only.
            self.state.view_deadline = t.ticks_add(now, config.CLOCK_DWELL_MS)
            return False

        self.state.active_view = nxt
        if nxt == VIEW_CALENDAR:
            self._rebuild_month_grid(snapshot.local)
            self._invalidate_calendar()
            self.state.view_deadline = t.ticks_add(now, config.CALENDAR_DWELL_MS)
        else:
            if hasattr(self._view, "invalidate"):
                self._view.invalidate()
            self.state.view_deadline = t.ticks_add(now, config.CLOCK_DWELL_MS)
        return True

    def _rebuild_month_grid(self, local):
        self._month_grid = build_month_grid(
            local.year,
            local.month,
            local.year,
            local.month,
            local.day,
        )

    def _invalidate_calendar(self):
        if hasattr(self._calendar_view, "invalidate"):
            self._calendar_view.invalidate()

    def _render(self, snapshot, now):
        reveal_started = self._bar_reveal_started
        if self.state.active_surface == SURFACE_BAR and reveal_started == now:
            bar_elapsed = config.BAR_ANIMATION_FRAME_MS
        elif reveal_started is None:
            bar_elapsed = 0
        else:
            bar_elapsed = self._ticks.ticks_diff(now, reveal_started)
        if self.state.active_view == VIEW_CALENDAR:
            grid = self._month_grid
            if grid is None and snapshot.local is not None:
                self._rebuild_month_grid(snapshot.local)
                grid = self._month_grid
            self._compositor.render(
                self._calendar_view,
                snapshot,
                grid,
                active_surface=self.state.active_surface,
                bar_elapsed_ms=bar_elapsed,
            )
        else:
            self._compositor.render(
                self._view,
                snapshot,
                active_surface=self.state.active_surface,
                bar_elapsed_ms=bar_elapsed,
            )

    def run_forever(self, sleep_ms_fn=None):
        """Device loop: step + short sleep. Not used by host tests."""
        if sleep_ms_fn is None:
            from time import sleep_ms as sleep_ms_fn

        if not self._booted:
            self.boot()
        while True:
            self.step()
            sleep_ms_fn(10)
