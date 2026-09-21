# Alert Clock Spine — Direct-GPIO `tut` Seam Review

Reviewed: 2026-09-21  
Lens: adversarial  
Scope: `ARCHITECTURE-SPINE.md`, alert PRD/addendum, and hardware source of truth.  
Focus: direct-GPIO `tut` cadence from GP15, not general alert architecture.

## Verdict

Do not implement production buzzer adapter yet. Cadence intent is clear, but
module identity/control mode, initialization-safe state, late-tick behavior,
terminal-silence ordering, and electrical gate remain under-specified or
contradictory. User bench test proves audible output only; it does not close
current/polarity/direct-drive safety evidence.

## Findings

```json
[
  {
    "lens": "adversarial",
    "location": "ARCHITECTURE-SPINE.md:95; prds/addendum.md:3-15",
    "trigger_condition": "Spine mandates fixed GP15 high/low pulses while technical addendum identifies supplied HW-508 as passive and requires a square-wave/PWM signal, with a different S/NC/- pinout.",
    "guard_snippet": "Reconcile source authority from physical module evidence: record exact board identity/pinout and choose active-module DC gating or passive-module PWM gating; remove superseded addendum claim.",
    "potential_consequence": "Builder can correctly implement 180/220 ms DC gating for installed VCC board yet fail sound or overdrive a passive board covered by addendum."
  },
  {
    "lens": "adversarial",
    "location": "ARCHITECTURE-SPINE.md:42,95,121; docs/hardware_configuration.md:78,82-87",
    "trigger_condition": "Spine calls output machine.Pin direct GPIO; hardware source calls S a PWM/control signal and says do not enable firmware PWM before validation.",
    "guard_snippet": "Name one electrical primitive in docs, PRD, spine, and BuzzerPort: Pin value gate for confirmed active board, or PWM frequency/duty plus envelope gate for confirmed passive board.",
    "potential_consequence": "Independent implementation/test units choose incompatible Pin and PWM semantics while both appear compliant."
  },
  {
    "lens": "adversarial",
    "location": "ARCHITECTURE-SPINE.md:91-101",
    "trigger_condition": "AD-7 has no construction contract requiring GP15 output-low before adapter becomes usable, despite hardware source requiring low before power application.",
    "guard_snippet": "Specify composition order: create output with initial value 0, verify/record init result, then expose BuzzerPort; every boot, reset, and retry begins silenced.",
    "potential_consequence": "GP15 can float or retain an audible high state during boot, reset, or adapter recreation."
  },
  {
    "lens": "adversarial",
    "location": "ARCHITECTURE-SPINE.md:95,101",
    "trigger_condition": "BuzzerPort tick result is named generically, but constructor/init, write-high, write-low, and emergency-silence failure boundaries are not distinct.",
    "guard_snippet": "Define compact result codes and phases such as init, drive_high, drive_low, silence; state which failures make port unavailable and when bounded retry is permitted.",
    "potential_consequence": "An adapter can throw during Pin construction or silence, bypass AD-8 or produce diagnostics too vague to repair hardware."
  },
  {
    "lens": "adversarial",
    "location": "ARCHITECTURE-SPINE.md:83,95",
    "trigger_condition": "Cadence has durations but no phase-start rule at alert raise or re-alert.",
    "guard_snippet": "On transition to sounding, set high immediately, set high-phase deadline from same now tick, and define postponed re-alert as a fresh high-first cadence.",
    "potential_consequence": "One implementation starts with 220 ms silence or waits until next phase boundary, weakening due-alert audibility and making tests nondeterministic."
  },
  {
    "lens": "adversarial",
    "location": "ARCHITECTURE-SPINE.md:83,95",
    "trigger_condition": "No late-tick/overrun policy says how BuzzerPort handles a loop delayed past one or multiple 180/220 ms boundaries.",
    "guard_snippet": "Use ticks_add/ticks_diff phase deadlines; on late tick, derive current phase from elapsed time or resynchronize from now, never replay missed transitions, and document chosen policy.",
    "potential_consequence": "Slow display/network work can stretch high drive, compress silence, or emit burst toggles after a stall, changing sound and electrical duty unpredictably."
  },
  {
    "lens": "adversarial",
    "location": "ARCHITECTURE-SPINE.md:71,89,95",
    "trigger_condition": "Stop, Postpone, auto-stop, and failure transitions promise immediate silence but spine does not bind output ordering against one-per-loop tick.",
    "guard_snippet": "Resolve terminal alert action before any sounding tick in each App step; call idempotent BuzzerPort.silence in same transition and prohibit a later call in that iteration from reasserting high.",
    "potential_consequence": "A valid Stop can be followed by another high write in same loop or wait a full loop for silence, violating FR-7/FR-8."
  },
  {
    "lens": "adversarial",
    "location": "ARCHITECTURE-SPINE.md:95,101",
    "trigger_condition": "Known-output silence after a drive failure is requested, but no adapter-local state defines whether output state is unknown, how low is retried, or when future alerts may retry.",
    "guard_snippet": "Track port state as available/sounding/silent/unknown; best-effort low exactly once on fault, report its outcome, and require fresh initialization before later alert retry when state is unknown.",
    "potential_consequence": "App can label alert recovered while GP15 remains high, or repeatedly hammer failed hardware and flood serial logs."
  },
  {
    "lens": "adversarial",
    "location": "ARCHITECTURE-SPINE.md:95,112,143",
    "trigger_condition": "Spine claims pinout and audible direct 3.3 V drive are bench-confirmed, while hardware source still labels control disabled and bench validation pending.",
    "guard_snippet": "Update hardware source with dated user-run evidence for 10-second and repeated 180/220 ms test, then retain explicit unpassed measurements; spine must reference exact evidence state, not infer deployment approval.",
    "potential_consequence": "Architecture status final can be misread as permission to deploy direct drive before required electrical checks complete."
  },
  {
    "lens": "adversarial",
    "location": "ARCHITECTURE-SPINE.md:95,121,147; docs/hardware_configuration.md:82-87",
    "trigger_condition": "Safety gate names current, polarity, and safe direct-drive validation but supplies no measurable acceptance limits, method, or owner for deciding direct versus buffered drive.",
    "guard_snippet": "Record test voltage, high/low polarity, measured peak and continuous current, Pico GPIO source/sink limit used, measurement method, and explicit pass/fail condition requiring a driver/buffer on failure.",
    "potential_consequence": ""Safe" remains subjective; direct GP15 drive may be shipped outside Pico or module electrical limits."
  },
  {
    "lens": "adversarial",
    "location": "ARCHITECTURE-SPINE.md:42,95,121,132; src/config.py",
    "trigger_condition": "Architecture hard-codes GP15 in diagrams/rules but does not bind a checked-in BUZZER GPIO/cadence configuration or composition injection seam; current config has no buzzer constants.",
    "guard_snippet": "Add non-secret BUZZER_SIGNAL_PIN, cadence durations, and active-level constants to src/config.py; main composition constructs one injected BuzzerPort from those values.",
    "potential_consequence": "Implementation can scatter literal 15/180/220 values, bypass inherited configuration and host-fake boundary conventions."
  },
  {
    "lens": "adversarial",
    "location": "ARCHITECTURE-SPINE.md:95,101,112",
    "trigger_condition": "No acceptance contract tests silence on boot, phase order, boundary timing, late-tick behavior, Stop/Postpone/auto-stop same-step silence, or adapter fault recovery.",
    "guard_snippet": "Map fake Pin/BuzzerPort host tests to each temporal contract and require flashed-device evidence separately for audible cadence, current/polarity, and recoverability.",
    "potential_consequence": "Pure scheduler tests can pass while cadence adapter violates user-visible sound and safety contracts."
  }
]
```

## Required seam shape

`main.py` builds one `BuzzerPort` from checked-in configuration. Constructor
drives GP15 low before port exposure and returns `init_*` result. `App` reduces
terminal alert actions before sound output, invokes idempotent `silence()` in
same state transition, then calls `tick(now, sounding)` once. `BuzzerPort`
alone owns phase/deadline state with wrap-safe tick arithmetic and returns
named result codes. Production direct-drive authorization follows documented,
dated target-device measurement evidence; audible test alone does not grant it.
