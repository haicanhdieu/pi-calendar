---
title: 'Story 2.2: Wire touch polling into App.step() and render the Bar overlay'
type: 'feature'
created: '2026-09-13'
status: 'done'
baseline_revision: '36d19ff3509f1c10ca2b1ecf36ef8d4d875526a6'
baseline_commit: '36d19ff06c318a6badf0296dafbe9f93a9f30569'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Touch hardware and pure surface decisions exist, but the application neither polls touch nor presents the temporary Bar needed to make the Settings entry discoverable.

**Approach:** Add a device-agnostic touch-port seam to App, process one touch read as step 0, and extend the compositor with a bounded bottom-Bar overlay that the App schedules during its reveal animation.

## Boundaries & Constraints

**Always:** App remains the sole AppState writer and calls `read()` exactly once at the start of each step when a touch port is supplied. A Rotation edge uses the existing pure transition function and commits its surface/deadline before sync work. Bar rendering is draw-last in the compositor, leaves the base view unchanged, uses named geometry/timing/color constants and DisplayPort primitives only, and exposes a centered gear item through an icon-list shape. Rotation view dwell runs only while the active surface is Rotation.

**Never:** Do not import device modules into App/UI modules; do not change touch SPI wiring, add Settings routing/outside-tap dismissal/idle retraction policy from Story 2.3, resize or dim the base view, add a framebuffer, or claim on-device animation behaviour from host tests.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|----------------------------|----------------|
| Rotation touch | `TouchPort.read()` returns edge-down during Rotation | App enters Bar with the pure-module deadline before sync work and requests prompt overlay paint | Absent/false edge is a no-op |
| Bar render | Bar active during reveal or steady state | A bottom-docked bounded strip and centered amber gear are drawn after the unchanged base | Prior Bar region is invalidated on visibility change |
| Frozen dwell | Bar active and view deadline due | Existing Clock/Calendar view and deadline remain unchanged | No deferred rotation occurs |
| No touch port | Existing host/product caller omits port | App preserves prior Rotation behavior | No error expected |

</intent-contract>

## Code Map

- `src/app.py` -- App owns `active_surface`/`surface_deadline`; insert polling before `_consume_sync_result`, gate the existing view-deadline branch, and pass surface/timing state to the compositor.
- `src/ui/touch_state.py` -- existing pure `next_surface` creates the Bar deadline and is the only transition source for this story.
- `src/ui/compositor.py` -- existing badge draw-last owner; add its single Bar overlay call site and retained prior visibility/dirty-region state here.
- `src/ui/components.py` -- existing display-only component helpers; add named Bar rectangle, icon-list item geometry, and bounded gear drawing helpers here.
- `src/config.py` -- existing named Bar dimensions, animation duration/cadence, target size and amber/base tokens; add named panel/flash colors only if necessary.
- `main.py` -- already constructs `TouchPort`; pass it into App without changing shared-SPI ownership.
- `tests/test_app_loop.py` and `tests/test_clock_view.py` -- existing host fake ports/display and compositor conventions; extend with App-order, dwell-gating, geometry, draw-order, and incremental-region tests.
- `tests/test_touch_state.py` -- previous Story 2.1 establishes the pure transition boundary and stays the source of transition semantics.

## Tasks & Acceptance

**Execution:**
- `src/app.py` and `main.py` -- inject and poll the already-created touch port as App step 0, commit the pure transition before sync work, gate dwell while Bar is active, and schedule animation-frame redraws -- preserve single AppState ownership and runtime wiring.
- `src/ui/components.py` and `src/ui/compositor.py` -- supply named Bar/icon-list geometry and draw the incremental bottom overlay after base/badge while invalidating prior Bar pixels -- render a bounded, non-invasive overlay with one compositor call site.
- `tests/test_app_loop.py` and `tests/test_clock_view.py` -- add fake edge-port integration and display-operation assertions -- prove external App/compositor behavior and preserved base rendering under CPython.

**Acceptance Criteria:**
- Given an edge-down touch while Rotation is active, when App steps, then it calls the port once and commits Bar state/deadline before later same-tick work.
- Given Bar is active, when the view deadline is due, then the Clock/Calendar dwell transition is skipped without changing its existing deadline.
- Given a Bar render, when its visibility changes, then its bottom region is invalidated and a full-width 36px panel plus centered gear is drawn last through compositor-owned rendering, without a full-frame overlay fill.
- Given no touch port is supplied, when existing App tests run, then prior behavior remains compatible.

## Spec Change Log

## Review Triage Log

### 2026-09-13 — Review pass
- verdicts: 7 findings — high 0, medium 5, low 1, false 1, maybe-false 0
- findings:
  - `[medium]` `[patch]` App applied the Bar expiry transition before Story 2.3 owns retraction -- `_poll_touch` now evaluates `next_surface` only while Rotation is active, retaining Bar state until the next story wires expiry plus fresh dwell rearming.
  - `[medium]` `[patch]` `boot()` could retain a prior Bar surface and deadline -- boot now explicitly restores Rotation and clears the surface deadline.
  - `[medium]` `[patch]` The first Bar frame had zero height -- the first render starts at one named animation-frame interval so it draws a bounded prompt panel.
  - `[medium]` `[patch]` Gear target and glyph had different vertical centers -- both now derive their center from `bar_gear_item_rect`.
  - `[low]` `[patch]` The compositor docstring claimed the badge was always last -- it now documents the actual badge-then-Bar draw order.
  - `[false]` `[reject]` Missing expiry/retraction restoration tests -- expiry/retraction, fresh dwell rearming, and dismissal pixel restoration are Story 2.3 behavior explicitly outside this story; the added test instead proves Story 2.2 does not wire that policy early.
  - `[medium]` `[patch]` The edge-case review independently identified premature Bar expiry -- same small `_poll_touch` scope correction prevents that observable early retraction.

## Design Notes

The Bar remains an overlay rather than a view so Clock/Calendar caching can continue below it. App supplies a reveal start time to the compositor; the compositor clips each panel fill to the current animation height and App requests only the named frame cadence until steady state. Gear tapping is visually represented by the generous item geometry now; target routing and the flash-to-Settings transition remain for later stories.

## Verification

**Commands:**
- `uv run pytest tests/test_app_loop.py tests/test_clock_view.py tests/test_touch_state.py` -- expected: App ordering, pure state, and display overlay tests pass.
- `uv run pytest` -- expected: complete host suite passes.

## Auto Run Result

Status: done

Implemented touch step-0 polling and a compositor-owned Bar reveal overlay. App now receives the hardware port from `main.py`, commits Rotation-to-Bar state before sync processing, freezes view dwell while Bar is active, and schedules bounded animation redraws.

Files changed:
- `main.py` -- injects the already-constructed TouchPort into App.
- `src/app.py` -- owns touch polling, Bar state entry, animation scheduling, and dwell gating.
- `src/config.py` -- defines the exact `#141414` Bar panel token.
- `src/ui/components.py` -- supplies Bar/gear geometry and bounded DisplayPort drawing.
- `src/ui/compositor.py` -- owns the sole draw-last Bar call site and visibility invalidation.
- `tests/test_app_loop.py` and `tests/test_clock_view.py` -- cover ordering, dwell freeze, no-port compatibility, bounded render geometry, and restoration.
- `sprint-status.yaml` -- records Story 2.2 progress.

Review findings: 6 patches applied (medium 5, low 1), 0 deferred, 1 rejected as outside this story's explicitly staged behavior. Two independent review layers were available in this nested run; verification-gap and intent-alignment layers were not launched because of shared reviewer capacity. Follow-up review recommendation: false (no high patches; the duplicated expiry observation has one shared correction).

Verification performed: `uv run pytest tests/test_app_loop.py tests/test_clock_view.py tests/test_touch_state.py` passed (47 tests); `uv run pytest` passed (322 tests); `git diff --cached --check` passed.

Residual risks: host tests cannot prove Pico SPI/touch polling, panel smoothness, or visible blanking. Flash the board and capture serial checkpoints plus observed Bar reveal behavior before device acceptance.
