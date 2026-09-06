---
name: Wi-Fi Provisioning & Admin Config
status: final
updated: 2026-09-06
colors:
  bg: '#12161c'
  surface: '#1b212a'
  border: '#2a323d'
  text-primary: '#e8ecf1'
  text-secondary: '#9aa5b1'
  accent: '#7c6cf6'
  accent-text: '#0a0f16'
  danger: '#ff5c5c'
  success: '#3ddc84'
typography:
  family: '-apple-system, "Segoe UI", Roboto, sans-serif'
  page-title:
    size: 20px
    weight: 700
  section-label:
    size: 12px
    weight: 700
    letter-spacing: 1px
    transform: uppercase
  body:
    size: 15px
    weight: 400
  input-label:
    size: 13px
    weight: 600
  button:
    size: 15px
    weight: 700
rounded:
  control: 10px
  card: 14px
  pill: 999px
spacing:
  page-padding: 20px
  field-gap: 16px
  section-gap: 28px
components:
  - setup-ssid-list
  - password-field
  - primary-button
  - status-banner
  - login-form
  - settings-row
  - theme-picker-stub
---

## Brand & Style

This is the Device's own configuration surface, not a marketing product. It shows up in exactly two contexts: once, tensely, when Minh is standing next to a brand-new or freshly-reset Device with a phone in hand and no network yet; and repeatedly, casually, when he's on his home Wi-Fi tweaking a setting he half-remembers. The visual register is **utility, not brand** — dark, quiet, single-column, phone-first. Nothing here competes with the Device's own Forest & Amber TFT identity; this is what you look at *before* the Device is glowing at you, or *instead of* walking over to it.

Setup page and Config page share this one token set (colors/type/spacing) but differ in tone and density, not palette: Setup page is stripped to the single task at hand (pick network, set passwords, submit), Config page allows a bit more structure (sections, settings rows) since it's revisited over time — confirmed as "one system, two moods."

This document and [[EXPERIENCE.md]] are the contract; where a mock in `mockups/` disagrees with either, the spine wins.

## Colors

A cool, neutral dark UI — deliberately **not** green/amber, so it never gets confused with the Device's own on-screen Forest & Amber language ([[pico-w-calendar-clock DESIGN.md]] `colors.digit-primary` / `colors.digit-secondary`). This is a phone-screen surface, viewed indoors at close range, not a glanceable-from-across-the-room instrument panel — so it can afford smaller text and denser layout than the Device screen.

- **Background (`#12161c`)** — near-black blue-gray, not true black; sits behind everything.
- **Surface (`#1b212a`)** — one step up, used for cards/rows (SSID list items, settings rows) so they read as grouped without needing borders everywhere.
- **Border (`#2a323d`)** — hairline dividers and input outlines only.
- **Text Primary (`#e8ecf1`)** — body copy, labels, values.
- **Text Secondary (`#9aa5b1`)** — helper text, placeholder text, timestamps.
- **Accent (`#7c6cf6`)** — violet indigo, calm/premium/modern register. The one active color: primary buttons, focused input border, selected SSID row, links. Chosen from 6 rendered options ([[color-themes-1]]), verified distinct from Device colors and from the danger/success pair. Button/focused-control labels use `accent-text` (dark, `#0a0f16`), not light text — verified 4.88:1 contrast (light text on this accent measured 3.32:1, below AA for 15px bold).
- **Danger (`#ff5c5c`)** — failed connection, wrong password, form errors.
- **Success (`#3ddc84`)** — successful join, saved confirmation toast.

Avoid: green/amber anywhere in this UI (reserved for the Device's own screen identity), decorative gradients, more than one accent hue.

## Typography

System sans-serif stack — no custom font loading on a page that may be served from the Device itself over a constrained AP connection.

- **Page title** — 20px/700, top of every screen ("Set Up Wi-Fi", "Device Settings").
- **Section label** — 12px/700, uppercase, letter-spaced — groups fields ("NETWORK", "ADMIN PASSWORD").
- **Body** — 15px/400, default copy and helper text.
- **Input label** — 13px/600, sits above each field.
- **Button** — 15px/700, all buttons.

## Layout & Spacing

Single-column, phone-width only — no desktop breakpoint in v1 (confirmed mobile-browser-only usage), so layout can hard-assume a narrow viewport rather than building responsive grid logic. 20px page padding, 16px between fields, 28px between sections. Primary action button is always full-width and pinned near the thumb (bottom of the visible content, not top).

## Elevation & Depth

Flat, one level of surface lift (`bg` → `surface`) via solid fill, no shadows — matches the no-chrome philosophy of the parent device, and avoids shadow-rendering inconsistencies on the constrained/embedded browsers this page is likely to be tested against.

## Shapes

Rounded throughout — 10px on inputs/buttons, 14px on cards/rows, full-pill on status badges — softer and more "app-like" than the Device's own near-unrounded panel aesthetic, since this is a touch-driven phone surface, not a glanceable display.

## Components

- **Setup SSID list** — scrollable list of `surface`-fill rows, each showing SSID name + signal indicator; selected row gets `accent` border/checkmark. Mock: [mockups/key-setup-ssid.html](mockups/key-setup-ssid.html).
- **Password field** — standard input with a show/hide toggle (text always small enough to mistype blind); `border` default, `accent` on focus, `danger` on validation error. Mock: [mockups/key-setup-ssid.html](mockups/key-setup-ssid.html), [mockups/key-setup-admin.html](mockups/key-setup-admin.html).
- **Primary button** — full-width, `accent` fill, `accent-text` label, disabled state at reduced opacity while a network join is in progress. Mock: [mockups/key-setup-admin.html](mockups/key-setup-admin.html).
- **Status banner** — full-width strip below the title for connect-attempt state ("Connecting…", "Couldn't join — check the password", "Connected!") using `text-secondary`/`danger`/`success` respectively. Mock: [mockups/key-setup-admin.html](mockups/key-setup-admin.html).
- **Login form** — single password field + primary button, centered, no username field (single admin, per PRD §2). Mock: [mockups/key-config-login.html](mockups/key-config-login.html).
- **Settings row** — Config page list row: label left, current value/control right, tap target full row height. Mock: [mockups/key-config-settings.html](mockups/key-config-settings.html).
- **Theme picker (stub)** — settings row that opens a single-item list (Forest & Amber, selected/disabled) — visually present per FR-4 but inert. Mock: [mockups/key-config-settings.html](mockups/key-config-settings.html).

## Do's and Don'ts

- **Do** keep Setup page to one task per screen — no multi-field forms competing for a stressed first-boot moment.
- **Do** reuse the same input/button/banner components across Setup and Config so the token set stays honestly single.
- **Don't** use green or amber anywhere in this web UI — that palette is reserved for the Device's own screen identity.
- **Don't** build a desktop layout — confirmed mobile-browser-only for v1.
- **Don't** add iconography beyond a signal-strength glyph on the SSID list — [ASSUMPTION] keep it text-first like the Device itself; flag if a richer icon set is wanted later.
