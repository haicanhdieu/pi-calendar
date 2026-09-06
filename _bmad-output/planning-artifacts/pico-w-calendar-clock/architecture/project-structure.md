---
title: Project Folder Structure Convention
status: proposed
created: 2026-09-05
updated: 2026-09-05
---

# Project Folder Structure Convention

This convention applies to the `pico-w-calendar-clock` PRD. Future PRDs must
copy or replace it in their own `_bmad-output/<prd-slug>/architecture/`
directory rather than writing structure rules into shared folders.

## Target layout

```text
pi-calendar/
├── main.py                         # MicroPython boot entry point
├── src/                            # Importable firmware code
│   ├── config.py                   # Hardware and product settings
│   ├── device/                     # Hardware boundaries and services
│   │   ├── display/                # TFT driver and display primitives
│   │   ├── network/                # Wi-Fi and NTP integration
│   │   └── input/                  # Buttons and physical inputs
│   ├── calendar/                   # Calendar/domain logic
│   │   ├── gregorian.py            # Pure Gregorian calculations
│   │   └── lunar.py                # Deferred Vietnamese lunar calculations
│   ├── time/                       # Time source and trust/state handling
│   └── ui/                         # View state and screen renderers
│       ├── clock_view.py
│       └── calendar_view.py
├── tests/                          # CPython host tests for pure logic
├── docs/                           # Product, hardware, and design decisions
├── _bmad-output/<prd-slug>/        # This PRD's planning-to-test trail
├── _bmad/                          # BMAD configuration and workflows
└── .bmad-loop/                     # BMAD loop state and policy
```

## Rules

- Keep `main.py` thin and put reusable firmware code in `src/`.
- Keep pure calendar, date, view-state, and lunar logic importable under
  CPython. It must not import `machine`, `network`, `ntptime`, or other
  MicroPython-only modules. Hardware access stays under `src/device/`.
- Add host tests under `tests/` with the first pure-logic implementation and
  run them with `uv run pytest`.
- Keep product, hardware, and design decisions in `docs/`; keep PRD-specific
  planning, implementation, and test evidence under this PRD directory.
- Do not create a `tools/` or deployment directory until a checked-in helper
  exists. Until then, keep deployment instructions in the PRD artifacts.
- When `src/` is deployed to the Pico, document and verify the host-to-device
  mapping so `main.py` can import the deployed modules.

## Current-state note

The repository currently has a root-level `main.py`. This convention does not
require an immediate migration; move files only as part of an implementation
task that verifies the device deployment layout.
