# Requirements Checklist: 833-notes-voice-out

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-11

## Process control stays in code

- [x] CHK001 The retro proposal and promotion path land charter changes unchanged [FR-002, US1]
- [x] CHK002 Goals approved at the gate are recorded by the approval, so `next` needs no goals step [FR-003, US2]
- [x] CHK003 The records protection (goals.md, the baseline, the ledger, memory/archive) stays [plan.md table]
- [x] CHK004 Every (a) unit names where its job goes, or nowhere [plan.md table]
- [x] CHK005 No text names a host terminal; the part 13 LEFT rows go [FR-008, T009]

## Completeness

- [x] CHK006 Every file deleted and edited is listed, with what part 12 already removed [plan.md]
- [x] CHK007 Retired keys and the retired file are listed for workspace.RETIRED and init [plan.md, RETIRED]
- [x] CHK008 The baseline path for design 5.6 is kept [spec Edge Cases, Assumption 3]
- [x] CHK009 What part 14 inherits is named [plan.md, Handoff]

## Tests

- [x] CHK010 Each behaviour change has a red test before its code [T001, T003, T005, T008]
- [x] CHK011 No test or budget is loosened; deleted tests cover only deleted code [SC-001, T010]
- [x] CHK012 Only touched test files run locally; CI runs the suite [tasks.md header]

## Writing

- [x] CHK013 No emojis, em-dashes, absolute local paths, or client, repository or people's names
