---
title: Pi Calendar Clock
status: draft
created: 2026-09-05
updated: 2026-09-05
---

# PRD: Pi Calendar Clock
*Working title — confirm.*

## 0. Document Purpose

This PRD scopes v1 of a Raspberry Pi Pico W-based desk clock that displays the current time and Gregorian calendar date on a physical screen. It builds on the existing [Project Folder Structure Convention](../architecture/project-structure.md), which already establishes the MicroPython/CPython split, module layout, and the deferred status of the Vietnamese lunar calendar. This PRD does not repeat that structure — it defines what the device does, for whom, and what's in/out of v1.

## 1. Vision

Pi Calendar Clock is a small hardware device — a Raspberry Pi Pico W driving a TFT display — that shows the current time and date on your desk, always on, no phone or laptop required. It syncs time over Wi-Fi via NTP so it's never wrong, and shows enough calendar context (day, date, month) to be useful as a glance-and-go clock. It's a personal hardware project: the point is having a dedicated, single-purpose object that does one thing well, rather than another notification-laden screen.

v1 deliberately stays small: clock + calendar display only. Alarm functionality and lunar calendar support are real future directions but are explicitly deferred so v1 can ship and be used.

## 2. Target User

### 2.1 Jobs To Be Done

- As the builder, I want a dedicated clock on my desk so I don't have to unlock a phone to check the time or date.
- I want time that's always accurate without manual adjustment (DST, drift).
- I want a build that's simple enough to maintain and extend later (add alarm, add lunar calendar) without a rewrite.

### 2.2 Non-Users (v1)

- Not a smart-home hub, not a notification display, not multi-user — this is a single-owner desk device.

### 2.3 Key User Journeys

- **UJ-1.** Minh glances at his desk, sees current time and today's date on the TFT display, no interaction needed. On boot/reconnect, the device fetches time over Wi-Fi via NTP; if Wi-Fi is unavailable it keeps ticking from its last known time and shows a visible "unsynced" indicator rather than silently drifting wrong. [ASSUMPTION: no user-facing settings/buttons needed for v1 beyond power — confirm if a settings/input flow is wanted.]

## 3. Glossary

- **Device** — the physical Raspberry Pi Pico W + TFT display unit running this firmware.
- **Time source** — the NTP-synced wall-clock time the device trusts; has a synced/unsynced trust state.
- **Clock view** — the display screen showing current time.
- **Calendar view** — the display screen showing current Gregorian date (day of week, day, month, year).
- **Gregorian calendar** — the standard calendar system; v1's only supported calendar system.
- **Lunar calendar** — Vietnamese lunar calendar date; out of scope for v1 (see §6.2).

## 4. Features

### 4.1 Time Sync

**Description:** On boot and periodically thereafter, the Device connects to Wi-Fi and fetches current time via NTP. Realizes UJ-1.

#### FR-1: Wi-Fi NTP time sync

Device can sync its Time source over Wi-Fi via NTP on boot and on a recurring interval.

**Consequences (testable):**
- On successful sync, Time source trust state becomes "synced."
- If Wi-Fi or NTP is unreachable, Device continues running from its last known Time source and trust state becomes "unsynced" rather than crashing or blocking display.
- Device re-attempts sync periodically (e.g. hourly) while unsynced. [ASSUMPTION: hourly retry interval — confirm.]

**Out of Scope:**
- Manual time entry / configuration UI.

### 4.2 Clock Display

**Description:** Device renders current time on its TFT screen continuously. Realizes UJ-1.

#### FR-2: Show current time

Device can render the current time on the Clock view.

**Consequences (testable):**
- Displayed time updates at least once per second (or per minute — [ASSUMPTION: minute-level resolution is enough for a desk clock; confirm if seconds are wanted]).
- When Time source is unsynced, Clock view shows a visible unsynced indicator alongside the (stale) time.

### 4.3 Calendar Display

**Description:** Device renders today's Gregorian date, either alongside the clock or on an adjacent view. Realizes UJ-1.

#### FR-3: Show current date

Device can render today's date (day of week, day, month, year) on the Calendar view, per the Gregorian calendar.

**Consequences (testable):**
- Date rolls over correctly at local midnight, using the synced Time source.
- Date display matches Gregorian calendar rules including leap years.

**Out of Scope:**
- Lunar calendar date (see §6.2, §5).

## 5. Non-Goals (Explicit)

- Not building alarm/buzzer functionality in v1 — deferred to a later phase (see §6.2). [NOTE FOR PM: user's original framing was "alarm/display" — alarm is a real intended direction, just not v1. Revisit once clock+calendar is stable and used daily.]
- Not building Vietnamese lunar calendar support in v1 (architecture already reflects this via deferred `lunar.py`).
- Not a multi-user or networked/remote-controllable device.
- Not building a settings UI or physical input handling in v1 beyond power connect/disconnect.

## 6. MVP Scope

### 6.1 In Scope

- Wi-Fi NTP time sync with synced/unsynced trust state (FR-1).
- Clock view showing current time (FR-2).
- Calendar view showing current Gregorian date (FR-3).
- CPython-testable pure logic for date/time calculations per the existing architecture convention (Gregorian calculations, view state).

### 6.2 Out of Scope for MVP

- Alarm/buzzer feature — deferred to v2. [NOTE FOR PM: emotionally load-bearing per original ask; revisit first.]
- Vietnamese lunar calendar — deferred to v2, module already stubbed as `lunar.py` per architecture doc.
- Physical button/input handling beyond what's needed to power the device.
- Any settings or configuration UI.

## 7. Success Metrics

Success: the device sits on the desk, stays accurate, and Minh actually keeps using it daily instead of reverting to checking a phone — no metric instrumentation planned for a hobby build.

## 8. Open Questions

1. Display resolution/refresh: does Clock view need seconds-level ticking, or is minute-level enough? (affects FR-2)
2. NTP resync interval — hourly assumed, confirm.
3. When is alarm functionality revisited — fixed follow-up or open-ended?
4. Any physical input (buttons) wanted in v1 for view switching, or is clock/calendar view split/toggle automatic or combined on one screen?

## 9. Assumptions Index

- §2.3 — No user-facing settings/buttons needed for v1 beyond power.
- §4.1 FR-1 — Hourly retry interval for unsynced time resync.
- §4.2 FR-2 — Minute-level display resolution is sufficient (vs. seconds).
