from src import config
from src.ui.alert_list_view import AlertListView
from src.ui.display_port import FakeDisplayPort


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
    assert ("fill_rect", 264, 23, 48, 21, config.COLOR_PRIMARY) in display.ops
    assert ("fill_rect", 264, 44, 48, 21, config.COLOR_SECONDARY) in display.ops


def test_state_controls_have_distinct_48_by_21_hit_regions_and_empty_state():
    display = FakeDisplayPort()
    view = AlertListView(display)
    alerts = [{"hour": 7, "minute": 0, "weekdays": [], "enabled": True}]

    assert view.state_index(alerts, 264, 23) == 0
    assert view.state_index(alerts, 311, 43) == 0
    assert view.state_index(alerts, 312, 30) is None
    assert view.state_index(alerts, 263, 30) is None
    assert view.state_index(alerts, 280, 44) is None

    view.render([])
    assert any(op[0] == "draw_text" and op[1] == "No alerts stored" for op in display.ops)
