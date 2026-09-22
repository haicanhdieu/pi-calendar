"""Lazy App alert orchestration."""

from src import config
from src.alert.scheduler import (
    AlertScheduler,
    add_minutes,
    due_reached,
    normalize_postpone_minutes,
)
from src.alert.terminal import disable_one_time_alerts


def _pending_payload(postponed):
    due = postponed["due"]
    return {
        "due": {
            "year": due.year, "month": due.month, "day": due.day,
            "weekday": due.weekday, "hour": due.hour, "minute": due.minute,
        },
        "alerts": [dict(item, weekdays=list(item.get("weekdays", [])))
                   for item in postponed["alerts"]],
        "delay": postponed["delay"],
    }


def _pending_datetime(raw):
    from src.time.model import DateTime

    due = raw.get("due", {})
    return DateTime(
        due["year"], due["month"], due["day"], due["weekday"],
        due["hour"], due["minute"], 0,
    )


def _commit_alert_state(store, settings, pending, log):
    if store is None or not isinstance(settings, dict):
        return settings
    try:
        return store.commit(
            wifi_ssid=settings["wifi_ssid"],
            wifi_password=settings["wifi_password"],
            admin_salt_hex=settings["admin_salt"],
            admin_verifier_hex=settings["admin_verifier"],
            color_scheme=settings["color_scheme"],
            alerts=settings.get("alerts", []),
            postpone_delay_minutes=settings.get("postpone_delay_minutes", 10),
            pending_postponed_occurrence=pending,
        )
    except Exception as exc:
        log("alert_fail persist %s" % getattr(exc, "code", "commit"))
        return None


def _refresh_committed_settings(app, buzzer, store, settings):
    """Read latest atomically committed config at alert-loop boundary."""
    if store is None:
        return settings
    try:
        committed = store.load()
    except Exception as exc:
        app._log("alert_fail load %s" % getattr(exc, "code", "load"))
        return settings
    if isinstance(committed, dict):
        app._alert_cfg = (buzzer, store, committed)
        return committed
    return settings


_BUZZER_CODES = {
    "init_fail", "not_ready", "high_fail", "low_fail",
}
_BUZZER_SUCCESS = {
    "ok", "silent", "high_start", "high_end", "low_end", "wait",
}


def _failure_code(result):
    if isinstance(result, str) and result in _BUZZER_CODES:
        return result
    return "operation"


def _is_buzzer_failure(result):
    return result is not None and result not in _BUZZER_SUCCESS


def _log_failure_once(app, phase, code, attr):
    if getattr(app, attr, False):
        return
    setattr(app, attr, True)
    app._log("alert_fail %s %s" % (phase, code))


def _buzzer_fault(app, buzzer, code):
    setattr(app, "_alert_buzzer_faulted", True)
    _log_failure_once(app, "buzzer", code, "_alert_buzzer_failure_logged")
    try:
        buzzer.silence()
    except Exception:
        pass


def _prepare_buzzer(app, buzzer):
    if buzzer is None or not getattr(app, "_alert_buzzer_faulted", False):
        return buzzer is not None
    initialize = getattr(buzzer, "initialize", None)
    if initialize is None:
        return False
    try:
        result = initialize()
    except Exception:
        _buzzer_fault(app, buzzer, "init_exception")
        return False
    if _is_buzzer_failure(result):
        _buzzer_fault(app, buzzer, _failure_code(result))
        return False
    app._alert_buzzer_faulted = False
    app._alert_buzzer_failure_logged = False
    return True


def _buzzer_tick(app, buzzer, now, sounding):
    if buzzer is None or getattr(app, "_alert_buzzer_faulted", False):
        return
    try:
        result = buzzer.tick(now, sounding)
    except Exception:
        _buzzer_fault(app, buzzer, "tick_exception")
        return
    if _is_buzzer_failure(result):
        _buzzer_fault(app, buzzer, _failure_code(result))


def _buzzer_silence(app, buzzer):
    if buzzer is None:
        return
    try:
        result = buzzer.silence()
    except Exception:
        _buzzer_fault(app, buzzer, "silence_exception")
        return
    if _is_buzzer_failure(result):
        _buzzer_fault(app, buzzer, _failure_code(result))


def _safe_render(app, snapshot, render_fn, phase="render"):
    if getattr(app, "_alert_render_failed", False):
        return False
    try:
        render_fn()
        return True
    except Exception:
        _log_failure_once(app, phase, "exception", "_alert_render_failure_logged")
        app._alert_render_failed = True
        return False


def _safe_base_render(app, snapshot, now):
    try:
        app._render(snapshot, now)
    except Exception:
        _log_failure_once(app, "render", "base_exception", "_alert_base_render_failure_logged")


def t(app, edge_down, y):
    if not edge_down:
        app.state.surface_deadline = None
        app._alert_touch_latched = False
        return
    active = getattr(app, "_active_alert", None)
    if active is None:
        return
    app.state.surface_deadline = -1
    display = app._view._display
    from src.ui.alert_view import stop_hit

    top = display.height // 4
    if stop_hit(y, display.height):
        if not getattr(app, "_alert_touch_latched", False):
            active["stop"] = True
            app._alert_touch_latched = True
    elif y is not None and y >= top + display.height // 2:
        from src.ui.alert_view import postpone_hit

        if not getattr(app, "_alert_touch_latched", False) and postpone_hit(y, display.height):
            active["postpone"] = True
            app._alert_touch_latched = True


def render(app, snapshot):
    if getattr(app, "_alert_view", None) is None:
        from src.ui.alert_view import AlertView

        app._alert_view = AlertView(app._view._display)
    occurrence = app._active_alert
    return _safe_render(app, snapshot, lambda: app._alert_view.render(
        snapshot,
        occurrence["local"],
        occurrence["postpone_minutes"],
        len(occurrence["alerts"]),
    ))


def render_postponed(app, snapshot, postponed):
    if getattr(app, "_alert_view", None) is None:
        from src.ui.alert_view import AlertView

        app._alert_view = AlertView(app._view._display)
    return _safe_render(app, snapshot, lambda: app._alert_view.render_postponed(
        snapshot,
        postponed["due"],
        len(postponed["alerts"]),
    ))


def evaluate(app, snapshot, now):
    ticks = app._ticks
    buzzer, store, settings = app._alert_cfg
    settings = _refresh_committed_settings(app, buzzer, store, settings)
    if not isinstance(settings, dict):
        settings = store.load() if store is not None else {}
        if not isinstance(settings, dict):
            settings = {"alerts": [], "postpone_delay_minutes": 10}
        app._alert_cfg = (buzzer, store, settings)
    active = getattr(app, "_active_alert", None)
    postponed = getattr(app, "_postponed_alert", None)
    if postponed is None:
        raw_pending = settings.get("pending_postponed_occurrence")
        if isinstance(raw_pending, dict):
            try:
                postponed = {
                    "alerts": [dict(item) for item in raw_pending["alerts"]],
                    "due": _pending_datetime(raw_pending),
                    "delay": raw_pending["delay"],
                    "confirmation": False,
                    "persisted": True,
                    "restored": True,
                }
                app._postponed_alert = postponed
            except (KeyError, TypeError, ValueError):
                postponed = None
    if postponed is not None:
        if due_reached(snapshot.local, postponed["due"]):
            if postponed.get("persisted") and postponed.get("restored"):
                cleared = _commit_alert_state(store, settings, None, app._log)
                if cleared is None and store is not None:
                    return False
                settings = cleared or settings
                app._alert_cfg = (buzzer, store, settings)
                # A restart must never turn an overdue pending occurrence into
                # a same-minute base-alert raise.
                app._postponed_alert = None
                return True
            if postponed.get("persisted"):
                cleared = _commit_alert_state(store, settings, None, app._log)
                if cleared is None and store is not None:
                    return False
                settings = cleared or settings
                app._alert_cfg = (buzzer, store, settings)
            app._postponed_alert = None
            app._active_alert = {
                "alerts": postponed["alerts"],
                "local": postponed["due"],
                "postpone_minutes": postponed["delay"],
            }
            app._alert_started_ticks = now
            app._alert_render_failed = False
            app._alert_render_failure_logged = False
            _prepare_buzzer(app, buzzer)
            _buzzer_tick(app, buzzer, now, True)
            render(app, snapshot)
            return True
        if postponed.get("confirmation"):
            postponed["confirmation"] = False
            return False
        postponed["restored"] = False
        return False
    if active is not None:
        # Admit later due alerts into same occurrence. Keep original start
        # tick and local time so cadence and auto-stop deadline stay stable.
        newly_due = app._alert_scheduler.evaluate(
            snapshot.local, settings.get("alerts", [])
        )
        if newly_due:
            member_ids = {item.get("id") for item in active["alerts"]}
            active["alerts"].extend(
                item for item in newly_due if item.get("id") not in member_ids
            )

        if active.get("postpone"):
            _buzzer_silence(app, buzzer)
            delay = normalize_postpone_minutes(settings.get("postpone_delay_minutes"))
            postponed = {
                "alerts": active["alerts"],
                "due": add_minutes(active["local"], delay),
                "delay": delay,
                "confirmation": True,
            }
            committed = _commit_alert_state(store, settings, _pending_payload(postponed), app._log)
            if store is not None and committed is None:
                return False
            if committed is not None:
                settings = committed
                app._alert_cfg = (buzzer, store, settings)
            app._postponed_alert = postponed
            app._active_alert = None
            app._alert_started_ticks = None
            app._alert_render_failed = False
            app._alert_render_failure_logged = False
            app.state.active_surface = "rotation"
            app._rearm_active_view_dwell(now)
            render_postponed(app, snapshot, postponed)
            return True
        if active.get("stop"):
            if buzzer is not None:
                buzzer.silence()
            settings = disable_one_time_alerts(
                active["alerts"], settings,
                store, app._log,
            )
            if store is not None and settings is not None:
                cleared = _commit_alert_state(store, settings, None, app._log)
                if cleared is not None:
                    settings = cleared
            app._alert_cfg = (buzzer, store, settings)
            app._alert_settings = settings
            app._active_alert = None
            app._alert_started_ticks = None
            app.state.active_surface = "rotation"
            app._rearm_active_view_dwell(now)
            _safe_base_render(app, snapshot, now)
            return True
        if ticks.ticks_diff(now, app._alert_started_ticks) >= config.ALERT_AUTO_STOP_MS:
            _buzzer_silence(app, buzzer)
            settings = disable_one_time_alerts(
                active["alerts"], settings,
                store, app._log,
            )
            if store is not None and settings is not None:
                cleared = _commit_alert_state(store, settings, None, app._log)
                if cleared is not None:
                    settings = cleared
            app._alert_cfg = (buzzer, store, settings)
            app._alert_settings = settings
            app._active_alert = None
            app._alert_started_ticks = None
            app.state.active_surface = "rotation"
            app._rearm_active_view_dwell(now)
            _safe_base_render(app, snapshot, now)
            return True
        _buzzer_tick(app, buzzer, now, True)
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
        "postpone_minutes": normalize_postpone_minutes(settings.get("postpone_delay_minutes")),
    }
    app._alert_started_ticks = now
    app._alert_render_failed = False
    app._alert_render_failure_logged = False
    _prepare_buzzer(app, buzzer)
    _buzzer_tick(app, buzzer, now, True)
    render(app, snapshot)
    return True
