# Requirements Checklist: 832-setup-profiles-out

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-11

## Process control stays in code

- [x] CHK001 The host measure moves unchanged and its tests move with it [FR-001, analysis P1]
- [x] CHK002 Every (a) unit names where its job goes, or nowhere [plan.md table]
- [x] CHK003 No row, fix or text sends the owner to a host terminal; the part 12 LEFT rows go [FR-009, analysis P2]
- [x] CHK004 No `next` row can stall the day on a declined card [analysis P3]

## Completeness

- [x] CHK005 Every file deleted and edited is listed, with every importer of the moved frame [plan.md]
- [x] CHK006 Retired keys and files are stated (none) [plan.md, RETIRED]
- [x] CHK007 What parts 13 and 14 inherit is named [plan.md, Handoff]

## Tests

- [x] CHK008 Each behaviour change has a red test before its code [T001, T003, T007, T009, T010]
- [x] CHK009 No test or budget is loosened; deleted tests cover only deleted code [SC-001, T012]
- [x] CHK010 Only touched test files run locally; CI runs the suite [tasks.md header]

## Writing

- [x] CHK011 No emojis, em-dashes, absolute local paths, or client, repository or people's names
