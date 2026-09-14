---
title: 'Calendar screen small unsynced clock'
type: 'feature'
created: '2026-09-14'
status: 'done'
baseline_revision: '7aa66a46e01e0d9726309dccbdd262b93fbb8c01'
baseline_commit: '7aa66a46e01e0d9726309dccbdd262b93fbb8c01'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred:
  - summary: >-
      Graphify generated files create a large unrelated-looking review diff.
    evidence: |-
      Required `graphify update .` refreshed tracked graph output; generated artifacts are repository-managed and are not product code.
    location: >-
      graphify-out/
    severity: low
---

<intent-contract>

## Intent

**Problem:** Calendar view does not show current time, so users cannot know the time while viewing the month grid.

**Approach:** Render local time as a small `HH:MM` label in the top-left corner of Calendar view. Use unsynced color for this label and update it as part of Calendar view rendering, without adding a separate refresh mechanism.

## Boundaries & Constraints

**Always:** Keep Calendar view pure and DisplayPort-only; use existing `TimeSnapshot.local`; format exactly 24-hour `HH:MM`; use `FONT_BADGE` and `COLOR_UNSYNCED`; keep label at top-left; redraw when displayed local minute changes so cached rendering cannot leave stale time.

**Never:** Add hardware imports, network/time polling, a second timer, a background refresh path, or alter Clock view, calendar grid geometry, unsynced badge behavior, or hardware wiring.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| LOCAL_TIME | Calendar render with local `14:07` | Draws `14:07` at `(0, 0)` using `FONT_BADGE` and `COLOR_UNSYNCED` | No error expected |
| MINUTE_CHANGE | Cached Calendar render changes local minute from `14:07` to `14:08` | Calendar redraw updates corner label to `14:08` during normal Calendar rendering | No separate refresh path |
| NO_LOCAL_TIME | Calendar render with `snapshot.local is None` | Draws `--:--` using same position/font/color, matching Clock placeholder semantics | No exception |

</intent-contract>

## Code Map

- `src/ui/calendar_view.py:1-140` -- Calendar renderer and cache; add compact local-time formatting, corner draw, and minute cache key.
- `src/config.py:64-96` -- Existing `FONT_BADGE`, `COLOR_UNSYNCED`, and clock placeholder constants; reuse without new hardware/runtime dependencies.
- `tests/test_calendar_view.py:98-370` -- Calendar renderer tests and FakeDisplayPort operation assertions; add happy, minute-change, and no-local coverage.

## Tasks & Acceptance

**Execution:**
- [x] `src/ui/calendar_view.py` -- render cached local `HH:MM` at top-left in unsynced color and invalidate cache on local-minute changes -- keeps time visible without independent refresh.
- [x] `tests/test_calendar_view.py` -- verify position, font, color, placeholder, and minute-change redraw -- covers matrix and prevents stale corner time.

**Acceptance Criteria:**
- Given Calendar view renders with local time `14:07`, when rendering completes, then `14:07` appears at x=0/y=0 with `FONT_BADGE` and `COLOR_UNSYNCED`.
- Given Calendar view has cached `14:07`, when next Calendar render receives local `14:08`, then screen operations include a redraw with `14:08`.
- Given Calendar view renders without local time, when rendering completes, then `--:--` appears at x=0/y=0 with `FONT_BADGE` and `COLOR_UNSYNCED`.
- Given Calendar view is rendered, when inspecting imports, then no hardware, network, or MicroPython-only module is imported.

## Spec Change Log

## Review Triage Log

### 2026-09-14 — Review pass
- verdicts: 14 findings — high 0, medium 0, low 1, false 11, maybe-false 1
- findings:
  - `[false]` `[reject]` Verification section lacked actual results — review occurred before finalization; results recorded below.
  - `[false]` `[reject]` Tasks lacked commit links — commit linkage is finalized after review, not an implementation defect.
  - `[low]` `[reject]` Formatter boundary cases lacked dedicated tests — valid values are domain-invariant and added tests cover required behavior; extra cases are low-value.
  - `[false]` `[reject]` Old clock label might remain — full redraw clears display before drawing new label.
  - `[false]` `[reject]` Same-minute cache behavior lacked coverage — existing Calendar cache test proves repeated identical renders are no-op.
  - `[false]` `[reject]` Local/None cache transitions lacked coverage — `has_local` participates in cache key, forcing redraw on either transition.
  - `[patch]` `[patch]` App render path lacked minute-change coverage — added `test_app_calendar_redraws_corner_clock_when_local_minute_changes`.
  - `[false]` `[reject]` Hour-boundary refresh lacked coverage — cache tracks hour as well as minute, so `14:07` to `15:07` redraws.
  - `[false]` `[reject]` Draw order lacked coverage — Calendar draws clock after background; compositor draws badge/bar afterward, and existing badge-order tests cover compositor ordering.
  - `[false]` `[reject]` Corner clock might overlap month header — clock is 8px high at y=0; month content starts at y=10.
  - `[low]` `[reject]` Digit table duplicates Clock view — no demonstrated user/developer harm; avoiding duplication would add coupling or a new shared module.
  - `[defer]` `[defer]` Graphify output expands review diff — generated output is required by repository policy; no product-code fix applies.
  - `[maybe-false]` `[defer]` Malformed DateTime fields could break exact formatting — all production DateTime construction supplies valid fields; malformed manually-created objects would require a separate domain-validation decision.
  - `[false]` `[reject]` Intent surface diverges from implementation surface — host renderer tests are the available verification surface; physical-device evidence is recorded as a residual risk.

## Verification

**Commands:**
- `uv run pytest tests/test_calendar_view.py` -- expected: all Calendar renderer tests pass.
- `uv run pytest` -- expected: full host suite passes.
- `graphify update .` -- expected: graphify output updates successfully.

</intent-contract>

## Design Notes

Corner clock uses same placeholder and compact font family as Clock view, but unsynced red remains intentional: this is a small status cue, not primary time typography. Calendar cache tracks local hour/minute so repeated render calls remain cheap while minute changes repaint the existing view and label together.

## Auto Run Result

Summary: Added small local `HH:MM` clock to Calendar view at top-left in unsynced color. Calendar cache redraws when local hour/minute changes, without a separate refresh path.

Files changed:
- `src/ui/calendar_view.py` -- formats and renders corner clock; tracks local time in cache.
- `tests/test_calendar_view.py` -- covers clock rendering, placeholder, and minute-change redraw.
- `tests/test_app_loop.py` -- covers App-driven Calendar minute update.
- `spec-calendar-screen-small-clock.md` -- implementation and review record.

Review findings breakdown: 1 patch applied, 1 item deferred, 11 findings rejected, 1 maybe-false item deferred. No high or medium patches. Follow-up review recommendation: false.

Verification: `uv run pytest tests/test_calendar_view.py` passed (17 tests); `uv run pytest` passed (548 tests); `graphify update .` passed; `git diff --check HEAD` passed; `uv run tools/deploy.py --port /dev/cu.usbmodem101` passed memory gate and completed filesystem deployment/reset. Pico hardware behavior was not observed; physical color/placement validation remains outstanding.

Residual risks: Host tests and deployment success cannot prove Pico display legibility or rendered physical behavior. Inspect Calendar screen on hardware before treating feature as device-verified.
