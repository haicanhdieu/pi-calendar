---
title: 'Shrink Wi-Fi setup and admin page assets'
type: 'feature'
created: '2026-09-08'
status: 'in-progress'
baseline_revision: '774d7329191989b1af0b8146370e5a737d4bfab7'
review_loop_iteration: 0
followup_review_recommended: false
context:
  - /Users/minhtrucnguyen/working/ntm/pi-calendar/_bmad-output/specs/spec-wifi-config/SPEC.md
  - /Users/minhtrucnguyen/working/ntm/pi-calendar/_bmad-output/specs/spec-wifi-config/override-trace.md
warnings: [multiple-goals]
deferred: []
---

<intent-contract>

## Intent

**Problem:** The Pico W setup page embeds roughly 4.3 KB of JavaScript and 1.8 KB of CSS. Fragmented heap conditions make page construction and web serving intermittently fail with `MemoryError`.

**Approach:** Replace setup-page fetch/DOM behavior with server-rendered HTML forms and full-page navigation. Remove duplicated login/settings styling and use one small CSS-only classless CDN stylesheet on station-online pages.

## Boundaries & Constraints

**Always:** Keep setup fully self-contained and usable over the isolated AP; preserve `/`, `/scan`, `/connect`, existing join success/failure renderers, escaping, semantic controls, dark token intent, and current coordinator/auth behavior. Keep setup JS below 1 KB (prefer zero) and CSS below 0.4 KB; remove duplicated config CSS and keep login/settings JS near zero.

**Never:** Do not add CDN assets to setup AP pages, change Wi-Fi/KDF/session/coordinator/validation behavior, add static routes, use a JS framework, or claim host tests prove Pico heap, WLAN, browser, or cold-boot behavior.

</intent-contract>

## Code Map

- `src/device/web/page_setup_content.py` -- current setup HTML/CSS/JS; replace SPA scan/render/submit with server-rendered select, link rescan, and form state.
- `src/device/web/setup_pages.py` -- existing setup response wrappers and join result state; preserve route-facing renderer contracts and adapt page calls only as needed.
- `src/device/web/pages.py` -- lazy page imports and HTTP response builders; read-only integration boundary for setup/login/settings pages.
- `src/device/web/page_login_content.py` -- duplicated `_CONFIG_CSS` and small password-toggle script; retain accessible login markup while sourcing minimal CDN CSS.
- `src/device/web/page_settings_content.py` -- duplicated `_CONFIG_CSS` and accordion/toggle script; retain settings controls while sourcing the same CDN CSS.
- `src/device/web/router.py`, `src/device/web/server.py` -- allowlisted route and response dispatch; read-only evidence that `/scan` and held `/connect` already exist.
- `tests/test_setup_http.py`, `tests/test_setup_candidate.py`, `tests/test_config_auth.py` -- update stale SPA/CSS assertions and add pure host checks for server-rendered setup flow and shared admin asset footprint.
- `_bmad-output/specs/spec-wifi-config/SPEC.md` and `override-trace.md` -- canonical requirements and rationale; no changes required for implementation.

## Tasks & Acceptance

**Execution:**
- `src/device/web/page_setup_content.py`, `src/device/web/setup_pages.py` -- render scan results and status states on the server, use native form/link navigation, and keep failure prefill semantics -- reduce setup allocation pressure while preserving the existing protocol.
- `src/device/web/page_login_content.py`, `src/device/web/page_settings_content.py` -- remove duplicated inline CSS and unnecessary JS, add the same minimal CSS-only CDN reference for station-online pages, and preserve labels, touch targets, accordion, and inert theme control -- avoid repeated page assets.
- `tests/test_setup_http.py`, `tests/test_setup_candidate.py`, `tests/test_config_auth.py` -- assert no setup fetch/DOM scan flow, native rescan/form behavior, escaped server-rendered SSIDs, and no duplicated admin CSS -- prevent regression at the HTML surface.

**Acceptance Criteria:**
- Given setup AP mode with scan results, when `GET /` is rendered, then the response contains a native escaped SSID `<select>`, Wi-Fi/admin fields, and a `POST /connect` form without client-side fetch or DOM-render code.
- Given an empty or failed scan, when the setup page is rendered, then it explains the state and exposes a plain `GET /` rescan link.
- Given a join failure or success, when the existing response renderer is called, then the server-rendered page shows the correct status, preserves SSID/admin prefill as specified, and clears Wi-Fi password.
- Given station-online login and settings pages, when either page is rendered, then both reference the same minimal CSS-only CDN asset, neither embeds `_CONFIG_CSS`, and no JS library or fetch is introduced.
- Given the updated host tests, when `uv run pytest` runs, then all relevant tests pass and no test treats host execution as device proof.

## Design Notes

The setup page must pay for scan results in the response, not in a browser-side JSON/DOM pipeline. Login/settings may reference a CDN only because they are reachable after station association; setup must never depend on WAN access. The exact small classless CSS provider is an implementation choice, but it must be shared and CSS-only.

## Verification

**Commands:**
- `uv run pytest` -- expected: all host tests pass.
- `rg -n "fetch\\(|_CONFIG_CSS|_LOGIN_JS|_SETTINGS_JS" src/device/web/page_setup_content.py src/device/web/page_login_content.py src/device/web/page_settings_content.py` -- expected: no setup fetch and no duplicated config CSS/script constants.
- `git diff --check` -- expected: no whitespace errors.
