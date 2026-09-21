# Reconcile — Alert Clock PRD

## Extracted UX decisions

- Active occurrence preempts every normal TFT surface with full-screen alert state; normal rotation resumes after Stop or Auto-stop.
- Screen must show clear alert label/time, combined-alert count when collisions join, plus separate `Stop` and `Postpone <N> min` controls.
- Both controls remain readable on 320×240 landscape TFT; each target at least 120×70 logical px. One valid tap resolves once; duplicate/replayed taps do nothing.
- `Stop` silences and resolves current occurrence immediately; repeating base alerts remain enabled.
- `Postpone` silences immediately, defers same occurrence by global configured delay (default 10 min), then shows deferred due time briefly before returning to rotation. Repeated Postpone replaces pending due time.
- Unanswered alert auto-stops after five monotonic minutes. One-time alert then disables; repeating alert remains enabled.
- Audible cadence: 500 ms sound / 500 ms silence, target 2 kHz PWM pending hardware bench validation. Buzzer/render failures must expose bounded TFT failure state and secret-free serial diagnostic while loop stays usable.
- Browser Config page, protected by existing auth, manages up to ten alerts and global Postpone delay (assumed 1–60 min). Device touch is active-alert response only.
- Unsynced time must preserve existing indication where alert layout permits; alerts operate from retained local time offline.

## Conflicts / gaps

- PRD requires existing resistive touch for active alerts, while base core UX describes unwired/unused touch and bans all input. Alert PRD explicitly supersedes this only for active-alert controls; wiring and touch availability must be verified by architecture/implementation.
- `clear label/time` has no exact labels, hierarchy, placement, typography, or formatting. Combined count copy unspecified.
- Deferred-time confirmation has no duration, surface, wording, or interruption rule.
- Buzzer/render failure state lacks content, recovery action, and visual priority.
- Collision behavior is an assumption: same-minute/during-active alerts combine; Stop/Auto-stop resolve all; Postpone defers all to shared due time. Needs confirmation if separate acknowledgement is desired.
- Postpone limits, unlimited repeat behavior, persisted pending postpone, skipped overdue postponed occurrence after restart, and resume-last-normal-view behavior remain assumptions.
- Hardware verification is phase blocker: physical pin order, safe 3.3 V drive, loudness, wiring, and actual touchscreen wiring are unresolved. No GPIO or wiring decision belongs in UX spines.

## Omitted by source boundary

- PRD non-goals exclude labels, custom sounds, volume, melodies, vibration, per-alert postpone duration, phone/cloud/voice controls, and multi-user ownership.
- Addendum compares Google/Apple alarm products only as research; it does not import their UI patterns or behavior.
- Browser Config-page layout, validation presentation, session UX, and delete-confirmation design need existing Wi-Fi-config UX source or separate capture; this PRD supplies requirements only.
