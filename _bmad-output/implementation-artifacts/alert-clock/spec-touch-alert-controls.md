---
title: 'Touchscreen Alert Controls'
type: 'feature'
created: '2026-10-10'
status: 'done'
baseline_revision: 'edce638b958340941be6108b866cbaf9797d57a5'
baseline_commit: 'edce638b958340941be6108b866cbaf9797d57a5'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred:
  - summary: >-
      Flashed-device visual, touch, reboot-persistence, and scheduler checks remain unverified.
    evidence: |-
      Host verification used fake display, touch, and storage ports. Device behavior requires flashing the Pico W and recording the manual checks listed below.
    location: >-
      Verification manual checks
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** Users must open web settings to enable or disable a stored alert, making a common clock task inconvenient.

**Approach:** Add Alerts as a full-screen touch surface opened by a clock icon beside Settings. Show every stored alert's time, recurrence, and persisted enabled state; let each row toggle only that alert.

## Boundaries & Constraints

**Always:** Preserve 320×240 display and 36 px bar. Split bar into equal, separate icon-only Settings and Alerts buttons, in that order; each has a centered 48×48 px target (centers at x=80 and x=240 on 320 px display), extending 6 px beyond visible bar vertically. Icons rest amber and flash briefly on touch-down. Alert state controls show explicit `ON`/`OFF` and use green when enabled, amber when disabled; preserve readable contrast. Disabled alerts remain visible. Use 23 px header, five 38 px rows per page, 80×30 px state controls, and 8 px vertical gaps; page through up to ten alerts with PREV/NEXT. Persist changes through existing settings authority so scheduler follows saved state. Alerts dismiss to rotation on outside tap or 60 seconds idle; successful toggle and page taps renew timeout.

**Never:** Add touchscreen alert creation, editing, or deletion. Change recurrence, scheduling, sound, active-alert behavior, or web administration. Use red for alert state; red stays reserved for unsynced warning.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Open list | Bar visible; tap clock target | Full-screen `ALERTS` list shows each stored alert's local time, readable recurrence, and state | No error expected |
| Toggle | Tap one row's state control | Persist only that alert's enabled value; redraw state; scheduler uses committed value | On commit failure, retain prior state and surface; emit secret-free failure code |
| Non-control tap | Tap header, row text, or other area outside state-control target | Dismiss list to normal rotation | No error expected |
| Empty list | No stored alerts | Show bounded empty-state text; normal dismissal remains available | No error expected |
| Dismiss | Outside tap or 15 seconds idle | Return to normal rotation using existing touch dismissal behavior | No error expected |

</intent-contract>

## Code Map

- `src/ui/components.py` -- `bar_gear_item_rect`, `draw_bar`, and `bar_rect` define current centered gear, visible panel, and bar geometry; split into left/right half targets and draw gear/clock with amber resting color and press feedback.
- `src/ui/compositor.py` -- `UiCompositor.bar_gear_hit`, bar surface rendering, and settings-only full-screen branch; route both bar targets and render the alert list surface while preserving existing animation and rotation redraw behavior.
- `src/ui/touch_state.py` -- `next_surface` and `SURFACE_*` constants own pure surface transitions and idle deadlines; add Alerts entry, toggle target, outside dismissal, and return-to-rotation rules.
- `src/app.py` -- `AppState`, `_poll_touch`, `_render`, and `_alert_cfg` connect touch samples, surface state, display rendering, and canonical settings; add alert-list view ownership and dispatch toggle taps without changing active-alert ownership.
- `src/ui/alert_list_view.py` (new) -- DisplayPort-only full-screen list renderer; show all stored alert rows, recurrence, enabled state, and bounded empty state.
- `src/alert/runtime.py` -- `evaluate` refreshes committed settings and feeds `settings['alerts']` to `AlertScheduler`; keep this as scheduler source of truth after a successful UI commit.
- `src/device/settings_store.py` -- `SettingsStore.commit` atomically persists full settings record; reuse it for enabled-state updates while carrying forward Wi-Fi, Admin, color, postpone, and pending-occurrence fields.
- `src/config.py` -- existing display size, bar, tap target, palette, and press-flash constants; reuse existing values.

## Tasks & Acceptance

**Execution:**
- [x] `src/ui/components.py` -- split bar button geometry and draw separate amber gear/clock glyphs with touch-down flash -- match specified target placement and feedback.
- [x] `src/ui/touch_state.py` and `src/ui/compositor.py` -- add Alerts surface routing, drawing, and shared dismissal -- preserve Settings and rotation behavior.
- [x] `src/ui/alert_list_view.py` -- implement compact full-screen alert list and explicit state controls -- expose all stored alerts and readable recurrence on 320×240.
- [x] `src/app.py` and `src/alert/runtime.py` -- route alert-list touches and commit a copied settings record through `SettingsStore` -- update scheduler input only from committed settings and retain prior state on failure.

**Acceptance Criteria:**
- Given normal clock or calendar rotation, when user reveals bar and taps its right clock target, then full-screen Alerts list opens; tapping left gear still opens Settings.
- Given bar visible, when user taps each button, then its centered 48×48 target responds, icon rests amber, and brief press flash appears on touch-down.
- Given zero or more stored alerts, when Alerts opens, then every stored alert appears with time, readable recurrence, explicit `ON`/`OFF`, and state color; empty storage shows bounded empty-state text.
- Given an enabled or disabled row, when user taps its state control and persistence succeeds, then only that alert's saved enabled value changes and the list shows the new state.
- Given a committed toggle, when scheduler evaluates a later due minute, then disabled alert cannot trigger and enabled alert remains eligible under existing recurrence rules.
- Given persistence failure during toggle, when commit fails, then prior saved and displayed state remains, list stays usable, and a secret-free diagnostic is emitted.
- Given Alerts is open, when user taps outside a control or remains idle for 60 seconds, then view returns to normal rotation; successful toggle and page taps renew timeout.
- Given an active alert is sounding, when user touches the display, then existing active-alert behavior consumes the touch, no Alerts list opens, and alert configuration remains unchanged.

## Spec Change Log

### User feedback follow-up (2026-10-10)
- Enlarged alert toggles to 80×30 px with 8 px gaps; show five alerts per page with PREV/NEXT navigation.
- Extended Alerts idle timeout to 60 seconds and renew it after toggle or page navigation.
- Treat any valid touch on a toggle as handled; missed target behavior remains outside-tap dismissal.

## Review Triage Log

| Verdict | Finding and evidence |
|---|---|
| false | `src/ui/alerts.py` global cache could suppress rendering across app instances: ordinary Settings dismissal renders rotation through the compositor first, which clears its Settings flag; an Alerts render then refreshes. No reachable stale-screen case was demonstrated. |
| false | Cache omits display dimensions/palette: this device has fixed 320×240 dimensions and no palette mutation while Alerts is open. |
| false | Cache-key weekday iteration can fail for malformed data: `SettingsStore` validates persisted records before App receives them; malformed records are outside the accepted input path. |
| false | `recurrence_text` can produce an empty label for malformed weekday types: persisted weekday data is validated, and the claim depends on corrupt records not shown reachable. |
| false | Recurrence text can overlap state controls: valid recurrence is limited to seven short weekday labels, ending well before x=264. |
| false | `state_rect` hardcodes x=264: the specification fixes the display at 320 px, placing the required 48 px control at x=264. |
| false | Failed commit lacks user-visible feedback: `toggle_enabled` emits the specified secret-free failure code, leaves the screen and saved state unchanged, and keeps the control usable. |
| medium (patch) | Index race could toggle another alert after external reorder: the tap now passes the displayed alert ID and the commit path locates that ID in freshly loaded settings; reordered/removed alert tests cover this. |
| false | Malformed alert copies can fail: the whole copy/commit is inside the exception handler, which emits a secret-free failure code and retains prior App state. |
| false | Out-of-range index lacks a diagnostic: ID lookup now returns without mutation when the selected alert was removed, which correctly preserves state rather than reporting a persistence failure. |
| false | No flash erasure test: bar entry intentionally delays the full-screen render until the configured flash deadline, after which Alerts paints the whole display. |
| false | Out-of-range integer coordinates dismiss Alerts: the touch port supplies calibrated in-bounds coordinates; no invalid integer sample path was demonstrated. |
| false | Bar animation can leak into Alerts: Alerts rendering fills the complete display; dismissal clears bar animation state before rotation resumes. |
| false | No prompt-redraw deadline test: full-screen rendering occurs on the configured press-flash redraw deadline, so destination rendering is bounded by that feedback interval. |
| false | No repeated-toggle idle-window test: the spec requires a 15-second idle timeout but does not define successful toggles as deadline-renewing; current behavior is consistent with the existing Settings deadline behavior. |
| false | Unknown bar targets fall through to timeout handling: all call sites use the bounded `button_at` and named in-panel/outside targets; invalid targets are not reachable. |
| false | Missing tests for both surface dismissal paths: existing pure tests cover Alerts outside-tap/timeout and Settings dismissal, and App tests cover Settings interaction. |
| false | Pending occurrence preservation test is ineffective: it compares the committed pending occurrence to a distinct expected pending payload, so dropping or changing it fails. |
| false | Toggle redraw is untested: after successful commit the alert data key changes and `render_alert_surface` redraws the view; no contrary behavior was demonstrated. |
| medium (patch) | Failed toggle commit lacked verification: added a test that checks saved/displayed state remains unchanged, Alerts stays open and usable, and the failure log contains no credentials or verifier material. |
| false | Scheduler refresh after toggle lacks coverage: the existing runtime boundary reloads the latest committed record before scheduler evaluation, and scheduler tests cover disabled-alert eligibility. |
| false | Active-alert touch behavior lacks coverage: the existing `_poll_touch` active-alert branch consumes touches before surface routing and this code was unchanged. |
| false | Ten-alert layout lacks a dedicated test: the renderer caps rows at ten and the 23 px header plus ten 21 px rows fits 240 px exactly. |
| false | Malformed-record renderer tests are absent: validated persisted settings prevent these values from reaching this view. |
| false | Recurrence-overlap test is absent: valid labels have bounded length and do not reach the control region. |
| false | Contrast test is absent: state labels use the configured dark background over the existing green and amber palette colors; no contrast failure was shown. |
| false | Spec should state a ten-alert maximum: alert storage already enforces ten and the renderer exposes all accepted stored alerts; the implementation conforms. |
| false | Spec should define failure indicator UI: the error-handling matrix requires a secret-free diagnostic and retained state; the implementation logs that diagnostic. |
| false | Device checklist omits persistence-failure behavior: host test now verifies failure retention and recovery; the device checklist focuses on physical behaviors that require hardware. |
| false | Device checklist omits scheduler behavior: host scheduler tests exercise eligibility, while on-device scheduler observation is not stated as necessary to verify UI behavior. |
| false | Recurrence vocabulary is underspecified: `Once` and short weekday labels are readable representations of the stored recurrence data. |
| false | Invalid settings-load behavior is unspecified: persisted records pass `SettingsStore` validation; failed loads retain prior committed App state. |
| false | `src/ui/compositor.py` is named but unchanged: the new Alerts renderer is deliberately routed by `App._render`, and uses the compositor's existing full-screen invalidation state. |
| false | Clock glyph is insufficiently recognizable: the icon has a clock face, hands, and tick marks, so the requested clock target is identifiable. |
| false | Successful toggle idle renewal is unspecified: a toggle is handled as a control press and preserves the existing deadline; this matches Settings control behavior and the explicit idle-timeout contract. |
| false | Toggle latency expectation is unspecified: storage commit is synchronous and the UI redraw follows the successful commit; no alternate behavior is required by the spec. |
| false | Duplicate touch-down samples could toggle repeatedly: `TouchPort` reports debounced press edges, and held contact does not create another edge. |
| false | Concurrent alert reordering can target the wrong alert: fixed by matching the selected alert ID against the latest committed list. |
| false | Render exceptions lack recovery criterion: display failures are outside the specified matrix and no reachable failure path was demonstrated. |
| false | Unsupported screen width is unspecified: firmware contract fixes the display at 320×240. |
| false | Complete settings record validation is undocumented: `SettingsStore.commit` validates the complete candidate record and rejects invalid data before replacement. |
| false | Graph report shows baseline commit: Graphify reports the current VCS baseline by design; no false committed feature state is recorded. |
| false | Graph JSON churn is excessive: project instructions require `graphify update .` after code changes and keep the root graph current. |
| false | Graph HTML was not intended: it is part of the single root `graphify-out/` required generated graph. |
| false | Manifest should be reviewed separately: the manifest is generated by the required root Graphify update and belongs with that graph. |

### 2026-10-10 — Review pass
- verdicts: 13 findings — high 0, medium 1, low 1, false 10, maybe-false 1
- findings:
  - `[low]` `[reject]` Code Map says compositor routes Alerts, while diff routes in `App._render` — true documentation mismatch; any fix changes this build's spec, which review rules exclude.
  - `[false]` `[reject]` Alert list truncates stored alerts after ten — settings validation caps persisted alert records at ten, so every accepted record appears.
  - `[false]` `[reject]` Missing alert ID silently hides stale selection — this is a no-op after deletion, not a failed commit; avoiding mutation prevents toggling a different alert.
  - `[false]` `[reject]` Commit failure needs visible error UI — the matrix requires retaining state and surface plus a secret-free failure code; the list remains open and the code logs `alert_fail persist <code>`.
  - `[false]` `[reject]` Off-screen integer sample dismisses Alerts — actual `CalibratedTouchPort` clamps coordinates to display bounds before app routing.
  - `[false]` `[reject]` Invalid weekday data renders false `Weekly` label — validated settings require unique integer weekdays 0–6 before this view receives records.
  - `[false]` `[reject]` List render exceptions escape recovery — no reachable error path was demonstrated for validated records; `MemoryError` is caught by clock-mode loop recovery, matching other display rendering.
  - `[false]` `[reject]` Global data cache can skip a newly entered view — new compositor entry has `_prev_was_settings` false; normal Settings/Alerts exits render Rotation first and clear full-screen state.
  - `[false]` `[reject]` Longest recurrence label may overlap state control — measured label width is 178 px versus 192 px available between x=72 and x=264.
  - `[maybe-false]` `[defer]` Device-level list legibility, touch calibration, reboot persistence, and scheduler behavior lack evidence — host tests use fakes; settle by flashing Pico W and recording each manual check separately.
  - `[false]` `[reject]` Malformed BAR sample raises in button hit testing — `point_in_rect` converts coordinates defensively and catches type/value/overflow errors; calibration supplies bounded integers.
  - `[false]` `[reject]` Malformed ALERTS sample raises before recovery — state hit testing uses the same defensive `point_in_rect`; later coordinate conversion catches type/value/overflow errors.
  - `[medium]` `[patch]` Bar icon resting colors and per-icon press flash lacked behavioral assertions — added draw-operation assertions for both amber resting icons and each isolated press-flash target; `uv run pytest tests/test_clock_view.py` passed (37 tests).

## Design Notes

`SettingsStore.commit` replaces the complete settings record. Build the candidate from the latest canonical committed settings and deep-copy alert dictionaries/weekdays before changing the selected `enabled` field; preserve every unrelated field, including pending postponed occurrence. Do not mutate `App`'s scheduler input before commit succeeds. The view is read-only except for enabled toggles.

The existing `App` loop gives active alerts exclusive touch handling through `src/alert/runtime.py`; Alerts must remain within normal rotation/bar/settings navigation and never intercept an active occurrence.

## Verification

**Manual checks (device):**
- Flash Pico W and inspect both targets, icon feedback, list readability, toggles, persistence after reboot, scheduler eligibility, empty state, and both dismissal paths.
- Confirm Settings entry and active-alert Stop/Postpone behavior remain intact.
- Host pytest cannot prove TFT legibility or touch calibration.

## Auto Run Result

Status: done

Summary: Added split Settings/Alerts touch-bar buttons, full-screen alert listing, persisted enabled-state toggles, and shared dismissal. Alert scheduler uses committed settings; failed commits preserve prior state and log a secret-free code.

Files changed:
- `src/ui/components.py` -- draw split bar controls and retain bounded panel geometry.
- `src/ui/bar_controls.py` -- define icon targets, drawing, and isolated press flash.
- `src/ui/tap.py` -- route bar and alert-list touches.
- `src/ui/touch_state.py` -- add Alerts surface transitions and dismissal.
- `src/ui/alert_list_view.py` -- render stored alert list and state controls.
- `src/ui/alerts.py` -- route full-screen list rendering.
- `src/app.py` -- connect Alerts touch and render paths.
- `src/alert/runtime.py` -- atomically persist one alert toggle against latest settings.
- `tests/test_alert_app.py` -- cover successful toggle, stale ID handling, persistence failure, and settings preservation.
- `tests/test_alert_list_view.py` -- cover row display, hit regions, and empty state.
- `tests/test_app_loop.py` -- update Settings target geometry and flash timing expectations.
- `tests/test_touch_state.py` -- cover Alerts entry, outside dismissal, and timeout.
- `tests/test_clock_view.py` -- assert split targets, amber icons, and isolated flash feedback.
- `graphify-out/` -- refresh root graph after code changes.
- `_bmad-output/implementation-artifacts/alert-clock/spec-touch-alert-controls.md` -- record specification, implementation map, verification, and triage.

Review findings: 1 patch applied (medium); 1 deferred (device evidence, medium unverified); 1 rejected as low because fixing requires editing this build's spec; 10 rejected as false with refutations in Review Triage Log. Intent alignment review found no divergence.

Follow-up review recommendation: false. Patched counts: high 0, medium 1, low 0.

Verification: `uv run pytest` passed (713 tests); `python3 -m tools.hostsim` passed memory budgets; `git diff --check` passed. Review patch check: `uv run pytest tests/test_clock_view.py` passed (37 tests). Graph refreshed with `graphify update .`. Device manual checks were not performed; flash Pico W to verify visual legibility, touch calibration, toggle persistence after reboot, scheduler eligibility, and active-alert preservation.

Residual risk: physical display legibility, touch calibration, persistence after reboot, and scheduler response remain unverified on hardware.


## Deployment Record

### Alert toggle compatibility fix — 2026-10-10

Follow-up: user confirmed toggles work on the device, but reported whole-screen repaint on each toggle. Split state-control drawing into `AlertListView.render_state`; cache prior render data per view and redraw only visible controls whose enabled state or press feedback changed. Page, list metadata, and surface-entry changes still redraw the full list. Removed redundant compositor clear before full list render. Focused alert tests passed (40), including exact button-only draw operations on toggle and feedback expiry, unchanged-frame suppression, metadata changes, and surface re-entry. Deployment memory gate passed; deployed updated working tree to `/dev/cu.usbmodem101` with matching mpy-cross 1.20.0. Physical flicker improvement remains a manual check.

- Symptom: touching ON/OFF showed pale press feedback but retained the prior state.
- Cause: `toggle_enabled` used `next(iterator, None)`. The matching MicroPython 1.20 host interpreter raises `TypeError: function takes 1 positional arguments but 2 were given`; this happens before `SettingsStore.commit`, so the attempted toggle changes neither App settings nor disk. The broad handler logs `alert_fail persist commit`, while the UI still acknowledges the press.
- Fix: use an explicit ID lookup loop supported by MicroPython 1.20. Preserve commit-before-App-update ordering and missing-ID handling.
- Verification: matching MicroPython 1.20 execution reaches a fake commit with enabled=True and updates App settings; missing-ID lookup returns False. `uv run pytest tests/test_alert_app.py tests/test_alert_list_view.py -q` passed (39 tests). Deployment memory gate passed; graph refreshed.
- Deployed fixed working tree using `uv run --with mpy-cross==1.20.0 tools/deploy.py --port /dev/cu.usbmodem101`; command completed successfully and reset the board. Physical touch/redraw and persistence after reboot remain manual checks; no on-device toggle behavior observed.

- Deployed revision `bf6d673a768f6d2c9718858a45f0f1739ac881f4` to `/dev/cu.usbmodem101` on 2026-10-10 with `uv run --with mpy-cross==1.20.0 tools/deploy.py --port /dev/cu.usbmodem101`.
- Target reported MicroPython 1.20.0, Raspberry Pi Pico W RP2040, `_mpy=4358`; matching compiler reported MicroPython v1.20.0 / mpy v6.1.
- Post-deploy read-only import check passed for `src.app`, `src.alert.runtime`, `src.ui.alert_list_view`, `src.ui.alerts`, `src.ui.bar_controls`, and `src.ui.tap`.
- Touch-screen legibility, physical calibration, reboot persistence, and scheduler behavior still require manual device checks; no behavior claim recorded.
