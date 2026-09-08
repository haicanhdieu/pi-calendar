# Override trace: wifi-config PRD/EXPERIENCE.md vs. this spec

This spec amends behavior already implemented under the `wifi-config` PRD
(`_bmad-output/planning-artifacts/wifi-config/prds/prd.md`) and its UX
companion (`_bmad-output/planning-artifacts/wifi-config/ux-designs/EXPERIENCE.md`).
Recorded here so the override is traceable, not silent.

## What the original intent actually said

`EXPERIENCE.md` line 14: "No UI framework assumed — plain HTML/CSS/minimal JS,
since this is served by the Device's own limited web server, not a
build-tooled SPA."

The shipped implementation (`src/device/web/page_setup_content.py`, ~4.3KB JS
implementing a fetch-based scan/render/submit SPA-like flow) is itself a
drift from that stated intent — not something this spec introduces. **CAP-1
restores the original documented intent; it does not override it.**

## What actually changes vs. the shipped implementation

| EXPERIENCE.md requirement | Shipped behavior (being changed) | CAP-1 behavior (this spec) |
|---|---|---|
| Manual, non-auto "Rescan" action (line 59) | Fetch-based rescan, no page reload | Plain link, full-page reload back to `GET /` — still manual, still non-auto |
| Status banner during connecting/failure (lines 48-50) | Client JS renders banner in place | Server re-renders the page with the banner already implemented in `response_join_failure`/`response_join_success` (`src/device/web/pages.py`) |
| Form fields retain values on failure — Wi-Fi password cleared, admin password kept (line 50) | Client JS preserves in-memory state | Server-side prefill via the existing `response_join_failure(ssid, admin_password)` mechanism — same behavior, different transport |
| No auto-navigate away until success/failure known (line 49) | Client JS holds the current screen | Server holds the request (existing candidate-join flow in `coordinator.py`) and only responds once resolved — same guarantee |
| `aria-live` announcements on status banner (line 65) | Client-rendered banner carries `aria-live` | Server-rendered banner markup carries the same `aria-live` attribute — unchanged |

**The one real behavior delta:** interactions that previously updated in
place without a page reload (rescan, submit) now cause a visible full-page
reload. This is the deliberate tradeoff CAP-1 makes for on-device memory
reliability, and is the only place this spec's outcome differs from
EXPERIENCE.md's implied (though not explicitly mandated) no-reload feel.

## Recommendation for the source documents

Once CAP-1/CAP-2 ship, `EXPERIENCE.md` line 14 and the setup-page mock
(`mockups/key-setup-ssid.html`, `mockups/key-setup-admin.html`) should be
updated to reflect the full-page-reload interaction model, so the UX doc and
the shipped device stay in sync. Not done as part of this spec — flagged for
whoever implements CAP-1 to follow up on.
