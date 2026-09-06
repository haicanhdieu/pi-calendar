# Final Adversarial Seam Review

Reviewed: 2026-09-06  
Artifacts: `wifi-config/architecture/ARCHITECTURE-SPINE.md` and the referenced `pico-w-calendar-clock/architecture/ARCHITECTURE-SPINE.md`  
Lens: ownership and independently implemented integration seams  
Scope: critical and high-severity findings only

## Verdict

**No critical ownership contradiction remains.** The Wi-Fi feature is now the
authoritative owner of WLAN, HTTP, provisioning, and persisted settings; the
core spine delegates those concerns and retains only App/RTC/time-trust and
display integration. The former worker-versus-cooperative-owner conflict is
removed. The setup browser transaction now has one owner and an explicit
AP/socket ordering, so it no longer conflicts with the UX result requirement.

One high-severity provisioning-transaction gap remains before implementation.

## Findings

### H1 — Persistence failure after association has no required terminal path

**Evidence:** Wi-Fi AD-2 defines association success as the point at which the
candidate is persisted, response is flushed, and AP is torn down. Wi-Fi AD-3
requires a power-loss-safe settings commit, but neither spine defines what the
coordinator emits or how it recovers when that commit fails after the STA has
associated. The parent core spine correctly delegates settings persistence to
this feature, so it cannot supply the missing behavior.

**Failure construction:** A coordinator associates to the selected network and
then `SettingsStore.commit()` fails (for example, flash write/rename failure).
One compliant implementation can report setup success and remain online with
non-durable credentials; another can disconnect STA and restart setup AP; a
third can retain the AP but leave the request without a terminal outcome. These
give different next-boot and browser behavior while respecting the current
rules.

**Required binding:** Make persistence failure an explicit terminal setup
outcome: preserve the AP and originating connection through its response,
discard the candidate secrets after responding, disconnect any uncommitted STA
association, emit a named `settings_commit_failed` event, and return to the
retryable setup form. Only a successful durable commit may emit the connection
success event, flush its response, then close clients and deactivate AP.

## Confirmed Seam Ownership

- `NetworkCoordinator` exclusively owns WLAN/AP/STA and HTTP socket lifecycle;
  core NTP accesses it only through commands/events.
- `App` exclusively reduces network outcomes into time trust and TFT status;
  no network or web component writes product/display state.
- `SettingsStore` exclusively owns the ignored credential/settings record;
  core configuration and pure modules cannot import it or legacy `secrets.py`.
- The Wi-Fi feature spine is authoritative for these concerns; the core spine
  references it without re-deciding their behavior.

No other critical or high-severity seam finding was identified.
