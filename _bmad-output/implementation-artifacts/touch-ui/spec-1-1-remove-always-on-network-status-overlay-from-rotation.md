---
title: 'Story 1.1: Remove always-on network status overlay from Rotation'
type: 'feature'
created: '2026-09-13'
status: 'done'
baseline_revision: 'fca9a1a3493d79b76a9ad0c5e99e94b4328030cc'
baseline_commit: 'fca9a1a3493d79b76a9ad0c5e99e94b4328030cc'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** The ambient Clock and Calendar rotation currently renders Setup AP SSID/gateway and station IP text continuously, making the default display less glanceable. Network state must remain available to the App for the later Settings surface.

**Approach:** Remove normal-rotation rendering of the network-status payload at the compositor boundary while retaining App event reduction and network status ownership. Preserve the existing Clock/Calendar drawing, cadence, and UNSYNCED badge behavior.

## Boundaries & Constraints

**Always:** Clock and Calendar renders must not emit Setup AP SSID/gateway or a station IPv4 address; the UNSYNCED badge remains the only status treatment and stays rendered after the base view. App must continue consuming setup/station events and retaining `kind`, `ssid`, and `ip` status data without importing device modules into pure/UI logic.

**Never:** Do not change rotation deadlines, Clock/Calendar content, pin assignments, network coordinator behavior, display-port ownership, or introduce Bar, Settings, touch interactions, or replacement network UI. Do not delete the retained App network-state boundary merely because its rotation rendering is removed.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Setup status during Clock rotation | Setup AP event with SSID and gateway | App retains status; Clock draw operations contain neither setup string nor gateway | Missing event data continues using existing App fallback values, but neither is drawn |
| Station status during Calendar rotation | Online station event with an IPv4 address | App retains station status; Calendar draw operations contain no address and remain a Calendar render | Missing IP retains existing clear/no-false-address behavior and produces no network text |
| Unsynced rotation | Unsynced time snapshot plus any retained network status | `UNSYNCED` remains drawn after the base view; no network overlay is drawn | No error expected |

</intent-contract>

## Code Map

- `src/ui/compositor.py` -- `UiCompositor.render()` currently derives a network key, invalidates on its change, and calls `draw_network_status_overlay()` after the UNSYNCED badge; this is the narrow rotation rendering seam to remove while preserving badge invalidation/rendering.
- `src/ui/components.py` -- defines the legacy network overlay drawing helper and its bottom-left layout constants; do not leave a reachable normal-rotation call path.
- `src/app.py` -- `_drain_network_events()`, `_apply_network_event()`, `_network_status()`, and `_render()` own reduction of coordinator events into retained `kind`/`ssid`/`ip`; preserve that state ownership while no longer passing it to ambient rotation rendering.
- `tests/test_app_network_overlay.py` -- existing host tests assert the superseded visible overlay behavior and provide event fixtures; replace/adjust them to prove retained state and the absence of setup/station text in Clock and Calendar output.
- `tests/test_clock_view.py` and `tests/test_calendar_view.py` -- existing compositor assertions establish the base-view and UNSYNCED badge contracts; use them as regression evidence without changing view content.
- `src/device/network/coordinator.py` -- event producer; read-only for this story because coordinator ownership is retained.

## Tasks & Acceptance

**Execution:**
- [x] `src/ui/compositor.py` and, only if made unreachable by the compositor change, `src/ui/components.py` -- remove the ambient network-status overlay render/invalidation path while preserving `draw_unsynced_badge()` as the draw-last status layer -- make Rotation glanceable without altering base views.
- [x] `src/app.py` -- stop supplying retained network status to Clock/Calendar rendering but preserve event reduction and the retained `kind`/`ssid`/`ip` state boundary -- keep data available for the later Settings story.
- [x] `tests/test_app_network_overlay.py` -- revise the obsolete visible-overlay tests to cover setup and station events on both rotation views, retained App status, and no emitted setup/gateway/IP text -- prove the external display behavior and retained state.
- [x] `tests/test_clock_view.py` and/or `tests/test_calendar_view.py` -- add only focused regression coverage if required to demonstrate that UNSYNCED still renders last while a status payload cannot produce network text -- protect the surviving compositor contract.

**Acceptance Criteria:**
- Given a Setup AP status event and a Clock rotation, when `App.step()` renders, then neither the setup SSID nor gateway appears in display text operations and App still retains setup `kind`, `ssid`, and `ip`.
- Given an online station event with an IP and a Calendar rotation, when `App.step()` renders, then the IP does not appear in display text operations, Calendar remains active, and App still retains station `kind`, `ssid`, and `ip`.
- Given an unsynced Clock or Calendar snapshot with retained network status, when the compositor renders, then the base view and `UNSYNCED` badge remain visible with the badge rendered after base content and no network status text.
- Given status changes or clearing between renders, when ambient rotation redraws, then no obsolete overlay-clearing/invalidation behavior is required and no stale setup/station text is emitted.

## Spec Change Log

## Review Triage Log

### 2026-09-13 — Review pass
- verdicts: 6 findings — high 0, medium 0, low 4, false 2, maybe-false 0
- findings:
  - `[false]` `[reject]` Retained station status could expire before Settings captures it — `STATION_IP_DISPLAY_MS` is currently `None`, so `_expire_station_ip_overlay()` cannot clear the retained status; the current behavior preserves it across later renders.
  - `[low]` `[reject]` `STATION_IP_DISPLAY_MS` has stale overlay-oriented comments — the dormant constant has no runtime effect while set to `None`; removing or redesigning the historic timed-status policy is beyond the direct Rotation rendering removal.
  - `[false]` `[reject]` The wifi-config PRD still requires on-screen address text — the active touch-ui architecture explicitly overrides wifi-config's continuous-display clause in AD-1 while retaining its event-reduction rule.
  - `[low]` `[reject]` The compositor test does not assert a removed `status` keyword is rejected — the public behavior is proven through App-to-display output, and `UiCompositor.render()` no longer accepts or reads a status payload.
  - `[low]` `[patch]` Later Clock/wrap renders lacked retained-status assertions — added assertions that station status remains unchanged after those renders in `tests/test_app_network_overlay.py`.
  - `[low]` `[patch]` Badge-hidden Rotation lacked network-text coverage — added synced Clock and Calendar cases that prove retained setup/station data is not drawn in `tests/test_app_network_overlay.py`.

## Design Notes

Removing the call at the compositor boundary is deliberately narrower than changing coordinator events or App's retained state. Later Settings work needs an entry-time network snapshot, so the producer and reducer remain intact even though Rotation no longer consumes the display payload.

## Verification

**Commands:**
- `uv run pytest tests/test_app_network_overlay.py tests/test_clock_view.py tests/test_calendar_view.py` -- expected: all affected rendering and state tests pass.
- `uv run pytest` -- expected: complete host suite passes with no device imports introduced into pure logic.

## Auto Run Result

Removed the ambient network-status overlay from the Clock/Calendar compositor path while preserving App-owned reduced network state for the later Settings surface.

- `src/app.py` — retains network events/status but no longer supplies them to Rotation rendering.
- `src/ui/compositor.py` and `src/ui/components.py` — remove network-overlay composition and its obsolete drawing helper.
- `tests/test_app_network_overlay.py` — proves setup/station text is absent for synced and unsynced Clock/Calendar rotation while retained status survives.
- `sprint-status.yaml` — records Story 1.1 in progress during the implementation run.

Review: two low findings patched; two low findings rejected as non-actionable for this story; two findings refuted by the active configuration/architecture. No items deferred. Follow-up review recommendation: false (two low patches, no high patch).

Verification: `uv run pytest tests/test_app_network_overlay.py tests/test_clock_view.py tests/test_calendar_view.py` passed (43 tests); `uv run pytest` passed (301 tests).

Residual risk: host tests validate the rendering contract only; on-device display behavior still requires a flashed-device check.
