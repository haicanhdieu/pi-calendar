# Good-spine rubric review — Wi-Fi Provisioning & Admin Config

**Verdict: concerns — one internal recovery-policy conflict remains.** The
updated canonical record, KDF-job, and session rules successfully remove their
former cross-module ambiguity. The backup-recovery rule needs one final choice
before implementation.

## Re-reviewed AD-3 / AD-5 delta

| Area | Result | Evidence |
| --- | --- | --- |
| Canonical settings record | Pass | AD-3 fixes JSON version, field types, encodings, lengths, verifier version, and invalid-record behavior. |
| KDF work and secret lifetime | Pass | One correlated `KdfJob`, fixed busy admission, 200-round global tick budget, terminal result codes, and bytearray wiping give router/coordinator/store units one contract. |
| Session semantics | Pass | AD-5 fixes ID entropy and exact base64url representation, strict decoding, expiry comparison, sliding-renewal trigger, full-table behavior, invalid-cookie response, and password-change ordering. |

## Finding

### High — invalid/unsupported-current recovery conflicts with preservation

AD-3 says unknown, malformed, or unsupported records are preserved and never
deleted. It also says that, if the current record is not valid, a valid backup
is restored. Restoring the backup as the current record necessarily replaces
that invalid/unsupported current record unless the store uses a separate
quarantine path, which is not specified.

**Required resolution:** choose and bind one recovery behavior: either (1)
rename the invalid/unsupported current record to a stated quarantine filename
before promoting the backup, or (2) do not promote a backup when a current
record exists but is invalid/unsupported. Define the error/result code as well.
This keeps power-loss recovery reproducible and honors the no-deletion promise.

## Remaining rubric checks

- `lint_spine.py --workspace` passes with zero mechanical findings.
- The KDF and session decisions no longer belong under Deferred and are
  implementation-ready.
- All other previously reviewed ownership, parent-invariant, capability, and
  operational-envelope checks remain passing.
