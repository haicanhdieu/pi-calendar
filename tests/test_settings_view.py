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
    labels = [t[1] for t in texts]
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
    assert _texts(display.ops) == []


def test_unrecognized_kind_draws_no_status_or_guideline_text():
    display = FakeDisplayPort()
    SettingsView(display).render({"kind": "other"})
    assert _texts(display.ops) == []
