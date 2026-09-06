# PRD Quality Review — Wi-Fi Provisioning & Admin Config

## Overall verdict

This is a tight, well-scoped companion PRD that earns its brevity: FRs are testable, trade-offs (open Setup AP, no password recovery) are stated rather than hidden, and the MVP boundary is coherent with the stated problem. The one real defect is a broken cross-reference — FR-4 attributes "Forest & Amber" to the sibling `prd.md`, but that term appears only in the sibling's `DESIGN.md`, not its PRD — which undermines the "standalone-except-for-cross-references" premise this document relies on. FR/UJ numbering also restarts at 1 in both PRDs with no namespace, a latent collision risk if the two are ever read or referenced together outside their own epics.

## Decision-readiness — strong

Open Questions (§8) are genuinely open, each tied to a real unresolved tradeoff rather than a rhetorical setup: Q1 names the open-AP security exposure explicitly ("anyone in radio range can join it and submit Wi-Fi/admin credentials while it's up") without resolving it in the next sentence; Q3 leaves the factory-reset timeline undecided. FR-1's Out of Scope explicitly cross-references the security tradeoff instead of burying it. FR-3's "no password-recovery flow exists in v1" is stated as a real gap with consequence, not softened.

### Findings
- **low** No `[NOTE FOR PM]` callouts anywhere in the document, despite at least one candidate tension (the admin-password-recovery gap in FR-3, which has real user impact if triggered) — currently covered adequately via Non-Goals + Open Question 3, so this is stylistic rather than a loss of information. *Fix:* optional; not required given the tension is already surfaced elsewhere.

## Substance over theater — strong

No persona inflation (correctly inherits the single user from the sibling PRD rather than restating). FR-4 is labeled a "stub" plainly rather than dressed up as a feature — "v1 ships with exactly one theme... Selecting the only available option is a no-op that doesn't error." No NFR boilerplate, no vision statement that could be swapped into another PRD ("a brand-new or reset Device has no way to join a network and no keyboard for input" is specific to this device's constraints).

## Strategic coherence — strong

Clear thesis: the sibling PRD assumes Wi-Fi already exists; this PRD's entire arc is "get onto Wi-Fi with no keyboard, recover when it breaks, then manage settings afterward" (§1). Every FR serves that arc directly — FR-1 (join), FR-2 (find the address without a keyboard), FR-3 (secure the ongoing surface), FR-4 (stub for a settings surface the config page will need later). Success Metrics (§7) is qualitative and appropriately matched to a hobby build rather than a padded KPI list.

## Done-ness clarity — adequate

Most FRs have concrete, testable consequences (e.g., FR-1's 3-consecutive-failure retrigger, FR-3's "old password stops working, new one required for the next login"). Two soft spots:

### Findings
- **medium** FR-2's on-screen IP consequence — "at least briefly (e.g. on a boot/status screen)" — leaves the actual display duration untestable; "briefly" isn't a bound. (§4.1 FR-2) *Fix:* either pin a minimum duration/persistence rule, or fold it explicitly into the existing `[ASSUMPTION]` on that same FR so it's flagged as deferred rather than silently vague.
- **low** FR-1's "stops the Setup AP" and "attempts to join the chosen network" don't specify a join timeout before falling back to Setup AP mode again — implied by the "3 consecutive attempts" language elsewhere but not stated for the first-boot path specifically. Minor; low stakes for a hobby device.

## Scope honesty — strong

Non-Goals (§5) and MVP Out of Scope (§6.2) are consistent and explicit, each Out-of-Scope item under FR-1/2/4 is mirrored correctly in §6.2, and the Assumptions Index (§9) round-trips cleanly with the two inline `[ASSUMPTION]` tags (FR-1, FR-2) — no orphans either direction. Open-items density (3 Open Questions + 2 Assumptions) is appropriate for hobby stakes, not padded.

## Downstream usability — adequate

Glossary (§3) extends the sibling's cleanly with no term collisions (Setup AP, Setup page, Admin password, Config page are all new coinages, not reused/redefined sibling terms). Each FR section is self-contained and readable in isolation. One structural issue:

### Findings
- **high** Broken cross-reference: FR-4 states "v1 ships with exactly one theme (Forest & Amber, per [pico-w-calendar-clock prd.md])" (§4.2 FR-4), but the sibling `prd.md` contains no mention of "Forest," "Amber," "theme," "color," or "palette" anywhere — the term is defined only in the sibling's `ux-designs/DESIGN.md`. A reader following this PRD's own citation to verify what "Forest & Amber" means will not find it there. *Fix:* point the citation at `pico-w-calendar-clock/ux-designs/DESIGN.md` (where the palette is actually specified), not the sibling PRD.
- **medium** FR and UJ numbering both restart at 1 independently in this PRD and the sibling (sibling has FR-1..FR-3/UJ-1; this PRD has FR-1..FR-4/UJ-1..UJ-3), with no namespace prefix distinguishing them. Downstream epics currently appear to stay scoped per-PRD (confirmed via `_bmad-output/.../pico-w-calendar-clock/epics/epics.md` existing separately), so this hasn't caused breakage yet, but any future doc, story, or commit message that says "FR-1" without naming which PRD is ambiguous across this pair. *Fix:* prefix IDs by domain (e.g., `WIFI-FR-1`, `CLOCK-FR-1`) if these two PRDs will keep being read together, or note explicitly in §0 that FR/UJ IDs are local to each document.

## Shape fit — strong

Correctly scoped as a capability spec for a single-operator hobby device, matching the sibling's shape. Three UJs are load-bearing (first-boot, recovery, ongoing config are genuinely distinct flows worth separating) rather than UJ-density padding — not over-formalized. Not under-formalized either: a consumer-facing but single-user provisioning flow benefits from the UJ structure it has. The explicit "companion, does not restate" framing in §0 is honored throughout — no drift back into re-explaining base device vision/hardware.

## Mechanical notes

- Glossary drift: none found. New terms (Setup AP, Setup page, Admin password, Config page) are used consistently across §3 and all FRs.
- ID continuity: FR-1 through FR-4 and UJ-1 through UJ-3 are contiguous and unique *within this document*. Cross-document collision with sibling's FR-1..FR-3/UJ-1 noted above (downstream usability, medium).
- Assumptions Index roundtrip: clean. Both inline `[ASSUMPTION]` tags (§4.1 FR-1, FR-2) appear in the Index (§9), and both Index entries have inline counterparts.
- UJ protagonist naming: all three UJs name Minh explicitly and carry context inline (device state, trigger, action) — no floating UJs.
- "Single owner" claim: consistent with sibling. This PRD's §2 references sibling §2 verbatim in substance; sibling's §2.2 states "not multi-user — this is a single-owner desk device," and UJ-1 in both documents names Minh as the actor.
- Required sections: all present and proportionate for the stakes (hobby, companion capability spec) — no missing section flagged.
</content>
