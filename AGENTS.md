<!-- bmad:context -->
<!-- Verified 2026-09-05 against the uncommitted working tree (no commits yet). Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## pi-calendar

Firmware and planning repository for a Raspberry Pi Pico W clock and calendar device. This block carries only rules and pointers: read the active PRD artifacts and `docs/` for product, hardware, design, and project-structure decisions before changing anything; do not restate them here.

## Policy

- For every PRD, derive one stable lowercase kebab-case `<prd-slug>` and place all related BMAD artifacts under `_bmad-output/<prd-slug>/`; never flatten artifacts directly into `_bmad-output/` or shared `planning-artifacts/`, `implementation-artifacts/`, or `test-artifacts/` directories.
- Keep artifacts for different PRDs isolated in separate slug directories; preserve BMAD's expected filenames and artifact types inside the active PRD directory.
- Before running a BMAD workflow, rebase or override its output location to the active `_bmad-output/<prd-slug>/` directory; do not edit installer-managed `_bmad/config.toml` to achieve this.
- Treat `_bmad-output/<prd-slug>/` as the source of truth for that PRD's planning-to-implementation-to-testing trail; do not place those artifacts in `docs/` or the repository root.
- Keep product, hardware, and design decisions in `docs/` and the PRD artifacts, never in this block.
- Do not change hardware pin assignments in software unless the physical wiring has changed and the documentation is updated in the same change.

## Where things are

- Hardware and product source of truth: `docs/`
- Per-PRD planning, implementation, and test artifacts, including briefs: `_bmad-output/<prd-slug>/`
- Project folder structure: `_bmad-output/<prd-slug>/architecture/project-structure.md`
- BMAD configuration and workflow scripts: `_bmad/config.toml` and `_bmad/scripts/`
- Firmware entry point: `main.py`
- BMAD loop state and policy: `.bmad-loop/`

## Running and verifying

- Run BMAD scripts as `uv run _bmad/scripts/<name>.py`; they declare `requires-python = ">=3.11"` inline and bare `python` ignores that.
- TODO: no host test suite exists. When the first calendar logic lands, create it under `tests/` and run it with `uv run pytest`.
- Firmware cannot be run in this environment. Never report on-device behaviour as observed; say what needs flashing and leave the device run to the user. Deployment tooling is recorded in the active PRD's artifacts.

## Conventions that differ from defaults

- Pure logic — calendar math, date arithmetic, view-state decisions, lunar conversion — must not import `machine`, `network`, or `ntptime`; those imports fail under CPython and take the whole host test suite down. Keep hardware access in the display and device layers and pass values in.

<!-- /bmad:context -->
