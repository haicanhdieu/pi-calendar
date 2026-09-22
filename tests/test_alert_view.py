from src import config
from src.time.model import DateTime, TimeSnapshot, TRUST_SYNCED, TRUST_UNSYNCED
from src.ui.alert_view import AlertView
from src.ui.display_port import FakeDisplayPort


def _snapshot(trust):
    local = DateTime(2026, 9, 9, 2, 7, 0, 0)
    return TimeSnapshot(local, local, trust, 0)


def test_active_alert_renders_exact_labels_and_fixed_bands():
    display = FakeDisplayPort()
    AlertView(display).render(_snapshot(TRUST_SYNCED), _snapshot(TRUST_SYNCED).local, 15)
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "ALERT" in texts
    assert "07:00" in texts
    assert "STOP" in texts
    assert "POSTPONE 15 MIN" in texts
    assert ("fill_rect", 0, 0, 320, 240, config.COLOR_BACKGROUND) in display.ops


def test_active_alert_uses_requested_colors_and_high_contrast_action_bands():
    display = FakeDisplayPort()
    AlertView(display).render(_snapshot(TRUST_SYNCED), _snapshot(TRUST_SYNCED).local, 15)

    assert any(
        op[0] == "draw_text" and op[1] == "ALERT" and op[4:] == (config.FONT_SETTINGS_STATUS, config.COLOR_ALERT)
        for op in display.ops
    )
    assert any(
        op[0] == "draw_text" and op[1] == "07:00" and op[4:] == (config.FONT_TIME, config.COLOR_LUNAR)
        for op in display.ops
    )
    assert ("fill_rect", 0, 66, 320, 108, config.COLOR_PRIMARY) in display.ops
    assert ("fill_rect", 0, 186, 320, 54, config.COLOR_SECONDARY) in display.ops
    assert any(
        op[0] == "draw_text" and op[1] == "STOP" and op[5] == config.COLOR_BACKGROUND
        for op in display.ops
    )
    assert any(
        op[0] == "draw_text" and op[1] == "POSTPONE 15 MIN" and op[5] == config.COLOR_BACKGROUND
        for op in display.ops
    )


def test_unsynced_badge_is_preserved_without_changing_alert_labels():
    display = FakeDisplayPort()
    AlertView(display).render(_snapshot(TRUST_UNSYNCED), _snapshot(TRUST_UNSYNCED).local, 10)
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "UNSYNCED" in texts
    assert "ALERT" in texts


def test_postpone_hit_uses_only_the_lower_band():
    from src.ui.alert_view import postpone_hit

    assert not postpone_hit(185, 240)
    assert postpone_hit(186, 240)
    assert postpone_hit(239, 240)


def test_stop_hit_excludes_padding_gaps():
    from src.ui.alert_view import stop_hit

    assert not stop_hit(65, 240)
    assert stop_hit(66, 240)
    assert stop_hit(173, 240)
    assert not stop_hit(174, 240)


def test_postponed_confirmation_renders_exact_local_due_date_and_time():
    display = FakeDisplayPort()
    due = DateTime(2026, 10, 1, 3, 14, 17, 0)
    AlertView(display).render_postponed(_snapshot(TRUST_SYNCED), due)
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "POSTPONED" in texts
    assert "DUE 2026-10-01 14:17" in texts
