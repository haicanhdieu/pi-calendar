from src import config
from src.ui.alert_list_view import AlertListView
from src.ui.display_port import FakeDisplayPort


def test_toggle_and_feedback_redraw_only_changed_controls():
    from src.ui.alerts import render_alert_surface
    from src.ui.compositor import UiCompositor

    display = FakeDisplayPort()
    view = AlertListView(display)
    compositor = UiCompositor(display)
    alerts = [
        {"id": "a", "hour": 7, "minute": 5, "weekdays": [], "enabled": False},
        {"id": "b", "hour": 8, "minute": 30, "weekdays": [], "enabled": False},
    ]
    render_alert_surface(compositor, view, alerts)
    display.ops.clear()
    alerts[0]["enabled"] = True
    view.feedback_alert_id = "a"
    view.feedback_color = config.COLOR_PRESS_FLASH
    render_alert_surface(compositor, view, alerts)
    assert [op for op in display.ops if op[0] == "fill_rect"] == [
        ("fill_rect", 232, 27, 80, 30, config.COLOR_PRESS_FLASH),
    ]
    assert [op[1] for op in display.ops if op[0] == "draw_text"] == ["ON"]

    display.ops.clear()
    view.clear_feedback()
    render_alert_surface(compositor, view, alerts)
    assert [op for op in display.ops if op[0] == "fill_rect"] == [
        ("fill_rect", 232, 27, 80, 30, config.COLOR_PRIMARY),
    ]
    display.ops.clear()
    render_alert_surface(compositor, view, alerts)
    assert display.ops == []

    # Metadata changes and re-entry must repaint the list, not just controls.
    alerts[0]["minute"] = 6
    render_alert_surface(compositor, view, alerts)
    assert ("fill_rect", 0, 0, 320, 240, config.COLOR_BACKGROUND) in display.ops
    display.ops.clear()
    compositor._prev_was_settings = False
    render_alert_surface(compositor, view, alerts)
    assert ("fill_rect", 0, 0, 320, 240, config.COLOR_BACKGROUND) in display.ops


def test_alert_list_draws_recurrence_and_explicit_state_controls():
    display = FakeDisplayPort()
    view = AlertListView(display)
    alerts = [
        {"id": "a", "hour": 7, "minute": 5, "weekdays": [0, 2, 4], "enabled": True},
        {"id": "b", "hour": 8, "minute": 30, "weekdays": [], "enabled": False},
    ]

    view.render(alerts)

    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "ALERTS" in texts
    assert "07:05" in texts and "Mo We Fr" in texts and "ON" in texts
    assert "08:30" in texts and "Once" in texts and "OFF" in texts
    assert ("fill_rect", 232, 27, 80, 30, config.COLOR_PRIMARY) in display.ops
    assert ("fill_rect", 232, 65, 80, 30, config.COLOR_SECONDARY) in display.ops


def test_state_controls_are_spaced_and_paged_and_empty_state_is_bounded():
    display = FakeDisplayPort()
    view = AlertListView(display)
    alerts = [
        {"id": str(index), "hour": 7, "minute": index, "weekdays": [], "enabled": True}
        for index in range(6)
    ]

    for index in range(5):
        top = 23 + index * 38
        assert view.state_index(alerts, 224, top) == index
        assert view.state_index(alerts, 319, top + 37) == index
    assert view.state_index(alerts, 312, 30) == 0
    assert view.state_index(alerts, 231, 30) == 0
    assert view.state_index(alerts, 280, 60) == 0
    assert view.state_index(alerts, 280, 61) == 1
    assert view.state_index(alerts, 223, 30) is None
    assert view.state_index(alerts, 280, 175) == 4
    assert view.state_index(alerts, 280, 213) is None

    view.render(alerts)
    assert any(op[0] == "draw_text" and op[1] == "1/2" for op in display.ops)
    view.page = 1
    assert view.state_index(alerts, 280, 27) == 5
    display.ops.clear()
    view.render(alerts)
    assert any(op[0] == "draw_text" and op[1] == "NEXT" for op in display.ops) is False
    assert any(op[0] == "draw_text" and op[1] == "PREV" for op in display.ops)

    view.render([])
    assert any(op[0] == "draw_text" and op[1] == "No alerts stored" for op in display.ops)


def test_feedback_tracks_alert_id_and_page_change_clears_it():
    from types import SimpleNamespace

    from src.ui.alert_list_view import handle_touch

    display = FakeDisplayPort()
    view = AlertListView(display)
    alerts = [
        {"id": str(index), "hour": 7, "minute": index, "weekdays": [], "enabled": True}
        for index in range(6)
    ]
    view.feedback_alert_id = "1"
    view.feedback_color = config.COLOR_PRESS_FLASH
    view.render(alerts)
    assert ("fill_rect", 232, 65, 80, 30, config.COLOR_PRESS_FLASH) in display.ops

    display.ops.clear()
    view.render([alerts[1], alerts[0], *alerts[2:]])
    assert ("fill_rect", 232, 27, 80, 30, config.COLOR_PRESS_FLASH) in display.ops

    app = SimpleNamespace(
        _alert_list_view=view,
        _alert_cfg=(None, None, {"alerts": alerts}),
        _view=SimpleNamespace(_display=display),
    )
    assert handle_touch(app, 250, 230) == (True, True)
    assert view.page == 1
    assert view.feedback_alert_id is None
    assert view.feedback_until is None
