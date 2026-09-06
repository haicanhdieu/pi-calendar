"""Host regression tests for the TFT boot checkpoint boundary."""

from __future__ import annotations

import ast
from pathlib import Path

from src import config
from src.device.display.bootstrap import initialize_display
from src.device.display import splash
from src.device.display.splash import BLACK, CYAN, NAVY, WHITE


ROOT = Path(__file__).resolve().parents[1]


class RecordingDisplay:
    width = config.SCREEN_WIDTH
    height = config.SCREEN_HEIGHT

    def __init__(self, events=None):
        self.events = [] if events is None else events
        self.ops = []

    def fill(self, color):
        self.ops.append(("fill", color))

    def fill_rect(self, x, y, width, height, color):
        self.ops.append(("fill_rect", x, y, width, height, color))


def test_display_boot_checkpoint_precedes_app_dependencies():
    events = []

    def display_factory(**kwargs):
        events.append(("construct", kwargs))
        return RecordingDisplay(events)

    def render_checkpoint(display):
        assert events == [
            (
                "construct",
                {
                    "spi": "spi",
                    "dc": config.TFT_DC,
                    "rst": config.TFT_RST,
                    "cs": config.TFT_CS,
                },
            ),
            ("log", "TFT initialized; showing boot checkpoint"),
        ]
        events.append(("checkpoint", display))

    def dwell(milliseconds):
        assert events[-1][0] == "checkpoint"
        events.append(("dwell", milliseconds))

    display = initialize_display(
        "spi",
        display_factory,
        render_checkpoint,
        dwell,
        lambda message: events.append(("log", message)),
    )

    assert display is events[2][1]
    assert [event[0] for event in events] == ["construct", "log", "checkpoint", "dwell"]
    assert events[-1] == ("dwell", config.BOOT_CHECKPOINT_DWELL_MS)

    main_tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(main_tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    boot_call = next(call for call in calls if call.func.id == "initialize_display")
    adapter_call = next(call for call in calls if call.func.id == "Ili9341DisplayPort")
    assert boot_call.lineno < adapter_call.lineno


def test_splash_renders_high_contrast_tft_ready_checkpoint(monkeypatch):
    display = RecordingDisplay()
    labels = []

    monkeypatch.setattr(
        splash,
        "centered_text",
        lambda target, text, y, scale, color: labels.append(
            (target, text, y, scale, color)
        ),
    )
    splash.splash_screen(display)

    assert display.ops[:3] == [
        ("fill", NAVY),
        ("fill_rect", 0, 0, config.SCREEN_WIDTH, 18, BLACK),
        ("fill_rect", 0, config.SCREEN_HEIGHT - 18, config.SCREEN_WIDTH, 18, BLACK),
    ]
    assert labels == [
        (display, "TFT", 88, 6, WHITE),
        (display, "READY", 160, 6, CYAN),
    ]
