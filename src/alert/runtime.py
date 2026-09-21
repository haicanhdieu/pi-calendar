"""Lazy App alert orchestration."""

from src import config
from src.alert.scheduler import AlertScheduler
from src.alert.terminal import disable_one_time_alerts


def render(app, snapshot):
    if getattr(app, "_alert_view", None) is None:
        from src.ui.alert_view import AlertView

        app._alert_view = AlertView(app._view._display)
    occurrence = app._active_alert
    app._alert_view.render(
        snapshot,
        occurrence["local"],
        occurrence["postpone_minutes"],
        len(occurrence["alerts"]),
    )


def evaluate(app, snapshot, now):
    ticks = app._ticks
    buzzer, store, settings = app._alert_cfg
    if not isinstance(settings, dict):
        settings = store.load() if store is not None else {}
        if not isinstance(settings, dict):
            settings = {"alerts": [], "postpone_delay_minutes": 10}
        app._alert_cfg = (buzzer, store, settings)
    active = getattr(app, "_active_alert", None)
    if active is not None:
        if ticks.ticks_diff(now, app._alert_started_ticks) >= config.ALERT_AUTO_STOP_MS:
            if buzzer is not None:
                buzzer.silence()
            settings = disable_one_time_alerts(
                active["alerts"], settings,
                store, app._log,
            )
            app._alert_cfg = (buzzer, store, settings)
            app._alert_settings = settings
            app._active_alert = None
            app._alert_started_ticks = None
            app.state.active_surface = "rotation"
            app._rearm_active_view_dwell(now)
            app._render(snapshot, now)
            return True
        if buzzer is not None:
            buzzer.tick(now, True)
        render(app, snapshot)
        return True
    if getattr(app, "_alert_scheduler", None) is None:
        app._alert_scheduler = AlertScheduler()
    due = app._alert_scheduler.evaluate(snapshot.local, settings.get("alerts", []))
    if not due:
        return False
    app._active_alert = {
        "alerts": due,
        "local": snapshot.local,
        "postpone_minutes": settings.get("postpone_delay_minutes", 10),
    }
    app._alert_started_ticks = now
    if buzzer is not None:
        buzzer.tick(now, True)
    render(app, snapshot)
    return True
