# Proof 1.4 — Nonblocking network mailbox (AD-8)

**Story:** 1-4-prove-the-nonblocking-network-boundary-on-hardware  
**Spec:** `spec-1-4-prove-the-nonblocking-network-boundary-on-hardware.md`  
**Harness:** `src/device/network/proof.py` (gated by `config.NETWORK_PROOF_MODE`)

This artifact **separates** host protocol verification from flashed-device
observation. Device rows stay **PENDING** until a human flashes the Pico W and
records serial markers. Do not invent on-device results.

---

## Host Results

| Check | Command / scope | Result | Notes |
|-------|-----------------|--------|-------|
| Pure mailbox import | `uv run python -c "from src.device.network.mailbox import Mailbox, SyncCommand, SyncResult"` | PASS | 2026-09-06 post-review; import ok |
| Pytest (full suite incl. mailbox) | `uv run pytest` | PASS | 70 passed in 0.06s (2026-09-06 post-review) |
| AST purity (`mailbox.py`) | Covered by `tests/test_mailbox.py` | PASS | mailbox tests ban `machine` / `network` / `ntptime` / `_thread` |
| `NETWORK_PROOF_MODE` default | `tests/test_config_hardware_defaults.py` | PASS | pinned False so product Clock boot is default |

### Host run log

```
2026-09-06 post-review
uv run pytest → 70 passed in 0.06s
uv run python -c "from src.device.network.mailbox import Mailbox, SyncCommand, SyncResult" → ok
```

---

## Device Observation (user flash required)

**Flash procedure:**

1. Set `NETWORK_PROOF_MODE = True` in `src/config.py`.
2. Deploy `main.py` + `src/` to the Pico W (same layout as product).
3. Open a serial console; reboot the device.
4. Expect `PROOF:SUITE_BEGIN story-1-4-network-mailbox` and per-scenario
   `PROOF:BEGIN` / `PROOF:PASS` or `PROOF:FAIL` markers.
5. Record each row below. Set `NETWORK_PROOF_MODE = False` before returning to
   product Clock boot.
6. **Do not** start Story 1.5 NTP integration until every critical row is PASS
   (or AD-8 is revised — never a blocking-App fallback).

| Scenario | Serial marker | Result | Operator notes |
|----------|---------------|--------|----------------|
| Successful DNS/NTP stub | `PROOF:… success_dns_ntp` | PENDING | |
| Failed DNS stub | `PROOF:… fail_dns` | PENDING | |
| Failed NTP stub | `PROOF:… fail_ntp` | PENDING | |
| Result-slot contention / saturation fatal | `PROOF:… result_slot_contention` | PENDING | Expect `FATAL:MAILBOX_SATURATION` |
| Stale / expired discard | `PROOF:… stale_expired_results` | PENDING | |
| Retry sequencing | `PROOF:… retry_sequencing` | PENDING | |
| Soft reset recovery | `PROOF:… soft_reset` | PENDING | |
| Render continuity (poll while busy) | `PROOF:… render_continuity` + `poll_count=` | PENDING | Render thread must keep polling |
| Sustained lock / memory iterations | `PROOF:… sustained_lock_memory` | PENDING | |
| Suite summary | `PROOF:SUITE_SUMMARY passed=N total=9` | PENDING | |

### Device run log

```
(date / firmware / serial excerpt — fill after user flash; leave empty until then)
```

---

## Gate decision

| Outcome | Next step |
|---------|-----------|
| All device rows PASS | Story 1.4 → done; Story 1.5 may wire App NTP via this mailbox |
| Any critical FAIL / hang / corruption | Revise AD-8; **no** blocking Wi-Fi/NTP inside App/render loop |
| Host PASS + device PENDING | Story remains **blocked** awaiting user flash evidence |

**Current gate:** host PASS; device evidence **PENDING** (agent environment cannot flash). Parent should set sprint status to `blocked` awaiting user-run flash.
