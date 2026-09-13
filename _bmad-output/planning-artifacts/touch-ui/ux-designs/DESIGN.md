---
name: Pi Calendar Clock — Touch UI
status: final
updated: 2026-09-13
extends: ../../pico-w-calendar-clock/ux-designs/DESIGN.md
colors:
  bg: '#0a0a0a'
  digit-primary: '#3dff7a'
  digit-secondary: '#ffb238'
  today-fill: '#3dff7a'
  today-text: '#0a0a0a'
  unsynced-bg: '#ff4d4d'
  unsynced-text: '#0a0a0a'
  bar-panel-bg: '#141414'
  press-flash: '#ffe9b8'
typography:
  settings-status:
    size: 16px
    weight: 700
    letter-spacing: 1px
  settings-guideline:
    size: 13px
    weight: 400
    letter-spacing: 0.5px
  settings-reboot:
    size: 14px
    weight: 700
    letter-spacing: 2px
rounded:
  bar-panel: 0px
  gear-glyph: 0px
spacing:
  bar-height: 36px
  settings-block-gap: 18px
  settings-top-padding: 28px
components:
  - touch-bar
  - gear-icon
  - settings-view
  - reboot-button
---

## Brand & Style

Same instrument-panel register as the base Device (see `extends`): dark screen, green-and-amber glow, no chrome, no decoration, answers only to "is it readable in a half-second glance." The Touch UI adds exactly one new idea to that register — a single interactive surface — and nothing else. It must look like it was always part of the panel, not a UI bolted on top of it.

This spine **amends** one rule from the base DESIGN.md: "Don't introduce any icon set" now reads **"No icon set beyond what Settings needs"** — a single gear glyph, added because Settings needs one scannable, thumb-legible symbol for its one control. No other icons follow from this without a new design decision.

## Colors

Inherits the base palette in full — {colors.bg}, {colors.digit-primary}, {colors.digit-secondary}, {colors.unsynced-bg}/{colors.unsynced-text} — unchanged, and unchanged in meaning. Two colors are added, both supporting-tier, neither competing with the hero green:

- **Bar Panel Background (`#141414`)** — a hair lighter than {colors.bg}, just enough to read the Bar as a distinct docked strip without introducing a shadow or elevation effect. This is the only new "surface" color in the system.
- **Press Flash (`#ffe9b8`)** — a brief, lighter tint of {colors.digit-secondary}, shown only for the instant a tap registers on the gear icon or the Reboot button, then gone. It never appears as a resting color.

The Reboot button uses {colors.digit-secondary} (amber) at rest — explicitly **not** {colors.unsynced-bg} (red). Red stays reserved exclusively for the unsynced badge; Reboot is a normal, low-stakes action on this hobby device, not an alert.

Avoid: any dimming/scrim layer behind the Bar or Settings (this is still a flat, single-layer display, per base rule); using Press Flash as a resting/hover color; using red anywhere outside the unsynced badge.

## Typography

Inherits the base type scale for anything unchanged (Clock/Calendar views untouched). Settings view introduces three new roles, sized for full-screen legibility rather than corner-strip legibility:

- **Settings status** — 16px bold, letter-spaced, {colors.digit-primary}. This is the same status data that used to render as a small corner strip; now it's the largest text on the Settings view, since reading it is the entire point of opening Settings (UJ-2).
- **Settings guideline** — 13px regular, {colors.digit-secondary}, one line. Plain instructional sentence, no emphasis — supporting text under the status line.
- **Settings reboot** — 14px bold, letter-spaced, all-caps ("REBOOT"), {colors.digit-secondary}. Same visual tier as the guideline line, not louder — it is a normal control, not a warning.

## Layout & Spacing

**Touch Bar** — a bottom-docked strip, {spacing.bar-height} tall (~15% of the 240px frame height), full width, {colors.bar-panel-bg}. Slides up from the bottom edge over 200–300ms. The gear icon sits centered in the strip. The Clock/Calendar view above it is completely unaffected — no resize, no dim, no scrim — it simply continues rendering as the Bar docks over its bottom edge.

**Settings view** — full-screen (replaces Clock/Calendar entirely while open, per base full-bleed rule), stacked and top-aligned rather than centered:
1. {spacing.settings-top-padding} top padding, then Settings status line.
2. {spacing.settings-block-gap} gap, then Settings guideline line.
3. A larger gap below the guideline, then the Reboot button, positioned lower on the screen with clear separation from the status/guideline block above it — so Reboot reads as a distinct, deliberate action, not part of the informational block.

No back/close icon anywhere: Settings and the Bar both close only via idle timeout or an outside tap, matching the rest of this spine's tap-target-minimalism (see EXPERIENCE.md Interaction Primitives).

## Elevation & Depth

Still flat, single-layer — the base rule holds. {colors.bar-panel-bg} is a **flat color swap**, not a shadow or overlay; it reads as a distinct panel purely through hue difference, the same technique the base spine already uses for the unsynced badge.

## Shapes

Unrounded, matching the base "panel with numbers on it" rule. The gear glyph is a solid filled gear silhouette (8 teeth, punched center hole) at 0px corner rounding — not a sun/radiating-spoke glyph, and not a soft/rounded gear — so it doesn't introduce a shape language the rest of the device doesn't have.

## Components

- **Touch Bar** — {spacing.bar-height} bottom-docked strip, {colors.bar-panel-bg}, holds an icon list (one entry in v1: the gear). Built as a list container from the start so a second icon later is a data change, not a redesign.
- **Gear icon** — single glyph, {colors.digit-secondary} at rest, {colors.press-flash} on touch-down, centered in the Bar. The device's first and only icon. See [mockups/bar-revealed.html](mockups/bar-revealed.html).
- **Settings view** — full-screen replacement view: Settings status (16px, {colors.digit-primary}) + Settings guideline (13px, {colors.digit-secondary}) + Reboot button (14px, {colors.digit-secondary}), stacked top-down per Layout & Spacing above.
- **Reboot button** — text control, "REBOOT", {colors.digit-secondary} at rest, {colors.press-flash} on touch-down, no confirmation step, no alert coloring. See [mockups/settings-view.html](mockups/settings-view.html).

## Do's and Don'ts

- **Do** treat the gear glyph as the one and only permitted icon until a new feature explicitly earns another — the amended rule is "no icon set beyond what Settings needs," not "icons are now fine."
- **Do** keep {colors.bar-panel-bg} as the only new surface color — resist adding more panel shades as more UI gets added later.
- **Do** give every tap target a Press Flash — this is the device's first interactive surface, and a resistive/XPT2046 touch panel needs immediate visual acknowledgment that a tap registered.
- **Don't** use {colors.unsynced-bg} (red) for Reboot or any other new control — it stays exclusively the unsynced-state alert color.
- **Don't** add a scrim/dim layer behind the Bar or Settings — this device has never had elevation, and one interactive surface isn't reason enough to start.
- **Don't** add a back/close icon — timeout and outside-tap are the only exits, by design (keeps the icon count at one).
