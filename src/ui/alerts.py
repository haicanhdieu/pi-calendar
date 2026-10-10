"""Lazy full-screen alert-list rendering path."""

from src import config

_PREVIOUS_DATA = None


def render_alert_surface(compositor, view, alerts):
    global _PREVIOUS_DATA
    feedback = (
        getattr(view, "feedback_alert_id", None),
        getattr(view, "feedback_color", None),
    )
    data = tuple(
        (item.get("id"), item.get("hour"), item.get("minute"),
         tuple(item.get("weekdays", [])), bool(item.get("enabled")))
        for item in alerts
    )
    data = (data, getattr(view, "page", 0), feedback)
    if not compositor._prev_was_settings or data != _PREVIOUS_DATA:
        display = compositor._display
        display.fill_rect(0, 0, display.width, display.height, config.COLOR_BACKGROUND)
        if hasattr(view, "invalidate"):
            view.invalidate()
        view.render(alerts)
        _PREVIOUS_DATA = data
        compositor._prev_badge = False
        compositor._prev_bar_height = 0
    compositor._prev_was_settings = True


def render(app):
    if getattr(app, "_alert_list_view", None) is None:
        from src.ui.alert_list_view import AlertListView

        app._alert_list_view = AlertListView(app._view._display)
    settings = app._alert_cfg[2]
    alerts = settings.get("alerts", []) if isinstance(settings, dict) else []
    view = app._alert_list_view
    if view.feedback_until is not None and app._ticks.ticks_diff(
        view.feedback_until, app._ticks.ticks_ms()
    ) <= 0:
        view.clear_feedback()
    render_alert_surface(app._compositor, view, alerts)
