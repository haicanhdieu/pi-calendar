"""Lazy full-screen alert-list rendering path."""

from src.ui.alert_list_view import ROWS_PER_PAGE


def render_alert_surface(compositor, view, alerts):
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
    previous = getattr(view, "_previous_data", None)
    full_redraw = (
        not compositor._prev_was_settings
        or previous is None
        or data[1] != previous[1]
        or len(data[0]) != len(previous[0])
    )
    if not full_redraw:
        for current, old in zip(data[0], previous[0]):
            if current[:4] != old[:4]:
                full_redraw = True
                break
    if full_redraw:
        view.render(alerts)
        compositor._prev_badge = False
        compositor._prev_bar_height = 0
    elif data != previous:
        start = view.page * ROWS_PER_PAGE
        for index in range(start, min(start + ROWS_PER_PAGE, len(alerts))):
            alert_id = data[0][index][0]
            old_feedback = previous[2][1] if previous[2][0] == alert_id else None
            new_feedback = feedback[1] if feedback[0] == alert_id else None
            if data[0][index][4] != previous[0][index][4] or old_feedback != new_feedback:
                view.render_state(alerts[index], index)
    # Publish only after drawing succeeds so failed SPI writes retry.
    view._previous_data = (data[0], view.page, feedback)
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
