---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - ../prds/prd.md
  - ../architecture/ARCHITECTURE-SPINE.md
  - ../ux-designs/DESIGN.md
  - ../ux-designs/EXPERIENCE.md
  - ../../../../docs/hardware_configuration.md
  - ../../../../docs/pico_w_calendar_clock_handoff.md
---

# Pi Calendar Clock — Wi-Fi Provisioning & Admin Config - Epic Breakdown

## Overview

This document decomposes the Wi-Fi Provisioning & Admin Config PRD into implementation stories. It extends the existing clock/calendar firmware without changing its physical hardware configuration.

## Requirements Inventory

### Functional Requirements

FR1: When no valid saved Wi-Fi credentials exist, or saved credentials fail three consecutive connection attempts, the Device must create the open `PiCalendar-Setup` access point and serve its Setup page.

FR2: The Setup page must scan and list nearby SSIDs, collect the selected Wi-Fi password and an Admin password, and save neither until its single final submission includes both.

FR3: After final Setup submission, the Device must persist Wi-Fi credentials and the Admin password, stop the Setup AP, and try to join the selected network with a 15-second per-attempt timeout; a failed join must return to usable Setup AP mode.

FR4: The Device must automatically re-enter Setup AP mode after three consecutive saved-credential connection failures, at boot or after a dropped formerly-working connection.

FR5: In Setup AP mode, the TFT must continuously show `PiCalendar-Setup` and its gateway address `192.168.4.1`; after each successful station connection or reconnection, it must show the assigned IPv4 address for at least 10 seconds.

FR6: On the home LAN, unauthenticated Config-page requests must redirect to a password-only login form, reject an incorrect password without revealing the correct one, and permit authenticated access through a session.

FR7: An authenticated admin must be able to change the Admin password; the new password must apply immediately to subsequent logins.

FR8: The Config page must visibly provide a Color Scheme control with exactly one option, `Forest & Amber`; choosing it is an inert no-op that does not error.

### NonFunctional Requirements

NFR1: Networking, HTTP handling, and setup join work must be cooperative and bounded so rendering never blocks or freezes.

NFR2: Provisioning policy, settings validation, password verification, HTTP parsing/routing, and page decisions must run under CPython without device imports; host tests run with `uv run pytest`, while radio, socket, flash, and TFT behavior require a flashed-device check.

NFR3: The Device must use one `NetworkCoordinator` as the only owner of WLAN interfaces and sockets; only `App` may alter product state or draw/update TFT status.

NFR4: Settings must be held in one ignored, versioned, power-loss-safe record containing Wi-Fi credentials, a salted one-way admin verifier, and `forest-amber`; no plaintext admin password or secret may be returned or logged.

NFR5: HTTP must be a small local implementation: allowlisted GET and form-urlencoded POST routes, fixed assets/templates, explicit escaping, strict checked-in resource limits, and fixed errors for malformed, oversized, or unsupported requests.

NFR6: Sessions must be opaque, unpredictable, bounded, in-memory only, and sent in `HttpOnly`, `SameSite=Strict`, `Path=/` cookies; all config routes require a session and password change invalidates other sessions.

NFR7: The mobile-only web UI must use semantic controls, 44px minimum touch targets, announced status changes, labeled password toggles, and the approved color-contrast/token system.

NFR8: The existing hardware GPIO assignments, SPI0, TFT orientation, and display lifecycle must remain unchanged; no new physical input or reset mechanism is part of this work.

### Additional Requirements

- Build a functional core / imperative shell under the approved structure: `src/provisioning/`, `src/device/network/`, `src/device/web/`, `src/device/settings_store.py`, `src/app.py`, and `src/ui/`.
- Implement coordinator modes `BOOT`, `STATION_CONNECTING`, `STATION_ONLINE`, and `SETUP_AP`, with a sole pending setup candidate, wrap-safe `ticks_ms` deadlines, named result codes, and exactly three terminal failures before fallback.
- During setup join, retain the AP and requesting connection through its terminal browser response; persist only after success. If persistence fails, disconnect the candidate, retain setup/retry capability, and report a named failure.
- Validate the Pico W 1.29 STA/AP coexistence, scan behavior, gateway, and bounded socket fairness on flashed hardware; do not represent host tests as that proof.
- Use checked-in, bounded HTTP limits for request line, headers, body, clients, candidates, and per-tick I/O. Setup routes only exist in `SETUP_AP`; login/settings routes only in `STATION_ONLINE`.
- Choose and version a MicroPython-supported password-verifier algorithm/parameters, and choose checked-in session limits and idle timeout before implementation.
- Do not deploy legacy `secrets.py` once SettingsStore owns provisioning; resolve legacy migration explicitly only if existing device credentials must survive.

### UX Design Requirements

UX-DR1: Implement the shared dark mobile token system: `#12161c` background, `#1b212a` surface, `#2a323d` border, `#e8ecf1` primary text, `#9aa5b1` secondary text, `#7c6cf6` accent with `#0a0f16` button text, `#ff5c5c` danger, and `#3ddc84` success; do not use green or amber in this web UI.

UX-DR2: Implement the reusable Setup SSID list, password field with independently labeled show/hide toggle, full-width primary button, status banner, login form, settings row, and disabled one-item theme picker using the specified type, spacing, and rounded-control tokens.

UX-DR3: Implement the linear two-screen Setup flow: SSID selection and Wi-Fi password with Next, then Admin password and a single Connect submission; do not save or attempt a join before that final submission.

UX-DR4: Implement explicit Setup states: scanning, empty scan with a manual Rescan action, connecting with disabled button, join failure retaining the selected SSID/admin password but clearing Wi-Fi password, and a browser reload fallback for lost AP sessions.

UX-DR5: Implement a password-only Config login and an authenticated flat settings screen whose Admin Password and Color Scheme controls expand inline; theme is visible, preselected, and inert.

UX-DR6: Use direct technical copy, status-banner `aria-live` announcements, standard semantic HTML controls, and mobile screen-reader access; no UI framework, custom-only widgets, desktop layout, external fetches, or rich icon set.

### FR Coverage Map

FR1: Epic 1 — make a Device with no usable credentials discoverable through its setup network.

FR2: Epic 1 — let the owner complete the one-shot network and Admin-password setup flow.

FR3: Epic 1 — safely attempt, persist, and report Wi-Fi connection results without stranding the owner.

FR4: Epic 1 — automatically recover access after repeated Wi-Fi failures.

FR5: Epic 1 — tell the owner exactly how to reach the Device during setup and on the home LAN.

FR6: Epic 2 — protect ongoing LAN configuration with password-only login and a session.

FR7: Epic 2 — let the authenticated owner change the Admin password safely.

FR8: Epic 2 — expose the present and future-facing color-scheme setting without false functionality.

## Epic List

### Epic 1: Connect or Recover the Device Without Reflashing

Minh can provision a new Device onto home Wi-Fi, see how to reach it, and repeat the same familiar flow automatically after Wi-Fi credentials stop working.

**FRs covered:** FR1, FR2, FR3, FR4, FR5

### Epic 2: Securely Manage Device Settings on the Home Network

Once connected, Minh can authenticate to the Device’s local settings surface, maintain his Admin password, and see the ready-for-expansion color-scheme control.

**FRs covered:** FR6, FR7, FR8

## Epic 1: Connect or Recover the Device Without Reflashing

Minh can provision a new Device onto home Wi-Fi, see how to reach it, and repeat the same familiar flow automatically after Wi-Fi credentials stop working.

### Story 1.1: Start a new Device in a safe, testable setup mode

As Minh,
I want a new or invalidly configured Device to offer a dependable setup path,
So that I can start configuring it without reflashing or exposing stored secrets.

**Implements:** FR1; NFR1–NFR4.

**Acceptance Criteria:**

**Given** an absent, unreadable, malformed, unsupported, or incomplete device settings record, **when** the Device boots, **then** pure validation treats it as unconfigured and the coordinator enters `SETUP_AP` without deleting the record or crashing.

**Given** a Device in `SETUP_AP`, **when** the coordinator is ticked from the main loop, **then** it alone owns Pico WLAN/socket objects, activates open `PiCalendar-Setup`, and emits typed events rather than mutating `App` or drawing the TFT.

**Given** persisted settings, **when** they are read or committed, **then** only `SettingsStore` accesses the ignored versioned record, validates it as a whole, performs its target-proven atomic replacement protocol, and stores a salted one-way Admin verifier rather than plaintext Admin password.

**Given** provisioning validation, state-machine, and settings logic, **when** imported under CPython, **then** it has no `machine`, `network`, or socket imports and `uv run pytest` can exercise it with fakes.

### Story 1.2: Complete Wi-Fi setup from a phone

As Minh,
I want to choose a nearby Wi-Fi network and submit its password together with an Admin password,
So that the Device can securely join my home network from its own setup page.

**Implements:** FR2, FR3; NFR1, NFR2, NFR5, NFR7; UX-DR1–UX-DR4, UX-DR6.

**Acceptance Criteria:**

**Given** `SETUP_AP` mode, **when** I request the Setup page from a phone, **then** the Device serves only its allowlisted setup routes and displays a semantic, mobile-only two-screen flow using the approved dark tokens, 44px targets, and accessible labeled controls.

**Given** the first Setup screen, **when** scan results arrive, **then** it lists deduplicated, safely decoded SSIDs with selection and Wi-Fi-password entry; an empty result shows the specified manual Rescan state, and no password or BSSID is displayed.

**Given** I select an SSID and provide required fields, **when** I tap Next and then Connect, **then** no network action or persistence occurs before the final Connect submission containing `ssid`, `wifi_password`, and `admin_password`.

**Given** a valid final Setup submission, **when** the join begins, **then** the page announces `Connecting…` through an `aria-live` status banner, disables its primary button, keeps the AP and request connection available through the terminal result, and enforces the 15-second wrap-safe attempt deadline.

**Given** join success, **when** the candidate record commits, **then** the requesting browser receives the success result before its connection closes, the AP is deactivated only afterward, and an online event is emitted; **given** join or persistence failure, **then** no candidate is committed, the AP/form retry route remains usable, and the user gets the specified failure state with Wi-Fi password cleared but selected SSID and Admin password retained.

**Given** an embedded HTTP request, **when** it is malformed, unsupported, escaped unsafely, or exceeds configured request/client/body limits, **then** the bounded incremental server emits a fixed error and closes it without blocking the rendering loop or logging secrets.

### Story 1.3: Recover Wi-Fi automatically and show the Device address

As Minh,
I want the Device to tell me where to connect and automatically return to the familiar setup flow after Wi-Fi failures,
So that changed router credentials never leave it silently unreachable.

**Implements:** FR4, FR5; NFR1–NFR3, NFR8.

**Acceptance Criteria:**

**Given** a complete saved settings record, **when** the Device starts or loses a formerly-working station connection, **then** it makes bounded station attempts and enters `SETUP_AP` after exactly three consecutive terminal failures.

**Given** a successful setup join, **when** the online station event is processed, **then** the coordinator resets its failure count only after persistence succeeds and `App` remains the sole writer of product state.

**Given** `SETUP_AP`, **when** `App` receives the setup status event, **then** the established TFT overlay continuously shows `PiCalendar-Setup` and `192.168.4.1` without web/network code calling display APIs.

**Given** each successful station connection or reconnection, **when** its assigned IPv4 address is received, **then** `App` directs the overlay to show that address for at least 10 seconds while preserving the clock/calendar rendering lifecycle.

**Given** this story is ready to close, **when** the Pico W 1.29 proof is flashed, **then** it records observed STA/AP coexistence, `192.168.4.1` gateway behavior, scan availability during AP mode, bounded socket fairness, browser terminal responses, flash commits, and TFT legibility separately from host-test results; an unsupported coexistence result blocks the browser-result claim for redesign rather than silently changing it.

## Epic 2: Securely Manage Device Settings on the Home Network

Once connected, Minh can authenticate to the Device’s local settings surface, maintain his Admin password, and see the ready-for-expansion color-scheme control.

### Story 2.1: Sign in to protected local settings

As Minh,
I want to log in to the Device’s LAN settings page with my Admin password,
So that only I can access its ongoing configuration.

**Implements:** FR6; NFR1, NFR2, NFR5–NFR7; UX-DR1, UX-DR2, UX-DR5, UX-DR6.

**Acceptance Criteria:**

**Given** the Device is `STATION_ONLINE`, **when** I request a protected Config route without a valid session, **then** the allowlisted router redirects me to a password-only login form and Setup routes are unavailable.

**Given** the login form, **when** I submit an invalid password, **then** the page returns only `Incorrect password` without diagnostic detail, secret logging, or a session.

**Given** a valid password, **when** the auth service verifies it using its versioned salted verifier and constant-time comparison where available, **then** it creates an opaque unpredictable entry in a checked-in bounded in-memory session table and sends an `HttpOnly`, `SameSite=Strict`, `Path=/` cookie.

**Given** a valid session, **when** I open the Config page, **then** I see the mobile flat settings list with inline controls, approved visual tokens, semantic controls, and no external fetch or framework dependency.

### Story 2.2: Maintain the Admin password and see the theme setting

As Minh,
I want to change my Admin password and inspect the available color-scheme setting,
So that I can keep local access current and understand the Device’s current configuration.

**Implements:** FR7, FR8; NFR4–NFR7; UX-DR1, UX-DR2, UX-DR5, UX-DR6.

**Acceptance Criteria:**

**Given** an authenticated Config session, **when** I open the inline Admin Password control and submit a valid replacement, **then** `SettingsStore` atomically persists only its new verifier, the current session remains usable, all other sessions are invalidated, and the UI announces `Password changed.`.

**Given** a completed password change, **when** another browser or a subsequent login uses the old password, **then** it is rejected; **when** it uses the new password, **then** it succeeds.

**Given** the authenticated settings list, **when** I open Color Scheme, **then** the visible inline picker shows exactly one preselected, disabled `Forest & Amber` option; selecting it is a no-op and never errors.

**Given** the password and theme controls, **when** their requests are malformed, unauthorized, or outside `STATION_ONLINE`, **then** the router rejects them through the defined bounded HTTP/auth behavior and does not disclose or alter settings.
