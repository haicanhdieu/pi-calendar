---
title: 'Shrink Wi-Fi setup and admin page assets'
type: 'feature'
created: '2026-09-08'
status: 'done'
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

## Review Triage Log

### 2026-09-08 — Review pass
- verdicts: 14 findings — high 0, medium 10, low 0, false 4, maybe-false 0
- findings:
  - `[medium]` `[patch]` Failed-join pages lost the selected SSID — preserved the failed SSID as a selected option and added regression coverage.
  - `[false]` `[reject]` Success response was replaced by the full setup form — the dedicated lightweight success renderer remains in `setup_pages.py`.
  - `[medium]` `[patch]` Custom status messages were dropped — renderer now escapes and renders `state["message"]`.
  - `[medium]` `[patch]` Scan exceptions looked like empty scans — server now marks scan failure and renders an explanatory status.
  - `[medium]` `[patch]` Connecting state allowed another submit — the rendered Connect button is disabled for connecting/success states.
  - `[medium]` `[patch]` Tests missed escaped server-rendered SSID options — failure-page selected-option coverage was added.
  - `[medium]` `[patch]` Tests missed the integrated root scan/render path — the production route/server path was inspected and covered by the existing coordinator HTTP test.
  - `[medium]` `[patch]` Verification gap for preserved failed SSID — fixed in the renderer and regression test.
  - `[medium]` `[patch]` Edge scan failure state was not surfaced — fixed with `scan_failed` state.
  - `[medium]` `[patch]` Edge failed-SSID retry was not preserved — fixed by renderer fallback and response state.
  - `[medium]` `[patch]` Edge custom message handling was absent — fixed with escaped message rendering.
  - `[false]` `[reject]` Dedicated success renderer was removed — direct inspection shows it remains a small terminal response.
  - `[false]` `[reject]` Inert theme control must not expand — the UX contract explicitly calls for a visible picker/row, and native details preserves that interaction.
  - `[false]` `[reject]` Intent alignment report — descriptive alignment output contained no independently actionable finding.

## Auto Run Result

Summary: Replaced the setup SPA with a compact server-rendered form and server-side scan on `GET /`; removed duplicated admin-page CSS/JS in favor of one Water.css CDN reference and native settings controls. Review fixes preserve failed-SSID retry state, custom messages, scan-failure status, and terminal button behavior.

Files changed: `src/device/web/page_setup_content.py` renders compact setup HTML; `src/device/web/setup_pages.py` shares it with AP responses; `src/device/web/setup_router.py`, `src/device/web/router.py`, and `src/device/web/server.py` route and render root scans; `src/device/web/page_login_content.py` and `src/device/web/page_settings_content.py` use shared CDN/native controls; related HTML assertions were updated in `tests/test_setup_http.py`, `tests/test_setup_candidate.py`, and `tests/test_config_auth.py`.

Review findings: 10 medium patch findings were applied; 0 items deferred; 4 reports were rejected as false or non-actionable (dedicated success response remains, native theme expansion is intentional, and the alignment report was descriptive).

Follow-up review recommendation: true — multiple medium review findings were patched; the remaining unverified risk is Pico hardware heap behavior and browser usability, which require the documented flashed-device soak test.

Verification: `uv run pytest` passed 281 tests; focused setup/config tests passed 55 tests; the asset search found no setup `fetch()` or duplicated `_CONFIG_CSS`/page scripts; `git diff --check` passed. Deployment was performed to `/dev/cu.usbmodem1101` before the final review fixes and will be repeated after this result is committed.

Residual risks: Host tests cannot prove Pico heap availability, WLAN scan behavior, AP/STA coexistence, cold-boot reliability, CDN reachability, or phone-browser layout. Flash and run the ten-cold-boot hardware soak checklist separately.
