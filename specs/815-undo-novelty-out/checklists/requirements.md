# Requirements Checklist: 815-undo-novelty-out

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-11

## Process control stays in code

- [x] CHK001 Routing after the change uses the written door and the CISR class only [FR-001]
- [x] CHK002 The merge recovery check (revert PR, breaker, page on a red base) is kept and its test named [FR-005, analysis A2]
- [x] CHK003 Each removed unit is classed (a) or (b); no (b) check is lost [plan, process-control table]
- [x] CHK004 The charters keep "when unsure, it is one-way" [FR-007]

## Completeness

- [x] CHK005 Every file deleted and edited is listed, with what changes [plan.md]
- [x] CHK006 What part 9 already did is stated, and this part does not touch it again [plan.md header]
- [x] CHK007 Retired files are removed by init --upgrade; no config key is retired [FR-006, plan RETIRED]
- [x] CHK008 Code that batches 1 and 2 delete is marked skip if already gone [plan.md]

## Tests

- [x] CHK009 Each behaviour change has a red test before its code [T001, T004, T007]
- [x] CHK010 No test is loosened; deleted tests cover only deleted code [SC-001, T003]
- [x] CHK011 Only touched test files run locally; CI runs the suite [tasks.md header]

## Writing

- [x] CHK012 No emojis, em-dashes, absolute local paths, or client, repository or people's names in the artifacts
