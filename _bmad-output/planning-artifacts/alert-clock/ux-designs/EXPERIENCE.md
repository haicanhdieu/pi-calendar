---
name: Alert Clock Buzzer
status: in-progress
sources:
  - ../prds/prd.md
  - ../prds/addendum.md
  - ../../pico-w-calendar-clock/ux-designs/DESIGN.md
  - ../../pico-w-calendar-clock/ux-designs/EXPERIENCE.md
  - ../../wifi-config/ux-designs/DESIGN.md
  - ../../wifi-config/ux-designs/EXPERIENCE.md
updated: 2026-09-21
---

# Alert Clock Buzzer — Experience Spine

## Foundation

Single-owner Pi Calendar Clock extension. Local active-alert response runs on
320×240 landscape ILI9341 TFT with existing resistive touch; web configuration
remains authenticated Config-page behavior. `DESIGN.md` owns visual identity;
this spine owns behavior. Base clock/calendar rotation and touch-menu behavior
continue unless active alert preempts them.

Alert logic uses Device local Time source, including retained local time while
unsynced. It must function without Wi-Fi at due time. Pure schedule/state
logic stays CPython-compatible; hardware drive, rendering, touch, web service,
and Wi-Fi layers remain cooperative and responsive.

Hardware is unresolved phase blocker: actual Maker's Electronics passive
HW-508 module, header order, 3.3 V current/drive safety, loudness, and driver
need require physical bench verification before GPIO assignment or deployment.

## Information Architecture

| Surface | Reached from | Purpose |
|---|---|---|
| Authenticated Alert settings | Existing Config page | View, add, edit, enable/disable, delete up to ten persisted Alerts; set global Postpone delay |
| Normal Clock / Calendar / touch-menu view | Boot, Rotation, normal navigation | Existing time/date experience; paused by active alert |
| Active-alert TFT | Due or postponed Occurrence | Audible, full-screen attention state; local Stop or Postpone resolution |
| Deferred confirmation | Valid Postpone | Confirm next due time, then return to normal Rotation |
| Bounded alert failure state | Buzzer or render failure | Secret-free recoverable user-facing state; later Alerts can retry |

Active alert has priority over every normal TFT view. No local Device surface
exists for managing base Alerts. Configuration access controls and session
behavior inherit existing authenticated Config page.

Alert Settings is one inline `ALERTS` section in Config page: list → expanded
editor → saved list, plus global Postpone delay. It creates no browser page,
navigation hierarchy, or local-TFT management surface.

→ Composition references: [Alert Settings](mockups/key-alert-settings.html),
[Active Alert TFT](mockups/key-active-alert.html). Spine wins on conflict.

## Voice and Tone

Microcopy is terse, explicit, and action-first. Brand posture lives in
`DESIGN.md.Brand & Style`.

| Do | Don't |
|---|---|
| `ALERT` | `Wake up!!!` |
| `STOP` | `Dismiss` |
| `POSTPONE 10 MIN` | `Snooze` |
| Explicit deferred due time | Icon-only or ambiguous confirmation |
| Clear ten-alert limit explanation | Disabled Add control without explanation |
| Clear required-field / invalid-time / invalid-recurrence feedback | Save failure that changes stored configuration |

Diagnostic phase/codes remain serial-only and secret-free. Exact bounded
user-facing failure wording is unresolved. [ASSUMPTION]

## Component Patterns

Behavioral; visual specs live in `DESIGN.md.Components`.

| Component | Use | Behavioral rules |
|---|---|---|
| Alert list | Authenticated Config page | Shows time, enabled state, readable recurrence for each stored Alert. Add/Edit/Enable/Disable/Delete remain browser actions. Add unavailable with clear explanation at ten stored Alerts. |
| Alert editor | Authenticated Config page | Requires local wall-clock time, enabled state, and recurrence: no selected weekday means one-time; any Monday–Sunday subset repeats. Invalid required fields, time, or recurrence reject save without changing stored configuration. |
| Delete confirmation | Authenticated Config page | Explicit browser-side confirmation before persisted Alert removal. [ASSUMPTION] |
| Postpone-delay field | Authenticated Config page | Whole minutes, clearly labeled; default 10; accepted range 1–60. Saved value applies to next/later Postpone without reboot. [ASSUMPTION: range] |
| Active-alert screen | TFT | Preempts normal views; fixed vertical 25% info / 50% Stop / 25% Postpone bands; holds until resolved. |
| Stop target | TFT | Full-width middle 50% band. Valid tap resolves every joined current Occurrence and silences buzzer/exits screen within one second. Does not disable/delete repeating base Alert. |
| Postpone target | TFT | Full-width bottom 25% band. Valid tap immediately silences buzzer, keeps base Alert unchanged, replaces pending postponed due time with action time + saved global delay, and defers every joined Occurrence to shared due time. |
| Deferred confirmation | TFT | Shows deferred due time before normal Rotation. No persistent postpone indicator. [ASSUMPTION] |

## State Patterns

| State | Surface | Treatment |
|---|---|---|
| No active alert | Normal views | Existing rotation/menu rules continue. Scheduler evaluates enabled alerts against local time. |
| Due enabled Alert | Active-alert TFT | Raise within one second of matching local minute/recurrence; begin non-blocking 500 ms sound / 500 ms silence cadence. Key occurrence by local date/hour/minute to prevent repeated-loop and backward-time duplicate raise. |
| Combined occurrence | Active-alert TFT | Alerts due same minute, or due while active alert unanswered, join one Active alert; explicit combined count shown. Stop and Auto-stop resolve all; Postpone defers all to shared due time. [ASSUMPTION: collision policy] |
| Active / sounding | Active-alert TFT | Buzzer cadence continues; Stop/Postpone remain visible; normal Rotation, Bar, Settings, idle timeout cannot reclaim screen. Web, Wi-Fi recovery, timekeeping, touch remain responsive. |
| Stop | Normal Rotation | Silence immediately; resolve current joined occurrence. Repeating base Alerts stay enabled; completed one-time base Alerts disable but remain stored. [ASSUMPTION: stored disabled one-time Alert] |
| Postponed | Deferred confirmation → Normal Rotation | Silence immediately; show next due time, then return to normal Rotation. Pending postponement persists through reboot if due time has not passed. [ASSUMPTION] |
| Re-alert | Active-alert TFT | At deferred time, re-enter full Active flow including Stop, Postpone, Auto-stop. Repeated Postpone allowed; newest action time + delay replaces prior postponed due time. [ASSUMPTION: unlimited repeats] |
| Auto-stop | Normal Rotation | At five elapsed monotonic minutes since each Active/re-alert start, silence and resolve joined occurrence. NTP/time correction cannot alter timeout. Repeating bases remain enabled; one-time bases disable. |
| Unsynced time | Active-alert TFT + normal views | Preserve existing `UNSYNCED` badge where layout permits; schedule retained local time rather than suppressing alerts. |
| Config changed during active alert | Active-alert TFT | Already-raised occurrence completes under raised state; later occurrences use saved settings. [ASSUMPTION] |
| Restart with pending Postpone | Normal views / scheduler | Persist pending future postponed occurrence. If overdue on restart, skip rather than sound immediately. [ASSUMPTION: power-loss policy] |
| Buzzer or render failure | Bounded failure state | Emit secret-free serial phase/code; leave cooperative loop/AP recoverable; do not silently treat as no alert; later Alerts retry. |

## Interaction Primitives

- **Browser configuration:** authenticated user saves Alert or Postpone-delay
  changes; valid saved changes take effect without reboot and persist across
  restart/power loss. Unauthenticated callers cannot read or modify settings.
- **Touch Stop:** one valid debounced tap resolves current occurrence; duplicate
  or replayed taps after resolution do nothing.
- **Touch Postpone:** one valid debounced tap resolves current sounding phase and
  schedules same occurrence once at action time plus global delay. It may recur
  through later re-alerts.
- **Automatic due detection:** evaluates local date/time and weekday boundary;
  works across date/month/year rollovers.
- **Auto-stop:** automatic five-minute monotonic safety exit, no touch needed.
- **Banned:** physical-button path, local alert editing, remote trigger,
  notifications, labels, custom sounds/volume/melodies/vibration, per-alert
  delay, and any interaction that suggests Stop/Postpone resolution happened
  when it did not.

## Accessibility Floor

- Fixed vertical bands make `STOP` a 50%-height full-width target and
  `POSTPONE <N> MIN` a 25%-height full-width target on 320×240 landscape TFT.
  Both remain visible/readable while sounding.
- Two actions are distinguishable through separate position and exact text,
  never color alone. `UNSYNCED` remains labeled text, not red-only signal.
- Alert demands attention through audible cadence plus visible `ALERT` state;
  design must not assume sound alone is noticed.
- Preserve inherited high-contrast, distance-legible treatment. Validate actual
  TFT legibility and touch calibration on device; host tests cannot prove either.
- Motion is unnecessary: normal-to-alert and alert-to-normal changes are plain
  cuts; no animation delays access to controls.

## Key Flows

### Flow 1 — Weekday alert (Minh, early morning, desk alarm)

1. Minh opens authenticated Config page on phone and creates enabled 07:00
   Alert with Monday–Friday recurrence.
2. Valid save persists immediately; Device needs no reboot.
3. At 07:00 on weekday, local Device time matches Alert. Active-alert TFT
   replaces whatever normal view was present and buzzer starts cadence within
   one second.
4. Minh sees `ALERT`, time, Stop, and `POSTPONE 10 MIN` together.
5. **Climax:** one tap on `STOP` silences buzzer and returns Device to normal
   Rotation within one second. Weekday Alert remains ready for next match.

### Flow 2 — Postpone while not ready (Minh, morning)

1. Active alert sounds while Minh needs more time.
2. He taps `POSTPONE 10 MIN` once.
3. Buzzer stops immediately; Device schedules same occurrence for now + ten
   minutes and shows explicit deferred due time.
4. Device returns to normal Rotation.
5. At deferred time, full Active alert returns unless Minh resolves it.
6. **Climax:** he taps `STOP`; buzzer stops, current occurrence ends, future
   weekday schedule remains intact.

### Flow 3 — Avoid unwanted alert (Minh, phone, before weekend)

1. Minh opens authenticated Config page.
2. He disables an Alert or chooses Delete and accepts explicit confirmation.
3. Save persists without reboot.
4. **Climax:** after Device restart/power loss, disabled/deleted Alert does not
   fire; no stale active schedule survives configuration change.

### Flow 4 — Two alerts collide (Minh, morning)

1. Two enabled Alerts become due in same local minute, or second becomes due
   while first is unanswered.
2. Device combines them into one Active alert and explicitly identifies joined
   count.
3. Minh taps `POSTPONE 10 MIN`.
4. **Climax:** one action silences one buzzer state and defers both joined
   occurrences to same due time. [ASSUMPTION: combined-occurrence policy]

### Flow 5 — Unanswered alert (Minh, away from desk)

1. Alert becomes active and cadence begins.
2. No valid touch action occurs for five elapsed monotonic minutes.
3. Device Auto-stops buzzer and exits Active-alert TFT.
4. **Climax:** normal Rotation returns without a frozen screen or continuing
   sound; repeating Alert remains enabled, one-time Alert disables. 
