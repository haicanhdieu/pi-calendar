"""Clock-mode composition root: the clock stack, and no web stack at all.

Everything the clock face needs is imported here at module scope, which is
what makes ``tools/hostsim`` able to measure it. ``main.py`` imports this
module only after deciding the boot is a clock boot, so a config-mode boot
never pays for App, the views, the compositor or the touch stack.

The only HTTP presence in this mode is ``ConfigModeKnock``: a bare listening
socket on port 80 that answers one connection with a fixed interstitial and
reboots into config mode. Clock mode never imports the router, the pages,
sessions or the KDF, so the two heavy halves are never live together.
"""

from src import config
from src.credentials import credentials_valid
from src.device.display.adapter import Ili9341DisplayPort
from src.device.network.mailbox import Mailbox
from src.device.network.models import (
    MODE_SETUP_AP,
    MODE_STATION_CONNECTING,
    MODE_STATION_ONLINE,
    make_settings_coordinator,
    ntp_sync_enabled,
)
from src.device.knock import ConfigModeKnock
from src.device.config_mode_port import ConfigModePort
from src.device.touch_port import TouchPort
from src.app import App
from src.ui.calendar_view import CalendarView
from src.ui.clock_view import ClockView
from src.ui.compositor import UiCompositor
from src.ui.touch_calibration import CalibratedTouchPort


def run(display, spi, touch_cs, settings_store, clock_port, reboot_port,
        sleep_ms_fn, led=None, log=None):
    """Run the clock loop until a browser knocks and reboots into config."""
    log = print if log is None else log
    import gc

    touch_port = CalibratedTouchPort(TouchPort(spi, touch_cs, display.cs))
    display_port = Ili9341DisplayPort(display)
    clock_view = ClockView(display_port)
    calendar_view = CalendarView(display_port)
    compositor = UiCompositor(display_port)

    # Keep buzzer adapter out of module-scope boot imports; construct it only
    # after display/network prerequisites are ready.
    from src.device.buzzer_port import BuzzerPort, INIT_OK

    buzzer_port = BuzzerPort(
        config.BUZZER_SIGNAL_PIN,
        config.BUZZER_HIGH_MS,
        config.BUZZER_LOW_MS,
        active_high=config.BUZZER_ACTIVE_HIGH,
    )
    if buzzer_port.init_result != INIT_OK:
        log("Buzzer init failed: {}".format(buzzer_port.init_result))

    mailbox = Mailbox()
    network_events = []
    coordinator = make_settings_coordinator(
        mailbox,
        settings_store,
        network_events,
        ntp_address=config.NTP_SERVER_ADDRESS,
        # Clock mode serves no admin site; the knock listener owns port 80.
        # Setup-AP provisioning is unaffected and still runs its own web stack.
        station_web=False,
    )
    # Store-owned Wi-Fi: hold NTP until App sees station online (story 1.3).
    # Connecting/setup must not enqueue SyncCommands that expire mid-associate.
    creds_ok = settings_store.is_configured() or credentials_valid()
    if coordinator.mode in (MODE_SETUP_AP, MODE_STATION_CONNECTING):
        sync_enabled = False
    else:
        sync_enabled = ntp_sync_enabled(coordinator.mode, creds_ok)

    app = App(
        clock_port=clock_port,
        clock_view=clock_view,
        calendar_view=calendar_view,
        compositor=compositor,
        mailbox=mailbox,
        sync_enabled=sync_enabled,
        network_events=network_events,
        buzzer_port=buzzer_port,
        settings_store=settings_store,
        touch_port=touch_port,
        reboot_port=reboot_port,
        config_mode_port=ConfigModePort(reboot_port),
        sleep_ms_fn=sleep_ms_fn,
    )

    if not creds_ok and coordinator.mode != MODE_SETUP_AP:
        app.report_time_source_failure("missing or empty Wi-Fi credentials")

    if led is not None:
        led.value(0)
    log("App loop starting (Clock view)")
    app.boot()

    knock = ConfigModeKnock()
    while True:
        try:
            coordinator.tick()
            app.step()
            if coordinator.mode == MODE_STATION_ONLINE and knock.tick():
                log("config_mode requested; rebooting")
                # Let the browser finish reading the interstitial before the
                # reset tears the connection down; without this the page it
                # was told to refresh never renders.
                sleep_ms_fn(300)
                reboot_port.reset()
                return
        except MemoryError:
            gc.collect()
            log("App loop: MemoryError, recovered")
            if hasattr(clock_view, "invalidate"):
                clock_view.invalidate()
            if hasattr(calendar_view, "invalidate"):
                calendar_view.invalidate()
        except Exception as exc:
            log("App loop: transient error, recovered: {}".format(exc))
            if hasattr(clock_view, "invalidate"):
                clock_view.invalidate()
            if hasattr(calendar_view, "invalidate"):
                calendar_view.invalidate()
        sleep_ms_fn(10)
