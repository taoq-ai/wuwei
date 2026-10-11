# Requirements Checklist: 814-cruise-scores-out

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-11

## Process control stays in code

- [x] CHK001 Routing after the change is named with its inputs: door, blast radius, CISR class and `autonomy.mode` [spec Context, FR-001]
- [x] CHK002 Every record that reached the owner still does, and owner routes come back from `next` unchanged [spec US1, Assumption 6]
- [x] CHK003 The seat mandate keeps its default text, fixed in code [FR-003, T004]
- [x] CHK004 Each removed unit is classed (a) or (b); the one (b) unit (profile refusals) is moot with its keys [plan, process-control table]
- [x] CHK005 Measured reversibility keeps working between parts 9 and 10 [FR-006, analysis A1]

## Completeness

- [x] CHK006 Every file deleted and edited is listed with what changes, with "skip if already gone" for batch 1 and 2 code [plan.md]
- [x] CHK007 The retired table is listed for the lead [plan.md, RETIRED at rebase]
- [x] CHK008 Old day state, events and `memory/cruise.json` are covered as edge cases [spec Edge Cases]
- [x] CHK009 Generated agents are rebuilt, never hand edited [T013]

## Tests

- [x] CHK010 Each behaviour change has a red test before its code [T001, T002, T004, T006, T007]
- [x] CHK011 No test is loosened; deleted tests cover only deleted code, and kept assertions move first [SC-001, T002, T004]
- [x] CHK012 Only touched test files run locally; CI runs the suite [tasks.md header]

## Writing

- [x] CHK013 No emojis, em-dashes, absolute local paths, or client, repository or people's names in the artifacts
