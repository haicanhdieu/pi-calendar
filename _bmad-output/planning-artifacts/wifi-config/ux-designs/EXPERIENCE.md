---
name: Wi-Fi Provisioning & Admin Config
status: final
updated: 2026-09-06
---

## Foundation

**Form factor:** mobile browser only (confirmed — no desktop responsive requirement for v1). Two distinct surfaces served by the Device itself, never installed as an app:

1. **Setup page** — served over the open `PiCalendar-Setup` AP, reachable only while the Device has no working Wi-Fi (first boot, or after 3 failed reconnect attempts per FR-1).
2. **Config page** — served on the home LAN once the Device has joined Wi-Fi, gated by the Admin password (FR-3).

No UI framework assumed — plain HTML/CSS/minimal JS, since this is served by the Device's own limited web server, not a build-tooled SPA. Visual tokens per [[DESIGN.md]]; this document specifies behavior only. This document and [[DESIGN.md]] are the contract; where a mock in `mockups/` disagrees with either, the spine wins.

## Information Architecture

**Setup page** (linear two-screen flow, no nav):
- Screen 1: SSID picker (list from FR-1 scan) → select one → Wi-Fi password field appears → "Next" (no save yet, no network action). Mock: [mockups/key-setup-ssid.html](mockups/key-setup-ssid.html)
- Screen 2: Admin password field, one primary "Connect" button — this is the actual submit: saves both Wi-Fi credentials and Admin password together, drops the Setup AP, and attempts the join. Matches FR-1's requirement that setup isn't "complete" (i.e. nothing is saved/attempted) until both are captured — the two-screen split is presentational only, not a two-submit flow. Mock: [mockups/key-setup-admin.html](mockups/key-setup-admin.html)

**Config page** (login + flat settings list, no deep nav):
- Login screen (password only, no username). Mock: [mockups/key-config-login.html](mockups/key-config-login.html)
- Settings screen: "Admin Password" row (opens change-password form), "Color Scheme" row (opens theme picker stub). Mock: [mockups/key-config-settings.html](mockups/key-config-settings.html)

Surface closure check: every UJ lands on a surface — UJ-1/UJ-2 → Setup page; UJ-3 → Config page. No orphaned surfaces, no unmet journey.

## Voice and Tone

Direct, technical-instrument tone — matches the Device's own no-decoration identity ([[pico-w-calendar-clock DESIGN.md]] Brand & Style). No cheerful copy ("Yay, connected!"), no apologetic hedging on errors. State what happened and what to do next.

- Success: "Connected to {ssid}." / "Password changed."
- Failure: "Couldn't join {ssid}. Check the password and try again." / "Incorrect password." (per FR-3: no hint about the correct one)
- In-progress: "Connecting…" / "Joining {ssid}…"

[ASSUMPTION] no localization beyond English in v1 (single owner, English-speaking) — confirm.

## Component Patterns

- **SSID list row** — tap selects, reveals the Wi-Fi password field below on the same screen (Screen 1); re-tapping a different row before "Next" re-selects cleanly.
- **Password field** — masked by default with a show/hide toggle; toggle state does not persist across the two password fields (each toggles independently), since Wi-Fi password and Admin password are different sensitivity contexts.
- **Primary button** — disabled until required fields are non-empty; on tap, immediately shows in-progress state (per FR-1's ~15s join timeout — an [ASSUMPTION] carried from the PRD) — button must not appear inert during that wait.
- **Settings row** — tapping opens its control inline (accordion-style) rather than navigating to a new page, since there are only two settings in v1 and a full navigation stack would be overbuilt.
- **Theme picker (stub)** — shows the one available option pre-selected and visually disabled/inert (per FR-4: selecting the only option is a no-op, must not error).

## State Patterns

- **Setup page — scanning:** brief loading state while SSIDs populate; if scan returns empty, show "No networks found — move closer to your router and reload" with a manual text-link "Rescan" action (confirmed, no auto-retry). Mock: [mockups/key-setup-ssid.html](mockups/key-setup-ssid.html) (empty-scan panel).
- **Setup page — connecting:** status banner shows "Connecting…"; primary button disabled; screen does not auto-navigate away until success or failure is known (bounded by FR-1's per-attempt timeout). Mock: [mockups/key-setup-admin.html](mockups/key-setup-admin.html) (connecting panel).
- **Setup page — join failed:** status banner shows failure copy (see Voice and Tone); form fields retain entered values (password field cleared for security — [ASSUMPTION] Wi-Fi password field clears on failure, Admin password field does not, since re-typing a Wi-Fi password after a typo is the expected retry path); user can resubmit without re-selecting SSID. Mock: [mockups/key-setup-admin.html](mockups/key-setup-admin.html) (failure panel).
- **Setup page — AP dropped mid-fill (UJ-2 edge case):** [ASSUMPTION] if the Setup AP session times out while Minh is mid-form (e.g. he steps away), a reload of the page re-shows the SSID picker from scratch rather than preserving partial state — no session persistence across AP restarts in v1.
- **Config page — logged out:** any request redirects to login; wrong password shows generic "Incorrect password" with no further hint (per FR-3). Mock: [mockups/key-config-login.html](mockups/key-config-login.html).
- **Config page — session active:** settings screen accessible; session persists until browser closed or an explicit idle timeout (not specified in PRD). No logout control — confirmed: single-owner trusted LAN device, closing the tab is sufficient.
- **Config page — password changed:** success toast, no forced re-login (per FR-3: "takes effect immediately" describes the next login, not the current session) — [ASSUMPTION] current session stays valid after a password change; confirm this isn't a security concern for a single-owner device. Mock: [mockups/key-config-settings.html](mockups/key-config-settings.html).

## Interaction Primitives

- Tap targets minimum 44px height (settings rows, SSID rows, buttons) — phone-thumb usage throughout.
- No swipe gestures, no pull-to-refresh — [ASSUMPTION] a manual "Rescan" text action on the SSID list covers the refresh case instead, since gesture affordances are easy to miss on a one-time setup screen.
- Form submission is the only navigation trigger on Setup page — no back button needed (linear, one-shot flow); browser back button behavior not specially handled (out of scope, [ASSUMPTION]).

## Accessibility Floor

- All interactive elements reachable via standard mobile screen-reader tap/swipe navigation (semantic HTML controls, not custom-drawn widgets) — no custom JS-only inputs.
- Status changes (connecting/success/failure) announced via `aria-live` region on the status banner, since a screen-reader user won't see a color change.
- Password show/hide toggle has a text label, not an icon-only control, per DESIGN.md's text-first stance.
- Color contrast: `text-secondary` (`#9aa5b1`) on `bg` = 7.25:1, on `surface` = 6.47:1 — passes AA and AAA for body text. Accent button labels must use `accent-text` (dark) on the violet `accent` fill — measured 4.88:1 (passes AA); light text on the same fill measured only 3.32:1 (fails for 15px bold), so dark labels are load-bearing, not a style choice.

## Key Flows

**UJ-1 — Minh sets up a brand-new Device.** Minh powers on the Device; its TFT shows "Connect to PiCalendar-Setup, then visit 192.168.4.1." He joins that AP from his phone, opens the address, and sees a scanning spinner resolve into a list of nearby SSIDs. He taps his home network, types its password, taps "Next." A second screen asks for an Admin password; he sets one and taps "Connect" (full-width, now showing "Connecting…") — this single tap is what actually saves both passwords, drops the AP, and starts the join. The screen holds for a few seconds, then flips to "Connected to HomeNet." — the climax beat: the AP has already dropped, his phone quietly rejoins his home Wi-Fi on its own, and the Device's TFT (out of this UX's scope, but the payoff) now shows its new IP.

**UJ-2 — Minh's router password changes.** Days later, the Device can't reconnect — silently, from Minh's point of view, until he happens to glance at the TFT and sees it's back in `PiCalendar-Setup` mode (Device auto-fell-back after 3 failed attempts). He repeats the UJ-1 flow exactly — no separate "recovery" UI, no error message to dismiss, just the same Setup page asking again. The climax beat here is the *absence* of drama: it's the identical form he saw once before, so there's nothing new to figure out.

**UJ-3 — Minh changes his admin password months later.** Half-remembering a URL he wrote down once, Minh opens `http://192.168.1.47` (the IP his TFT showed at last reconnect) on his phone. He hits a login screen, types his admin password, and lands on a short settings list: "Admin Password", "Color Scheme". He taps "Admin Password," an inline field expands, he types a new one, taps "Save" — a small toast confirms "Password changed." He glances at "Color Scheme" out of curiosity, taps it, sees "Forest & Amber" as the only, pre-selected, grayed-out option, and closes the tab satisfied there's nothing else to do yet.
