# Technology Currency and Security-Policy Review

**Artifact reviewed:** `../ARCHITECTURE-SPINE.md`  
**Review date:** 2026-09-06  
**Scope:** MicroPython v1.29.0 RP2 crypto/entropy/tick APIs and the now-chosen
PBKDF2/session policy  
**Verdict:** **PASS — with target preflight evidence still required**

## Evidence

- MicroPython v1.29 documents `hashlib.sha256`, `update`, and `digest`; SHA-256
  is described as cryptographically suitable. The v1.29 RP2 configuration does
  not override `MICROPY_PY_HASHLIB_SHA256`, whose v1.29 default is enabled.
  Thus a small, project-owned HMAC-SHA256/PBKDF2 implementation is compatible
  with the pinned firmware. Do **not** assume CPython conveniences such as
  `hashlib.pbkdf2_hmac`, `hmac`, or `compare_digest`: they are not part of this
  documented contract.
- RP2 v1.29 explicitly enables `MICROPY_PY_OS_URANDOM`; the documented
  `os.urandom(n)` returns bytes and uses a hardware RNG whenever possible. A
  16-byte salt and 16-byte opaque session identifier therefore have the required
  128 bits of nominal random input, pending a flashed-target smoke test.
- `ticks_ms` values wrap and MicroPython requires `ticks_add`/`ticks_diff` for
  deadlines. AD-5's 15-minute sliding idle timeout is safe only when the
  injected tick port follows those semantics; ordinary integer comparison or
  subtraction is not safe across wrap.
- The v1.29 `binascii` surface provides ordinary RFC 3548 Base64, not a
  documented URL-safe helper; its decoder also ignores invalid characters.
  AD-5 remains compatible because it requires strict canonical decoding, but
  the implementation must validate the 22-character Base64url alphabet and length
  before translating `-_` to `+/`, adding the two required padding characters,
  and calling `a2b_base64`. It must not treat `a2b_base64` alone as validation.
- v1.29 documents `os.rename` and `os.sync`; RP2 v1.29 explicitly enables
  `MICROPY_PY_OS_SYNC`. The revised temp → current/backup recovery protocol
  consequently uses supported calls. The documentation does not specify FAT
  rename/power-loss semantics, so AD-7's flashed-target replacement/recovery
  evidence remains necessary.

Primary sources: [MicroPython v1.29 `hashlib`](https://docs.micropython.org/en/v1.29.0/library/hashlib.html), [v1.29 `os`](https://docs.micropython.org/en/v1.29.0/library/os.html), [v1.29 `time`](https://docs.micropython.org/en/v1.29.0/library/time.html), [RP2 v1.29 configuration](https://github.com/micropython/micropython/blob/v1.29.0/ports/rp2/mpconfigport.h), and [v1.29 defaults](https://github.com/micropython/micropython/blob/v1.29.0/py/mpconfig.h).

Cookie encoding source: [MicroPython v1.29 `binascii`](https://docs.micropython.org/en/v1.29.0/library/binascii.html).

## Policy assessment

`pbkdf2-sha256-v1` is a stable, self-describing record: 20,000 iterations,
16-byte salt, 32-byte verifier, and a verifier version permit a future KDF
upgrade without accepting an ambiguous record. The 200-round cooperative slice
requires 100 ticks per full derivation and keeps password work within the
architecture's rendering rule. It must retain PBKDF2 state between ticks and
reject a concurrent login/password-change job rather than starting a second
derivation.

The revised four-entry, RAM-only session table, expiry-before-admission rule,
reject-on-full behavior, `ticks_diff` expiry predicate, `ticks_add` renewal,
strict 22-character Base64url session IDs, and all-but-current invalidation are
defined and compatible. `HttpOnly`, `SameSite=Strict`, and `Path=/` are feasible
attributes. Their protection is intentionally limited by the explicitly accepted
HTTP-only local-LAN/open-AP boundary: a network observer there can still capture
a cookie. The documented v1 scope also excludes rate limiting, so this is an
accepted product risk, not an omitted decision.

## Required target evidence

Before credentials or sessions are accepted on hardware, flash the pinned
firmware and record a preflight that imports `hashlib`/`os`/`binascii`, executes
`hashlib.sha256(b"").digest()`, obtains 16 bytes from `os.urandom`, round-trips
a valid Base64url session ID while rejecting malformed variants, verifies the
tick-port wrap-safe expiry test, and exercises the current/backup recovery
sequence across reset points. This confirms the released image rather than
merely the upstream source configuration. The repository's currently observed
connected target remains MicroPython v1.20, so it cannot stand in for this
v1.29 proof.

## Findings

None that block sprint planning. The updated AD-3/AD-5 clauses resolve the
prior KDF/session-policy ambiguity and use v1.29-compatible primitives; the
listed preflight is an implementation/on-device acceptance gate, consistent
with AD-7.
