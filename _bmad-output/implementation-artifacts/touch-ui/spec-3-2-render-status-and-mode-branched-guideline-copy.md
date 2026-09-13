---
title: 'Story 3.2: Render status and mode-branched guideline copy'
type: 'feature'
created: '2026-09-13'
status: 'done'
followup_review_recommended: false
route: 'dispatch'
review_loop_iteration: 0
baseline_revision: '9079fb32b0ffce28d1b93f1ab1ea456ad43c0be3'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The Settings view (Story 3.1) will have a status/guideline area with nothing drawn into it, so Minh cannot yet read the exact SSID/gateway or IP and browser-URL instructions needed to reach the Config page.

**Approach:** Render the captured `AppState.settings_status_snapshot` into two mode-branched text elements — a status block and a guideline line — using new Settings typography roles, exactly per the Setup AP and station branches.

## Boundaries & Constraints

**Always:**
- Read only `settings_status_snapshot` (a dict shaped `{kind, ssid, ip}`, matching the existing `App._network_status()` reduction); never read live network state.
- Setup AP branch (`kind == "setup"`): status block draws SSID then gateway as two stacked lines; guideline line reads exactly `"Connect to Wi-Fi <SSID> then browse to <gateway>"`.
- Station branch (`kind == "station_ip"`): status block draws the IPv4 address as one line; guideline line reads exactly `"Browse to http://<ip>"`.
- Status block uses a new `FONT_SETTINGS_STATUS` id (bitmap scale 2 = 16px, exact match) and `COLOR_PRIMARY`; guideline uses a new `FONT_SETTINGS_GUIDELINE` id (bitmap scale 1 = 8px — the only remaining integer scale, chosen over scale 2 to preserve status > guideline size hierarchy) and `COLOR_SECONDARY`. Bold weight / letter-spacing are not representable by the single-weight bitmap font and are not attempted.
- Layout: `SETTINGS_TOP_PADDING_PX` (28) above the status block, `SETTINGS_BLOCK_GAP_PX` (18) before the guideline line, both centered horizontally; add these two constants to `config.py` only if Story 3.1 has not already added them.
- Draw nothing, and raise nothing, when `settings_status_snapshot` is falsy or its `kind` matches neither branch.

**Never:** Do not implement the Reboot button, Settings entry/exit wiring, idle timeout, outside-tap dismissal, Press Flash, or touch hit-testing (Stories 3.1/3.3/3.4). Do not read live network state or mutate `settings_status_snapshot`. Do not add a third `kind` branch.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Setup AP branch | `{kind:"setup", ssid:"PiCalendar-AP42", ip:"192.168.4.1"}` | Status lines "PiCalendar-AP42" / "192.168.4.1"; guideline "Connect to Wi-Fi PiCalendar-AP42 then browse to 192.168.4.1" | N/A |
| Station branch | `{kind:"station_ip", ssid:"HomeWifi", ip:"192.168.1.42"}` | Status line "192.168.1.42" only; guideline "Browse to http://192.168.1.42" | N/A |
| No snapshot yet | `None` | Nothing drawn for status/guideline | No exception |
| Unrecognized kind | `{kind:"other"}` | Nothing drawn | No exception |

</frozen-after-approval>

## Code Map

- `src/app.py` -- `_network_status()` (~L342-351) already reduces network events into `{kind, ssid, ip}` with kind values `_OVERLAY_SETUP="setup"` / `_OVERLAY_STATION_IP="station_ip"` (module-private, L30-31); `AppState.settings_status_snapshot` field exists (`__slots__` L58, init L72) but nothing assigns it yet — Story 3.1 wires that assignment at Settings entry. This story only consumes the shape, never populates it.
- `src/ui/settings_view.py` -- does not exist yet. If Story 3.1 has already created it (view scaffold + Reboot placeholder), extend its status/guideline rendering. If absent, create a `SettingsView` class mirroring `ClockView`'s shape in `src/ui/clock_view.py`: `__init__(self, display)`, `render(self, status_snapshot)`.
- `src/ui/components.py` -- the removed `draw_network_status_overlay`/`_draw_status_lines` helpers (git history, commit `42d7ad2`) establish the precedent this story reuses: Setup AP renders SSID and gateway as two stacked lines, not one combined string.
- `src/config.py` -- add `FONT_SETTINGS_STATUS`, `FONT_SETTINGS_GUIDELINE` (plus their `FONT_SCALES` entries) and `SETTINGS_STATUS_LINE_GAP_PX` (reuse the removed overlay's historical 2px two-line gap); add `SETTINGS_TOP_PADDING_PX`/`SETTINGS_BLOCK_GAP_PX` only if not already present from Story 3.1.
- `tests/test_settings_view.py` (new, or extend if Story 3.1 created one) -- follow the `FakeDisplayPort` op-recording assertion style used for `ClockView` (`tests/test_clock_view.py`) to verify exact drawn strings, font ids, and colors per branch, plus the no-snapshot/unrecognized-kind no-op cases.

## Tasks & Acceptance

**Execution:**
- [x] `src/config.py` -- add `FONT_SETTINGS_STATUS`/`FONT_SETTINGS_GUIDELINE` font ids + scales, `SETTINGS_STATUS_LINE_GAP_PX`, and layout constants if missing -- named constants only, no inline literals.
- [x] `src/ui/settings_view.py` -- implement (or extend) status-block and guideline-line rendering branched on `settings_status_snapshot["kind"]` -- the sole rendering logic this story owns.
- [x] `tests/test_settings_view.py` -- cover every I/O Matrix row via `FakeDisplayPort` op assertions -- prove exact copy, typography, and no-op safety.

**Acceptance Criteria:**
- Given `settings_status_snapshot.kind` is `"setup"`, when the Settings view renders, then the status block draws the SSID line followed by the gateway line in `FONT_SETTINGS_STATUS`/`COLOR_PRIMARY`, and the guideline line reads exactly `"Connect to Wi-Fi <SSID> then browse to <gateway>"` in `FONT_SETTINGS_GUIDELINE`/`COLOR_SECONDARY`.
- Given `settings_status_snapshot.kind` is `"station_ip"`, when the Settings view renders, then the status block draws only the IPv4 address in `FONT_SETTINGS_STATUS`/`COLOR_PRIMARY`, and the guideline line reads exactly `"Browse to http://<ip>"` in `FONT_SETTINGS_GUIDELINE`/`COLOR_SECONDARY`.
- Given `settings_status_snapshot` is falsy or carries an unrecognized `kind`, when the Settings view renders, then no status or guideline text is drawn and no exception is raised.

## Implementation Notes

## Spec Change Log

## Review Triage Log

### 2026-09-13 — Review pass
- verdicts: 5 findings — high 0, medium 0, low 0, false 3, maybe-false 0, reject 2
- findings:
  - `[false]` `[reject]` Empty-dict snapshot truthy but kind absent draws nothing safely — `{}` is not in the I/O matrix; behavior matches "unrecognized kind" no-op without exception.
  - `[false]` `[reject]` No compositor integration test asserts rendered Settings copy — `tests/test_settings_view.py` exercises `SettingsView.render` directly with FakeDisplayPort; compositor is a pass-through to the same method.
  - `[false]` `[reject]` Setup branch missing-ip uses empty string in guideline — `_network_status()` always supplies ip for setup kind; empty-string path is unreachable in production.
  - `[reject]` `[reject]` Kind string constants duplicated vs `app.py` — private module constants; no shared import needed for two-file boundary.
  - `[reject]` `[reject]` `test_font_ids_are_stable_config_names` omits new font ids — cosmetic test gap only; FONT_SCALES entries verified by settings view tests using the ids.

## Design Notes

The exact status-line format for Setup AP mode is not fully pinned by the current planning docs: `epics.md`'s AC says "SSID + gateway" and the guideline copy spells out both values, but the UX mockup (`ux-designs/mockups/settings-view.html`) only shows the SSID on the status line. This spec resolves that by git-history precedent: the pre-Epic-1 `draw_network_status_overlay` (removed in commit `42d7ad2`) rendered Setup AP status as two stacked lines — SSID then gateway — from the same `{kind, ssid, ip}` shape this story consumes. Reusing that convention satisfies the AC text without inventing new formatting.

Font scale choice: the bitmap font only offers integer scales (`FONT_CELL_HEIGHT=8` × scale). 16px (status) is an exact match at scale 2. 13px (guideline) has no exact scale; scale 1 (8px) is chosen over scale 2 (16px) specifically to preserve the UX-mandated status > guideline size hierarchy, even though scale 2 is numerically closer to 13.

## Verification

**Commands:**
- `uv run pytest tests/test_settings_view.py` -- expected: all new branch/no-op cases pass.
- `uv run pytest` -- expected: entire host suite passes.

## Auto Run Result

Status: done

Summary: Settings view now renders mode-branched status and guideline copy from the captured snapshot — Setup AP shows SSID/gateway stacked lines plus connect instruction; station mode shows IPv4 plus http URL — using new typography roles and centered layout.

Files changed:
- `src/config.py` — added FONT_SETTINGS_STATUS/GUIDELINE ids, scales, and SETTINGS_STATUS_LINE_GAP_PX
- `src/ui/settings_view.py` — branched status/guideline text rendering; reboot placeholder panel retained
- `tests/test_settings_view.py` — new matrix coverage for setup, station, None, and unrecognized kind
- `tests/test_clock_view.py` — updated compositor settings test for reboot-only panel placeholder

Review findings breakdown: 0 patches applied, 0 deferred, 5 rejected (3 false, 2 low not worth fixing).

Follow-up review recommendation: false

Verification performed:
- `uv run pytest tests/test_settings_view.py` — 4 passed
- `uv run pytest` — 349 passed

Residual risks: None identified for host-tested paths; on-device flash verification remains user responsibility per AGENTS.md.
