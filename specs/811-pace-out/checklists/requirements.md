# Requirements Checklist: 811-pace-out

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-11

## Process control stays in code

- [x] CHK001 The tier rule after the change is named with its inputs (diff, FULL track, lead flags, floor, docs-only, lead tier) [spec Context, plan Summary]
- [x] CHK002 CAP after the change is `calibrate.host` used as given, with the budget bound kept [FR-003, FR-004]
- [x] CHK003 Each removed unit is classed (a) or (b), and the one (b) guard (push evidence) is kept [plan, process-control table]
- [x] CHK004 The (b) parts of I15 and I17 name the tests that keep them [plan, Constitution Check]

## Completeness

- [x] CHK005 Every file deleted and edited is listed with what changes [plan.md]
- [x] CHK006 Retired config keys are listed for the lead [plan.md, RETIRED at rebase]
- [x] CHK007 Old day state and event rows are covered as edge cases [spec Edge Cases]
- [x] CHK008 Generated agents are rebuilt, not hand edited [T022]

## Tests

- [x] CHK009 Each behaviour change has a red test before its code [T001-T003, T007, T011, T012, T016, T017]
- [x] CHK010 No test is loosened; deleted tests cover only deleted code [SC-001, T009, T011, T020]
- [x] CHK011 Only touched test files run locally; CI runs the suite [tasks.md header]

## Writing

- [x] CHK012 No emojis, em-dashes, absolute local paths, or client, repository or people's names in the artifacts
