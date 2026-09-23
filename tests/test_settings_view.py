"""Host tests for Settings view status/guideline rendering (Story 3.2)."""

from src import config
from src.ui.settings_view import SettingsView
from src.ui.display_port import FakeDisplayPort


def _texts(ops):
    return [op for op in ops if op[0] == "draw_text"]


def _setup_snapshot(ssid="PiCalendar-AP42", ip="192.168.4.1"):
    return {"kind": "setup", "ssid": ssid, "ip": ip}


def _station_snapshot(ssid="HomeWifi", ip="192.168.1.42"):
    return {"kind": "station_ip", "ssid": ssid, "ip": ip}


def test_setup_branch_draws_ssid_gateway_and_guideline():
    display = FakeDisplayPort()
    SettingsView(display).render(_setup_snapshot())

    texts = _texts(display.ops)
    labels = [t[1] for t in texts]
    assert "PiCalendar-AP42" in labels
    assert "192.168.4.1" in labels
    assert (
        "Connect to Wi-Fi PiCalendar-AP42 then browse to 192.168.4.1" in labels
    )

    ssid = next(t for t in texts if t[1] == "PiCalendar-AP42")
    gateway = next(t for t in texts if t[1] == "192.168.4.1")
    guideline = next(
        t
        for t in texts
        if t[1] == "Connect to Wi-Fi PiCalendar-AP42 then browse to 192.168.4.1"
    )
    assert ssid[4] == config.FONT_SETTINGS_STATUS
    assert ssid[5] == config.COLOR_PRIMARY
    assert gateway[4] == config.FONT_SETTINGS_STATUS
    assert gateway[5] == config.COLOR_PRIMARY
    assert guideline[4] == config.FONT_SETTINGS_GUIDELINE
    assert guideline[5] == config.COLOR_SECONDARY

    _, line_h = display.measure_text("Ag", config.FONT_SETTINGS_STATUS)
    assert ssid[3] == config.SETTINGS_TOP_PADDING_PX
    assert gateway[3] == ssid[3] + line_h + config.SETTINGS_STATUS_LINE_GAP_PX
    assert ssid[2] == (display.width - display.measure_text("PiCalendar-AP42", config.FONT_SETTINGS_STATUS)[0]) // 2
    assert gateway[2] == (display.width - display.measure_text("192.168.4.1", config.FONT_SETTINGS_STATUS)[0]) // 2
    assert guideline[3] == gateway[3] + line_h + config.SETTINGS_STATUS_GUIDELINE_GAP_PX


def test_station_branch_draws_ip_only_and_http_guideline():
    display = FakeDisplayPort()
    SettingsView(display).render(_station_snapshot())

    texts = _texts(display.ops)
    labels = [t[1] for t in texts if len(t[1]) > 1]
    assert labels == ["192.168.1.42", "Browse to http://192.168.1.42"]

    ip = texts[0]
    guideline = texts[1]
    assert ip[4] == config.FONT_SETTINGS_STATUS
    assert ip[5] == config.COLOR_PRIMARY
    assert guideline[4] == config.FONT_SETTINGS_GUIDELINE
    assert guideline[5] == config.COLOR_SECONDARY
    assert ip[3] == config.SETTINGS_TOP_PADDING_PX
    _, line_h = display.measure_text("Ag", config.FONT_SETTINGS_STATUS)
    assert guideline[3] == ip[3] + line_h + config.SETTINGS_STATUS_GUIDELINE_GAP_PX


def test_none_snapshot_draws_no_status_or_guideline_text():
    display = FakeDisplayPort()
    SettingsView(display).render(None)
    texts = _texts(display.ops)
    assert not any(op[4] == config.FONT_SETTINGS_STATUS for op in texts)
    assert not any(op[4] == config.FONT_SETTINGS_GUIDELINE for op in texts)
    assert any(op[1] == "R" and op[4] == config.FONT_SETTINGS_REBOOT for op in texts)


def test_unrecognized_kind_draws_no_status_or_guideline_text():
    display = FakeDisplayPort()
    SettingsView(display).render({"kind": "other"})
    texts = _texts(display.ops)
    assert not any(op[4] == config.FONT_SETTINGS_STATUS for op in texts)
    assert not any(op[4] == config.FONT_SETTINGS_GUIDELINE for op in texts)
    assert any(op[1] == "R" and op[4] == config.FONT_SETTINGS_REBOOT for op in texts)


def test_reboot_label_uses_specified_typography_and_tap_target():
    from src.ui.components import settings_reboot_item_rect

    display = FakeDisplayPort()
    SettingsView(display).render(None)

    reboot_x, reboot_y, reboot_w, reboot_h = settings_reboot_item_rect(display)
    reboot_chars = [
        op
        for op in display.ops
        if op[0] == "draw_text"
        and op[1] in config.SETTINGS_REBOOT_LABEL
        and reboot_y <= op[3] < reboot_y + reboot_h
    ]
    assert len(reboot_chars) == len(config.SETTINGS_REBOOT_LABEL)
    for op in reboot_chars:
        assert op[4] == config.FONT_SETTINGS_REBOOT
        assert op[5] == config.COLOR_SECONDARY

    item_x, item_y, item_w, item_h = reboot_x, reboot_y, reboot_w, reboot_h
    label_ops = [op for op in reboot_chars]
    min_x = min(op[2] for op in label_ops)
    max_x = max(op[2] for op in label_ops)
    min_y = min(op[3] for op in label_ops)
    max_y = max(op[3] for op in label_ops)
    assert item_x <= min_x
    assert max_x < item_x + item_w
    assert item_y <= min_y
    assert max_y < item_y + item_h
    assert item_w * item_h > (max_x - min_x + 1) * (max_y - min_y + 1)
    assert item_h == config.TAP_TARGET_SIZE_PX
    reboot_chars.sort(key=lambda op: op[2])
    step = (
        config.FONT_CELL_WIDTH * config.FONT_SCALE_SETTINGS_REBOOT
        + config.SETTINGS_REBOOT_LETTER_SPACING_PX
    )
    for left, right in zip(reboot_chars, reboot_chars[1:]):
        assert right[2] - left[2] == step


def test_setting_mode_label_is_above_reboot():
    from src.ui.components import (
        settings_mode_item_rect,
        settings_reboot_item_rect,
        settings_reboot_rect,
    )

    display = FakeDisplayPort()
    SettingsView(display).render(None)
    mode_chars = [
        op
        for op in display.ops
        if op[0] == "draw_text" and op[1] in config.SETTINGS_MODE_LABEL
        and op[3] < settings_reboot_rect(display)[1]
    ]
    reboot_y = settings_reboot_rect(display)[1]
    mode_rect = settings_mode_item_rect(display)
    reboot_rect = settings_reboot_item_rect(display)
    mode_x, mode_y, mode_w, mode_h = mode_rect
    assert mode_x >= 0 and mode_y >= 0
    assert mode_x + mode_w <= display.width
    assert mode_y + mode_h <= display.height
    assert mode_y + mode_h < reboot_rect[1]
    assert len(mode_chars) == len(config.SETTINGS_MODE_LABEL)
    assert max(op[3] for op in mode_chars) < reboot_y


def test_draw_reboot_press_flash_uses_press_flash_color():
    from src.ui.components import settings_reboot_item_rect

    display = FakeDisplayPort()
    view = SettingsView(display)
    view.render(None)
    display.clear_ops()
    view.draw_press_flash()

    item_x, item_y, item_w, item_h = settings_reboot_item_rect(display)
    assert (
        "fill_rect",
        item_x,
        item_y,
        item_w,
        item_h,
        config.COLOR_PRESS_FLASH,
    ) in display.ops
