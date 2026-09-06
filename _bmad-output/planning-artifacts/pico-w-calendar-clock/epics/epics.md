---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - ../prds/prd.md
  - ../architecture/ARCHITECTURE-SPINE.md
  - ../architecture/project-structure.md
  - ../architecture/reviews/reconcile-hardware-code.md
  - ../architecture/reviews/reconcile-prd-brief.md
  - ../architecture/reviews/reconcile-ux.md
  - ../architecture/reviews/review-adversarial-compatibility.md
  - ../architecture/reviews/review-good-spine-rubric.md
  - ../architecture/reviews/review-technology-currency.md
  - ../ux-designs/DESIGN.md
  - ../ux-designs/EXPERIENCE.md
  - ../briefs/brief.md
  - ../briefs/addendum.md
  - ../../../../docs/hardware_configuration.md
  - ../../../../docs/pico_w_calendar_clock_handoff.md
---

# Pi Calendar Clock - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Pi Calendar Clock, decomposing the requirements from the PRD, UX design, and architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: The device must synchronize its UTC time source over Wi-Fi using NTP on boot and on a recurring schedule; a successful synchronization marks time as `synced`.

FR2: If Wi-Fi or NTP is unavailable, the device must keep displaying and advancing its last known valid time without blocking or crashing, mark time as `unsynced`, and retry synchronization periodically (hourly is the v1 default).

FR3: The Clock view must render the current Vietnam-local Gregorian time in 24-hour `HH:MM:SS` form and a local date line; changed clock glyphs update every second.

FR4: Both Clock and Calendar views must visibly show the text `UNSYNCED` whenever time trust is `unsynced`, and show no equivalent placeholder or success badge when it is `synced`.

FR5: The Calendar view must render the current Gregorian month as a Monday-first seven-column grid, with correct weekday placement, leap-year/month-length handling, adjacent-month overflow days, and today's date highlighted.

FR6: With no user input in v1, the device must boot to Clock and automatically cut between Clock and Calendar views using configurable, clock-dominant dwell periods (30 seconds Clock and 8 seconds Calendar by default).

FR7: The local date line and today highlight must update at local midnight; if a month changes during Calendar dwell, the new grid is shown on the next Calendar entry rather than changing mid-dwell.

### NonFunctional Requirements

NFR1: All local date/time shown to the user must be derived from stored UTC using fixed `Asia/Ho_Chi_Minh` (UTC+07:00, no DST); wall-clock time must not schedule elapsed work.

NFR2: The display and application loop must remain responsive while networking fails or blocks; network work must not freeze rendering.

NFR3: Continuous operation must use bounded memory: no full 320×240×16-bit framebuffer, no per-second allocation on the steady-state render path, and dirty-region redraws only.

NFR4: Pure calendar, time, and view-state logic must run unchanged under CPython and MicroPython and must not import `machine`, `network`, `ntptime`, or device adapters.

NFR5: Host tests for pure logic and adapter contracts must run with `uv run pytest`; on-device behavior must be verified only by a flashed-device check.

NFR6: The render contract must use clipped half-open pixel rectangles, RGB565 colors, stable font IDs, and high-byte-first display transfer through the adapter.

NFR7: The interface must remain legible at normal desk distance (about 0.5–1 m), use high contrast, and convey degraded time trust with the `UNSYNCED` text rather than color alone.

NFR8: Wi-Fi credentials must remain device-local and untracked; missing or invalid credentials must result in unsynced operation rather than a boot crash.

NFR9: Hardware GPIO assignments, SPI0 at 40 MHz, 320×240 landscape orientation, and `MADCTL 0xA8` must remain unchanged unless physical wiring/documentation changes together.

NFR10: The v1 implementation must have no buttons, touch, remote control, settings UI, alarm, lunar-calendar display, or other input affordance.

### Additional Requirements

- Use the functional-core/imperative-shell layout: `main.py` is composition/fatal boot boundary; reusable code belongs in `src/`; hardware adapters are isolated under `src/device/`.
- The single-threaded App loop is the sole writer of `AppState`, time-trust state, active view, and deadlines; renderers only consume snapshots and keep draw caches.
- Time state must support an invalid-before-first-sync case: render `--:--` plus the unsynced badge and do not enter Calendar until a local time exists.
- Use `ticks_ms`, `ticks_add`, and `ticks_diff` for all deadlines and retry/view scheduling, including wrap-safe comparison; schedule a next NTP attempt after both success and failure.
- Implement NTP through the AD-8 isolated worker: capacity-one command/result slots protected by one lock, matching command IDs, bounded operations, no result overwrite, App-only RTC writes, and stale/expired result discard.
- Do not use `ntptime.settime()`; App writes a successful UTC value through `ClockPort` backed by `machine.RTC` and later reads the advancing RTC.
- Before FR1 implementation, prove the specified MicroPython `_thread` worker/mailbox behavior on a flashed Pico W; if it is unstable, revise AD-8 rather than blocking the App loop.
- Calendar core must expose a stable `MonthGrid` of Monday-first weeks and `DayCell` records with Gregorian date, `in_month`, `is_today`, and an ordered collection of semantic annotations; v1 emits no annotations.
- Rendering must go through one `DisplayPort`; renderers own prior-value caches and invalidate them on view entry, while `UiCompositor` owns the shared badge and draws it last.
- Keep non-secret pins, dimensions, palette, retry interval, and dwell durations as named constants in `src/config.py`; ignore `/secrets.py` and commit only a value-free `secrets.example.py`.
- Preserve deploy-relative paths for `main.py` and `src/`; controller identity, endurance, panel legibility, and network behavior need user-run flashed-device evidence.

### UX Design Requirements

UX-DR1: Implement the fixed 320×240 landscape instrument-panel palette: `#031406` background; `#3dff7a` primary; `#1c6b38` secondary; and reserve `#ff6b3d` exclusively for the unsynced badge.

UX-DR2: Render Clock as a centered, bold, fixed-width/tabular `HH:MM` hero at target 88px, with a 30px secondary `SS` trailer that does not shift the main time block while ticking.

UX-DR3: Render the Clock date line as `DOW · MON D YYYY`, 14px secondary text with letter spacing, and roll it over immediately at local midnight.

UX-DR4: Render Calendar with a 16px uppercase month label, Monday-first weekday header, seven-column grid, 10px/12px frame padding, 2px gaps, and 14px day cells.

UX-DR5: Render today's Calendar cell with a 3px rounded primary fill and background-colored text; render adjacent-month overflow days in secondary green.

UX-DR6: Render the 10px all-caps `UNSYNCED` text as a 3px rounded orange top-right badge identically in both views; it must not reflow other content or reserve space while absent.

UX-DR7: Use a plain-cut Clock-to-Calendar-to-Clock transition only; no animation, touch hint, cursor, focus ring, or other input affordance.

UX-DR8: Preserve glanceability: no gradients, cards, icons, extra chromatic accents, seven-segment font, theme, brightness schedule, or additional information that reduces the specified type sizes.

UX-DR9: Update only changed clock glyph/dirty regions every second to avoid flicker; full-view redraw is allowed only when entering a view or invalidating it for badge changes.

UX-DR10: Validate physical-panel legibility under normal desk lighting and ensure that the text badge—not color alone—communicates the unsynced state.

### FR Coverage Map

FR1: Epic 1 — synchronize the device time at boot and on its recurring schedule.

FR2: Epic 1 — preserve a usable clock and report untrusted time when synchronization fails.

FR3: Epic 1 — present current Vietnam-local time and date in the Clock view.

FR4: Epic 1 — present the shared text-based `UNSYNCED` indicator consistently on both eligible views.

FR5: Epic 2 — present a correct, readable current Gregorian month grid with today highlighted.

FR6: Epic 2 — alternate automatically between the primary Clock and Calendar views using clock-dominant dwell periods.

FR7: Epic 2 — keep displayed date and calendar state correct across local midnight and month rollover.

## Epic List

### Epic 1: Trusted, Glanceable Desk Clock

Minh can rely on an always-visible local clock and date, with an unambiguous indication whenever synchronization is unavailable.

**FRs covered:** FR1, FR2, FR3, FR4

### Epic 2: Automatic Gregorian Calendar Companion

Minh can see a correct, readable current-month calendar without interacting with the device; it rotates predictably from the primary Clock view.

**FRs covered:** FR5, FR6, FR7

## Epic 1: Trusted, Glanceable Desk Clock

Minh can rely on an always-visible local clock and date, with an unambiguous indication whenever synchronization is unavailable.

### Story 1.1: Establish the testable time and device foundation

As Minh,
I want the clock's time rules and device boundaries to be testable before they drive the display,
So that the clock can become trustworthy without tying its core behavior to Pico-only APIs.

**Implements:** NFR4, NFR5, NFR8; architecture AD-1, AD-3, AD-9, AD-10.

**Acceptance Criteria:**

**Given** the repository's existing TFT bring-up code and the approved architecture, **when** the firmware substrate is introduced, **then** `main.py` is only composition/fatal boot handling and reusable code is organized under the approved `src/` boundaries.

**Given** pure time and view-state modules, **when** CPython imports them, **then** they import without `machine`, `network`, `ntptime`, or device-adapter imports, and host tests run with `uv run pytest`.

**Given** a UTC `DateTime`, **when** a pure snapshot is derived, **then** its local value is fixed to UTC+07:00, retains named date/time fields, and provides the synced/unsynced trust and sync-age state defined by the architecture.

**Given** no valid RTC/NTP time exists yet, **when** a snapshot is requested, **then** its date-time and age fields are absent, it is unsynced, and a Calendar entry is not permitted.

**Given** checked-in configuration, **when** time, retry, display, and dwell defaults are needed, **then** they are named constants in `src/config.py`, credentials remain outside it, `/secrets.py` is ignored, and `secrets.example.py` contains no values.

### Story 1.2: Render an immediately legible Clock view

As Minh,
I want a readable Clock view that clearly distinguishes trusted from untrusted time,
So that I can check the local time and date at a glance.

**Implements:** FR3, FR4; NFR3, NFR6, NFR7, NFR9; UX-DR1–UX-DR3, UX-DR6, UX-DR9.

**Acceptance Criteria:**

**Given** a valid local `TimeSnapshot`, **when** Clock renders, **then** it displays centered 24-hour `HH:MM`, a secondary `SS` trailer, and `DOW · MON D YYYY` using the specified 320×240 landscape layout and RGB565 palette.

**Given** sequential one-second snapshots, **when** only seconds change, **then** only changed/dirty clock regions are redrawn, the HH:MM block does not shift, and the steady-state render path makes no recurring allocation.

**Given** an invalid or unsynced snapshot, **when** Clock renders, **then** it shows `--:--` before any usable time exists or the advancing best-known time thereafter, and draws the top-right orange `UNSYNCED` text badge without reflowing content.

**Given** a synced snapshot, **when** Clock renders, **then** no success badge or reserved badge space appears.

**Given** renderer code, **when** it draws the display, **then** it uses only the `DisplayPort` contract with clipped half-open rectangles, stable font IDs, and RGB565 colors; the display adapter alone owns controller windows, SPI handles, and reusable transfer buffers.

### Story 1.3: Keep the Clock running through time-source failures

As Minh,
I want the desk clock to keep advancing and disclose uncertainty when its time source is unavailable,
So that a network outage never leaves me with a frozen or deceptively trusted display.

**Implements:** FR2, FR3, FR4; NFR1, NFR2; architecture AD-2–AD-5.

**Acceptance Criteria:**

**Given** App boot, **when** the loop starts, **then** Clock is the active view, App is the sole writer of `AppState`, and renderers/adapters cannot mutate the active view or time-trust state.

**Given** a valid RTC value, **when** the App derives recurring snapshots, **then** it reads the advancing UTC only through `ClockPort`, converts it locally through pure time logic, and refreshes the Clock at least once per second.

**Given** an expected time-source failure or an invalid credential file, **when** it is reported to App, **then** App marks trust unsynced, continues rendering any valid RTC time, emits concise serial diagnostics, and does not crash or block.

**Given** App deadlines, **when** it schedules redraw, retry, freshness, or view work, **then** it uses `ticks_ms`, `ticks_add`, and `ticks_diff` rather than wall-clock values or raw tick comparisons.

### Story 1.4: Prove the nonblocking network boundary on hardware

As Minh,
I want the proposed network-worker boundary checked on my actual Pico W,
So that time synchronization is built only on a device capability that has evidence behind it.

**Implements:** FR1 prerequisite; NFR2, NFR5; architecture AD-8.

**Acceptance Criteria:**

**Given** the specified capacity-one command and result mailbox prototype, **when** it is flashed to the Pico W, **then** it exercises successful and failed DNS/NTP, result-slot contention, stale/expired results, retry sequencing, soft reset, render continuity, and sustained lock/memory behavior.

**Given** a user-run proof outcome, **when** the prescribed worker protocol is stable, **then** its recorded evidence permits NTP integration; **when** it is unstable, **then** AD-8 is revised and no blocking-App fallback is introduced.

**Given** the host environment, **when** this story is verified, **then** host tests cover the pure mailbox protocol while the artifact explicitly separates those results from the required flashed-device observation.

### Story 1.5: Synchronize Clock time without blocking the display

As Minh,
I want the clock to synchronize at boot and periodically over Wi-Fi,
So that it returns to a trustworthy local time automatically after connectivity is available.

**Implements:** FR1, FR2, FR4; NFR1, NFR2, NFR8; architecture AD-3–AD-5, AD-8, AD-9.

**Acceptance Criteria:**

**Given** Story 1.4's successful hardware proof, **when** App needs a sync attempt, **then** it non-blockingly enqueues one bounded `SyncCommand(command_id, deadline_ms)` only while the worker is idle, and the isolated worker alone owns WLAN, DNS, and UDP NTP operations.

**Given** a terminal worker result, **when** App consumes it, **then** it accepts only the matching, non-expired result; successful UTC is written only by App through `ClockPort` and marks trust synced, while failed, expired, or stale results mark trust unsynced.

**Given** the capacity-one command/result protocol, **when** a slot is occupied, **then** results are never overwritten, retry waits for prior-result consumption and worker-idle state, and saturation is logged as a fatal contract violation.

**Given** a successful or failed attempt, **when** its next deadline is scheduled, **then** the default recurring interval is configurable and is one hour for v1; bundled `ntptime.settime()` is not called.

## Epic 2: Automatic Gregorian Calendar Companion

Minh can see a correct, readable current-month calendar without interacting with the device; it rotates predictably from the primary Clock view.

### Story 2.1: Generate a correct Gregorian month model

As Minh,
I want the device to calculate the current month correctly,
So that the calendar always places dates and today's highlight where I expect.

**Implements:** FR5, FR7; NFR4, NFR5; architecture AD-1, AD-4, AD-6, AD-10.

**Acceptance Criteria:**

**Given** any valid Gregorian local date, **when** the month grid is generated, **then** it returns Monday-first weeks with exactly seven `DayCell` entries per week and correct month boundaries, weekday alignment, and leap-year behavior.

**Given** a `DayCell`, **when** Calendar consumes it, **then** the cell exposes its Gregorian date, `in_month`, `is_today`, and an ordered collection of `CalendarAnnotation(kind, value)` records; v1 emits an empty annotation collection.

**Given** calendar model code, **when** host tests run under CPython, **then** they cover ordinary months, leap-year February, Monday/Sunday boundaries, adjacent-month overflow, and today identification without hardware imports.

**Given** future enrichment providers, **when** they are added later, **then** allowed lowercase-kebab-case annotation kinds and ordering remain owned by `src/calendar/models.py`, while renderers retain formatting ownership.

### Story 2.2: Render the current-month Calendar view

As Minh,
I want a compact, high-contrast monthly calendar with today clearly marked,
So that I can confirm the current date and weekday without a phone.

**Implements:** FR4, FR5; NFR3, NFR6, NFR7; UX-DR1, UX-DR4–UX-DR6, UX-DR8–UX-DR10; architecture AD-6, AD-7, AD-11, AD-12.

**Acceptance Criteria:**

**Given** a valid local snapshot and its `MonthGrid`, **when** Calendar is entered, **then** it renders the current uppercase month/year label, Monday-first weekday header, and seven-column day grid using 10px/12px frame padding and 2px gaps.

**Given** Calendar cells, **when** they render, **then** in-month days use primary green, adjacent-month overflow uses secondary green, and today's cell has the specified 3px rounded primary fill with background-colored text.

**Given** a Calendar view, **when** trust is unsynced, **then** the shared compositor draws the same fixed top-right `UNSYNCED` badge last; a badge visibility change invalidates the active base view so underlying pixels are restored.

**Given** a display transition, **when** Calendar is re-entered, **then** its renderer invalidates its prior-value cache and may redraw the full view, while no full framebuffer is introduced.

### Story 2.3: Rotate views and handle local-date transitions

As Minh,
I want Clock and Calendar to alternate automatically without awkward mid-glance changes,
So that the clock remains primary while the calendar is always available.

**Implements:** FR3, FR5, FR6, FR7; NFR1, NFR4, NFR5, NFR10; UX-DR3, UX-DR7; architecture AD-2, AD-5, AD-12.

**Acceptance Criteria:**

**Given** a valid local time at boot, **when** App starts view scheduling, **then** it begins on Clock, holds it for the configurable 30-second default, cuts to Calendar for the configurable 8-second default, and repeats with no animation or input affordance.

**Given** a local midnight while either view is active, **when** App processes its loop events, **then** it updates the Clock date line and Calendar today highlight immediately using its one defined event order: consume adapter results, derive snapshot, handle date/month rollover, handle view deadline, render base view, render status layer.

**Given** a local month rollover during Calendar dwell, **when** App detects it, **then** it cuts to Clock, resets Clock dwell, and builds the new month grid only on the next Calendar entry.

**Given** no valid local time yet, **when** the Clock dwell expires, **then** App remains in Clock and does not enter Calendar.

**Given** view-state and lifecycle rules, **when** host tests run, **then** they prove wrap-safe deadlines, dwell rotation, invalid-time gating, midnight today refresh, and deferred month-grid refresh without device imports.
