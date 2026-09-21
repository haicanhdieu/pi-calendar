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


def test_unsynced_badge_is_preserved_without_changing_alert_labels():
    display = FakeDisplayPort()
    AlertView(display).render(_snapshot(TRUST_UNSYNCED), _snapshot(TRUST_UNSYNCED).local, 10)
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "UNSYNCED" in texts
    assert "ALERT" in texts


def test_postpone_hit_uses_only_the_lower_band():
    from src.ui.alert_view import postpone_hit

    assert not postpone_hit(179, 240)
    assert postpone_hit(180, 240)
    assert postpone_hit(239, 240)


def test_postponed_confirmation_renders_exact_local_due_date_and_time():
    display = FakeDisplayPort()
    due = DateTime(2026, 10, 1, 3, 14, 17, 0)
    AlertView(display).render_postponed(_snapshot(TRUST_SYNCED), due)
    texts = [op[1] for op in display.ops if op[0] == "draw_text"]
    assert "POSTPONED" in texts
    assert "DUE 2026-10-01 14:17" in texts
