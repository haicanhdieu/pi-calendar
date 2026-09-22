"""Config-mode composition root: the web stack, and no clock stack at all.

The device reaches this module only after clock mode answered a browser knock
on port 80, wrote the config-mode flag and reset. Everything here is imported
at module scope so ``tools/hostsim`` can measure exactly what is resident
while the station admin site is live.

What is deliberately absent is the point: App, the clock/calendar/settings
views, the compositor, the touch stack and the calendar grid maths are never
constructed here. That is what gives the authenticated request path -- router,
sessions, KDF, the settings POST handlers and the alert editor -- room to be
resident at once in a 179,328-byte heap (issue #2).

Config mode is a session, not a state: it ends on an explicit "return to
clock" from the settings page, on an idle timeout, or when an alert comes due,
and each ending is a plain reset back into clock mode.
"""

from src import config
from src import ticks as default_ticks
from src.alert.scheduler import AlertScheduler
from src.device.display.color import color565
from src.device.display.font import centered_text
from src.device.network.mailbox import Mailbox
from src.device.network.models import MODE_STATION_ONLINE, make_settings_coordinator
from src.time.service import utc_to_local

_BLACK = color565(0, 0, 0)
_NAVY = color565(0, 18, 38)
_CYAN = color565(0, 210, 255)
_WHITE = color565(255, 255, 255)

# Re-check the alert list this often. Config mode holds no scheduler state
# across a reset, so this only has to be fast enough that the reboot back into
# clock mode still leaves the alarm firing within its own minute.
_ALERT_POLL_MS = 5_000


def _paint(display, ip):
    """Draw the whole static config-mode screen (no partial redraw logic)."""
    display.fill(_NAVY)
    display.fill_rect(0, 0, display.width, 18, _BLACK)
    display.fill_rect(0, display.height - 18, display.width, 18, _BLACK)
    centered_text(display, "CONFIG", 72, 5, _WHITE)
    centered_text(display, "MODE", 120, 5, _WHITE)
    centered_text(display, ip if ip else "CONNECTING", 180, 2, _CYAN)


def _due_alerts(scheduler, clock_port, settings_store):
    """Enabled alerts due in the current local minute, or an empty list."""
    try:
        utc = clock_port.read_utc()
    except Exception:
        return []
    if utc is None:
        return []
    try:
        local = utc_to_local(utc)
        settings = settings_store.load()
    except Exception:
        return []
    alerts = settings.get("alerts", ()) if isinstance(settings, dict) else ()
    return scheduler.evaluate(local, alerts)


def run(display, settings_store, clock_port, reboot_port, sleep_ms_fn,
        led=None, log=None, ticks_module=None):
    """Serve the admin site until config mode ends, then reset."""
    log = print if log is None else log
    t = default_ticks if ticks_module is None else ticks_module
    import gc

    mailbox = Mailbox()
    network_events = []
    coordinator = make_settings_coordinator(
        mailbox,
        settings_store,
        network_events,
        ntp_address=config.NTP_SERVER_ADDRESS,
        station_web=True,
    )

    scheduler = AlertScheduler()
    painted_ip = None
    _paint(display, None)
    if led is not None:
        led.value(0)
    log("Config mode: serving admin site")

    now = t.ticks_ms()
    idle_deadline = t.ticks_add(now, config.CONFIG_MODE_IDLE_MS)
    alert_deadline = t.ticks_add(now, _ALERT_POLL_MS)

    while True:
        now = t.ticks_ms()
        try:
            coordinator.tick()
        except MemoryError:
            gc.collect()
            log("Config mode: MemoryError, recovered")
        except Exception as exc:
            log("Config mode: transient error, recovered: {}".format(exc))

        if coordinator.mode == MODE_STATION_ONLINE:
            ip = coordinator.station_ip
            if ip and ip != painted_ip:
                painted_ip = ip
                _paint(display, ip)
                log("Config mode: http://{}".format(ip))

        if coordinator.web_busy:
            idle_deadline = t.ticks_add(now, config.CONFIG_MODE_IDLE_MS)

        if coordinator.web_exit_requested:
            log("Config mode: exit requested")
            return _leave(coordinator, reboot_port, sleep_ms_fn)

        if t.ticks_diff(now, alert_deadline) >= 0:
            alert_deadline = t.ticks_add(now, _ALERT_POLL_MS)
            if _due_alerts(scheduler, clock_port, settings_store):
                # Clock mode owns alarm playback, the buzzer and the dismiss
                # surface, so the alert is served by going back there now.
                log("Config mode: alert due; returning to clock")
                return _leave(coordinator, reboot_port, sleep_ms_fn)

        if t.ticks_diff(now, idle_deadline) >= 0:
            log("Config mode: idle timeout")
            return _leave(coordinator, reboot_port, sleep_ms_fn)

        sleep_ms_fn(10)


def _leave(coordinator, reboot_port, sleep_ms_fn):
    """Flush any pending response, then reset back into clock mode.

    The config-mode flag was already deleted at entry, so this reset lands in
    clock mode; nothing here can wedge the device in a reboot loop.
    """
    try:
        coordinator.drain_web_writes()
    except Exception:
        pass
    sleep_ms_fn(250)
    reboot_port.reset()
