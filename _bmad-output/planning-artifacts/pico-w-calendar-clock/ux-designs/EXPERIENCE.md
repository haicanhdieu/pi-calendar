---
name: Pi Calendar Clock
status: final
sources:
  - "../prds/prd.md"
  - "../architecture/project-structure.md"
  - "docs/hardware_configuration.md"
updated: 2026-09-06
---

# Pi Calendar Clock — Experience Spine

## Foundation

Single embedded device, no UI system: a Raspberry Pi Pico W (RP2040, MicroPython) driving a 2.4" ILI9341 SPI TFT, 320×240, landscape. No touch (touch pins present on the panel but unwired/unused), no physical buttons in v1. The device has no input modality at all — it is a pure output surface. `DESIGN.md` is the visual identity reference; this spine is the behavior.

Single-owner, single-surface-class product: there is no "app" boundary, no navigation stack, no settings screen. The entire experience is two full-screen views that alternate on a timer.

## Information Architecture

| Surface | Reached from | Purpose |
|---|---|---|
| Clock view | Boot (default); auto-rotation | Current time (HH:MM:SS) + today's date line |
| Calendar view | Auto-rotation from Clock view | Current month grid, today highlighted |

No navigation input exists — there is nothing to tap, press, or swipe. The only "IA transition" is the automatic rotation described in Interaction Primitives. Clock view is primary: the device always boots into it and returns to it after each Calendar dwell.

→ Composition reference: `mockups/key-clock.html`, `mockups/key-calendar.html`. Spine wins on conflict.

## Voice and Tone

Microcopy surface area is minimal — this device has almost no text beyond numbers. Brand posture lives in `DESIGN.md.Brand & Style`.

| Do | Don't |
|---|---|
| `UNSYNCED` (badge, all-caps, one word) | "Time sync failed!" / "Error: NTP timeout" |
| `SAT · SEP 5 2026` (date line, terse) | "Saturday, September 5th, 2026" (too long for 320px width) |
| `SEPTEMBER 2026` (month label) | "September '26" or any abbreviation |
| Silence when everything is working | Any "Synced" confirmation badge — absence of the badge *is* the confirmation |

## Component Patterns

Behavioral. Visual specs live in `DESIGN.md.Components`.

| Component | Use | Behavioral rules |
|---|---|---|
| Clock digits | Clock view | Renders `HH:MM` in 24-hour format. Updates on every second tick (redraw only the changed glyphs to avoid visible flicker). |
| Seconds trailer | Clock view | Renders `SS`, ticks every second independent of minute rollover. |
| Date line | Clock view | One line, format `DOW · MON D YYYY`, always local calendar date derived from the current Time source. Rolls over at local midnight. |
| Month grid | Calendar view | Renders the current calendar month only (no month navigation — there is no input to navigate with). Monday-start week, weekday header row. Recomputed on entry to the view (or on date rollover if the device happens to be sitting on this view at midnight). |
| Unsynced badge | Both views | Renders identically on both surfaces whenever Time source trust state is `unsynced`. No badge, no reserved space, when `synced`. |

## State Patterns

| State | Surface | Treatment |
|---|---|---|
| Boot / first sync pending | Clock view | Show best-effort time once any Time source exists (RTC default or prior NTP sync); `UNSYNCED` badge shown until first successful NTP sync completes. |
| Synced | Both | No badge. Digits in Digit Primary. |
| Unsynced (Wi-Fi/NTP unreachable) | Both | `UNSYNCED` badge shown top-right; device keeps ticking forward from its last known time rather than freezing or blanking; FR-1's hourly retry continues silently in the background — no visible retry indicator beyond the badge persisting or clearing. |
| Midnight rollover | Both | Date line and month grid's "today" highlight update immediately at local midnight, whichever view is currently on-screen. |
| Month rollover during Calendar dwell | Calendar view | Grid recomputes for the new month on the *next* rotation into Calendar view, not mid-dwell (avoids the grid changing under the user's eyes). |
| View rotation | Clock ⇄ Calendar | See Interaction Primitives — the only "transition" state on this device. |

## Interaction Primitives

There is no user interaction — v1 has no buttons, no touch, no remote control. The one primitive is **automatic view rotation**:

- Clock view holds for ~30s, then transitions to Calendar view for ~5–10s, then returns to Clock view. Repeats indefinitely.
- Transition itself is a plain cut (no animation) — an animated wipe/fade would be a decorative addition this device doesn't need or have cycles to spare on.
- **Banned:** any interaction affordance implying input exists (no "tap to switch" hint, no cursor, no focus ring) — the device has no input hardware in v1, so nothing should visually suggest otherwise.

## Accessibility Floor

This is a fixed-position physical display with a single, non-configurable viewer (Minh, at his own desk) and no software accessibility APIs (no screen reader, no OS-level settings) — the floor here is entirely about **physical legibility**, not software a11y:

- Contrast: Digit Primary (`#3dff7a`) and Digit Secondary (`#ffb238`) against `#0a0a0a` background must both remain clearly legible under normal desk lighting and from typical desk-viewing distance (~0.5–1m) — verify on the physical panel once built, not only in the HTML mock.
- No color-only signaling: the unsynced state is communicated by badge *text* ("UNSYNCED"), not by a color shift alone, so it doesn't depend on the viewer's color perception.
- Fixed high-contrast palette only (see `DESIGN.md.Do's and Don'ts`) — no reliance on adjustable brightness, since the hardware has none.
- Text sizes (88px time, 14px+ everything else) are chosen for legibility at distance on a 320×240 panel, not for information density — nothing should be added to either view that would force these sizes down.

## Key Flows

### Flow 1 — Glance and go (Minh, desk, mid-afternoon)

1. Minh looks up from his laptop toward the device sitting on his desk. It's mid-rotation on Clock view — no interaction needed, it was already showing.
2. He reads `14:07:32` and the date line `SAT · SEP 5 2026` in under a second. No badge is present, so he trusts it without thinking about it — that's the whole point of the device.
3. **Climax beat:** thirty seconds later, without Minh touching anything, the screen cuts to the September month grid with the 5th filled solid green. He confirms "yeah, Saturday" for a half-second, then looks back at his laptop. He never had to pick up his phone, unlock anything, or wait for an app to load — the information was just *there*, on the object whose only job was to have it ready.
4. The device rotates back to Clock view on its own. Minh's attention is already gone.

### Flow 2 — Wi-Fi drops overnight (Minh, next morning)

1. Overnight, the router restarts and the device's hourly NTP resync fails a few times in a row.
2. Minh walks by in the morning; Clock view shows a time that's drifted slightly, but the `UNSYNCED` badge is visible top-right on both Clock and Calendar views.
3. **Climax beat:** because the badge is unmistakable (the one red thing on an otherwise green-and-amber device) and *present on whichever view happens to be showing*, Minh doesn't need to guess whether the displayed time is trustworthy — he knows at a glance to check his router before trusting the clock, rather than being silently misled by a wrong time with no signal that anything's off.
4. Once Wi-Fi recovers and the next hourly retry succeeds, the badge disappears on its own — no acknowledgment needed from Minh.
