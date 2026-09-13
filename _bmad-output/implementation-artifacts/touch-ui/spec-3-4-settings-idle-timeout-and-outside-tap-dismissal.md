---
title: 'Story 3.4: Settings idle timeout and outside-tap dismissal'
type: 'feature'
created: '2026-09-13'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_revision: 'd97e50bde265b0311ea463c087368df8e796445a'
followup_review_recommended: false
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Once Settings opens it has no owned dismissal policy — `next_surface`'s `settings` branch is an inert pass-through that never returns to Rotation, so the Device would sit in Settings indefinitely regardless of idle time or an outside tap.

**Approach:** Extend the Bar's established idle-timeout/outside-tap dismissal pattern (Story 2.3) to the Settings surface: arm the shared `TOUCH_IDLE_TIMEOUT_MS` deadline once on Settings entry, dismiss to Rotation on expiry or any tap outside the Reboot button's tap target, and re-arm the interrupted Clock/Calendar view's dwell exactly as the Bar's return-to-Rotation path already does.

## Boundaries & Constraints

**Always:** Arm Settings' idle deadline once, on entry from the Bar's gear edge, using the existing `TOUCH_IDLE_TIMEOUT_MS` constant — never a separate value. Use the pure `next_surface` tick-safe due-deadline comparison, mirroring the Bar branch's shape. A tap on the Reboot button's own tap-target neither dismisses Settings nor counts as an outside tap. Returning to Rotation always re-arms the previously active Clock/Calendar view's dwell deadline from `now`, exactly as the Bar's return path already does. Closing Settings always returns straight to `rotation`, never to `bar`.

**Never:** Do not add a separate or tunable timeout for Settings. Do not add reveal/retract animation state or reverse-frame cadence for Settings — its dismissal is an instant surface swap, unlike the Bar's animated retraction. Do not implement or modify Settings' status/guideline rendering, Press Flash, or the Reboot side effect itself (Stories 3.1-3.3's territory) beyond the minimal hit-test wiring this story needs. Do not renew or reset the Settings deadline on any touch, including a Reboot tap.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Idle expiry | Settings active, deadline due, no edge | Returns to Rotation, deadline cleared, active view's dwell re-armed from now | No error expected |
| Outside tap | Settings active, edge outside Reboot target | Returns to Rotation immediately, no stale deadline retained | Malformed/absent coordinates are not a hit and do not raise |
| Reboot tap | Settings active, edge on Reboot target | Settings retained by this decision; Story 3.3's reboot trigger governs the resulting reset | No error expected |
| Settings entry | Bar's gear edge fires | Enters Settings with a freshly armed `TOUCH_IDLE_TIMEOUT_MS` deadline, not left unset | N/A |

</frozen-after-approval>

## Code Map

- `src/ui/touch_state.py` -- the `SURFACE_SETTINGS` branch (currently an inert pass-through) becomes idle-expiry + outside-tap dismissal, mirroring the `SURFACE_BAR` branch's shape; add a `settings_target` parameter and `SETTINGS_TARGET_REBOOT` constant analogous to `bar_target`/`BAR_TARGET_GEAR`. Also change the `SURFACE_BAR` branch's gear-edge case (currently `return SURFACE_SETTINGS, None`) to arm `ticks_add(now, TOUCH_IDLE_TIMEOUT_MS)` instead of `None`.
- `src/app.py` -- `_poll_touch` computes `settings_target` when `previous == SURFACE_SETTINGS` via a Reboot hit-test (analogous to the existing `self._compositor.bar_gear_hit` used for the gear), and passes it into `next_surface`. Add an `elif previous == SURFACE_SETTINGS:` branch mirroring the existing `SURFACE_BAR` branch, re-arming the active view's dwell only when `surface == SURFACE_ROTATION`. No Bar-style reveal/retract timestamps are needed for Settings.
- `src/ui/compositor.py` -- if Story 3.3 has not already exposed a Reboot hit-test helper, add one following `bar_gear_hit`'s shape, scoped to the Reboot tap-target rect only.
- `src/config.py` -- read-only; reuse `TOUCH_IDLE_TIMEOUT_MS`, no new constant.
- `tests/test_touch_state.py` -- update `test_bar_routes_gear_edge_to_settings_and_other_edges_to_rotation` and `test_gear_edge_wins_when_bar_deadline_is_due` to expect an armed deadline instead of `None`; replace `test_settings_is_preserved_without_a_new_deadline` with idle-expiry, outside-tap, and Reboot-target-preserved cases mirroring the Bar's existing tests.
- `tests/test_app_loop.py` -- extend the FakeTouchPort/App integration seam (already used for the Bar's Story 2.3 coverage) with Settings idle-timeout dismissal, outside-tap dismissal, and dwell re-arm cases.

## Tasks & Acceptance

**Execution:**
- [x] `src/ui/touch_state.py` -- add `settings_target`/`SETTINGS_TARGET_REBOOT`, replace the Settings pass-through with idle-expiry + outside-tap dismissal, and arm the deadline on Settings entry -- gives Settings the same tick-safe, single-owner transition logic already proven for the Bar.
- [x] `src/app.py` -- wire the Reboot hit-test into `settings_target` and add the Settings-to-Rotation dwell re-arm branch -- keeps App the sole mutable-state committer for the dismissal path.
- [x] `src/ui/compositor.py` -- expose a Reboot hit-test helper only if Story 3.3 has not already added one -- keeps geometry centralized rather than embedded in App.
- [x] `tests/test_touch_state.py` -- update and replace the Settings placeholder tests -- prove the pure decision logic for all three Settings scenarios.
- [x] `tests/test_app_loop.py` -- add Settings dismissal/re-arm integration coverage -- prove observable App-level behavior.

**Acceptance Criteria:**
- Given Settings is active with no further touch and its deadline elapses, when App steps, then `active_surface` returns to `rotation` and the previously active view's dwell deadline is re-armed from that tick.
- Given Settings is active and a touch lands outside the Reboot tap target, when App steps, then `active_surface` returns to `rotation` immediately with no stale deadline retained.
- Given Settings is active and a touch lands on the Reboot tap target, when App steps, then `active_surface` remains `settings` from this decision alone — Story 3.3's reboot trigger governs the resulting device reset.
- Given the Bar's gear edge enters Settings, when App steps, then Settings' deadline is armed for `TOUCH_IDLE_TIMEOUT_MS` from that tick, not left unset.

## Implementation Notes

- `App._poll_touch` filters Settings edges through `settings_outside_edge` before calling `next_surface`, mirroring Bar's malformed-coordinate guard via `bar_outside_edge`.
- Settings→Rotation clears stale Bar retract animation state (`_bar_retract_started`, etc.) so dismissal is an instant surface swap with no partial Bar overlay on the restored Rotation frame.
- Reboot handling runs after `next_surface` commit; `return reboot_tap` preserves `force_redraw` when the surface is unchanged.

## Spec Change Log

## Review Triage Log

### 2026-09-13 — Review pass
- verdicts: 15 findings — high 1, medium 2, low 1, false 11, maybe-false 0
- findings:
  - `[false]` `[reject]` Empty Implementation Notes/Spec Change Log headers — filled during finalize, not a code defect.
  - `[false]` `[reject]` Frontmatter `context: []` empty — optional metadata; epic context is on disk separately.
  - `[false]` `[reject]` Task checkboxes unchecked — updated at finalize after implementation completed.
  - `[medium]` `[patch]` No pure test for reboot edge winning when Settings deadline is simultaneously due — added `test_settings_reboot_edge_wins_when_settings_deadline_is_due` and App-level `test_settings_reboot_tap_wins_when_idle_deadline_is_due`.
  - `[medium]` `[patch]` No App-level malformed-edge test for Settings — added `settings_outside_edge` in compositor, `surface_edge_down` filtering in `_poll_touch`, and `test_settings_malformed_edge_stays_on_settings_without_error`.
  - `[low]` `[patch]` No integration test for Settings idle-timeout with Calendar active view — added `test_settings_idle_timeout_rearms_calendar_dwell`.
  - `[false]` `[reject]` Acceptance criteria omit malformed-coordinate row — covered by integration test matching I/O matrix; AC list unchanged per frozen intent.
  - `[false]` `[reject]` Code Map lists conditional compositor task as open — Story 3.3 already landed `settings_reboot_hit`; task marked done.
  - `[false]` `[reject]` Verification section missing `git diff --check` — not required by this spec's verification block.
  - `[high]` `[patch]` Settings→Rotation did not clear Bar retract state, risking partial Bar overlay — cleared retract fields and added `test_settings_outside_tap_clears_bar_retract_state`.
  - `[false]` `[reject]` Design Notes omit App `_poll_touch` return contract — documented in Implementation Notes; behavior verified by existing reboot flash tests.
  - `[high]` `[patch]` Edge-case: Settings dismiss while bar retract armed leaves partial overlay — same root cause as above; fixed with retract state clear on Settings→Rotation.
  - `[high]` `[patch]` Claim: instant surface swap violated by stale bar retract — same fix as retract state clear.
  - `[medium]` `[patch]` Verification gap: reboot-vs-deadline priority untested — tests added (grouped with finding 4).
  - `[medium]` `[patch]` Verification gap: malformed edge not adopted from Bar pattern — compositor helper + App filter + test added (grouped with finding 5).

## Design Notes

The Settings branch should read as the Bar branch's mirror, not a divergent shape:

```python
if active_surface == SURFACE_SETTINGS:
    if edge_down and settings_target == SETTINGS_TARGET_REBOOT:
        return SURFACE_SETTINGS, surface_deadline
    if surface_deadline is not None and ticks_diff(surface_deadline, now) <= 0:
        return SURFACE_ROTATION, None
    if edge_down:
        return SURFACE_ROTATION, None
    return SURFACE_SETTINGS, surface_deadline
```

App layer: filter malformed Settings edges via `settings_outside_edge` before passing `surface_edge_down` to `next_surface`; clear Bar retract state on Settings→Rotation.

## Verification

**Commands:**
- `uv run pytest tests/test_touch_state.py tests/test_app_loop.py` -- expected: Settings idle-timeout, outside-tap, Reboot-preserved, and dwell re-arm cases pass.
- `uv run pytest` -- expected: entire host suite passes.

## Auto Run Result

Status: done

Summary: Implemented Settings idle-timeout and outside-tap dismissal mirroring Story 2.3's Bar pattern. Settings arms `TOUCH_IDLE_TIMEOUT_MS` on gear entry, dismisses to Rotation on expiry or valid outside tap, preserves surface on Reboot tap, and re-arms Clock/Calendar dwell on return. Review patches added malformed-edge filtering, bar-retract cleanup on dismiss, and precedence/deadline tests.

Files changed:
- `src/ui/touch_state.py` — Settings branch with `SETTINGS_TARGET_REBOOT`, gear entry deadline arming
- `src/app.py` — settings target wiring, dwell re-arm, retract cleanup, reboot-after-commit ordering
- `src/ui/compositor.py` — `settings_outside_edge` helper for valid outside taps
- `tests/test_touch_state.py` — pure Settings dismissal and precedence tests
- `tests/test_app_loop.py` — integration tests for idle/outside/reboot/malformed/retract cases

Review findings: 5 patches applied (1 high, 4 medium/low grouped); 11 rejected as documentation/metadata or duplicate; 0 deferred.

Follow-up review recommended: false (one high patch applied; converged in single pass).

Verification: `uv run pytest tests/test_touch_state.py tests/test_app_loop.py` — 59 passed; `uv run pytest` — 366 passed.

Residual risks: On-device touch coordinate behavior and bar-retract visual timing require flash verification; host tests cannot prove Pico heap or physical touch sampling.
