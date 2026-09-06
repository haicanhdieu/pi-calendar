# Final good-spine rubric review — Wi-Fi Provisioning & Admin Config

**Verdict: pass.** The Wi-Fi feature spine is now the authoritative contract for
WLAN ownership, provisioning, local HTTP configuration, and device-local
settings. The core clock spine references that contract for those concerns and
retains only generic clock/rendering integration rules.

## Review basis

- Target: `../ARCHITECTURE-SPINE.md` (final, 2026-09-06)
- Delegating reference: `../../../pico-w-calendar-clock/architecture/ARCHITECTURE-SPINE.md`
- Feature inputs: `../../prds/prd.md`, `../../ux-designs/DESIGN.md`, and
  `../../ux-designs/EXPERIENCE.md`
- Mechanical gate: `lint_spine.py` passed with zero findings.

## Authority-direction check

| Concern | Authoritative source | Evidence |
| --- | --- | --- |
| WLAN/socket lifecycle and concurrency | Wi-Fi spine AD-1/AD-2 | Core AD-8 explicitly names the Wi-Fi `NetworkCoordinator` and says provisioning, AP/STA transitions, and HTTP are exclusively owned by this feature. |
| Wi-Fi/admin credential persistence | Wi-Fi spine AD-3 | Core AD-9 delegates the ignored `SettingsStore` record and legacy `/secrets.py` migration to this spine; core modules may not import either. |
| Wi-Fi operational proof | Wi-Fi spine AD-7 and Deferred | Core's capability map and Deferred section point to this feature rather than restating AP/STA or persistence decisions. |
| Core integration | Core AD-2, AD-3, AD-8, AD-12 | `App` remains the product/time/display-state writer; it interacts with the feature through typed commands/events. This is an integration constraint, not competing Wi-Fi ownership. |

## Checklist results

| Rubric item | Result |
| --- | --- |
| Real feature-level divergence points fixed | Pass — single coordinator, explicit modes, settings boundary, bounded HTTP, auth, and display/event seam are all bound. |
| Parent/core relationship | Pass — prior coordinator and credential conflicts are reconciled upstream by delegation to the Wi-Fi spine. |
| PRD/UX coverage | Pass — setup fallback, 15-second join, three-failure fallback, on-screen addresses, LAN login/config, and single-theme stub map to rules. |
| Deferred items safe | Pass — KDF choice, session limits, AP/STA target proof, migration policy, and operational proof have explicit revisit conditions. |
| Brownfield compatibility | Pass — the cooperative coordinator ratifies the observed code path; no incompatible worker model remains in core. |
| Operational/environmental envelope | Pass — deployment, ignored settings, bounded memory/HTTP, host versus flashed-device proof, and local-network boundary are explicit. |

## Non-blocking editorial note

`Deferred` currently contains an adopted statement declaring this spine
authoritative. It is accurate, but it would read more cleanly as a short
**Authority** section near Design Paradigm in a future editorial pass. This is
not a build blocker: the core's explicit AD-8/AD-9 delegation is the operative
authority proof.
