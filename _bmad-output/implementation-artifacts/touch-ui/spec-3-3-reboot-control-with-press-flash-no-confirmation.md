---
title: 'Story 3.3: Reboot control with Press Flash, no confirmation'
type: 'feature'
created: '2026-09-13'
status: 'done'
followup_review_recommended: false
route: 'dispatch'
review_loop_iteration: 0
baseline_revision: 66e90abc28fd31d9046d10f739a3aff38204b859
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Settings has no way to actually restart the Device — Minh must be able to recover from a stuck state with a single tap, and the resistive/XPT2046 touch panel's inconsistent latency means an unacknowledged tap reads as broken hardware.

**Approach:** Add a Reboot button to the Settings view with mandatory Press Flash feedback, wired to call the existing `RebootPort.reset()` synchronously with no confirmation step.

## Boundaries & Constraints

**Always:** Tapping inside the Reboot button's tap-target rect renders a Press Flash (`#ffe9b8`) on the button, then calls `RebootPort.reset()` exactly once, synchronously, with no confirmation dialog or second tap. The button shows label "REBOOT" (14px bold, 2px letter-spacing, all-caps, `COLOR_SECONDARY` at rest — never `COLOR_UNSYNCED`), sized with a tap-target rect larger than its drawn text bounds, positioned in the lower block Story 3.1 reserves for it. Flash color/duration and label typography are named `src/config.py` constants; no literal durations, colors, or pixel rects inline. Only this one button may ever trigger `RebootPort.reset()`.

**Never:** No confirmation dialog, second-tap requirement, or gesture beyond single tap. Do not modify `TouchPort`, `RebootPort`'s own implementation, Bar reveal/retract logic, or Settings' idle-timeout/outside-tap dismissal (Story 3.4). Do not implement Settings entry/snapshot capture (Story 3.1) or status/guideline rendering (Story 3.2) — treat both as already landed; if the real `settings_view.py` module, class, or `VIEW_SETTINGS` naming differs from this spec's references, follow the actual code instead of inventing a parallel path.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Reboot tap | `active_surface == "settings"`, edge-down touch inside the reboot button's rect | Press Flash draws, then `RebootPort.reset()` is called exactly once | N/A |
| Miss tap | `active_surface == "settings"`, edge-down touch outside the reboot button's rect | No flash, no reset call from this tap (dismissal handled by Story 3.4) | N/A |
| No reboot port injected | `App` constructed with `reboot_port=None` | Reboot-button tap still renders Press Flash; no exception, no call | Guard on `None` port before invoking |

</frozen-after-approval>

## Code Map

- `src/config.py` -- add `COLOR_PRESS_FLASH_RGB = (0xFF, 0xE9, 0xB8)` / derived `COLOR_PRESS_FLASH`, and a Settings-reboot label font id + `FONT_SCALES` entry (14px-equivalent scale); reuse the existing `PRESS_FLASH_MS = 120` and `TAP_TARGET_SIZE_PX = 48` constants.
- `src/ui/settings_view.py` (created by Story 3.1, extended here) -- add the Reboot button's rect/draw helpers plus a hit-test method, mirroring `bar_gear_item_rect`/`bar_gear_hit`/`point_in_rect` in `src/ui/components.py` and `src/ui/compositor.py`.
- `src/app.py` -- `AppState.active_surface`/`surface_deadline` and `SURFACE_SETTINGS` (`src/ui/touch_state.py`) already exist (Story 1.2). Extend `_poll_touch` (or the Settings-tap handler Story 3.1 introduces) so an edge-down touch on the reboot rect while `active_surface == SURFACE_SETTINGS` draws the Press Flash directly via the display, then calls `self._reboot_port.reset()`. Add `reboot_port=None` and `sleep_ms_fn=None` constructor kwargs, following the injected-sleep precedent in `src/device/display/bootstrap.py:initialize_display` and `App.run_forever`'s own MicroPython `time.sleep_ms` fallback (lines ~550-559).
- `main.py` -- `RebootPort` is already constructed (`reboot_port = RebootPort(reset)`, line 62) but not yet passed into `App(...)` (lines 93-101); add `reboot_port=reboot_port`.
- `tests/test_app_loop.py` -- existing fake-port/AppState conventions; add a fake reboot port (records call count) and a fake `sleep_ms_fn` (records duration) to assert flash-then-reset ordering, exactly-one-call, and the `None`-port no-crash guard.

## Tasks & Acceptance

**Execution:**
- [x] `src/config.py` -- add `COLOR_PRESS_FLASH_RGB`/`COLOR_PRESS_FLASH` and the Settings-reboot label font/scale constants -- keep flash color and label styling single-sourced.
- [x] `src/ui/settings_view.py` -- draw the "REBOOT" label in its reserved lower block with the specified typography/color, plus a tap-target rect and hit-test helper -- match the Bar's existing icon-geometry convention.
- [x] `src/app.py` -- accept `reboot_port`/`sleep_ms_fn`, detect a Settings-surface tap on the reboot rect, draw the Press Flash, sleep `PRESS_FLASH_MS`, then call `reboot_port.reset()` exactly once -- deliver mandated tap feedback before the irreversible reset.
- [x] `main.py` -- pass the already-constructed `reboot_port` into `App(...)` -- complete production wiring.
- [x] `tests/test_app_loop.py` -- fake reboot port + fake `sleep_ms_fn` assert flash-before-reset ordering, single call, and no crash when `reboot_port` is `None` -- prove the boundary without touching real hardware.

**Acceptance Criteria:**
- Given Settings is open and the Reboot button is rendered, when the view draws, then it shows "REBOOT" at the specified typography/color, sized with a tap-target rect larger than its drawn text bounds.
- Given a user taps within the Reboot button's tap-target rect while Settings is active, when the tap registers, then Press Flash (`#ffe9b8`) renders on the button before `RebootPort.reset()` is invoked exactly once, synchronously, with no confirmation step.
- Given a touch lands inside Settings but outside the Reboot button's rect, when the tap registers, then `RebootPort.reset()` is never called from that tap.
- Given `App` is constructed without a `reboot_port`, when a reboot-button tap registers, then Press Flash still renders and no exception is raised.

## Implementation Notes

## Spec Change Log

## Review Triage Log

### 2026-09-13 — Review pass
- verdicts: 18 findings — high 0, medium 3, low 2, false 5, maybe-false 0, reject 1, defer 7
- findings:
  - `[false]` `[reject]` measure/draw spaced-text 1px centering drift — verified measure and draw use consistent step formula for layout; negligible at 320px scale.
  - `[false]` `[reject]` unused `_centered_spaced_text_x` — removed during review patch pass.
  - `[low]` `[defer]` `settings_reboot_item_rect` aliases full-width reserved block rather than centered 48px square — full-width strip is larger than label bounds and matches Story 3.1 reserved region.
  - `[low]` `[defer]` `SettingsView.reboot_hit` unused while compositor path is wired — spec Code Map requested view-level hit helper; compositor owns App poll path like Bar gear.
  - `[medium]` `[patch]` `test_unrecognized_kind` missing REBOOT assert — added REBOOT font assertion alongside none-snapshot test.
  - `[low]` `[defer]` no direct unit tests for `gfx.draw_spaced_text` — covered indirectly via settings_view typography test.
  - `[medium]` `[patch]` letter-spacing not asserted — added inter-glyph step assertion in `test_reboot_label_uses_specified_typography_and_tap_target`.
  - `[medium]` `[patch]` miss-tap test omitted flash absence — added `COLOR_PRESS_FLASH` fill_rect absence check.
  - `[low]` `[reject]` spec Verification commands omit new test files — verification section left as spec-authored scope; full suite run recorded in Auto Run Result.
  - `[low]` `[defer]` Implementation Notes empty for 14px/bold bitmap constraints — documented in config comment; bitmap font has no separate bold weight.
  - `[low]` `[defer]` `test_config_hardware_defaults` not extended — constants pinned by settings_view and app_loop tests.
  - `[false]` `[reject]` FakeRebootPort allows post-reset App.step — host tests intentionally continue; production calls `machine.reset()`.
  - `[false]` `[defer]` `sleep_ms_fn` exception before reset — acceptable on device about to reset; no guard added.
  - `[false]` `[defer]` `reboot_port.reset()` exception aborts loop — reset callback is device `machine.reset`; host fake cannot throw realistically.
  - `[false]` `[reject]` claim item_rect must mirror centered bar_gear square — spec requires tap target larger than text; full-width block satisfies intent.
  - `[medium]` `[patch]` flash-before-reset ordering not enforced — `FakeRebootPort` now asserts sleep ran before reset; event log checks sleep→reset sequence.
  - `[medium]` `[patch]` `main.py` missing `reboot_port=` wiring test — AST assertion added in `test_display_boot_checkpoint.py`.
  - `[medium]` `[patch]` letter-spacing verification gap (verification-gap layer) — same patch as typography spacing assertion above.

## Design Notes

A blocking `sleep_ms_fn` call between the flash draw and `RebootPort.reset()` is acceptable here specifically because the Device is about to permanently reset — nowhere else in `App` may block. Inject `sleep_ms_fn` the same way `initialize_display` does, defaulting to MicroPython's `time.sleep_ms` outside host tests (mirrors `App.run_forever`'s existing fallback).

## Verification

**Commands:**
- `uv run pytest tests/test_app_loop.py tests/test_touch_state.py` -- expected: reboot wiring, flash ordering, and existing surface-transition tests pass.
- `uv run pytest` -- expected: full host suite passes; no device imports leak into host-importable modules.

**Manual checks (if no CLI):**
- Flash the board, open Settings, tap REBOOT: confirm the amber flash is visible before the Device restarts. Host tests cannot observe `machine.reset()` actually restarting hardware.

## Auto Run Result

Status: done

Summary: Story 3.3 adds a Settings REBOOT control with letter-spaced label, Press Flash feedback, and synchronous `RebootPort.reset()` on tap. `App` accepts injected `reboot_port` and `sleep_ms_fn`; production wiring passes the existing `RebootPort` from `main.py`.

Files changed:
- `src/config.py` — press-flash color, reboot font/label/spacing constants
- `src/gfx.py` — spaced text measure/draw helpers
- `src/ui/components.py` — reboot item rect helper
- `src/ui/compositor.py` — `settings_reboot_hit`
- `src/ui/settings_view.py` — REBOOT label render and press-flash draw
- `src/app.py` — reboot tap handler with flash→sleep→reset
- `main.py` — pass `reboot_port` and `sleep_ms_fn` into App
- `tests/test_app_loop.py` — reboot tap/miss/none-port integration tests
- `tests/test_settings_view.py` — label typography and flash color tests
- `tests/test_clock_view.py` — REBOOT label on settings surface
- `tests/test_display_boot_checkpoint.py` — AST check for main reboot wiring

Review findings breakdown: 6 patches applied (ordering guard, main wiring AST, letter-spacing assert, miss-tap no-flash, unrecognized-kind REBOOT assert, removed dead helper); 7 deferred (exception paths on reset, duplicate hit API, bitmap bold/14px notes, gfx unit isolation); 6 rejected/false.

Follow-up review recommendation: false — no high-severity patches; medium patches were test hardening only.

Verification performed:
- `uv run pytest tests/test_app_loop.py tests/test_touch_state.py` — pass
- `uv run pytest` — 354 passed

Residual risks: host tests cannot prove visible flash duration on hardware or actual `machine.reset()` restart; manual flash check still required.
