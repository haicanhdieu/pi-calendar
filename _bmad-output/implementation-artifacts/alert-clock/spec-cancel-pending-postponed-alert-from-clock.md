---
title: 'Cancel a postponed alert from the clock screen'
type: 'feature'
created: '2026-09-23'
baseline_revision: '0fd0ef6305aaf7ad1548e0d5ed603facb45cdecc'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred:
  - summary: >-
      A separate base alert that becomes due while a postponed occurrence is pending may not be evaluated until postponed state ends.
    evidence: |-
      The alert runtime returns through pending-occurrence handling while that occurrence remains future-due. This behavior predates the cancel control and needs a separate policy decision for overlapping occurrences.
    location: >-
      src/alert/runtime.py pending-occurrence evaluation
    severity: medium
  - summary: >-
      Countdown cancel control is unavailable while local time is unknown.
    evidence: |-
      Remaining minutes cannot be calculated without a valid local time snapshot. Clock view continues its existing unsynchronized behavior; no safe countdown value can be displayed until time returns.
    location: >-
      src/app.py _pending_button_label
    severity: low
---

<intent-contract>
## Intent

**Problem:** After postponing an alert, user returns to normal display with no local control to call that occurrence back early. The pending occurrence also gives no persistent countdown.

**Approach:** Keep clock screen visible while an occurrence is postponed. Show full-width amber `CANCEL ALERT ##m` button in bottom band; tapping clears postponement and immediately resumes active alert for same captured occurrence.

## Boundaries & Constraints

**Always:** Show whole minutes remaining until scheduled re-alert, rounded up by minute boundary; singular `1m`, plural `##m`. Use amber fill `COLOR_SECONDARY` and near-black `COLOR_BACKGROUND` text. Button replaces upcoming-event rows while pending. Preserve alert membership, one-time/repeating semantics, persistence, touch release latch, and cooperative loop. Clear persisted pending state before starting buzzer, so reboot cannot replay canceled occurrence.

**Never:** Modify base alert configuration, postpone duration, recurrence, buzzer cadence, active-alert controls, hardware pins, or claim device behavior without flashing.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Pending occurrence | Future due time | Clock view shows amber `CANCEL ALERT ##m`; upcoming events hidden | Keep normal status badge behavior |
| Cancel tap | First valid touch inside full-width bottom-band target | Persist pending state as cleared, then sound same occurrence and show active-alert controls | If persistence fails, retain pending occurrence and do not start sound |
| Touch replay | Held/replayed edge before release | At most one cancel and one active occurrence | Consume until release |
| Due boundary | Clock reaches pending due minute | Existing scheduled re-alert runs once; pending button disappears | Existing scheduler recovery applies |

</intent-contract>

## Code Map

- `src/alert/runtime.py` -- evaluates persisted/in-memory pending occurrence and active alert; add pending-button hit handling and clear-before-realert cancel path alongside due-time transition.
- `src/app.py` -- polls touch before alert evaluation, owns view rotation and base render; route pending button taps and keep clock view active while pending.
- `src/ui/clock_view.py` -- dirty-region clock renderer and reserved bottom event band; draw/update pending button and suppress event rows while button shown.
- `src/ui/compositor.py` -- forwards render inputs while preserving unsynced badge and touch-menu overlays.
- `src/alert/scheduler.py` -- pure local-minute scheduling helpers; add bounded remaining-minute formatting support without hardware imports.
- `src/config.py` -- existing `COLOR_SECONDARY`, `COLOR_BACKGROUND`, and `CLOCK_EVENTS_BAND_H_PX` provide button palette and geometry; reuse them.
- `tests/test_alert_app.py`, `tests/test_clock_view.py` -- existing fake App/display fixtures document alert lifecycle and clock draw operations.
- `_bmad-output/planning-artifacts/alert-clock/prds/prd.md`, `ux-designs/EXPERIENCE.md`, `ux-designs/DESIGN.md` -- source of truth for postponed-alert behavior and visual rules; align with approved control.

## Tasks & Acceptance

**Execution:**
- `src/alert/runtime.py`, `src/app.py` -- add release-latched pending-button touch action and clear persisted pending state before immediate re-alert -- preserve one-shot semantics across loop and reboot.
- `src/ui/clock_view.py`, `src/ui/compositor.py`, `src/alert/scheduler.py` -- render amber countdown button in bottom band and update remaining minutes without rebuilding unrelated UI -- retain clock/status layout and replace upcoming-event rows only while pending.
- `_bmad-output/planning-artifacts/alert-clock/prds/prd.md`, `ux-designs/EXPERIENCE.md`, `ux-designs/DESIGN.md` -- record persistent pending control, clock-view behavior, and palette -- keep product and UX source of truth aligned.

**Acceptance Criteria:**
- Given a future postponed occurrence, when normal display resumes, then clock view remains available and shows `CANCEL ALERT ##m` in amber bottom-band target with remaining whole minutes.
- Given pending postponement, when user taps button once, then Device clears saved pending postponement before resuming buzzer and active-alert screen for same occurrence.
- Given pending postponement and tap held/replayed, when input is sampled repeatedly before release, then only one active occurrence starts.
- Given pending postponement reaches due minute before a valid cancel tap, when scheduler evaluates it, then existing re-alert path runs once and button is removed.
- Given no pending postponement, when clock view renders, then existing upcoming-event and normal rotation behavior remain unchanged.

## Spec Change Log

## Review Triage Log

- `2026-09-23` — Independent review: 11 findings total; 4 low patches applied, 5 false findings rejected, 1 maybe-false finding deferred, and 1 medium finding deferred. No high findings. Follow-up review not recommended because all applied patches were low severity.
  - `[maybe-false]` `[defer]` Countdown button hidden when `snapshot.local` is unavailable — no trustworthy remaining-minute value can be computed until local time returns; record limitation and revisit time-loss UX policy.
  - `[false]` `[reject]` Bottom-band cancel touch may trigger under Bar/Settings — handler now requires rotation surface, and pending control hides whenever another surface is active.
  - `[false]` `[reject]` Persisted pending occurrence is not restored in test — existing test seeds saved state and verifies boot restoration before cancel behavior.
  - `[low]` `[patch]` No simultaneous cancel/due-minute boundary regression — added boundary test proving due transition wins and runs once.
  - `[low]` `[patch]` Countdown minute change may not redraw label — added redraw regression for changed remaining-minute label.
  - `[false]` `[reject]` Remaining-minute calculation floors instead of rounds up — due-minute ordinal difference yields required ceiling to scheduled minute boundary.
  - `[low]` `[patch]` Bar idle timeout test did not verify restored button — added assertion that cancel label returns after overlay timeout.
  - `[medium]` `[defer]` Separate base alert due during postponed interval may be skipped — pre-existing overlapping-occurrence policy outside this feature; track as follow-up.
  - `[false]` `[reject]` Repeated touch can replay cancellation — release latch consumes the contact until release; existing lifecycle tests plus new cancel coverage confirm one transition.
  - `[false]` `[reject]` Upcoming-event restoration lacks integration assertion — App does not yet populate event rows in this path; ClockView restores normal event drawing when pending label clears.
  - `[low]` `[patch]` Malformed touch coordinates may throw during hit testing — coordinates now convert inside guarded error handling; added malformed-coordinate regression.

## Design Notes

The clock view stays selected while pending so the cancel control remains glanceable through long configured delays. Existing surface menu may still open; its normal timeout returns to the clock. Whole-minute display is based on the due minute key: an alert due at 07:50 displays `1m` throughout 07:49 and re-alerts at 07:50.

## Verification

**Commands:**
- `uv run pytest tests/test_alert_app.py tests/test_clock_view.py tests/test_alert_scheduler.py` — 75 passed.
- `git diff --check` — passed.
- `graphify update .` — completed.

## Auto Run Result

Status: done

Summary: Implemented pending postponed-alert cancel control and countdown. Approved control uses amber fill and near-black text in clock bottom band; tapping clears persisted postponement before sounding the same occurrence. Button hides while Bar/Settings cover Clock and returns after overlay timeout.

Files changed:

- `src/alert/runtime.py`, `src/alert/scheduler.py`, `src/app.py` — cancellation, due-time handling, touch latching, and minute calculation.
- `src/ui/clock_view.py`, `src/ui/compositor.py` — countdown button rendering, event-row replacement, and redraw behavior.
- `tests/test_alert_app.py`, `tests/test_clock_view.py` — lifecycle, persistence, touch, redraw, boundary, and malformed-coordinate coverage.
- `_bmad-output/planning-artifacts/alert-clock/prds/prd.md`, `ux-designs/EXPERIENCE.md`, `ux-designs/DESIGN.md` — product and UX decisions.
- `_bmad-output/party-mode/memories/installed/.memlog.md` — approved control decision.
- `graphify-out/` — refreshed generated code graph.
- `_bmad-output/implementation-artifacts/alert-clock/spec-cancel-pending-postponed-alert-from-clock.md` — implementation, review, and verification record.

Review findings: 4 low findings patched; 5 rejected as false; 1 maybe-false and 1 medium finding deferred. Follow-up review recommendation: false.

Verification:

- `uv run pytest tests/test_alert_app.py tests/test_clock_view.py tests/test_alert_scheduler.py` — 75 passed.
- `git diff --check` — passed.
- `graphify update .` — passed.
- Device behavior validation — not performed; TFT legibility, touch calibration, and audible response need on-device verification.

Deployment record (2026-09-23): `uv run --with mpy-cross==1.20.0 tools/deploy.py --port /dev/cu.usbmodem1101` passed memory gate and deployment; Pico reports MicroPython 1.20.0 (`_mpy=4358`), matching `mpy-cross` v6.1 was used, and `src.alert.runtime` imported successfully over `mpremote`. Device was reset after import verification. Cancel-button rendering, physical touch response, and audible behavior remain unverified on hardware.
