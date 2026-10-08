# Specification Analysis Report: 552-graph-register

Artifacts: spec.md, plan.md, tasks.md, checklists/requirements.md, against AGENTS.md, the
constitution, the item and the orchestrator notes. Base: a3ca047 (#565 novelty gate, #564
path). No tests/test_invariants.py and no design 9.2 invariant table on this base (A9).

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
| --- | --- | --- | --- | --- | --- |
| A1 | Principle (#530) | HIGH | spec FR-004, US3 s3; plan offer, upgrade | A damaged register made every config write and the upgrade exit 2, a new stop on card answers for a record no guard reads. | Resolved: a register failure is one warning with the fix; config.toml is written with its usual exit; the damaged file is never overwritten (A13, `graph.warn`). |
| A2 | Principle (#530) | HIGH | spec FR-009; plan doctor | A damaged register was a doctor `fail` in the workspace section, which `setup.ending` treats as a required step. | Resolved: `warn` only, fix named, no apply. |
| A3 | Correctness | HIGH | plan `cite` | Citing every class edge of a named node would cite both lists for a channel in work_channels and external_channels, not the edge that decided. | Resolved: `cite` keeps only edges whose view key the guard's reason names; T003 pins the two-list case. |
| A4 | Consistency | MEDIUM | plan outbound `apply` | The second sync (names and members) failing returned UNRUN after config.toml was written and before the event, so the card looked failed. | Resolved: event first, then sync; failure warns and apply returns CLEAN. |
| A5 | Coverage | MEDIUM | spec, item | Known thread participants (already in outbound.people) need no card (#526), so no member_of edge is written for them; `who` lists only card-recorded members. | Recorded as A14: the register is written only after an owner answer or an owner-confirmed write, per the item. |
| A6 | Deviation from item | MEDIUM | item Deliver bullet 1 | The item says writers write nodes and edges "instead of" the sections and the sections become generated views. The plan keeps the guards' config.toml as written today and builds the register from the same validated text in the same step (A2), so no TOML generator exists. | Kept: same observable result (views equal the register, doctor reports drift, one writer); smaller diff; recorded in A2. |
| A7 | Terminology | LOW | item vs FR-001 | Item names `tool` nodes; the plan stores none (A6) and resolves a tool name to its connector. | Recorded in A6. |
| A8 | Underspecification | LOW | plan Project Structure | Upgrade tests live in tests/test_workspace.py, not test_config_transition.py. | Resolved in plan and T006. |
| A9 | Wording | LOW | spec SC-002 | "no other file read by the reader" was ambiguous (`who` reads config.toml for the tier). | Resolved: the owner or planner opens no section or guard code. |
| A10 | Invariant | LOW | spec A9 | The register-or-view invariant cannot go in tests/test_invariants.py on this base. | T005 pins it in tests/test_graph.py and tells the builder to add the row if the file has landed. |

## Coverage

| Requirement | Tasks |
| --- | --- |
| FR-001 register shape, FR-002 views | T001, T002, T004 |
| FR-003 guards unchanged | T005 |
| FR-004 one writer | T011, T012 |
| FR-005 learn members and names | T013, T014 |
| FR-006 who | T017, T018 |
| FR-007 why edge | T019, T020 |
| FR-008 upgrade | T006, T007, T008 |
| FR-009 doctor | T009, T010 |
| FR-010 records floor | T015, T016 |
| FR-011 docs | T021, T022 |

Every behaviour task has its test task ordered before it. No unmapped tasks.

## Constitution and program principles

- Stdlib only, three-state exits, one function per behaviour, test first: pass.
- #530: no new refusal under observe or guarded; the only refusal added is the records
  floor for `.wuwei/graph.json`; the register never stops a write, a card or an upgrade.
- #551: `who --json` gives the planner the node, edges, tier and rule; a miss names the
  next command (`bin/wuwei outbound learn` or `bin/wuwei init --upgrade`).

## Metrics

Requirements 11, tasks 23, coverage 100 percent, CRITICAL 0, HIGH 3 (all resolved),
MEDIUM 3 (resolved or recorded), LOW 4.
