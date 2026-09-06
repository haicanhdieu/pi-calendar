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
| Successful DNS/NTP stub | `PROOF:… success_dns_ntp` | PASS | SyncResult ok=True, utc DateTime present |
| Failed DNS stub | `PROOF:… fail_dns` | PASS | error_code='dns_fail' |
| Failed NTP stub | `PROOF:… fail_ntp` | PASS | error_code='ntp_fail' |
| Result-slot contention / saturation fatal | `PROOF:… result_slot_contention` | PASS | `FATAL:MAILBOX_SATURATION`; prior untouched |
| Stale / expired discard | `PROOF:… stale_expired_results` | PASS | expired_apply=False mismatch_apply=False |
| Retry sequencing | `PROOF:… retry_sequencing` | PASS | early=False retry=True second_id=7 |
| Soft reset recovery | `PROOF:… soft_reset` | PASS | follow_ok=True |
| Render continuity (poll while busy) | `PROOF:… render_continuity` + `poll_count=` | PASS | poll_count=22 |
| Sustained lock / memory iterations | `PROOF:… sustained_lock_memory` | PASS | failures=0; mem_free 89120→38336 |
| Suite summary | `PROOF:SUITE_SUMMARY passed=N total=9` | PASS | passed=9 total=9 |

### Device run log

```
2026-09-06 — Raspberry Pi Pico W / MicroPython v1.20.0-198-g0eacdeb1c (2023-06-13)
Port: /dev/cu.usbmodem1101
Transport: mpremote 1.29.0 (deploy src/ + exec run_proof)
Note: MicroPython 1.20 rejected adjacent/regular+f-string __repr__; fixed to .format() before pass.

PROOF:SUITE_BEGIN story-1-4-network-mailbox
PROOF:BEGIN success_dns_ntp
PROOF:PASS success_dns_ntp SyncResult(command_id=1, ok=True, utc=DateTime(year=2026, month=9, day=6, weekday=6, hour=12, minute=0, second=0), error_code=None)
PROOF:BEGIN fail_dns
PROOF:PASS fail_dns SyncResult(command_id=2, ok=False, utc=None, error_code='dns_fail')
PROOF:BEGIN fail_ntp
PROOF:PASS fail_ntp SyncResult(command_id=3, ok=False, utc=None, error_code='ntp_fail')
PROOF:BEGIN result_slot_contention
FATAL:MAILBOX_SATURATION result slot occupied; prior result untouched
PROOF:PASS result_slot_contention fatal=True prior_ok=True
PROOF:BEGIN stale_expired_results
PROOF:PASS stale_expired_results expired_apply=False mismatch_apply=False
PROOF:BEGIN retry_sequencing
PROOF:PASS retry_sequencing early=False retry=True second_id=7
PROOF:BEGIN soft_reset
PROOF:PASS soft_reset follow_ok=True
PROOF:BEGIN render_continuity
PROOF:MARKER poll_count=22
PROOF:PASS render_continuity polls=22
PROOF:BEGIN sustained_lock_memory
PROOF:MARKER mem_free_start=89120
PROOF:MARKER mem_free_end=38336
PROOF:PASS sustained_lock_memory failures=0 mem_free_start=89120 mem_free_end=38336
PROOF:SUITE_SUMMARY passed=9 total=9
PROOF:SUITE_ROW success_dns_ntp PASS
PROOF:SUITE_ROW fail_dns PASS
PROOF:SUITE_ROW fail_ntp PASS
PROOF:SUITE_ROW result_slot_contention PASS
PROOF:SUITE_ROW stale_expired_results PASS
PROOF:SUITE_ROW retry_sequencing PASS
PROOF:SUITE_ROW soft_reset PASS
PROOF:SUITE_ROW render_continuity PASS
PROOF:SUITE_ROW sustained_lock_memory PASS
PROOF:SUITE_END story-1-4-network-mailbox

NETWORK_PROOF_MODE restored to False after capture.
```

---

## Gate decision

| Outcome | Next step |
|---------|-----------|
| All device rows PASS | Story 1.4 → done; Story 1.5 may wire App NTP via this mailbox |
| Any critical FAIL / hang / corruption | Revise AD-8; **no** blocking Wi-Fi/NTP inside App/render loop |
| Host PASS + device PENDING | Story remains **blocked** awaiting user flash evidence |

**Current gate:** host PASS; device evidence **PASS** (9/9). Story 1.4 may be marked **done**; Story 1.5 may proceed.
