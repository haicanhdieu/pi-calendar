---
stepsCompleted: [1, 2, 3]
inputDocuments:
  - _bmad-output/planning-artifacts/alert-clock/prds/prd.md
  - _bmad-output/planning-artifacts/alert-clock/prds/addendum.md
  - _bmad-output/planning-artifacts/alert-clock/architecture/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/alert-clock/ux-designs/DESIGN.md
  - _bmad-output/planning-artifacts/alert-clock/ux-designs/EXPERIENCE.md
  - _bmad-output/planning-artifacts/alert-clock/ux-designs/mockups/key-active-alert.html
  - _bmad-output/planning-artifacts/alert-clock/ux-designs/mockups/key-alert-settings.html
decisions:
  - Buzzer cadence is 180 ms high / 220 ms low (PRD FR-5, DESIGN, AD-7). The
    "500 ms sound / 500 ms silence" line in EXPERIENCE.md State Patterns is
    stale and must be corrected as part of this feature's work.
---

# Alert Clock - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Alert Clock, decomposing the requirements from the PRD, UX Design, and Architecture requirements into implementable stories.

Alert Clock extends the existing Pi Calendar Clock with configurable, persisted audible alerts. It builds on three shipped features — core clock/calendar, Wi-Fi/admin configuration, and touch UI — and narrowly supersedes the core PRD's alarm/buzzer non-goal and the wifi-config PRD's no-touch-input non-goal, for active-alert controls only.

## Requirements Inventory

### Functional Requirements

FR-1: Manage up to ten alerts. An authenticated admin can view, add, edit, enable/disable, and delete up to ten Alerts from the existing Config page. The list identifies each Alert's time, enabled state, and recurrence in readable form. The Add control becomes unavailable with a clear explanation at ten stored Alerts. Save validates required fields and rejects an invalid time or recurrence without changing stored configuration. Delete requires explicit browser-side confirmation. A saved change takes effect without reboot and survives reboot and power loss. An unauthenticated caller can neither read nor modify Alert settings.

FR-2: Configure timing and recurrence. Each Alert holds a local wall-clock time, an enabled state, and a recurrence that is either one-time or a selected set of weekdays. No selected weekday means one-time; any subset of Monday–Sunday repeats. A one-time Alert disables itself after its Occurrence ends by any path (Stop, Postpone then Stop, or Auto-stop) and remains stored rather than being deleted. A repeating Alert stays enabled after each Occurrence. Time calculations use the Device Time source, and the scheduler keeps using retained local time while the Time source is unsynced.

FR-3: Configure global postpone delay. An authenticated admin can set a single global Postpone delay in whole minutes, constrained to 1–60, defaulting to 10. A saved delay applies to the next and later Postpone actions without reboot. The Config page shows the current delay and its unit clearly.

FR-4: Raise due Alert. When the current local time matches an enabled Alert's time and recurrence, the Device begins one Active alert. The due Alert replaces the normal Rotation or Settings screen and starts the buzzer within one second of its due local minute. The scheduler keys each due Alert by local date, hour, and minute, so repeated loop iterations and a backward time adjustment raise no duplicate Occurrence. Due detection works across date, month, and year rollovers and across selected weekday boundaries. Alerts due in the same local minute, or becoming due while another Active alert is unanswered, join one combined occurrence. Configuration changed during an Active alert affects only later Occurrences.

FR-5: Sound buzzer safely. During an Active alert the Device produces repeating `tut` pulses on GP15: high for 180 ms, then low for 220 ms, repeating until a user action or Auto-stop, and stopping immediately when the Active alert ends. The installed HW-508 board's silkscreen is `S`, `VCC`, `GND`, wired as recorded in `docs/hardware_configuration.md`. Buzzer control must not block the cooperative main loop: touch controls, web requests, and timekeeping stay responsive during the sound cadence. A hardware or control failure emits a secret-free serial diagnostic, shows a bounded TFT failure state, and leaves the Device usable for later Alerts.

FR-6: Render and prioritize active-alert screen. While an Active alert exists the Device renders a full-screen alert state with a clear label and time plus two large, separately tappable controls, `STOP` and `POSTPONE <N> MIN`. It pauses normal Rotation and preempts the existing Bar and Settings views. Each touch target is at least 120×70 logical pixels on the 320×240 landscape TFT. The active-alert screen does not idle-timeout into Rotation or Settings before the occurrence ends. Touch input is debounced so that one tap produces one resolved action and duplicate or replayed taps after resolution do nothing. The screen resumes the normal Rotation after the alert resolves, returning to the last normal view.

FR-7: Stop current occurrence. Tapping `STOP` immediately silences the buzzer and ends the current Occurrence. The buzzer stops and the Device exits the active-alert screen within one second of a valid Stop touch. Stop does not disable or delete a repeating base Alert. Stop resolves every Alert in a combined occurrence.

FR-8: Postpone current occurrence. Tapping `POSTPONE <N> MIN` immediately silences the buzzer, leaves base Alert configuration unchanged, and schedules the current Occurrence once at action time plus the configured Postpone delay. The Device displays an explicit confirmation of the deferred due time before returning to normal Rotation. A postponed Occurrence re-enters the Active alert flow with the same Stop, Postpone, and Auto-stop behavior. Postpone can be used repeatedly, each use replacing the pending postponed due time with the new action time plus delay. A pending postponed Occurrence survives reboot and power loss if its due time has not yet passed.

FR-9: Auto-stop unanswered alert. If an Active alert is unanswered for five minutes, the Device stops the buzzer and ends the current Occurrence. Auto-stop measures five minutes of elapsed monotonic runtime from Active-alert start, including a postponed re-alert, so NTP or time correction can neither shorten nor extend it. Auto-stop leaves a repeating base Alert enabled and disables a completed one-time Alert. The Device returns to normal Rotation afterwards.

### NonFunctional Requirements

NFR-1 Reliability: Alert scheduling, recurrence and date math, collision policy, postpone calculation, and state transitions stay pure CPython-compatible logic, with no `machine`, `network`, or `ntptime` imports.

NFR-2 Responsiveness: Buzzer operation must be cooperative and non-blocking. Alert controls and the web server remain responsive throughout the sound cadence.

NFR-3 Persistence: Alert data and pending Postpone state survive a normal restart and power loss without corrupting existing Wi-Fi and admin settings.

NFR-4 Safety: The Pico GPIO receives no 5 V. The buzzer module shares ground. GP15 direct 3.3 V pulse audibility is bench-verified; measured current, control polarity, and safe-drive validation remain required before deployment. No hardware pin assignment changes unless the physical wiring and the hardware documentation change together.

NFR-5 Recovery: A buzzer or render failure leaves the loop recoverable, produces a secret-free phase and code over serial, and permits later alert attempts.

NFR-6 Test evidence: Host pytest evidence and flashed-device evidence are recorded separately under `test-artifacts/alert-clock/`. Device evidence covers buzzer operation, controls, Auto-stop, Postpone, simultaneous due alerts, reboot persistence, and Wi-Fi-unavailable operation.

### Additional Requirements

No greenfield starter template applies. Alert Clock is a feature addition to an existing MicroPython codebase whose structure, ports, and settings boundary already exist.

- **AD-1 One combined active occurrence.** Due alerts in the same local minute, or due while an alert is active, join one occurrence held in `AppState.alert_state`. Stop and Auto-stop resolve every joined alert; Postpone defers every joined alert to one shared due time.
- **AD-2 Persist postponed occurrence, skip overdue on restart.** Persist the pending postponed occurrence atomically. On boot, restore it only when its local due instant is still in the future; discard an overdue pending occurrence without ringing.
- **AD-3 Configuration commits govern future occurrences.** An active or postponed occurrence captures its member alert identities at raise time and completes through Stop, Postpone, or Auto-stop. After a successful commit the web shell emits one canonical `alert_config_committed` event carrying a validated snapshot, which `App` applies at the next loop boundary. Terminal one-time disable re-reads the current canonical configuration and is conditional on the alert id still existing, so a delete wins and no stale occurrence can recreate an alert.
- **AD-4 One versioned alert settings record.** `SettingsStore` remains the sole persistence boundary. It migrates a valid `settings_version: 1` record to an alert-capable next record version before accepting alert fields, preserving Wi-Fi and admin values; unsupported records retain existing quarantine behavior. The committed record owns `alerts`, `postpone_delay_minutes`, and the pending postponed occurrence. Each alert has a stable lowercase string id, local `hour` and `minute`, `enabled`, and a weekday set where `[]` means one-time, Monday is index `0`, and the maximum is ten alerts.
- **AD-5 Split civil due detection from elapsed deadlines.** The pure scheduler keys base due detection by `(alert_id, local_date, hour, minute)` and records each raised key for the current runtime. It evaluates only when `TimeSnapshot.local` exists and never retrofires a missed base minute after boot. Local Device time drives recurrence and postponed due instants only. `App` uses wrap-safe monotonic ticks (`ticks_add` / `ticks_diff`) for the five-minute Auto-stop, the postponed-confirmation dwell, and the `tut` cadence.
- **AD-6 Alert surface exclusively owns attention and resolution.** `active-alert` is an App-owned exclusive surface evaluated before the inherited `touch_state.next_surface`. Normal Bar and Settings hit testing, rendering, and deadlines do not run while an alert is active. Pure alert hit testing maps one debounced edge to `stop` or `postpone`; duplicate edges after resolution are ignored. Postpone puts `App` in a bounded monotonic confirmation state, after which every terminal path enters Rotation and rearms normal view dwell.
- **AD-7 Buzzer is a bounded adapter, not scheduler state.** Pure alert logic emits desired sound state only. Main composition injects `BUZZER_SIGNAL_PIN=15`, `BUZZER_HIGH_MS=180`, `BUZZER_LOW_MS=220`, and active-high polarity into one device `BuzzerPort`; no other layer owns GPIO literals. Port construction drives output low before exposure. `App` resolves Stop, Postpone, Auto-stop, and alert failure before its one bounded `tick(now, sounding)` call each loop; a terminal transition calls idempotent `silence()` in the same step and cannot reassert high. On sound start or re-alert the port drives high immediately, then uses wrap-safe phase deadlines for the repeating cadence; a late tick resynchronizes from `now` without replaying missed edges. Init, drive-high, drive-low, and silence return named secret-free results; a failed drive marks output unknown, attempts one best-effort low, and requires fresh low-first initialization before a later retry.
- **AD-8 Explicit, recoverable alert failures.** Buzzer and alert-render adapters return named secret-free result codes. `App` logs `alert_fail <phase> <code>`, enters a bounded alert failure presentation, silences known buzzer output, and continues the cooperative loop; later occurrences retry normal activation.
- **Inherited invariants.** From `pico-w-calendar-clock`: pure core, App as single state writer, monotonic timing, bounded rendering, host/device parity, DisplayPort. From `wifi-config`: cooperative web ownership, sole settings persistence, bounded authenticated HTTP, session auth, explicit device proof. From `touch-ui`: polled TouchPort, SPI ownership, pure surface state, suspended dwell, fixed loop insertion point.
- **Structural seed.** `src/alert/` (pure domain), `src/app.py` (sole live-state writer), `src/ui/alert_view.py`, `src/device/buzzer_port.py`, `src/device/settings_store.py`, `src/device/web/`.
- **Deferred, tracked outside these epics.** Buzzer current draw, control polarity, and whether GP15 needs a driver or buffer, all required before production deployment. The `wifi-config` parent spine's version-1 settings statement must be updated before implementation so shared persistence authority covers the versioned alert-record migration.
- **Documentation correction.** `EXPERIENCE.md` State Patterns still states a `500 ms sound / 500 ms silence` cadence. The governing value is 180 ms high / 220 ms low, and that line must be corrected so the PRD, DESIGN, EXPERIENCE, and architecture spine agree.
- **Stack.** Raspberry Pi Pico W / RP2040 on stock MicroPython 1.29.0. No custom firmware, frozen modules, or UF2 builds.

### UX Design Requirements

UX-DR1: Active-alert screen layout. Render the full 320×240 landscape frame as three fixed vertical bands: the top 25% for the `ALERT` headline, the occurrence time, an optional joined count, and the `UNSYNCED` badge; the middle 50% as one full-width `STOP` target; the bottom 25% as one full-width `POSTPONE <N> MIN` target. The screen replaces, and is not overlaid on, Rotation, Bar, and Settings content.

UX-DR2: Active-alert typographic hierarchy. The `ALERT` headline is distance-legible; the occurrence time uses the largest treatment the fit permits with tabular numerals; support text and action labels use the smaller support and action-label treatments. All labels stay as text — never icons or abbreviated glyphs.

UX-DR3: Exact device microcopy. Use `ALERT`, `STOP`, and `POSTPONE <N> MIN`, all uppercase, where `<N>` is the saved global whole-minute delay. Never use `Snooze` or `Dismiss` on any device surface. State a combined count as explicit words such as `2 ALERTS`, never a bare number.

UX-DR4: Active-alert color discipline. Use the inherited base palette only: near-black canvas, green for the current focal information (headline and occurrence time), amber for supporting state (combined count, deferred-time confirmation, and control labels where hierarchy permits). Red stays exclusive to the `UNSYNCED` badge and must never signal alert urgency, Stop, Postpone, failure, or decoration.

UX-DR5: `UNSYNCED` badge during active alert. Preserve the inherited fixed top-right badge while an alert is active, where layout permits. It must not reflow the alert hierarchy, and it keeps its existing red background with the badge corner radius and no alert-specific alternate state.

UX-DR6: Deferred confirmation state. After a valid Postpone, briefly replace the top information band with a text-only confirmation naming the explicit deferred due time, then return to normal Rotation. It requires no acknowledgement, must be readable within its dwell, and leaves no persistent postpone indicator.

UX-DR7: Bounded failure presentation. A buzzer or render failure shows a bounded, text-only state carrying no secret and no raw diagnostic, using text hierarchy within the inherited green and amber palette. Exact wording is currently unspecified and must be settled during implementation.

UX-DR8: No new visual language on TFT. Keep the flat, single-layer instrument panel. Action regions are bounded by position, label, and text hierarchy — no cards, shadows, modal overlays, raised button chrome, pills, circles, or icons. Transitions into and out of the alert are plain cuts with no animation.

UX-DR9: Alert Settings section placement. Add one inline `ALERTS` section to the existing flat Config page list, ordered as alert rows, then `Add alert`, then a global `POSTPONE DELAY` control. Create no new browser page, navigation hierarchy, or modal stack, and no local TFT surface for managing base Alerts.

UX-DR10: Alert row and inline editor. Each row shows the local time prominently plus the readable recurrence and enabled state. Editing expands inline within the row into a form offering time, enabled state, weekday selection, Save, and Delete. There are no label, sound, volume, or per-alert postpone controls.

UX-DR11: Weekday selector. Present seven text labels with a visible selected state and multi-select behavior. No selection means one-time. Recurrence renders back to the list in readable form, such as `Monday–Friday` or `One time`.

UX-DR12: Global postpone-delay control. Provide one whole-minute numeric control labeled `Postpone delay (min)`, defaulting to 10, accepting 1–60, placed in its own `POSTPONE` section.

UX-DR13: Browser feedback states. Show a brief success-colored `Alert saved.` confirmation after a valid save, danger-colored inline feedback for a required-field, invalid-time, or invalid-recurrence rejection, and a danger-colored explicit confirmation before a delete. A rejected save must not change stored configuration.

UX-DR14: Ten-alert limit explanation. At ten stored Alerts, render the Add control unavailable together with a clear explanation of why. Never show a disabled control with no explanation.

UX-DR15: Browser and device visual separation. Alert Settings inherits the Wi-Fi Config dark phone-first palette, 20px page padding, 16px field gap, 28px section gap, 10px input and button corners, and 14px row corners. TFT green and amber never enter the browser Settings page, and browser rounded control chrome never transfers to the TFT.

UX-DR16: Accessibility floor. The two actions must be distinguishable by position and exact text, never by color alone. The alert must combine audible cadence with a visible `ALERT` state and must not assume sound alone is noticed. Preserve the inherited high-contrast, distance-legible treatment; validate actual TFT legibility and touch calibration on the device, since host tests can prove neither.

### FR Coverage Map

FR-1: Epic 1 - Alert list, add, edit, enable/disable, delete, ten-alert limit, authentication boundary.
FR-2: Epic 1 - Alert time, enabled state, one-time versus weekday recurrence, one-time terminal disable.
FR-3: Epic 1 - Global postpone delay in whole minutes, range 1-60, default 10.
FR-4: Epic 2 - Due detection keyed by local date, hour and minute; collision combine; config-commit boundary.
FR-5: Epic 2 - `BuzzerPort` 180 ms / 220 ms cadence, non-blocking tick, hardware validation, failure recovery.
FR-6: Epic 2 - Exclusive active-alert surface, band layout, debounced touch, Rotation resume.
FR-7: Epic 2 - Stop resolves every joined alert, same-step silence, repeating base alert stays enabled.
FR-8: Epic 2 - Postpone defers every joined alert to a shared due time, deferred confirmation, reboot-surviving pending state.
FR-9: Epic 2 - Five-minute monotonic auto-stop, immune to NTP correction.

All nine functional requirements are mapped. No requirement is left uncovered.

## Epic List

### Epic 1: Browser-Managed Alert Configuration

Minh manages up to ten alerts and the global postpone delay from the authenticated Config page on his phone. Each alert carries a local time, an enabled state, and either one-time or weekday recurrence. A valid save takes effect without reboot and survives power loss without disturbing existing Wi-Fi or admin settings.

**FRs covered:** FR-1, FR-2, FR-3
**NFRs addressed:** NFR-1 (pure domain), NFR-3 (persistence)
**Core files:** `src/alert/` (records, validation, recurrence), `src/device/settings_store.py` (AD-4 migration), `src/device/web/`
**Standalone:** Yes. A complete, testable configuration surface that delivers UJ-4 outright. It requires nothing from Epic 2 to function.
**Implementation notes:** AD-4 record migration from `settings_version: 1` is the principal risk and must preserve Wi-Fi and admin values. Two pre-implementation documentation corrections land as the first story, because AD-4 depends on them: update the `wifi-config` parent spine's version-1 settings statement so shared persistence authority covers the versioned alert-record migration, and correct the stale `500 ms sound / 500 ms silence` line in `EXPERIENCE.md`.

### Epic 2: Audible Alert Occurrence and Resolution

A configured alert actually wakes Minh. At the due local minute the Device preempts normal Rotation with a full-screen alert state and sounds the buzzer. One tap on `STOP` ends the occurrence; one tap on `POSTPONE <N> MIN` defers it and survives a reboot. An unanswered alert auto-stops after five monotonic minutes. A buzzer or render failure stays bounded and recoverable.

**FRs covered:** FR-4, FR-5, FR-6, FR-7, FR-8, FR-9
**NFRs addressed:** NFR-2 (non-blocking), NFR-4 (electrical safety), NFR-5 (recovery), NFR-6 (device evidence)
**Core files:** `src/alert/` (scheduler, collisions, transitions), `src/app.py` (sole live-state writer), `src/ui/alert_view.py`, `src/device/buzzer_port.py`, `src/device/settings_store.py` (pending postpone)
**Standalone:** Yes. It builds on Epic 1 and requires nothing after it. It delivers UJ-1, UJ-2, and UJ-3.
**Implementation notes:** Ringing and on-screen resolution are one epic because AD-6 and AD-7 tie them into a single state machine: `App` must resolve Stop, Postpone, Auto-stop, and alert failure before its one bounded `BuzzerPort.tick(now, sounding)` call each loop, and a terminal transition must call idempotent `silence()` in the same step. Splitting them would divide that state machine across two epics and force a throwaway render. Hardware electrical validation under NFR-4 (measured current, control polarity, safe direct GP15 drive) is a deployment gate rather than a code gate and is sequenced as its own story.

## Epic 1: Browser-Managed Alert Configuration

Minh manages up to ten alerts and the global postpone delay from the authenticated Config page on his phone, with every change persisted through the single versioned settings record and applied without a reboot.

### Story 1.1: View stored alerts on the Config page

As the device owner,
I want to see my stored alerts listed in the authenticated Config page,
So that I know what the Device will do before I change anything.

**Acceptance Criteria:**

**Given** a Device holding a valid `settings_version: 1` record with Wi-Fi and admin values and no alert fields
**When** `SettingsStore` loads that record
**Then** it migrates the record to the alert-capable next version, adding an empty `alerts` list and `postpone_delay_minutes` of 10
**And** every existing Wi-Fi and admin value is preserved byte-for-byte in the migrated record
**And** the migration is committed atomically, so an interrupted write leaves either the old or the new record intact and never a partial one

**Given** a Device holding a record whose version is unsupported
**When** `SettingsStore` loads it
**Then** the existing quarantine behaviour applies unchanged and no alert fields are invented

**Given** an authenticated session on the Config page and a migrated record holding zero alerts
**When** Minh opens the page
**Then** an `ALERTS` section appears inline in the existing flat settings list, placed above a `POSTPONE` section
**And** the section shows an explicit empty state rather than a bare blank region
**And** no new browser page, navigation level, or modal stack is introduced

**Given** a record holding a 07:00 alert repeating Monday through Friday and enabled, plus a 09:30 one-time alert that is disabled
**When** Minh opens the Config page
**Then** each alert renders as one row showing its local time prominently plus its readable recurrence and enabled state, such as `Monday–Friday · On` and `One time · Off`
**And** recurrence renders in words, never as a raw weekday index list
**And** the rows use the inherited Wi-Fi Config dark palette, 14px row corners, 20px page padding, and 28px section gap, with no TFT green or amber anywhere on the page

**Given** an unauthenticated caller
**When** it requests the Config page or any alert route
**Then** the existing authentication and session behaviour rejects it
**And** no alert time, recurrence, or enabled state appears in the response

**Given** the planning artifacts as they stand before implementation
**When** this story is completed
**Then** the `wifi-config` parent architecture spine's version-1 settings statement is updated so that shared persistence authority covers this versioned alert-record migration
**And** the stale `500 ms sound / 500 ms silence` line in the alert-clock `EXPERIENCE.md` State Patterns table is corrected to 180 ms high and 220 ms low, so the PRD, DESIGN, EXPERIENCE, and architecture spine agree

### Story 1.2: Add an alert with a time and recurrence

As the device owner,
I want to add an alert by choosing a time and either one-time or weekday recurrence,
So that the Device can wake me when I need it to.

**Acceptance Criteria:**

**Given** an authenticated Config page showing fewer than ten alerts
**When** Minh activates `Add alert`
**Then** an editor expands inline within the list offering a local wall-clock time, an enabled state, a weekday selection, Save, and Delete
**And** the editor presents no label, sound, volume, or per-alert postpone control

**Given** the inline editor is open
**When** Minh inspects the weekday selection
**Then** seven weekday labels are shown as text with a visible selected state and multi-select behaviour
**And** selecting no weekday means the alert is one-time
**And** selecting any subset of Monday through Sunday makes the alert repeat on those days

**Given** a valid time of 07:00, an enabled state, and Monday through Friday selected
**When** Minh saves
**Then** the alert is appended to the record with a stable lowercase string id, integer `hour` and `minute`, `enabled` true, and a weekday set using Monday as index `0`
**And** the whole record is validated before a single atomic commit
**And** a brief success-coloured `Alert saved.` confirmation appears
**And** the new alert appears in the list with readable recurrence
**And** the saved change is in effect without a reboot

**Given** a save attempt with a missing required field, an out-of-range time, or a malformed recurrence
**When** Minh saves
**Then** the save is rejected with danger-coloured inline feedback naming what is wrong
**And** the stored configuration is unchanged, so reloading the page shows the prior state

**Given** a record already holding ten alerts
**When** Minh opens the Config page
**Then** the `Add alert` control is unavailable
**And** a clear explanation states that the ten-alert limit is reached
**And** no path through the browser or the route itself can commit an eleventh alert

**Given** a saved alert and a Device restart or power loss
**When** the Device boots
**Then** the alert is still present with its time, enabled state, and recurrence intact
**And** existing Wi-Fi and admin settings are uncorrupted

### Story 1.3: Edit an alert and toggle its enabled state

As the device owner,
I want to change an existing alert's time or recurrence and switch it on or off,
So that I can adjust my schedule without deleting and re-creating alerts.

**Acceptance Criteria:**

**Given** an authenticated Config page listing a stored alert
**When** Minh opens that row for editing
**Then** the editor expands inline in place, pre-filled with the alert's current time, enabled state, and weekday selection
**And** no other row's editor is affected

**Given** an open editor on an alert whose time is 07:00
**When** Minh changes the time to 06:30 and saves
**Then** the stored alert keeps its existing id and its recurrence, with only the time changed
**And** the list row reflects 06:30
**And** the change is in effect without a reboot and survives restart

**Given** an open editor on an alert repeating Monday through Friday
**When** Minh clears every weekday and saves
**Then** the alert becomes one-time
**And** the row renders `One time`

**Given** an enabled alert
**When** Minh disables it and saves
**Then** the stored alert's `enabled` becomes false while its time and recurrence are retained
**And** the row shows the disabled state
**And** the alert remains stored and countable against the ten-alert limit

**Given** an edit that fails validation
**When** Minh saves
**Then** the save is rejected with inline feedback and the stored alert is unchanged

### Story 1.4: Delete an alert with explicit confirmation

As the device owner,
I want to remove an alert I no longer want, with a confirmation step,
So that I free a slot without deleting the wrong one by accident.

**Acceptance Criteria:**

**Given** an authenticated Config page listing a stored alert
**When** Minh chooses Delete on that alert
**Then** an explicit browser-side confirmation is presented using the danger colour only
**And** nothing is removed until the confirmation is accepted

**Given** the delete confirmation is presented
**When** Minh declines it
**Then** the alert remains stored and unchanged

**Given** the delete confirmation is presented
**When** Minh accepts it
**Then** that alert is removed from the record in one atomic commit
**And** the remaining alerts keep their ids and values
**And** the list no longer shows the deleted alert
**And** the deletion survives restart and power loss

**Given** a record that held ten alerts with the `Add alert` control unavailable
**When** Minh deletes one alert
**Then** `Add alert` becomes available again and the limit explanation disappears

### Story 1.5: Set the global postpone delay

As the device owner,
I want to set how many minutes a postpone defers an alert,
So that the deferral matches how much extra time I actually need.

**Acceptance Criteria:**

**Given** a migrated record that has never had a postpone delay set
**When** Minh opens the Config page
**Then** the `POSTPONE` section shows one whole-minute control labelled `Postpone delay (min)` with a value of 10
**And** the unit is visible in the label rather than implied

**Given** the postpone-delay control
**When** Minh enters 15 and saves
**Then** `postpone_delay_minutes` is committed as 15 in the same single record
**And** a brief success-coloured confirmation appears
**And** the value is in effect without a reboot and survives restart

**Given** the postpone-delay control
**When** Minh enters 0, 61, a fraction, or a non-numeric value and saves
**Then** the save is rejected with danger-coloured inline feedback naming the accepted range of 1 to 60 whole minutes
**And** the stored delay is unchanged

**Given** a stored delay of 15
**When** any alert-related route or page reads the delay
**Then** it reads the single committed value from the record rather than a separate file or a duplicated constant

## Epic 2: Audible Alert Occurrence and Resolution

A configured alert wakes Minh: at the due local minute the Device preempts normal Rotation with a full-screen alert state and sounds the buzzer, and one visible touch action stops or postpones it, with a five-minute safety exit if no one answers.

### Story 2.1: Sound a bounded `tut` cadence through the buzzer port

As the device owner,
I want the Device to drive the installed buzzer in a safe, bounded, non-blocking cadence,
So that an alert can actually be heard without freezing the clock, the web server, or touch.

**Acceptance Criteria:**

**Given** the main composition root
**When** it constructs the device `BuzzerPort`
**Then** it injects `BUZZER_SIGNAL_PIN=15`, `BUZZER_HIGH_MS=180`, `BUZZER_LOW_MS=220`, and active-high polarity
**And** no other layer in the codebase contains a GPIO pin number or a cadence literal
**And** `src/alert/` imports no `machine`, `network`, or `ntptime` module

**Given** a newly constructed `BuzzerPort`
**When** construction completes
**Then** the output has been driven low before the port is exposed to any caller
**And** the init result is a named, secret-free value

**Given** an idle port
**When** `tick(now, sounding=True)` is called for the first time
**Then** the output is driven high immediately in that same call rather than waiting for a phase deadline
**And** the next phase deadline is 180 ms after `now`

**Given** a port that has been sounding for 180 ms
**When** `tick` is called at or after the high-phase deadline with `sounding=True`
**Then** the output is driven low and the next deadline is 220 ms later
**And** the cycle repeats indefinitely while `sounding` stays true

**Given** a port mid-cadence
**When** a tick arrives late, after several phase boundaries have already passed
**Then** the port resynchronizes its phase from `now` and drives at most one edge
**And** it does not replay the missed edges

**Given** a sounding port
**When** `silence()` is called
**Then** the output goes low and stays low
**And** calling `silence()` again is harmless and changes nothing
**And** a subsequent `tick(now, sounding=False)` cannot reassert high

**Given** the monotonic tick counter is near its wraparound point
**When** phase deadlines are computed and compared
**Then** `ticks_add` and `ticks_diff` are used, so the cadence is correct across the wrap

**Given** a drive call that fails at the hardware layer
**When** the port handles the failure
**Then** it returns a named secret-free result identifying the phase and code
**And** it marks its output state unknown
**And** it makes one best-effort attempt to drive low
**And** it refuses a later sound request until fresh low-first initialization has run

**Given** the physical Device flashed with this port
**When** the bench validation runs
**Then** measured current draw at GP15 is recorded
**And** control polarity is confirmed against the observed audible output
**And** a judgement is recorded on whether direct 3.3 V GP15 drive is electrically safe or a transistor or buffer stage is required
**And** the Pico GPIO is confirmed never exposed to 5 V and the module shares common ground
**And** `docs/hardware_configuration.md` is updated only if the physical wiring itself changed
**And** the evidence is filed under `test-artifacts/alert-clock/`, separate from host pytest output

### Story 2.2: A due alert takes over the screen, sounds, and auto-stops

As the device owner,
I want a configured alert to seize the display and sound at its due minute, and to give up on its own after five minutes,
So that it wakes me and can never ring forever if I am not there.

**Acceptance Criteria:**

**Given** an enabled alert at 07:00 repeating Monday through Friday and a Device whose local time reaches 07:00 on a Wednesday
**When** the main loop next evaluates the scheduler
**Then** one active occurrence is raised within one second of the due local minute
**And** the buzzer begins its 180 ms high, 220 ms low cadence
**And** normal Rotation is paused

**Given** the scheduler is evaluating due alerts
**When** it computes due state
**Then** it keys each raised alert by `(alert_id, local_date, hour, minute)` and records that key for the current runtime
**And** repeated loop iterations within the same minute raise no second occurrence
**And** a backward clock adjustment that revisits the same minute raises no second occurrence
**And** it evaluates only when `TimeSnapshot.local` exists
**And** it never retrofires a base minute that was missed while the Device was off

**Given** alerts configured across a month end, a year end, and a Sunday-to-Monday boundary
**When** local time crosses each boundary
**Then** due detection fires correctly in each case, with Monday treated as weekday index `0`

**Given** a disabled alert whose time matches the current local minute
**When** the scheduler evaluates
**Then** no occurrence is raised

**Given** a Time source that is unsynced but holds retained local time
**When** an alert's due minute arrives
**Then** the occurrence is raised from retained local time rather than suppressed
**And** the `UNSYNCED` badge is preserved in its fixed top-right position on the alert screen without reflowing the alert hierarchy

**Given** an active occurrence
**When** the active-alert screen renders on the 320×240 landscape TFT
**Then** it occupies the full frame in three fixed vertical bands: the top 25% for the `ALERT` headline and the occurrence time, the middle 50% as one full-width `STOP` region, and the bottom 25% as one full-width `POSTPONE <N> MIN` region
**And** `<N>` is the saved global postpone delay in whole minutes
**And** the labels are exactly `ALERT`, `STOP`, and `POSTPONE <N> MIN` in uppercase, with no `Snooze` or `Dismiss` wording anywhere
**And** the occurrence time uses tabular numerals and the largest treatment the fit permits
**And** only the inherited palette is used: near-black canvas, green for the headline and occurrence time, amber for supporting text, and red reserved exclusively for the `UNSYNCED` badge
**And** the screen is flat, with no card, shadow, overlay, raised chrome, pill, circle, or icon, and the transition into it is a plain cut with no animation

**Given** an active occurrence
**When** the loop evaluates surfaces
**Then** `active-alert` is evaluated before the inherited `touch_state.next_surface`, so Rotation, Bar, and Settings neither render nor claim the screen
**And** normal view dwell and idle timeouts cannot reclaim the screen before the occurrence ends

**Given** an active occurrence and a main loop under load
**When** the buzzer sounds
**Then** the web server still answers requests, timekeeping still advances, and Wi-Fi recovery still runs
**And** `App` calls `BuzzerPort.tick(now, sounding)` exactly once per loop pass, and that call is bounded

**Given** an active occurrence that no one answers
**When** five minutes of elapsed monotonic runtime have passed since the occurrence was raised
**Then** the buzzer is silenced and the occurrence ends
**And** the Device returns to normal Rotation
**And** the repeating base alert remains enabled for future matching days

**Given** an active occurrence and an NTP correction that shifts local time forward or backward during it
**When** the auto-stop deadline is evaluated
**Then** the deadline is unchanged, because it is measured with `ticks_add` and `ticks_diff` from the raise instant, not from civil time

**Given** a one-time alert whose occurrence ends by auto-stop
**When** the terminal transition runs
**Then** it re-reads the current canonical configuration and disables that alert only if its id still exists
**And** the alert remains stored rather than being deleted

### Story 2.3: Stop an active alert with one tap

As the device owner,
I want one tap on `STOP` to silence the alert and give me my clock back,
So that I can end it immediately without waiting out the safety timeout.

**Acceptance Criteria:**

**Given** an active, sounding occurrence
**When** a valid debounced touch lands in the middle 50% `STOP` band
**Then** the buzzer is silenced and the Device exits the active-alert screen within one second
**And** normal Rotation resumes at the last normal view rather than forcing the Clock view
**And** normal view dwell is rearmed

**Given** `App` is processing the Stop transition
**When** that loop pass executes
**Then** Stop is resolved before the single `BuzzerPort.tick(now, sounding)` call
**And** the idempotent `silence()` runs in that same step
**And** the cadence cannot reassert high after the terminal transition

**Given** an active occurrence raised from a repeating base alert
**When** Stop resolves it
**Then** the base alert remains enabled and is neither disabled nor deleted
**And** it fires again on its next matching day

**Given** an active occurrence raised from a one-time base alert
**When** Stop resolves it
**Then** the terminal transition re-reads the current canonical configuration and disables that alert only if its id still exists
**And** the alert remains stored

**Given** an occurrence that has just been resolved by Stop
**When** further touch edges arrive from the same physical press, from bounce, or from a replayed event
**Then** they are ignored and produce no second action
**And** exactly one resolution is recorded

**Given** a touch that lands outside both action bands
**When** the hit test runs
**Then** no action is produced and the occurrence stays active and sounding

**Given** the pure alert hit test
**When** it is exercised by host tests
**Then** it maps one debounced edge to exactly `stop` or `postpone` using only geometry and state, with no device import

### Story 2.4: Postpone an active alert and see its new due time

As the device owner,
I want one tap on `POSTPONE` to silence the alert now and bring it back shortly,
So that I get a few more minutes without losing the alert entirely.

**Acceptance Criteria:**

**Given** an active, sounding occurrence and a saved global postpone delay of 10 minutes
**When** a valid debounced touch lands in the bottom 25% `POSTPONE 10 MIN` band
**Then** the buzzer is silenced immediately in the same loop step as the transition
**And** the occurrence is scheduled once at the touch instant plus 10 minutes
**And** the base alert's time, enabled state, and recurrence are unchanged

**Given** a postpone has just been accepted
**When** the Device presents its confirmation
**Then** a text-only confirmation naming the explicit deferred due time replaces the top information band
**And** it requires no acknowledgement
**And** it is held for a bounded monotonic dwell long enough to read, after which normal Rotation resumes
**And** it never rebuilds the normal screen while the buzzer still needs resolution
**And** no persistent postpone indicator remains on the normal views

**Given** a pending postponed occurrence
**When** its deferred due instant arrives
**Then** the full active-alert flow re-enters, with the same screen, cadence, `STOP`, and `POSTPONE` behaviour
**And** its five-minute auto-stop deadline is measured fresh from the re-alert instant

**Given** a re-alerted occurrence
**When** Minh taps `POSTPONE` again
**Then** the pending deferred due time is replaced by the new touch instant plus the saved delay
**And** repeated postponing is permitted with no imposed limit until the occurrence is stopped or auto-stopped

**Given** a saved global postpone delay that is changed from 10 to 15 while no alert is active
**When** the next postpone is taken
**Then** it defers by 15 minutes
**And** the action label reads `POSTPONE 15 MIN`

**Given** the postpone due-time calculation
**When** host tests exercise it
**Then** it is pure logic over local civil time with no device import
**And** it is correct across an hour, date, month, and year rollover

### Story 2.5: A pending postpone survives a reboot

As the device owner,
I want a postponed alert to still come back after a brief power cut,
So that a short outage does not silently cancel the alert I deliberately deferred.

**Acceptance Criteria:**

**Given** a postpone is accepted
**When** the pending occurrence is recorded
**Then** it is written into the same single versioned settings record, atomically, alongside `alerts` and `postpone_delay_minutes`
**And** existing Wi-Fi and admin values are preserved
**And** it captures the member alert identities of the occurrence, not just a bare timestamp

**Given** a Device holding a pending postponed occurrence whose deferred due instant is still in the future
**When** the Device reboots and restores state
**Then** the pending occurrence is restored
**And** it raises normally at its deferred due instant with the full active-alert flow

**Given** a Device holding a pending postponed occurrence whose deferred due instant has already passed while the Device was off
**When** the Device reboots
**Then** the overdue pending occurrence is discarded without sounding
**And** the discard is committed so it cannot be restored again on a later boot
**And** the base alerts themselves are untouched and still fire on future matches

**Given** a pending postponed occurrence that is then resolved by Stop or by auto-stop
**When** the terminal transition runs
**Then** the pending record is cleared in the same commit
**And** a later reboot restores no stale pending occurrence

**Given** a pending postponed occurrence naming an alert id that has since been deleted from the Config page
**When** the Device restores or resolves it
**Then** the missing id is tolerated without error
**And** the delete wins, so no deleted alert is recreated

### Story 2.6: Alerts that collide join one occurrence

As the device owner,
I want two alerts that come due together to ring as one alert with one pair of controls,
So that I do not have to dismiss the same noise twice.

**Acceptance Criteria:**

**Given** two enabled alerts due in the same local minute
**When** the scheduler evaluates
**Then** exactly one active occurrence is raised holding both alert identities
**And** exactly one buzzer cadence runs

**Given** an unanswered active occurrence
**When** a second enabled alert becomes due
**Then** that alert joins the existing occurrence rather than raising a second one
**And** the buzzer cadence continues without restarting or doubling
**And** the existing five-minute auto-stop deadline is not extended by the join

**Given** an occurrence holding two or more alerts
**When** the active-alert screen renders
**Then** it shows an explicit combined count in words, such as `2 ALERTS`, in the supporting amber tier
**And** the count updates if a further alert joins
**And** an occurrence holding exactly one alert shows no count at all

**Given** a combined occurrence
**When** Stop resolves it
**Then** every joined alert is resolved
**And** every joined repeating base alert stays enabled, while every joined one-time base alert is disabled but remains stored

**Given** a combined occurrence
**When** auto-stop resolves it
**Then** every joined alert is resolved under the same rules as Stop

**Given** a combined occurrence
**When** Postpone defers it
**Then** every joined alert is deferred to one shared due time
**And** the re-alert raises them again as one combined occurrence with its count intact

### Story 2.7: Configuration changes never disrupt an alert already ringing

As the device owner,
I want a save I make on my phone while an alert is ringing to apply from the next alert onward,
So that editing settings can never leave the buzzer stuck or the screen inconsistent.

**Acceptance Criteria:**

**Given** an active occurrence that captured its member alert identities at raise time
**When** an authenticated save commits an edit, a disable, or a delete affecting one of those alerts
**Then** the active occurrence completes under the state already raised
**And** Stop, Postpone, and auto-stop continue to behave exactly as before the save
**And** the buzzer is never left sounding by the save

**Given** a successful settings commit
**When** the web or coordinator shell finishes it
**Then** it emits exactly one canonical `alert_config_committed` event carrying the validated snapshot
**And** `App` applies that snapshot at the next loop boundary, as the sole writer of live alert state
**And** no web handler mutates live alert state directly

**Given** a newly applied configuration snapshot
**When** the scheduler next evaluates due alerts
**Then** it uses the new configuration for all later due detection

**Given** an active occurrence raised from a one-time alert that is deleted from the Config page while that occurrence is still ringing
**When** the occurrence later reaches a terminal transition
**Then** the terminal one-time disable re-reads the current canonical configuration, finds the id absent, and writes nothing
**And** the deleted alert is not recreated

**Given** concurrent activity
**When** a web commit and a touch resolution land in the same loop pass
**Then** ordering is deterministic, with resolution handled before the single buzzer tick and the snapshot applied at the loop boundary
**And** no interleaving can produce a sounding buzzer with no active occurrence, or an active occurrence with a silent buzzer

### Story 2.8: A buzzer or render failure stays bounded and recoverable

As the device owner,
I want a hardware or drawing fault to degrade into a visible, recoverable state,
So that one bad alert never takes down my clock, my Wi-Fi setup, or every later alert.

**Acceptance Criteria:**

**Given** a `BuzzerPort` call that fails during init, drive-high, drive-low, or silence
**When** `App` receives the named result
**Then** it logs `alert_fail <phase> <code>` over serial
**And** the log line contains no Wi-Fi password, admin credential, session token, or raw exception payload

**Given** an alert-render adapter call that fails
**When** `App` receives the named result
**Then** it logs `alert_fail <phase> <code>` under the same secret-free rule

**Given** a buzzer or render failure during an active occurrence
**When** `App` handles it
**Then** it silences any known buzzer output
**And** it enters a bounded, text-only failure presentation carrying no secret and no raw diagnostic, using text hierarchy within the inherited green and amber palette, with red still reserved for `UNSYNCED`
**And** the failure state is bounded in time and exits to normal Rotation rather than persisting indefinitely

**Given** a failure has been handled
**When** the main loop continues
**Then** the clock, calendar rotation, web server, Wi-Fi recovery, and touch all keep running cooperatively
**And** the failure is never silently treated as if no alert had been due

**Given** a port whose output was marked unknown by a failed drive
**When** a later alert becomes due
**Then** the port runs fresh low-first initialization before sounding
**And** if that succeeds, the later occurrence activates normally

**Given** the failure paths
**When** host tests exercise them with a fake port
**Then** low-on-init, high-first phase order, timing boundaries, late ticks, same-step terminal silence, and fault recovery are each covered
**And** the pure domain is tested without any device import

### Story 2.9: Prove the whole alert flow on the flashed Device

As the device owner,
I want the complete alert behaviour demonstrated on the real hardware and the evidence recorded,
So that I can trust the desk alarm before I rely on it to wake me.

**Acceptance Criteria:**

**Given** a Pico W flashed with stock MicroPython 1.29.0 and the alert feature, with no custom firmware, frozen module, or bespoke UF2 build
**When** the device evidence run is executed
**Then** every result is filed under `test-artifacts/alert-clock/`, kept separate from host pytest output

**Given** the flashed Device
**When** an alert is configured from a phone browser and reached at its due minute
**Then** audible buzzer output at the 180 ms and 220 ms cadence is captured as evidence
**And** the active-alert screen is photographed, confirming that `ALERT`, the occurrence time, `STOP`, and `POSTPONE <N> MIN` are legible at desk distance
**And** touch calibration is confirmed, so a tap intended for each band lands in that band

**Given** the flashed Device with an active alert
**When** `STOP` is tapped
**Then** evidence records silence and exit to normal Rotation within one second

**Given** the flashed Device with an active alert
**When** `POSTPONE` is tapped
**Then** evidence records immediate silence, the displayed deferred due time, the return to Rotation, and the re-alert at the deferred time

**Given** the flashed Device with an unanswered active alert
**When** five minutes elapse
**Then** evidence records the auto-stop and the return to Rotation

**Given** two alerts configured for the same minute on the flashed Device
**When** they come due
**Then** evidence records one combined occurrence with its explicit count and one resolution

**Given** a pending postponed occurrence on the flashed Device
**When** power is cut and restored before the deferred due time
**Then** evidence records that the occurrence still raises at its deferred time
**And** a second run with power restored after the deferred time records that it is skipped silently

**Given** the flashed Device with Wi-Fi unavailable at the due minute
**When** the alert comes due
**Then** evidence records that it still raises and sounds from retained local time
**And** the `UNSYNCED` badge is visible on the alert screen

**Given** the flashed Device during a sounding alert
**When** the web Config page is requested and the clock is observed
**Then** evidence records that the page still responds and timekeeping still advances, confirming the cadence is non-blocking
