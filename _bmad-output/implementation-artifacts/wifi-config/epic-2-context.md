# Epic 2 Context: Securely Manage Device Settings on the Home Network

<!-- Generated from planning artifacts. Regenerate with compile-epic-context if planning docs change. -->

## Goal

Once the Device is on the home LAN, Minh can authenticate to a local Config surface with his Admin password, change that password safely, and see a visible one-option Color Scheme control ready for future themes—without reflashing, multi-user accounts, or password recovery.

## Stories

- Story 2.1: Sign in to protected local settings
- Story 2.2: Maintain the Admin password and see the theme setting

## Requirements & Constraints

- Unauthenticated Config requests on the LAN redirect to a password-only login; incorrect password returns only “Incorrect password” with no hint, diagnostic detail, or session. Successful login starts a session that gates the rest of Config.
- Authenticated admin can change the Admin password; new password applies immediately to subsequent logins. Current session stays usable; no forced re-login. No password-recovery or factory-reset path in v1.
- Color Scheme is visibly present with exactly one option, `Forest & Amber`; selecting it is an inert no-op that must not error. Multi-theme logic is out of scope.
- Login/settings routes exist only while `STATION_ONLINE`; Setup routes are unavailable in this mode. HTTP is allowlisted GET + form-urlencoded POST, fixed local assets/templates, explicit escaping, checked-in resource limits, fixed errors for malformed/oversized/unsupported requests.
- Networking/HTTP must stay cooperative and bounded so rendering never blocks; policy, verification, HTTP parsing/routing, and page decisions must run under CPython without device imports (`uv run pytest`).
- Single salted one-way Admin verifier in the versioned settings record—never plaintext returned or logged. Sessions are opaque, unpredictable, in-memory only, bounded; cookies are `HttpOnly`, `SameSite=Strict`, `Path=/`. Password change invalidates other sessions.
- Mobile-only UI: semantic controls, 44px min targets, announced status changes, labeled password toggles, approved dark token/contrast system. No UI framework, desktop layout, external fetches, TLS, WAN exposure, username, or logout control (closing the tab ends use).

## Technical Decisions

- Auth lives in `src/provisioning/` + `src/device/web/` under the same coordinator-owned HTTP shell: `NetworkCoordinator` owns sockets; router enforces allowlist and session guards; `SettingsStore` alone persists verifiers.
- Verifier: PBKDF2-HMAC-SHA256 (`admin_verifier_version: "pbkdf2-sha256-v1"`), 20,000 iterations, 16-byte `os.urandom` salt, 32-byte derived verifier; constant-time compare. At most one `KdfJob` per coordinator; ≤200 PBKDF2 rounds per tick; concurrent KDF → fixed `503 Busy`; overwrite/discard password bytearrays on terminal outcomes.
- Session: opaque 16-byte `os.urandom` ID as unpadded base64url (exactly 22 ASCII chars) in an in-memory table of ≤4 entries; idle renew only on successful authenticated protected requests (`ticks_add(now, 900000)` / 15 min); expire with wrap-safe `ticks_diff`; invalid/expired cookies cleared with `Max-Age=0` and redirect to login; full table after expiry cleanup → `503 Busy`, no cookie. IDs must match `[A-Za-z0-9_-]{22}` then decode; compare decoded IDs constant-time.
- Password change: derive candidate → atomic SettingsStore commit → one terminal coordinator transition invalidates all sessions except the acting ID and renews that ID 15 minutes; derivation/commit failure leaves old verifier and every session unchanged. Settings commit uses the established tmp/bak/sync protocol; `color_scheme` remains `"forest-amber"`.
- Diagnostics: named codes only—never log cookies, verifiers/salts, bodies, or raw headers. No persistent login, recovery route, CSRF beyond `SameSite=Strict`, or remote exposure in v1.

## UX & Interaction Patterns

- Shared dark utility tokens (`#12161c` bg, `#1b212a` surface, `#2a323d` border, `#e8ecf1` / `#9aa5b1` text, `#7c6cf6` accent with `#0a0f16` button text, `#ff5c5c` danger, `#3ddc84` success); never green/amber in the web UI. Flat single-column phone layout; system sans; 44px targets; `aria-live` for status.
- Login: single password field + primary button, no username. Settings: flat list—Admin Password and Color Scheme rows expand inline (accordion), not separate pages. Theme picker: one preselected, visually disabled “Forest & Amber” item. Password change success copy: “Password changed.” Direct technical tone only.

## Cross-Story Dependencies

- Depends on Epic 1 leaving the Device `STATION_ONLINE` with a persisted Admin verifier and SettingsStore; Config auth must not exist in `SETUP_AP`.
- 2.1 delivers login, session cookie, and protected Config shell that 2.2’s password-change and theme-stub controls require.
- 2.2’s password change must invalidate other sessions while keeping the acting session; theme stub must not invent multi-theme persistence beyond the fixed `forest-amber` value.
