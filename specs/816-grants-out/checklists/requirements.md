# Requirements Checklist: 816-grants-out

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-11

## Process control stays in code

- [x] CHK001 Each condition a grant skipped is named, with where it goes: a wait the policy clears, or an owner block [FR-001, analysis P1]
- [x] CHK002 Every owner block yields exactly one owner row from `next`; waits keep the `pr` row [FR-003, US1]
- [x] CHK003 Every merge passes `merge.check` with no other input [SC-003]
- [x] CHK004 Deploy, release and publish refuse from the session in every posture [FR-004]
- [x] CHK005 The evidence check (b) keeps its posture levels and has no card [FR-005]
- [x] CHK006 The constitution floor and the wall-lint exemption are amended together, not loosened [analysis C1, L1]

## Completeness

- [x] CHK007 Every file deleted and edited is listed, with what parts 9 and 10 already did [plan.md]
- [x] CHK008 Retired keys are listed for the lead [plan.md, RETIRED at rebase]
- [x] CHK009 The behaviour change for `merge.default_tier = "today"` workspaces is documented [spec Edge Cases, plan Risks]
- [x] CHK010 Generated agents are rebuilt, never hand edited [T014]

## Tests

- [x] CHK011 Each behaviour change has a red test before its code [T001, T002, T005, T008, T010]
- [x] CHK012 No test is loosened; deleted tests cover only deleted code [SC-001]
- [x] CHK013 Only touched test files run locally; CI runs the suite [tasks.md header]

## Writing

- [x] CHK014 No emojis, em-dashes, absolute local paths, or client, repository or people's names in the artifacts
