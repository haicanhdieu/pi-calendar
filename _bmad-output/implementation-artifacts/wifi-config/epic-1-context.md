# Epic 1 Context: Connect or Recover the Device Without Reflashing

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Minh can provision a new Device onto home Wi-Fi through an open setup AP and phone page, see how to reach it on the TFT, and automatically get the same familiar setup flow after saved credentials fail—without reflashing or physical input.

## Stories

- Story 1.1: Start a new Device in a safe, testable setup mode
- Story 1.2: Complete Wi-Fi setup from a phone
- Story 1.3: Recover Wi-Fi automatically and show the Device address

## Requirements & Constraints

- No usable/valid settings (or three consecutive station failures at boot or after a drop) → open AP `PiCalendar-Setup`, serve Setup page; setup AP is open by design (no WPA2, no captive-portal redirect).
- Setup collects SSID, Wi-Fi password, and Admin password; nothing is saved or joined until one final Connect submission with all three.
- After submit: persist credentials + salted Admin verifier, stop AP, join with 15s per-attempt timeout; failed join returns to usable Setup AP (not silent retry). Exactly three consecutive terminal failures re-enter Setup AP.
- TFT: in Setup AP, continuously show `PiCalendar-Setup` and `192.168.4.1`; after each successful station connect/reconnect, show assigned IPv4 ≥10s. No mDNS/hostname in v1.
- Networking/HTTP must be cooperative and bounded so the clock render loop never blocks; pure policy/validation/HTTP parsing must run under CPython without device imports (`uv run pytest`); radio/socket/flash/TFT need flashed-device proof.
- One ignored, versioned, power-loss-safe settings record; no plaintext Admin password returned or logged. Existing GPIO/SPI0/TFT orientation and display lifecycle unchanged; no new physical reset.
- Out of scope for this epic: LAN Config login/sessions, Admin password change UI, color-scheme stub (Epic 2).

## Technical Decisions

- Functional core / imperative shell: `NetworkCoordinator` sole owner of WLAN + sockets; `App` sole product-state and TFT-status writer via typed events/commands. Modes: `BOOT`, `STATION_CONNECTING`, `STATION_ONLINE`, `SETUP_AP`.
- At most one pending setup candidate; wrap-safe `ticks_ms` deadlines; named result codes; AP and requesting connection retained through terminal browser response; persist only after successful join; persistence failure disconnects candidate, keeps retry, named failure (no online/IP event, failure count not reset).
- SettingsStore alone reads/writes the record (`settings_version: 1`, Wi-Fi strings with length rules, PBKDF2-HMAC-SHA256 verifier params, `color_scheme: "forest-amber"`); invalid/unsupported records preserved and treated as unconfigured; atomic tmp/bak/sync commit protocol.
- Bounded allowlisted GET + form-urlencoded POST HTTP; setup routes only in `SETUP_AP`; fixed assets, explicit escaping, fixed errors for malformed/oversized requests. Structure seed: `src/provisioning/`, `src/device/network/`, `src/device/web/`, `src/device/settings_store.py`, `src/app.py`, `src/ui/`.
- Target MicroPython Pico W 1.29; validate STA/AP coexistence, scan during AP, gateway, socket fairness on flash—unsupported coexistence blocks browser-result claim rather than silent redesign. Do not deploy legacy `secrets.py` once SettingsStore owns provisioning.

## UX & Interaction Patterns

- Mobile-only, no framework: dark utility tokens (`#12161c` bg, `#1b212a` surface, `#7c6cf6` accent with dark `#0a0f16` button text, danger/success as specified); never green/amber in the web UI. 44px min targets; semantic HTML; `aria-live` status banner; labeled password show/hide.
- Linear two-screen Setup: (1) scan/list SSIDs → select → Wi-Fi password → Next (no save); (2) Admin password → Connect. Empty scan: manual Rescan, no auto-retry. Connecting: banner “Connecting…”, button disabled. Join failure: clear Wi-Fi password only; retain SSID + Admin password. Lost AP mid-fill: reload restarts SSID picker. Direct technical copy only.

## Cross-Story Dependencies

- 1.1 delivers SettingsStore + coordinator `SETUP_AP` foundation that 1.2’s HTTP Setup flow and candidate join require.
- 1.3 builds on the same state machine for three-failure fallback and App-owned TFT overlays; closes with on-device STA/AP coexistence proof that gates the browser terminal-response claim from 1.2.
- Epic 2 (Config login/settings) depends on Epic 1 leaving the Device `STATION_ONLINE` with a persisted Admin verifier; Config routes must not exist in Setup mode.
