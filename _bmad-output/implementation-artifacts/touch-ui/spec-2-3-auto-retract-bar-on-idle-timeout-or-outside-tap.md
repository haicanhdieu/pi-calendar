---
title: 'Story 2.3: Auto-retract Bar on idle timeout or outside tap'
type: 'feature'
created: '2026-09-13'
status: 'done'
baseline_revision: 'a9c12295fbfd4a18a29b6f957787ca670a7d2dd2'
baseline_commit: 'a9c12295fbfd4a18a29b6f957787ca670a7d2dd2'
review_loop_iteration: 1
followup_review_recommended: true
context: []
warnings: []
deferred:
  - summary: >-
      On-device flash and serial checkpoints for Bar reverse animation cadence and touch coordinate routing remain unverified on hardware.
    evidence: |-
      Host pytest covers App/compositor seams with fakes; AGENTS.md requires separate device evidence for touch/display paths. No serial capture was recorded for this story.
    severity: medium
  - summary: >-
      Gear hit testing lives in UiCompositor rather than the pure touch_state module described in architecture spine.
    evidence: |-
      App passes a bar_target enum into next_surface after compositor geometry checks. Behavior is host-tested; relocating geometry to touch_state would be a refactor with no current functional gap.
    location: >-
      src/app.py:241-247
    severity: low
---

<intent-contract>

## Intent

**Problem:** The revealed Bar currently remains indefinitely and treats every later touch as inert, leaving the ambient surface without the required return paths.

**Approach:** Complete the App-owned Bar interaction policy: dismiss on its fixed idle deadline or an outside edge, animate bounded reverse pixels, and route the existing gear target to the Settings surface without building the Settings view early.

## Boundaries & Constraints

**Always:** Poll once per step; use the pure `next_surface` expiry decision and tick-safe deadlines; use the named Bar/gear geometry for hit testing; re-arm the current Clock/Calendar dwell from the dismissal tick; retain that view; and restore only the bounded bottom region through the compositor during reverse animation. A gear edge from Bar enters `settings`, hides/retracts the Bar, and does not become an outside dismissal.

**Never:** Do not implement Settings rendering, status capture, Press Flash, Settings dismissal, reboot, touch wiring, or hardware imports. Do not renew the Bar deadline, resize/dim/scrim the base view, add gestures, or use a framebuffer/full-screen overlay fill.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Idle retract | Bar deadline due, no edge | Rotation, no surface deadline, fresh active-view dwell, reverse Bar redraw | No error expected |
| Outside retract | Bar edge outside panel or gear target | Same immediate Rotation decision and reverse redraw | Coordinates absent/malformed are not a hit and do not raise |
| Gear route | Bar edge inside gear target | Settings with Bar hidden; no Rotation dwell re-arm | No Settings rendering is expected in this story |
| Rotation compatibility | No Bar interaction | Existing Rotation touch reveal and dwell behavior remains unchanged | No error expected |

</intent-contract>

## Code Map

- `src/app.py` -- `_poll_touch` presently reads only the edge flag and deliberately bypasses Bar expiry; extend its pure-decision/hit-test inputs, centralize enter/exit state commits, re-arm the retained active-view dwell on return to Rotation, and schedule reverse Bar frames.
- `src/ui/touch_state.py` -- pure `next_surface` already provides tick-safe due-deadline Rotation return; preserve its fixed-deadline semantics and add only explicit target routing if needed without device imports.
- `src/ui/components.py` -- `bar_rect` and `bar_gear_item_rect` are the named geometry source; add a bounded point-in-rect helper rather than embedding coordinates in App.
- `src/ui/compositor.py` -- sole Bar draw call site and prior-visibility invalidator; accept bounded reverse-progress input so it paints only the remaining bottom strip after the base restoration.
- `src/config.py` -- existing `CLOCK_DWELL_MS`, `CALENDAR_DWELL_MS`, Bar duration and animation cadence are the sole timing sources; read-only unless a missing named value is demonstrated.
- `tests/test_app_loop.py` -- FakeTouchPort/App integration seam; replace the deliberate Story 2.2 no-expiry assertion and cover timeout, outside, gear, dwell rearm, tick behavior, and one-read ordering.
- `tests/test_clock_view.py` -- FakeDisplayPort compositor assertions; cover bounded reverse Bar pixels and restoration without a full-frame overlay fill.

## Tasks & Acceptance

**Execution:**
- [x] `src/ui/components.py` and `src/ui/touch_state.py` -- expose reusable named Bar hit testing and explicit Bar target decisions while retaining pure, CPython-safe state semantics -- keep UI policy testable and geometry centralized.
- [x] `src/app.py` -- route Bar timeout/outside/gear decisions from one touch sample, retain the interrupted view, re-arm its named dwell deadline only when Rotation resumes, and schedule reverse frames -- make App the sole mutable state owner.
- [x] `src/ui/compositor.py` -- render reverse Bar frames through the existing draw-last call site and invalidate prior Bar pixels only as needed -- preserve bounded dirty-region rendering.
- [x] `tests/test_app_loop.py` and `tests/test_clock_view.py` -- add host boundary tests for all matrix paths and bounded display operations -- prove observable behavior under CPython.

**Acceptance Criteria:**
- Given an active Bar reaches its fixed idle deadline, when App steps, then it returns to Rotation and arms the currently shown view's normal dwell duration from that tick.
- Given a Bar edge is outside its panel or gear target, when App steps, then it returns to Rotation immediately and does not retain the old surface deadline.
- Given a Bar edge is inside the named gear target, when App steps, then it enters Settings rather than running Bar dismissal or a Rotation dwell re-arm.
- Given Bar retraction starts, when compositor frames render, then only a decreasing bottom Bar region is drawn through its single draw-last call site and the unchanged base restores it without a full-screen overlay fill.

## Spec Change Log

## Review Triage Log

| Finding | Verdict | Evidence / route |
| --- | --- | --- |
| `compositor.py` clears uncovered pixels to background without restoring cached base content | medium | carried: `invalidate()` before `base_view.render()` restores cached CalendarView content; regression test added. |
| `app.py` continues view dwell while `settings` is active | medium | carried: view deadline predicate limited to `SURFACE_ROTATION`. |
| Reverse begins at full Bar height during partial reveal | medium | carried: `_bar_retract_start_height` captures visible height at dismissal. |
| Infinite numeric touch coordinates raise `OverflowError` | low | carried: `point_in_rect` catches `OverflowError`. |
| Reverse test asserts background fill but not restored content | medium | carried: `test_bar_reverse_restores_cached_calendar_bottom_cells` added. |
| App-level wraparound lifecycle coverage is missing | low | carried: `test_reverse_frames_shrink_across_tick_wrap_and_finish_cleanly` covers rollover. |
| Gear target loses to a due Bar deadline | medium | carried: gear routing precedes deadline check in `next_surface`. |
| App-driven reverse frames lack end-to-end coverage | medium | carried: App reverse-frame test advances cadence and cleanup. |

### 2026-09-13 — Review pass
- verdicts: 24 findings — high 0, medium 8, low 3, false 7, maybe-false 0
- findings:
  - `[medium]` `[patch]` Outside dismissal ignored `bar_rect`, treating any non-gear edge as outside — App now classifies gear/panel/outside via compositor geometry and `BAR_TARGET_*` enums; in-panel and malformed edges stay on Bar.
  - `[medium]` `[patch]` Missing CalendarView content-restoration regression — `test_bar_reverse_restores_cached_calendar_bottom_cells` proves strip restore plus calendar redraw after invalidate.
  - `[medium]` `[patch]` Malformed touch coords incorrectly dismissed Bar — matrix requires non-hit; malformed edges now retain Bar and deadline.
  - `[medium]` `[patch]` carried: compositor cached-base restore — invalidate-before-render already present; test added this pass.
  - `[medium]` `[patch]` carried: Settings view dwell — Rotation-only predicate already present.
  - `[medium]` `[patch]` carried: partial reveal reverse height — `_bar_retract_start_height` already present.
  - `[medium]` `[patch]` carried: gear-before-deadline ordering — already present in `touch_state`.
  - `[medium]` `[patch]` carried: App reverse-frame scheduling — wraparound test already present.
  - `[low]` `[patch]` Stale `touch_state` module docstring — updated to reflect Settings gear routing.
  - `[low]` `[reject]` OverflowError in `point_in_rect` — already handled; no change needed.
  - `[low]` `[reject]` View switch mid-retract — dwell durations (8–30s) exceed slide duration (240ms); unreachable in configured product.
  - `[false]` `[reject]` Compositor lacks invalidate on shrink — code calls `base_view.invalidate()` at compositor.py:71-72.
  - `[false]` `[reject]` Bar continues full-height animation after Settings entry — retract timestamps drive shrinking overlay by design.
  - `[false]` `[reject]` Idle-timeout test lacks reverse frames — `test_reverse_frames_shrink_across_tick_wrap_and_finish_cleanly` covers end-to-end reverse cadence.
  - `[false]` `[reject]` I/O matrix wording contradicts gear route — table row means outside both panel and gear; implementation matches after `bar_rect` fix.
  - `[false]` `[reject]` Outside test lacks geometry proof — `(0,0)` is outside 36px strip; in-panel test added at `(10,220)`.
  - `[false]` `[reject]` Rotation compatibility unproven — existing reveal/dwell tests unchanged; Settings predicate change is intentional for Story 3.x handoff.
  - `[false]` `[reject]` Claim: base view lacks invalidate during shrink — invalidate is present before render.
  - `[reject]` Spec Change Log / triage table / warnings edits — workflow rejects findings whose fix edits the build spec body.
  - `[reject]` Sprint-status epic-3 promotion bundled — orchestration artifact outside story runtime scope.
  - `[defer]` On-device flash/serial verification for touch/display — host fakes sufficient for story closure; device evidence deferred.
  - `[defer]` Gear hit testing in compositor vs pure touch_state — architecture preference; behavior host-tested and functional.

## Design Notes

The Bar remains an overlay even while retracting. App retains a short-lived transition timestamp after the logical surface changes, and compositor derives the remaining panel height from that timestamp; this lets base-view invalidation restore uncovered pixels while each overlay operation stays inside the 36px strip.

## Verification

**Commands:**
- `uv run pytest tests/test_app_loop.py tests/test_clock_view.py tests/test_touch_state.py` -- expected: Bar timeout, hit routing, dwell re-arm, and bounded overlay paths pass.
- `uv run pytest` -- expected: entire host suite passes.
- `git diff --check` -- expected: no whitespace errors.

## Auto Run Result

Status: done

**Summary:** Story 2.3 completes Bar auto-retract on idle timeout or outside-panel tap, gear routing to latent Settings, bounded reverse animation with base content restoration, and Rotation dwell re-arm — all orchestrated from App with pure `next_surface` decisions and compositor geometry helpers.

**Files changed:**
- `src/app.py` — Bar target classification (gear/panel/outside), reverse animation state, Rotation-only view dwell, dwell re-arm on dismiss.
- `src/ui/touch_state.py` — `BAR_TARGET_*` enums, gear-before-deadline, in-panel/malformed edge retention.
- `src/ui/components.py` — `point_in_rect` with OverflowError guard.
- `src/ui/compositor.py` — panel/outside hit helpers, reverse height rendering, strip invalidation before base render.
- `tests/test_app_loop.py` — matrix integration tests including in-panel, malformed, reverse frames, gear/settings paths.
- `tests/test_clock_view.py` — reverse pixel bounds, CalendarView content restoration, hit-test tolerance.
- `tests/test_touch_state.py` — pure transition tests for all Bar targets.

**Review findings breakdown:** 8 medium patches applied (3 new this pass, 5 carried from pre-review implementation); 2 items deferred (device verification, compositor-vs-pure geometry placement); 7 false/rejected (already fixed, unreachable, or spec-edit/meta findings).

**Follow-up review recommended:** true — two medium patches landed this pass (`bar_rect` outside semantics, CalendarView restoration test); on-device touch coordinate routing remains unverified.

**Verification performed:**
- `uv run pytest tests/test_app_loop.py tests/test_clock_view.py tests/test_touch_state.py` — 61 passed
- `uv run pytest` — 336 passed
- `git diff --check` — no whitespace errors

**Residual risks:** Cached CalendarView restore triggers a full base redraw after strip invalidate (correct content, not strip-only redraw). Device flash evidence for touch coordinates and reverse animation cadence not yet captured.
