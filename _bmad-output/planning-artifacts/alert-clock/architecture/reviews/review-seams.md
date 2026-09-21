# Alert Clock Spine — Adversarial Seam Review

**Scope:** `ARCHITECTURE-SPINE.md` draft, PRD/UX inputs, inherited core,
Wi-Fi-config, touch-ui spines. Review asks whether independently built domain,
App/UI, web/settings, device units interoperate without extra decisions.

## Verdict

**Changes required before implementation.** Spine establishes one App-owned
occurrence and separates civil from monotonic time. Five load-bearing seams
remain unspecified, including two inherited-spine conflicts.

## Findings

### S1 — Settings schema conflicts with inherited Wi-Fi record contract

**Severity:** blocker

Wi-Fi AD-3 binds `SettingsStore` to canonical `settings_version: 1` JSON
record with enumerated fields; malformed/unknown records are unconfigured.
Alert AD-4 requires same record own `alerts`, `postpone_delay_minutes`,
`pending_postponed_occurrence`, but supplies no compatible version/migration
rule. Wi-Fi builder can correctly reject new fields; alert builder can
correctly add them. They cannot both satisfy present rules.

**Needed invariant:** new canonical record version (or explicitly allowed
extension shape), reader migration from v1, backup/rejection behavior, old
firmware behavior for newer records. Update Wi-Fi authority spine if AD-3
changes; alert spine cannot locally weaken it.

### S2 — Web-save versus App single-writer ownership is undefined

**Severity:** blocker

Alert paradigm says App commits persisted settings and is sole live alert-state
writer. Wi-Fi design places authenticated HTTP/router and `SettingsStore`
under coordinator, and requires handlers not mutate `AppState`. Map places
CRUD in web + store but declares neither command/event contract nor commit
owner.

Two compliant builds diverge: router writes store directly and App discovers
change later; App receives command, validates/commits, then emits result. They
differ during active occurrence, commit failure, and future due-detection
visibility.

**Needed invariant:** choose flow, correlation/result shape, atomic visibility
boundary. If App commits, use bounded authenticated `NetworkCommand` /
`NetworkEvent` flow. If coordinator commits, App reloads/reduces only versioned
snapshot and never writes alert settings.

### S3 — Active/postponed occurrence can resurrect deleted one-time alert

**Severity:** blocker

AD-3 keeps active/postponed occurrence alive after base-alert deletion. FR-2
requires one-time alerts disable at terminal resolution. No rule states how
terminal completion merges with later web record.

Example: one-time `wake` rings; admin deletes `wake`; occurrence auto-stops.
App holding old settings snapshot can persist `wake.enabled = false`, recreating
deleted `wake`. Another builder leaves deletion intact. Both follow current
text.

**Needed invariant:** occurrence carries immutable member metadata to finish
after deletion; terminal one-time disable is conditional on same alert ID still
existing at committed record revision. Define compare/reload/retry semantics so
stale App writes cannot overwrite web commits.

### S4 — Touch-ui closed surface state conflicts with `active-alert`

**Severity:** blocker

Touch-ui AD-5 says valid `active_surface` values are exactly `rotation`, `bar`,
`settings`; AD-7 says Settings is third `active_view`. Alert AD-6 introduces
exclusive `active-alert` surface, but does not state whether it extends
`active_surface`, replaces `active_view`, is compositor-priority layer, or
where hit-test runs. Parent AD-9 fixes touch polling at step 0 and compositor
call site; alert code can otherwise create second input/render path.

**Needed invariant:** extend parent surface state machine or define App-owned
occurrence-priority mode gating parent reducer/rendering at fixed call sites.
Specify saved/resumed normal surface and deadline policy for alerts raised from
Rotation, Bar, Settings. Update touch-ui authority spine if closed value set
changes.

### S5 — Civil due-key lifetime and restart behavior is unbounded/ambiguous

**Severity:** major

AD-5 records every `(alert_id, local_date, hour, minute)` raised key but does
not state retention or persistence. Keeping every key leaks memory over device
life; memory-only history permits same-minute duplicate after reboot;
persisting it needs schema/recovery rules. Backward clock correction and
postponed re-alert need distinct keys so deferred occurrence is not suppressed
as original scheduled key.

**Needed invariant:** bound key history (for example current and prior local
dates), state reboot survival, give postponed occurrences stable identities
independent of recurring due keys. State behavior when local time unavailable
versus merely `unsynced`.

### S6 — Offline alert requirement lacks time-availability gate

**Severity:** major

PRD FR-2 requires retained local-time alerts while time trust is `unsynced`.
Core AD-3 permits `local: None` before valid time exists. Alert AD-5 says use
local Device Time, but not when due detection is allowed. One build schedules
whenever `trust == unsynced`; another requires non-null local snapshot. First
risks fabricated boot time; second can violate offline operation after retained
RTC value exists.

**Needed invariant:** schedule only when `TimeSnapshot.local` exists,
irrespective of `synced|unsynced`; never invent due times when local absent.

### S7 — Postpone confirmation is required but lacks owner/deadline

**Severity:** major

PRD FR-8 and UX require visible deferred-time confirmation before Rotation.
AD-6 says terminal resolution returns to normal lifecycle; touch-ui defines
only Bar/Settings idle deadlines. No state owner, duration, interrupt behavior,
render invalidation boundary exists. Independently built UI/App units can omit
it or make incompatible timers.

**Needed invariant:** App-owned bounded confirmation substate, monotonic
deadline named in config, compositor ownership, new-due preempts confirmation.
Make it non-interactive so it cannot conflict with parent touch states.

## Inherited-spine compatibility

- **Core AD-1/AD-2/AD-5/AD-7/AD-10/AD-11:** compatible if domain stays pure,
  App remains reducer/port caller, alert view uses DisplayPort.
- **Wi-Fi AD-1/AD-3/AD-4/AD-5/AD-7:** AD-1/4/5/7 compatible in principle;
  AD-3 conflicts directly with Alert AD-4 until record evolution is defined.
  AD-1 exposes S2 ownership ambiguity.
- **Touch-ui AD-2/AD-3/AD-5/AD-6/AD-9:** port/SPI/suspension compatible;
  AD-5/AD-7/AD-9 conflict with or leave Alert AD-6 unresolved until active
  alert integrates one state machine/call site.

## Pass conditions

Resolve S1–S4 before build. Resolve S5–S7 in spine or mark explicit product
behavior before story slicing. Add host tests for stale web-write versus
occurrence completion, preemption from every touch surface, bounded due-key
history, offline retained-local scheduling, confirmation preemption.
