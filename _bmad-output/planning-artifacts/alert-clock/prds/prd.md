---
title: Alert Clock
status: draft
created: 2026-09-21
updated: 2026-09-21
---

# PRD: Alert Clock

## 0. Document Purpose

This PRD adds configurable audible alerts to Pi Calendar Clock. It extends [core clock/calendar PRD](../../pico-w-calendar-clock/prds/prd.md), [Wi-Fi/admin configuration PRD](../../wifi-config/prds/prd.md), and [touch UI PRD](../../touch-ui/prds/prd.md). It supersedes core PRD's alarm/buzzer non-goal and wifi-config PRD's no-touch-input non-goal only for active-alert controls. Existing clock/calendar rotation, authenticated Config page, and touch-menu behavior remain unless this document explicitly changes them.

## 1. Vision

Minh can use Device as desk alarm clock without reflashing firmware. From authenticated web settings, he manages up to ten alerts, choosing each alert's time, enabled state, and one-time or weekday-repeat schedule. When an alert is due, audible buzzer and full-screen TFT state demand attention. Two large touch controls make outcome clear: Stop ends current occurrence; Postpone silences it and raises same occurrence again after configured delay. Normal clock/calendar display returns when occurrence ends.

## 2. Target User and Journeys

Same single owner, Minh, as core PRD §2.

- **UJ-1 (create weekday alert).** Minh opens authenticated Config page on phone, creates 07:00 alert, selects Monday through Friday, and saves. Device persists alert. At 07:00 on weekday, buzzer sounds and TFT replaces normal rotation with alert screen.
- **UJ-2 (postpone active alert).** Alert sounds while Minh is not ready. He taps Postpone 10 min on TFT. Buzzer stops immediately; current scheduled occurrence is deferred once for ten minutes. At new due time, alert screen and buzzer return unless he stops it.
- **UJ-3 (stop active alert).** Minh taps Stop on TFT. Buzzer stops immediately, alert screen exits, and weekly alert remains scheduled for future matching days.
- **UJ-4 (avoid unwanted alert).** Minh disables or deletes an alert from Config page. Disabled/deleted alert does not fire, including after reboot.

## 3. Glossary

Extends sibling PRDs' terms Device, Time source, Config page, Rotation, and Settings view.

- **Alert** — persisted configuration containing time, enabled state, and recurrence rule.
- **Occurrence** — one due instance of an Alert, including a postponed instance; distinct from base Alert configuration.
- **Active alert** — current Occurrence whose buzzer/alarm screen is active.
- **Postpone** — user action that stops current buzzer and schedules its same Occurrence once after configured delay. Also called snooze in comparable clock products; UI wording is `Postpone`.
- **Postpone delay** — global configurable minutes applied to a Postpone action; default 10 minutes.
- **Auto-stop** — safety timeout ending an unanswered Active alert after five minutes.

## 4. Features

### 4.1 Alert Settings in Config Page

**Description:** Existing authenticated Config page gains Alert settings. Configuration stays browser-based; Device screen is reserved for active-alert response.

#### FR-1: Manage up to ten alerts

Authenticated admin can view, add, edit, enable/disable, and delete up to ten Alerts. List identifies each Alert's time, enabled state, and recurrence in a readable form.

**Consequences (testable):**
- Add control is unavailable with clear explanation when ten stored Alerts exist.
- Save validates required fields and rejects invalid time/recurrence without changing stored configuration.
- Delete requires explicit confirmation because it removes persisted configuration. [ASSUMPTION: confirmation is browser-side, not Device-side.]
- Saved change takes effect without reboot and survives reboot/power loss.
- Unauthenticated caller cannot read or modify Alert settings; existing Config-page authentication/session behavior applies.

#### FR-2: Configure timing and recurrence

Each Alert has local wall-clock time, enabled state, and recurrence: one-time or selected weekdays.

**Consequences (testable):**
- User can select no recurrence for one-time Alert, or any subset of Monday–Sunday for repeating Alert.
- One-time Alert disables itself after its Occurrence ends, whether stopped, postponed then stopped, or auto-stopped. [ASSUMPTION: one-time Alert remains visible but disabled rather than being deleted.]
- Repeating Alert remains enabled after each Occurrence ends.
- Time calculations use Device Time source. Alert scheduler continues using retained local time while Time source is unsynced; TFT preserves existing unsynced indication where screen layout permits. [ASSUMPTION: alerts must work offline rather than requiring Wi-Fi at due time.]

#### FR-3: Configure global postpone delay

Authenticated admin can set global Postpone delay in whole minutes; default is 10 minutes.

**Consequences (testable):**
- Saved delay applies to next and later Postpone actions without reboot.
- Config page shows current delay and unit clearly.
- Value is constrained to safe supported range of 1–60 minutes. [ASSUMPTION: range; user selected 10-minute default.]

### 4.2 Due-Alert Detection and Audible Output

**Description:** Scheduler detects enabled Alert Occurrences and drives installed HW-508 buzzer module with direct GPIO pulses without blocking display, web service, Wi-Fi recovery, or touch processing.

#### FR-4: Raise due Alert

When current local time matches enabled Alert's time and recurrence, Device begins one Active alert.

**Consequences (testable):**
- Due Alert replaces normal Rotation/Settings screen and starts audible buzzer within one second of its due local minute.
- Scheduler keys each due Alert by local date, hour, and minute; repeated loop iterations and a backward time adjustment do not raise duplicate Occurrences for same key.
- Due detection works across date/month/year rollovers and selected weekday boundaries.
- Alerts due in same local minute, or becoming due while another Active alert is unanswered, join one combined occurrence. Active screen identifies combined-alert count; Stop and Auto-stop resolve every joined Occurrence, while Postpone defers every joined Occurrence to one shared due time. [ASSUMPTION: collision policy; avoids overlapping buzzer state.]
- If alert configuration changes while an Active alert exists, current Occurrence completes under state already raised; later Occurrences use saved configuration. [ASSUMPTION: no mid-alert cancellation by web edit.]

#### FR-5: Sound buzzer safely

During Active alert, Device produces repeating `tut` pulses: GP15 is high for 180 ms, then low for 220 ms. Cadence repeats until user action or Auto-stop. Buzzer stops immediately when Active alert ends.

**Consequences (testable):**
- Installed HW-508 board's controlling physical silkscreen is `S`, `VCC`, `GND`; it is connected as documented in `docs/hardware_configuration.md`: `S` to GP15, `VCC` to 3V3(OUT), and `GND` to common ground.
- Flashed-device bench test confirms audible output from direct 3.3 V GP15 pulses at 180 ms high / 220 ms low. Current measurement, polarity confirmation, and safe-drive validation remain required before production deployment.
- Buzzer control must not block cooperative main loop; touch controls, web requests, and timekeeping stay responsive during sound cadence.
- Hardware/control failure emits secret-free serial diagnostic and shows bounded TFT failure state; Device remains usable and can retry future Alerts.
- Alert sound must be tested on target Pico W hardware; host tests only verify scheduler/control decisions, not loudness or electrical behavior.

### 4.3 Active-Alert TFT Experience

**Description:** Active alert owns full TFT attention. It presents clear alert state plus two touch targets, without relying on physical button.

#### FR-6: Render and prioritize active-alert screen

While Active alert exists, Device renders full-screen alert state with clear label/time and large separately tappable `Stop` and `Postpone <N> min` controls. It pauses normal Rotation and preempts existing Bar/Settings views.

**Consequences (testable):**
- Stop and Postpone controls remain visible and readable on 320×240 landscape TFT while buzzer sounds; each touch target is at least 120×70 logical pixels. [ASSUMPTION: leaves space for title/time while avoiding accidental taps.]
- Active-alert screen does not idle-timeout into Rotation or Settings before occurrence ends.
- Touch input is debounced enough that one tap produces one resolved action; duplicate/replayed taps after resolution do nothing.
- Screen resumes normal Rotation after alert resolves, using existing touch UI's state rules. [ASSUMPTION: it resumes last normal view rather than forcing Clock view.]

#### FR-7: Stop current occurrence

Tapping Stop immediately silences buzzer and ends current Occurrence.

**Consequences (testable):**
- Buzzer stops and Device exits Active-alert screen within one second of valid Stop touch.
- Stop does not disable/delete repeating base Alert.
- Stop resolves every Alert in combined occurrence under FR-4 collision policy.

#### FR-8: Postpone current occurrence

Tapping Postpone immediately silences buzzer, leaves base Alert configuration unchanged, and schedules current Occurrence once at action time plus configured Postpone delay.

**Consequences (testable):**
- Device displays confirmation of deferred due time before returning to normal Rotation. [ASSUMPTION: brief confirmation is enough; no persistent postpone indicator.]
- Postponed Occurrence re-enters Active alert flow using same Stop, Postpone, and Auto-stop behavior.
- Postpone can be used repeatedly; each use replaces pending postponed due time with new action time plus delay. [ASSUMPTION: unlimited repeats until base occurrence resolves.]
- Pending postponed Occurrence survives reboot/power loss if its due time has not passed. [ASSUMPTION: persistence prevents missed user action after a short outage.]

#### FR-9: Auto-stop unanswered alert

If Active alert is unanswered for five minutes, Device stops buzzer and ends current Occurrence.

**Consequences (testable):**
- Auto-stop uses five minutes of elapsed monotonic runtime from Active-alert start, including a postponed re-alert; NTP/time correction cannot shorten or extend it.
- Auto-stop leaves repeating base Alert enabled; it disables completed one-time Alert per FR-2.
- Device returns to normal Rotation after Auto-stop.

## 5. Non-Goals

- No physical button; Stop/Postpone use existing resistive TFT touch only.
- No phone push notification, cloud account, remote alert trigger, voice assistant, or multi-user alert ownership.
- No alarm labels, custom sound selection, volume control, melodies, vibration, or per-alert postpone duration in this release.
- No GPIO assignment, wiring change, or claim that a generic HW-508 pinout is safe without inspecting actual module and recording confirmed wiring in `docs/hardware_configuration.md`.
- No modification to core clock/calendar content beyond temporary Active-alert screen.

## 6. MVP Scope

### 6.1 In Scope

- Up to ten persisted browser-configured Alerts.
- One-time and selected-weekday recurrence.
- Global 10-minute default configurable Postpone delay.
- HW-508 buzzer with direct-GPIO repeating 180 ms-on / 220 ms-off `tut` cadence, five-minute Auto-stop, and target-device validation.
- Full-screen TFT Active-alert state with touch Stop/Postpone.
- Host-testable pure alert scheduling logic.

### 6.2 Out of Scope

- Features in §5 Non-Goals.
- Hardware-specific GPIO/control design until physical module identity, pinout, power requirements, and safe drive method are verified.

## 7. Non-Functional Requirements

- **NFR-1 Reliability:** Alert scheduler, recurrence/date math, collision policy, postpone calculation, and state transitions stay pure CPython-compatible logic; no `machine`, `network`, or `ntptime` imports.
- **NFR-2 Responsiveness:** Buzzer operation must be cooperative/non-blocking; alert controls and web server remain responsive.
- **NFR-3 Persistence:** Alert data and pending Postpone state survive normal restart/power loss without corrupting existing Wi-Fi/admin settings.
- **NFR-4 Safety:** Pico GPIO receives no 5 V. Buzzer module shares ground. GP15 direct 3.3 V pulse audibility is bench-verified; current, polarity, and safe-drive validation remain required before deployment. No hardware pin assignments change until physical wiring and hardware docs change together.
- **NFR-5 Recovery:** Buzzer or render failure leaves loop recoverable, produces secret-free phase/code over serial, and supports later alert attempts.
- **NFR-6 Test evidence:** Host pytest and flashed-device evidence are recorded separately. Device evidence covers buzzer operation, controls, Auto-stop, Postpone, simultaneous due alerts, reboot persistence, and Wi-Fi-unavailable operation.

## 8. Success Metrics

Hobby-scale; no formal telemetry.

- **SM-1:** Minh configures weekday alert and sees it persist through reboot without source edits or reflashing.
- **SM-2:** On an active alert, Minh can silence or postpone it with one visible TFT action.
- **SM-3:** Device continues displaying/responding during buzzer cadence and returns to normal state after Stop, Postpone, or Auto-stop.

**Counter-metrics:** Alert handling must not degrade normal clock/calendar rotation, web administration, Wi-Fi setup/recovery, or touch-menu use.

## 9. Open Questions / Phase Blockers

1. **Hardware verification — phase blocker:** Installed board silkscreen and direct-GPIO audibility are confirmed: `S`/`VCC`/`GND`, GP15 high for 180 ms then low for 220 ms. Before deployment, measure current, confirm control polarity, and confirm direct GP15 drive is electrically safe. Physical wiring is recorded in `docs/hardware_configuration.md`.
2. **Collision policy — non-blocking assumption:** This draft resolves same-time Alerts as one combined occurrence. Confirm if separate sequential acknowledgment is wanted.
3. **Postpone range — non-blocking assumption:** Global range assumed 1–60 minutes. Confirm if different bounds needed.
4. **Power-loss handling — non-blocking assumption:** Pending postponed Occurrence persists through reboot; overdue occurrence on restart is skipped rather than immediately sounding. Confirm desired behavior.

## 10. Assumptions Index

- FR-1 — browser delete requires confirmation.
- FR-2 — one-time Alert remains stored but disables after completion; offline alerts remain operational.
- FR-3 — supported Postpone range is 1–60 minutes.
- FR-4 — same-minute and during-active Alerts combine; web edits do not cancel active occurrence.
- FR-5 — direct GP15 180 ms high / 220 ms low repeating `tut` cadence, confirmed audible on flashed target; electrical deployment validation remains open.
- FR-6 — 120×70 logical-pixel touch targets; normal display resumes from last normal view.
- FR-8 — brief deferred-time confirmation; repeated Postpone allowed; pending postpone persists.
- §9 — overdue pending postpone after restart is skipped.
