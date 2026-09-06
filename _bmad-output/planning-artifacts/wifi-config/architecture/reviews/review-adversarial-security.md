# Adversarial Security Seam Re-review

Reviewed: 2026-09-06  
Artifact: `wifi-config/architecture/ARCHITECTURE-SPINE.md` (final AD-3/AD-5)

## Result

**Pass — all 12 previously identified KDF, record-encoding, and session seams
are closed. No remaining blocker was found in the focused recovery re-review.**

| Concern | Closure evidence |
| --- | --- |
| Cooperative KDF | A single bounded `KdfJob`, a global 200-round tick budget, busy admission response, correlation ID, terminal outcomes, and plaintext discard are explicit. |
| Record schema | Version, JSON field types, UTF-8/bounds, canonical lower-hex verifier material, and unsupported-record handling are explicit. |
| Record recovery | A stale backup is removed before rotation; valid current wins; absent current restores valid backup; invalid current is quarantined before backup restore; occupied quarantine preserves both records and enters setup. |
| Sessions | Capacity, expiry predicate, renewal event, full-table response, invalid-cookie clearing, strict base64url IDs, and password-change commit/invalidation ordering are explicit. |

The AD-3 recovery sequence now gives independently built store units the same
observable recovery behavior across the previously ambiguous current/backup
states. Flashed-device proof of filesystem semantics remains required by AD-7,
but that is an implementation-evidence obligation rather than an architecture
seam blocker.
