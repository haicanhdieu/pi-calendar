---
title: 'Story 3.1: Open Settings view from the gear icon with a captured status snapshot'
type: 'feature'
created: '2026-09-13'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_revision: '9940f7ccf95ce4ae646816bd0e9bfa5f6965aff1'
followup_review_recommended: false
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A gear tap during Bar-Revealed already routes `active_surface` to `settings` in the pure transition table (`touch_state.next_surface`), but nothing yet suspends Rotation's render, captures a network-status snapshot, or draws a Settings surface — Settings has no visible view.

**Approach:** Add a `SettingsView` rendered through the existing `compositor.render()` call site, copy the app's already-reduced network status into `AppState.settings_status_snapshot` exactly once on Bar→Settings entry, and route `App._render()`/`UiCompositor.render()` to draw only that view (no badge, no Bar, no Clock/Calendar underneath) while `active_surface == "settings"`.

## Boundaries & Constraints

**Always:** Capture `settings_status_snapshot` exactly once, at the same `_poll_touch` transition point that already commits Bar→Settings, from the app's existing `_network_status()` reduction; never touch it again until the next Settings entry. Keep `state.active_view` unchanged while in Settings — it keeps tracking the interrupted Clock/Calendar view for later resume. While `active_surface == "settings"`, draw only the Settings view full-screen (no badge, no Bar, nothing underneath). Draw exclusively via existing `DisplayPort` primitives; layout gaps live as named `config.py` constants. Top-aligned layout: 28px top padding → status region; 18px gap → guideline region; a larger gap → Reboot region, clearly separated. No back/close icon anywhere on the view.

**Never:** Do not implement the exact status/guideline copy or mode-branching (Story 3.2), Reboot's tap handling/Press Flash/`RebootPort.reset()` (Story 3.3), or Settings' own idle-timeout/outside-tap dismissal (Story 3.4 — `next_surface`'s Settings branch stays the existing no-op pass-through). Do not add a Settings-specific timeout or renew/reset `surface_deadline` while in Settings. Do not resize/dim/scrim the interrupted Clock/Calendar view or use a full 320×240 framebuffer redraw for the Settings paint.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Gear tap from Bar | `active_surface=bar`, edge_down on gear rect | `active_surface`→`settings`, Bar hidden, snapshot copied once from `_network_status()` | N/A |
| No network status yet | `_network_status()` returns `None` at the moment of entry | `settings_status_snapshot` set to `None`; `SettingsView` renders without raising | Renderer tolerates a `None` snapshot |
| Re-entry to Settings later | A later Bar→Settings transition, with a different network state | Snapshot overwritten fresh on that entry only; unchanged for the whole intervening dwell | N/A |
| Settings active, step() re-runs | `active_surface` stays `settings`, no new transition | Snapshot untouched; no live re-read of network state | N/A |

</frozen-after-approval>

## Code Map

- `src/app.py` -- `AppState.settings_status_snapshot` and `_network_status()` (~L343-352) already exist; `_poll_touch()` (~L224-262) already commits Bar→Settings via `next_surface` but never writes the snapshot — add the one-time copy where `previous == SURFACE_BAR and surface == SURFACE_SETTINGS` (mirrors the existing `elif previous == SURFACE_BAR:` retract branch). `_render()` (~L488-541) always renders `self._view`/`self._calendar_view` regardless of surface — add a `SURFACE_SETTINGS` branch that renders the new Settings view instead and skips Bar animation math.
- `src/ui/touch_state.py` -- `SURFACE_SETTINGS` and the Bar→Settings transition already exist and are correct; its Settings branch is a deliberate no-op pass-through reserved for Story 3.4 — do not touch.
- `src/ui/compositor.py` -- `UiCompositor.render()` (~L31-84) unconditionally renders `base_view` then badge then Bar; add a branch so `active_surface == "settings"` renders only the passed Settings view, skipping badge/Bar, and invalidates any previously-shown Bar/badge pixels first.
- New `src/ui/settings_view.py` -- new `SettingsView` mirroring `ClockView`'s shape (`__init__(display)`, `render(status_snapshot)`, `invalidate()`); full-screen background clear plus three positioned regions; exact copy is later stories' scope, so render minimal structural placeholders here without pre-empting their layout.
- `src/ui/components.py` -- add rect helpers for the three Settings regions (status/guideline/reboot Y positions), alongside the existing `badge_rect`/`bar_rect` pattern, driven by new `config.py` constants.
- `src/config.py` -- add `SETTINGS_TOP_PADDING_PX = 28`, `SETTINGS_STATUS_GUIDELINE_GAP_PX = 18`, `SETTINGS_GUIDELINE_REBOOT_GAP_PX = 40` (clearly larger than 18); no touch/drawing module embeds a literal pixel value.
- `tests/test_app_loop.py` -- `test_bar_gear_edge_enters_settings_without_rotation_dwell_rearm` and `test_settings_retains_the_interrupted_view_after_its_dwell_is_due` (~L267-301) already assert surface/deadline/view-retention; extend with snapshot-capture and render-routing assertions.
- `tests/test_clock_view.py` -- compositor tests live here (see `test_bar_is_a_bounded_draw_last_overlay_and_visibility_restores_base` for the pattern); add coverage that `active_surface == "settings"` suppresses badge/Bar and calls the Settings view instead.

## Tasks & Acceptance

**Execution:**
- [x] `src/config.py` -- add Settings layout constants -- no inline literals in drawing code
- [x] `src/ui/components.py` -- add Settings region rect helpers -- centralize geometry like the existing badge/bar helpers
- [x] `src/ui/settings_view.py` -- new `SettingsView` (full-screen clear + three positioned regions, minimal placeholder content) -- gives 3.1 a real full-screen surface without pre-empting 3.2/3.3 copy
- [x] `src/ui/compositor.py` -- branch `render()` on `active_surface == "settings"` to draw only the Settings view (no badge, no Bar) -- keeps Settings a suspended, chrome-free full-screen surface
- [x] `src/app.py` -- capture `settings_status_snapshot` once on Bar→Settings entry in `_poll_touch`; route `_render()` to the Settings view while `active_surface == "settings"` -- makes the snapshot rule structural, not incidental
- [x] `tests/test_app_loop.py`, `tests/test_clock_view.py` -- cover snapshot capture-once, `None`-snapshot tolerance, and render routing/suppression -- prove the matrix

**Acceptance Criteria:**
- Given the Bar is revealed and the user taps the gear icon, when the tap registers, then `active_surface` becomes `settings`, Rotation's render is suspended (Clock/Calendar do not draw), and the Bar is hidden.
- Given a Bar→Settings entry occurs, when `App` commits the transition, then `AppState.settings_status_snapshot` is set exactly once from the existing reduced `kind`/`ssid`/`ip` state, and is not updated again until the next Settings entry.
- Given Settings is open, when it renders, then it draws full-screen through `compositor.render()` with 28px top padding then the status region, an 18px gap then the guideline region, and a larger gap before the Reboot region — with no back/close icon anywhere.
- Given Settings is open, when `App.step()` runs without a new Bar→Settings transition, then the badge and Bar are not drawn and the snapshot is not re-read from live network state.

## Implementation Notes

## Spec Change Log

## Review Triage Log

### 2026-09-13 — Review pass
- verdicts: 18 findings — high 0, medium 2, low 5, false 8, maybe-false 0, reject 3
- findings:
  - `[false]` `[reject]` Patch missing settings_view.py — file exists on disk; diff omitted untracked file only
  - `[false]` `[reject]` Full framebuffer redraw violates boundary — full-screen fill_rect is the intended exclusive-surface paint, not an offscreen framebuffer
  - `[medium]` `[patch]` None snapshot render untested — added test_settings_view_tolerates_none_snapshot
  - `[medium]` `[patch]` Layout Y positions not pinned to 28/18/40 — added test_settings_layout_rects_match_specified_spacing
  - `[low]` `[reject]` Guideline region height asymmetry — placeholder scaffold; Story 3.2 owns copy layout
  - `[false]` `[reject]` Snapshot nested in bar retract branch — guarded by explicit surface == SURFACE_SETTINGS
  - `[low]` `[reject]` Bar retract state active during Settings — existing retract bookkeeping; bar not drawn
  - `[low]` `[patch]` String literals for surface constants in test — switched to SURFACE_BAR/SURFACE_SETTINGS
  - `[low]` `[reject]` No station_ip first-entry test — re-entry test covers station_ip capture path
  - `[low]` `[reject]` SettingsView _valid unused — mirrors ClockView dirty-flag scaffold
  - `[low]` `[reject]` Re-entry test uses manual surface set — acceptable host shortcut for snapshot rule
  - `[low]` `[reject]` No dedicated SettingsView unit tests — covered via compositor and app-loop tests
  - `[medium]` `[defer]` Snapshot before network drain on same step — pre-existing step ordering; same-step event during gear tap unlikely on device
  - `[medium]` `[patch]` Calendar render suppression untested at App loop — added test_settings_render_suspends_calendar_and_hides_bar
  - `[false]` `[reject]` Dual clear strategy unspecified — acceptable implementation detail
  - `[false]` `[reject]` Region dimensions unspecified — TAP_TARGET-derived heights are reasonable scaffold
  - `[false]` `[reject]` Compositor snapshot parameter reuse — required by existing render signature
  - `[false]` `[reject]` Reboot region present but inert — intentional placeholder for Story 3.3

## Design Notes

`AppState.active_view` (Clock/Calendar) is deliberately left untouched while `active_surface == "settings"` — it keeps tracking whichever rotation view was interrupted so Rotation resumes it later (already covered by `test_settings_retains_the_interrupted_view_after_its_dwell_is_due`). Settings is a per-tick *render routing* decision keyed off `active_surface`, not a fourth value stored in `active_view`.

## Verification

**Commands:**
- `uv run pytest tests/test_app_loop.py tests/test_clock_view.py tests/test_touch_state.py` -- expected: snapshot-capture, render-routing, and existing surface-transition tests all pass.
- `uv run pytest` -- expected: full host suite passes.

## Auto Run Result

Status: done

**Summary:** Story 3.1 adds a full-screen Settings surface with one-shot network-status snapshot capture on Bar→Settings entry, render routing that suspends Clock/Calendar, and compositor isolation that suppresses badge and Bar overlays.

**Files changed:**
- `src/config.py` — Settings layout constants (28/18/40 px gaps)
- `src/ui/components.py` — settings_status/guideline/reboot rect helpers
- `src/ui/settings_view.py` — new SettingsView scaffold with three placeholder regions
- `src/ui/compositor.py` — early SURFACE_SETTINGS branch skipping badge/Bar
- `src/app.py` — snapshot capture on Bar→Settings; _render routes to SettingsView
- `tests/test_app_loop.py` — snapshot, render-routing, calendar-suppression tests
- `tests/test_clock_view.py` — compositor suppression, layout spacing, None-snapshot tests

**Review:** 4 patches applied (layout spacing test, None-snapshot test, calendar suppression test, surface constant literals). 1 item deferred (same-step network drain ordering). 11 findings rejected as false or low cosmetic.

**Follow-up review recommended:** false

**Verification:**
- `uv run pytest tests/test_app_loop.py tests/test_clock_view.py tests/test_touch_state.py` — 70 passed
- `uv run pytest` — 345 passed

**Residual risks:** Snapshot capture runs before `_drain_network_events` in the same step; deferred as unlikely on-device. Device flash evidence still required for touch/render timing on Pico W.
