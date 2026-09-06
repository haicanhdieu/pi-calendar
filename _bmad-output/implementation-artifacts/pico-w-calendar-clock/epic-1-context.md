# Epic 1 Context: Trusted, Glanceable Desk Clock

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Deliver a always-on Vietnam-local desk clock that syncs over Wi-Fi/NTP, keeps advancing when the network fails, and shows an unmistakable text `UNSYNCED` badge whenever time cannot be trusted—so Minh can glance at correct (or honestly degraded) time and date without interaction.

## Stories

- Story 1.1: Establish the testable time and device foundation
- Story 1.2: Render an immediately legible Clock view
- Story 1.3: Keep the Clock running through time-source failures
- Story 1.4: Prove the nonblocking network boundary on hardware
- Story 1.5: Synchronize Clock time without blocking the display

## Requirements & Constraints

- Sync UTC via Wi-Fi/NTP on boot and on a recurring schedule (v1 default: hourly after success or failure). Success marks trust `synced`; failure/unreachability marks `unsynced` without crashing or freezing the display.
- Clock shows 24-hour local time as `HH:MM` plus secondary `SS`, and a date line `DOW · MON D YYYY`, updating changed glyphs every second. Local values use fixed `Asia/Ho_Chi_Minh` (UTC+07:00, no DST).
- Before any valid time exists: show `--:--` with the unsynced badge; do not enter Calendar. With valid but untrusted time: keep advancing last-known time and show `UNSYNCED`. When synced: no success badge and no reserved badge space.
- Networking must not block rendering. Credentials stay device-local and untracked; missing/invalid secrets yield unsynced operation, not a boot crash.
- Continuous operation: no full 320×240×16-bit framebuffer; no per-second allocation on the steady-state render path; dirty-region redraws only.
- Pure time/view-state logic must run under CPython and MicroPython without `machine`/`network`/`ntptime`/device imports; host verification via `uv run pytest`. On-device claims need user-run flashed-device checks.
- Hardware pins, SPI0 @ 40 MHz, 320×240 landscape, and `MADCTL 0xA8` stay unchanged unless wiring and docs change together. v1 has no buttons, touch, settings UI, or lunar display.
- Legibility at desk distance (~0.5–1 m): high contrast; unsynced trust is conveyed by badge text, not color alone.

## Technical Decisions

- Functional core / imperative shell: `main.py` is composition/fatal boot only; reusable code under `src/`; hardware adapters under `src/device/`.
- Single-threaded App loop is the sole writer of `AppState` (time trust, view, deadlines). Renderers consume immutable snapshots and keep only draw caches.
- Time model: `DateTime` named integer fields; `TimeSnapshot` with `utc`/`local` (`DateTime | None`), `trust: synced | unsynced`, `sync_age_ms: int | None`. App alone reads/writes UTC through `ClockPort` (RTC-backed); never call `ntptime.settime()`.
- Store/sync wall time in UTC; convert to local only at the domain boundary for UI. Schedule all deadlines with `ticks_ms` / `ticks_add` / `ticks_diff`—never wall-clock or raw tick compares.
- Network path (AD-8): isolated worker owns WLAN/DNS/UDP NTP. Capacity-one command and result slots under one lock. App enqueues one `SyncCommand(command_id, deadline_ms)` only while idle; accepts only matching non-expired `SyncResult`; never overwrite results; retry only after consume + idle. Worker never touches RTC, TFT, or `AppState`.
- Prove MicroPython `_thread` mailbox behavior on a flashed Pico W before wiring NTP into production; if unstable, revise AD-8—do not block the App loop.
- Rendering goes through `DisplayPort` (clipped half-open rects, RGB565, stable font IDs; adapter owns SPI/windows/buffers, high-byte-first). Shared status layer draws `UNSYNCED` last at fixed top-right; badge visibility change invalidates the active base view.
- Non-secret defaults (pins, palette, retry, dwell) live as named constants in `src/config.py`; ignore `/secrets.py`; commit only value-free `secrets.example.py`. Preserve deploy-relative `main.py` + `src/` paths.

## UX & Interaction Patterns

- Instrument-panel palette: background `#031406`; primary `#3dff7a`; secondary `#1c6b38`; orange `#ff6b3d` reserved exclusively for the unsynced badge.
- Clock layout (320×240 landscape, centered): ~88px bold tabular `HH:MM`; ~30px secondary `SS` trailer that must not shift HH:MM; ~14px letter-spaced date line below.
- Badge: ~10px all-caps `UNSYNCED`, 3px rounded, fixed top-right; identical treatment whenever trust is unsynced; absent with no placeholder when synced.
- No animation, icons, gradients, seven-segment digits, themes, or extra chromatic accents. Dirty-region glyph updates every second; full redraw only on view entry or badge invalidation.
- Epic 1 boots and stays on Clock; Calendar rotation is Epic 2, but badge and trust semantics must already be shared-compositor ready.

## Cross-Story Dependencies

- 1.1 foundations (pure time model, config, `src/` boundaries, host tests) unlock 1.2–1.5.
- 1.2 Clock renderer and `DisplayPort` must support invalid/unsynced and dirty-second paths before 1.3’s failure-resilient loop is meaningful.
- 1.3 establishes App as sole state writer and tick-based scheduling that 1.5 plugs sync results into.
- 1.4 hardware proof of the worker/mailbox is a hard gate for 1.5 NTP integration; host mailbox tests alone are insufficient.
- Epic 2 (Calendar + auto-rotation) depends on valid local snapshots, trust/badge compositor behavior, and the App loop patterns from this epic; Calendar must not be entered until `TimeSnapshot.local` exists.
