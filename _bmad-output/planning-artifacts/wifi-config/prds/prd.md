---
title: Pi Calendar Clock — Wi-Fi Provisioning & Admin Config
status: final
created: 2026-09-06
updated: 2026-09-06
---

# PRD: Wi-Fi Provisioning & Admin Config

## 0. Document Purpose

This PRD scopes Wi-Fi provisioning and the admin config web interface for the Pi Calendar Clock device. It is a companion to [pico-w-calendar-clock prd.md](../../pico-w-calendar-clock/prds/prd.md) (core clock/calendar v1) — see that document for the Device's base vision, hardware, and Glossary terms (Device, Time source, Clock view, Calendar view). This PRD does not repeat those; it defines how the Device gets onto Wi-Fi in the first place, how it recovers when Wi-Fi changes, and how the owner configures it afterward. FR/UJ IDs (FR-1, UJ-1, etc.) are local to this document and restart independently from the sibling PRD's own FR-1/UJ-1 — when referencing either set outside its own document, name the PRD alongside the ID.

## 1. Vision

The core clock (see [pico-w-calendar-clock prd.md](../../pico-w-calendar-clock/prds/prd.md)) assumes Wi-Fi is already configured. This PRD covers what happens before that's true: a brand-new or reset Device has no way to join a network and no keyboard for input. It provisions itself by briefly acting as its own Wi-Fi access point and serving a setup page, then — once online — continues to serve an authenticated config page on the home network for ongoing settings (starting with admin password and color scheme).

## 2. Target User

Same single owner as [pico-w-calendar-clock prd.md](../../pico-w-calendar-clock/prds/prd.md) §2 (Minh, single-owner desk device, not multi-user).

### 2.1 Key User Journeys

- **UJ-1 (first boot / Wi-Fi setup).** Minh powers on a brand-new (or freshly reset) Device. It has no saved Wi-Fi credentials, so it broadcasts its own open access point, `PiCalendar-Setup`, and shows the AP's gateway address on its own screen. Minh joins that AP from his phone, browses to the shown address, sees a list of nearby SSIDs, picks his home network, enters its password, and also sets an admin password for the Device itself. Device saves both, drops the setup AP, and joins his home Wi-Fi.
- **UJ-2 (Wi-Fi changed / lost).** Minh's router password changes (or the Device is moved to a new place). Device tries its saved credentials, fails 3 times, and automatically falls back into the same setup-AP flow as UJ-1 so Minh can re-enter Wi-Fi details.
- **UJ-3 (ongoing admin config).** Once the Device is on Wi-Fi, Minh checks its own screen for the IP address it was assigned, opens that address in a browser, logs in with his admin password, and changes settings — currently: change the admin password, and pick a color scheme (stub for now).

## 3. Glossary

(Extends [pico-w-calendar-clock prd.md](../../pico-w-calendar-clock/prds/prd.md) §3.)

- **Setup AP** — the open Wi-Fi access point (`PiCalendar-Setup`) the Device broadcasts itself when it has no working Wi-Fi credentials, used to serve the first-boot setup page.
- **Setup page** — the web page served over the Setup AP for choosing an SSID, entering its password, and setting the admin password.
- **Admin password** — a password set during first boot that gates access to the Device's ongoing config page (distinct from any Wi-Fi password).
- **Config page** — the web interface served by the Device once it's on the home Wi-Fi, reachable on the LAN, gated by the admin password, for changing settings (admin password, color scheme, future settings).

## 4. Features

### 4.1 Wi-Fi Provisioning

**Description:** Device has no way to join a network out of the box, and no input mechanism beyond its own TFT screen — provisioning happens through a self-hosted web page over the Device's own AP. Realizes UJ-1, UJ-2.

#### FR-1: First-boot / fallback Wi-Fi setup

When the Device has no saved Wi-Fi credentials, or saved credentials fail to connect 3 times in a row, it broadcasts the Setup AP (open, SSID `PiCalendar-Setup`) and serves a Setup page.

**Consequences (testable):**
- Setup page lists nearby SSIDs (scanned by the Device's radio) for the user to choose from, plus a password field for the chosen network.
- Setup page also collects and sets the Admin password (see FR-2) — first-boot setup is not complete until both Wi-Fi credentials and an admin password are saved.
- On submit, Device saves Wi-Fi credentials and admin password to persistent storage, stops the Setup AP, and attempts to join the chosen network, bounded by a connection timeout (e.g. 15s) per attempt [ASSUMPTION: 15s timeout; confirm].
- If the join fails (wrong password or timeout), Device returns to Setup AP mode rather than getting stuck retrying silently.
- Saved Wi-Fi credentials that fail 3 consecutive connection attempts (whether at boot or after a previously-working connection drops) re-trigger Setup AP mode automatically — no user action needed to enter setup mode.

**Out of Scope:**
- WPA2/secured Setup AP — v1's setup AP is open by design (see §8 Open Questions on the security tradeoff).
- Captive-portal auto-redirect (OS auto-popup of the setup page on join) — user navigates to the Device's setup address manually. [ASSUMPTION: no captive-portal DNS trick in v1; confirm if this matters for usability.]

#### FR-2: Device shows its own address on-screen

Device has no keyboard and no other display, so it surfaces the URL/address the user needs at each stage directly on its own TFT screen rather than requiring router access or guesswork.

**Consequences (testable):**
- While in Setup AP mode, Device screen shows the Setup AP's SSID and its known gateway address (e.g. `192.168.4.1`) so the user knows where to browse — from first boot onward, not just after a reset.
- After successfully joining the home Wi-Fi, Device screen shows the IP address it was assigned for at least 10 seconds on a boot/status screen [ASSUMPTION: 10s is enough to read and note down; confirm], so the user can reach the Config page (FR-3) without checking their router's client list.
- If the Device's IP changes (e.g. router reassigns via DHCP after a restart), the next boot/reconnect re-displays the current IP. [ASSUMPTION: re-displaying IP on every reconnect, not just first boot, is enough — a persistent on-demand "show my IP" view is not required for v1; confirm.]

**Out of Scope:**
- mDNS / friendly hostname (e.g. `picalendar.local`) — v1 relies on the on-screen IP address only.

### 4.2 Admin Config Web Interface

**Description:** Once on Wi-Fi, the Device serves an authenticated config page on the LAN so Minh can manage settings without re-flashing or re-entering setup mode. Realizes UJ-3.

#### FR-3: Admin login and password change

Config page requires the Admin password (set at first boot per FR-1) to access. Logged-in admin can change that password.

**Consequences (testable):**
- Unauthenticated requests to the config page redirect to a login form; wrong password is rejected with no hint about the correct one.
- Successful login starts a session that gates access to the rest of the config page.
- Changing the password takes effect immediately (old password stops working, new one required for the next login).
- No password-recovery flow exists in v1: forgetting the admin password with no saved-Wi-Fi issue leaves the Device configurable only by whatever recovery mechanism ships later (see §6.2, §8 — no physical button exists yet).

#### FR-4: Color scheme setting (stub)

Config page exposes a color scheme control, but v1 ships with exactly one theme (Forest & Amber, per [pico-w-calendar-clock DESIGN.md](../../pico-w-calendar-clock/ux-designs/DESIGN.md)) selectable.

**Consequences (testable):**
- Setting is visibly present in the config page UI (not hidden), so the surface exists for future themes.
- Selecting the only available option is a no-op that doesn't error; multi-theme switching logic is not built in v1.

**Out of Scope:**
- Additional palettes / theme switching logic — deferred (see §6.2).

## 5. Non-Goals (Explicit)

- Not a multi-user device — single admin password, no per-user accounts.
- Not building physical input handling (buttons, touch) in v1 — all config happens over the web UI (FR-1/2/3/4); power connect/disconnect is the only physical interaction.
- Not building a factory-reset mechanism in v1 — no physical button exists yet to trigger one, so there's no admin-password recovery path (see FR-3, §8).

## 6. MVP Scope

### 6.1 In Scope

- First-boot / fallback Wi-Fi setup via self-hosted Setup AP and Setup page (FR-1).
- On-screen display of Setup AP gateway address and, once connected, the Device's Wi-Fi IP address (FR-2).
- Admin login, session, and password change on the Config page (FR-3).
- Color scheme setting, stubbed to one theme (FR-4).

### 6.2 Out of Scope for MVP

- Physical button/input handling (setup and config both happen over the web UI).
- Factory reset / admin-password recovery mechanism — no physical button exists yet to trigger one.
- Additional color themes beyond the current one — the setting exists (FR-4) but only one theme ships.
- mDNS/friendly hostname for reaching the Config page — v1 relies on the on-screen IP (FR-2).
- Secured (WPA2) Setup AP or captive-portal auto-redirect (FR-1).

## 7. Success Metrics

Success: Minh can set up the Device on a new network, or recover it after a Wi-Fi change, without re-flashing or reading source code — no metric instrumentation planned for a hobby build.

## 8. Open Questions

Resolved during finalize:

- ~~Open Setup AP (no password) security tradeoff — acceptable?~~ **Resolved:** accepted for v1 — FR-1's choice of an open `PiCalendar-Setup` AP already reflects this tradeoff being taken deliberately, not left undecided.

Deferred (non-blocking for v1 build):

1. Is showing the IP only on the Device's own screen (FR-2) sufficient, or does Minh want it reachable another way too (e.g. printed on a label, logged somewhere) if he's not near the desk when it reconnects? **Revisit if:** on-screen-only display proves impractical in daily use.
2. When is a physical-button factory-reset / password-recovery mechanism revisited — fixed follow-up or open-ended? (affects FR-3, §6.2) **Revisit when:** physical button hardware is added to the Device.

## 9. Assumptions Index

- §4.1 FR-1 — No captive-portal DNS trick in v1; user navigates to the setup address manually.
- §4.1 FR-1 — 15s connection timeout per join attempt before falling back to Setup AP mode.
- §4.1 FR-2 — IP address displayed for at least 10s on the boot/status screen.
- §4.1 FR-2 — Re-displaying IP on every reconnect (not a persistent on-demand view) is enough for v1.
