# Adversarial Compatibility Review

Reviewed: 2026-09-06  
Artifact: `ARCHITECTURE-SPINE.md` (Wi-Fi Provisioning & Admin Config)  
Lens: independently implemented downstream units that follow the written rules

## Verdict

**Not yet a safe build substrate.** The spine has a clear ownership intent, but three blocking seams permit compliant units that cannot work together. Resolve the parent-network ownership conflict and specify the setup-submit lifecycle before implementation. The remaining findings should be bound as contracts rather than left to individual route/coordinator implementations.

## Findings

### C1 — The feature's WLAN owner contradicts the inherited WLAN owner

**Evidence:** Parent AD-8 binds one isolated network worker as owner of WLAN, DNS, and NTP. This spine inherits AD-8, but AD-1 makes `NetworkCoordinator` the sole owner of every WLAN interface and has `main.py` call `tick()` in the application loop. AD-2 also makes this coordinator perform station joins and STA scans.

**Compatible-looking independent implementations:**

- The core-clock unit preserves parent AD-8: a worker owns `network.WLAN(STA_IF)` for reconnect/NTP and consumes its mailbox.
- The provisioning unit obeys feature AD-1: the main-loop coordinator owns that same STA interface for scan/connect/setup fallback.

Both units obey their local rule; together they race the same singleton WLAN handle and disagree about whether network work may run on the application thread. Alternatively, a builder can remove the worker to honor feature AD-1, silently violating inherited AD-8 and regressing clock isolation.

**Required binding:** Amend either parent AD-8 or feature AD-1/AD-2 to name one unified network owner and its execution model. Define how NTP requests, provisioning scans, joins, disconnects, and AP activation are serialized; the other side must use a typed command/result port and must not retain a WLAN handle.

### C2 — Setup submission necessarily destroys the browser exchange that UX requires

**Evidence:** AD-2 requires a submitted candidate to deactivate the AP before the station attempt, and says every transition first closes HTTP client sockets. The UX requires that same setup page to show `Connecting…`, then either a success or a failed-join message while retaining the selection. A phone reaches that page over the AP, so closing its socket and dropping the AP cuts its only transport before either terminal result exists.

**Compatible-looking independent implementations:**

- A coordinator closes all clients, disables AP, performs the 15-second join, and emits a join result, exactly as AD-2 says.
- A setup-page handler follows the UX contract by waiting for a terminal result and rendering success/failure into its existing HTTP response.

The handler cannot receive the event or send the response after the required close. A more literal streaming implementation either holds a socket that AD-2 requires closed, or claims success before association succeeds. On failure a new AP connection is possible, but the user has no specified route/state/token by which it can retrieve the failed candidate/result; the required retained form cannot be reconstructed without retaining secrets.

**Required binding:** Choose and document one observable protocol. For example, keep AP and the originating connection alive through the station attempt (if firmware proof permits), or deliberately make submission terminal: return a pre-transition acknowledgement, then require reconnect/reload and show a non-secret result identified by a short-lived opaque attempt ID. Specify when candidate secrets are discarded, how failed retries work, and the exact AP/HTTP close ordering. Align the UX flow to that choice.

### C3 — Router-to-provisioning control and result delivery are undefined

**Evidence:** The only declared command direction is `App → coordinator`; AD-4 also assigns `src/device/web/` “form-to-command mapping.” No command schema, recipient, queue/slot ownership, correlation ID, acceptance response, or event delivery semantics are defined for a browser POST. AD-1 prohibits handlers from mutating `AppState`, and AD-2 requires the coordinator to own transitions.

**Compatible-looking independent implementations:**

- The router validates `POST /setup`, creates `ProvisionCommand`, and sends it to App because the declared command direction says App is the coordinator's only caller.
- The coordinator implementer exposes only the App-originated command port and has no mechanism for a router-originated command.

Even if both add a queue, independently selected behavior for a second POST (replace active candidate, reject it, or queue it), disconnect during join, and event correlation produces different externally visible setup behavior.

**Required binding:** Define the web-to-coordinator ingress as a named port (or explicitly route it through App) with immutable command and terminal-event schemas, an attempt ID, capacity/overflow behavior, and ordering. State which layer authorizes setup versus config mutations and which layer owns conversion from decoded form fields to the validated candidate.

### H1 — Persistence and join-result sequencing leave first setup ambiguous

**Evidence:** AD-2 says the submitted candidate “persists only after success.” AD-3 says the persisted record is complete and includes the verifier. The PRD and UX describe one setup submission that supplies both Wi-Fi and admin passwords. The spine never specifies the volatile candidate shape, whether a successful association is enough to commit, what happens if the atomic write fails after association, or what event/App mode results.

**Failure construction:** A networking unit reports `station_connected` as success and tears down AP. A store unit's replace fails due to flash I/O. If the coordinator stays online, it has working but non-durable credentials; after reboot it enters setup. If it treats persistence failure as join failure, it needs an AP restart and must communicate that distinct result. Both obey the current wording.

**Required binding:** Make `commit(candidate)` part of the provisioning transaction state machine: enumerate association failure, persistence failure, and commit success terminal events; define cleanup and whether an uncommitted station association is disconnected before setup resumes.

### H2 — The HTTP/form contract is too underspecified for separately built UI and server

**Evidence:** AD-4 permits form POST and fixed routes but names neither routes nor field names nor response status/redirect behavior. It does not bind percent-decoding character set/error behavior, duplicate-field policy, maximum decoded SSID/password lengths, or which modes expose scan/rescan. The UX depends on a two-screen presentation with one final submit, rescan, generic login rejection, and protected config redirects.

**Failure construction:** A static/minimal-JS unit posts UTF-8 `ssid` and `admin_password` to `/setup`; a router independently accepts `/api/provision` and Latin-1-decodes body values. Both meet the route-table/form requirements, but non-ASCII SSIDs cannot provision. Another valid server chooses `401` for unauthenticated `/config`; a page assumes the PRD-required redirect to login.

**Required binding:** Add a concise route and form contract (method, mode, fields, decoded encoding/limits, result status/Location or body) and make the pure validator own normalization/length rules shared by router and store.

### M1 — Bounded sessions have no exhaustion or expiration behavior

**Evidence:** AD-5 requires a bounded in-memory table but does not bind its capacity, insertion policy, full-table response, invalid-session response, or expiry. The UX says a session lasts until browser close or an unspecified idle timeout; server memory cannot observe browser closure.

**Failure construction:** One auth unit rejects login once its table is full; another evicts the oldest session. Both obey “bounded,” but the resulting user behavior and security posture differ. With no expiry, abandoned browser-session IDs accumulate until that divergence is reached.

**Required binding:** Pick a small table capacity and deterministic full-table policy, and either bind an idle/absolute expiry or explicitly define safe eviction. Return the same unauthenticated response for expired/unknown IDs.

### M2 — Applying persisted color configuration has no ownership/event seam

**Evidence:** AD-3 persists `color_scheme`; the web layer maps settings forms; App alone owns product/display state. No event or read boundary states when App loads/applies a successful config change or how it keeps its snapshot coherent with an atomic store write.

**Failure construction:** The config handler writes the store and returns success, while App retains its boot-time theme snapshot; a different App unit polls and redraws immediately. Both honor the listed owners, yet differ on visible outcome and future themes.

**Required binding:** For the v1 no-op, state that the value is stored only as a validated future-setting and does not alter render state. Before a second theme ships, add an App-directed `settings_changed` event/version contract.

## Positive Compatibility Coverage

The following seams are meaningfully constrained: secret persistence is centralized; expected network failures use state transitions rather than exceptions; device imports are separated from host-testable policy; and TFT status has a single App-owned path. The findings above do not dispute those decisions; they identify connections that the current rules leave incompatible.

