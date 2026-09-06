---
name: Pi Calendar Clock
status: final
updated: 2026-09-05
colors:
  bg: '#031406'
  digit-primary: '#3dff7a'
  digit-secondary: '#1c6b38'
  today-fill: '#3dff7a'
  today-text: '#031406'
  unsynced-bg: '#ff6b3d'
  unsynced-text: '#031406'
typography:
  time:
    family: '-apple-system, "Helvetica Neue", Arial, sans-serif (device: bold sans bitmap font)'
    size: 88px
    weight: 700
    tabular-nums: true
  seconds:
    family: 'same as time, lighter weight/color'
    size: 30px
    weight: 700
  date-line:
    size: 14px
    letter-spacing: 2px
  month-label:
    size: 16px
    weight: 700
    letter-spacing: 2px
  weekday-header:
    size: 11px
    weight: 700
  day-cell:
    size: 14px
    weight: 600
  badge:
    size: 10px
    weight: 700
    letter-spacing: 1px
rounded:
  badge: 3px
  today-cell: 3px
spacing:
  grid-gap: 2px
  frame-padding: 10px 12px
components:
  - clock-digits
  - seconds-trailer
  - date-line
  - month-grid
  - unsynced-badge
---

## Brand & Style

Pi Calendar Clock is a single-purpose desk object, not an app. It has one job — tell Minh the time and date at a glance, from across a desk, without asking for attention. The visual register is **instrument panel**: a dark screen, one glowing hue, no chrome, no decoration. It should feel like a dedicated piece of hardware earning its keep, not a UI squeezed onto a small display.

Everything drawn on the 2.4" ILI9341 (320×240, landscape) answers to one question: is it readable in a half-second glance? If a decision doesn't serve glanceability, it's cut.

## Colors

Deep Forest Mono-green — a single hue on near-black, chosen for a calm, low-glare, "instrument display" feel rather than a bright multi-color gadget look.

- **Background (`#031406`)** — near-black, not pure black, so the phosphor-green never looks like it's floating on a void. Used on both screens, always.
- **Digit Primary (`#3dff7a`)** — the hero color. Used only for the thing the user is looking at *right now*: the HH:MM time, and today's date number in the calendar grid.
- **Digit Secondary (`#1c6b38`)** — a dimmed version of the same hue. Used for supporting information that should read as present but not compete: seconds, the date line under the clock, the weekday header row, and adjacent-month overflow days.
- **Unsynced Accent (`#ff6b3d`)** — the *only* non-green color on the device. Reserved exclusively for the unsynced badge. Its rarity is the point: if the user ever sees orange, something is wrong with the time source.

Avoid: any second chromatic accent, gradients, or full-brightness use of the secondary green (it must read as visibly dimmer than primary, not just a different shade).

## Typography

No embedded font rendering library is assumed beyond what the device driver supports; treat all sizes below as the target render size on a 320×240 canvas, backed by a bold sans bitmap/vector font (not seven-segment — tested and rejected, see Do's and Don'ts).

- **Time** — 88px, bold, tabular numerals so digits don't shift width tick to tick. The single largest element on the device.
- **Seconds** — 30px, same family, rendered in Digit Secondary so it reads as a detail, not a second headline.
- **Date line** (clock view) — 14px, letter-spaced, Digit Secondary.
- **Month label** (calendar view) — 16px, bold, letter-spaced, Digit Primary.
- **Weekday header / day cells** (calendar view) — 11px header (Digit Secondary) / 14px cells (Digit Primary, or Digit Secondary when dimmed for adjacent months).
- **Badge** — 10px, bold, letter-spaced, all-caps ("UNSYNCED").

## Layout & Spacing

Both views are full-bleed on the 320×240 frame — no visible margin/bezel content, since the physical TFT bezel already frames the screen. Content is centered vertically and horizontally on the Clock view. The Calendar view uses a fixed padding of 10px/12px around a 7-column grid with a 2px gap, so the grid reads as a tight table rather than floating cells.

The unsynced badge always docks to the same corner (top-right) on both views — fixed position, never reflowing other content, so its presence/absence is the only thing that changes.

## Elevation & Depth

None. This is a flat, single-layer display — no shadows, no overlays, no cards. Depth is simulated only by a subtle text-shadow glow on the primary green digits, evoking a lit display rather than printed text.

## Shapes

Minimal rounding — 3px on the unsynced badge and the today-cell fill, just enough to soften two small rectangular accents. Everything else is unrounded: the grid, the digits, the frame. This isn't an app with cards; it's a panel with numbers on it.

## Components

- **Clock digits** — `HH:MM` at 88px, Digit Primary, glow text-shadow. The sole focal point of the Clock view.
- **Seconds trailer** — small `SS` immediately right of the minutes, baseline-aligned, Digit Secondary. Ticks every second; must not cause the HH:MM block to shift.
- **Date line** — one line below the time, `DOW · MON D YYYY` format, Digit Secondary, letter-spaced.
- **Month grid** — 7-column grid, Monday-start, weekday header row, day cells; today's cell is solid-filled (`today-fill` background, `today-text` foreground); adjacent-month overflow days render in Digit Secondary.
- **Unsynced badge** — fixed top-right pill, `unsynced-bg`/`unsynced-text`, label "UNSYNCED"; appears on both Clock and Calendar views identically whenever Time source trust state is unsynced; otherwise absent entirely (no placeholder space reserved).

## Do's and Don'ts

- **Do** keep exactly one chromatic accent (orange) reserved for the unsynced state — its rarity is what makes it noticeable.
- **Do** use tabular/fixed-width numerals everywhere digits tick, so nothing visibly jitters.
- **Don't** use seven-segment/LED-style digit rendering — tried during design, produced overlapping ghost-segment artifacts at small render sizes and was dropped in favor of a bold modern sans.
- **Don't** add a second brightness level, dimming schedule, or theme switch in v1 — the hardware has no backlight control and no ambient light sensor; one fixed high-contrast palette is the only option.
- **Don't** introduce any icon set — the badge is text-only, matching the text-only aesthetic of the rest of the device.
