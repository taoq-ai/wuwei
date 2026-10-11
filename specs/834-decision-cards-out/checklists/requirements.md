# Requirements Checklist: 834-decision-cards-out

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-11

## Process control stays in code

- [x] CHK001 Every owner decision that reached the owner before reaches the owner from `next` or the parking command, on one Owner step card [spec table, SC-001]
- [x] CHK002 PARK, ESCALATE, round cap, parked items, scope, merge and owner_merge each have a row and a test [spec table, T003]
- [x] CHK003 A declined card applies the safe choice in code, so no row repeats forever [FR-001, FR-005]
- [x] CHK004 The round cap still forbids a fix round past budget [FR-002, Assumption 2]
- [x] CHK005 The Owner step recording and the `wuwei hook` refusal stay, moved out of the decision guard [FR-007, US5, T001, T002]
- [x] CHK006 Seats record two-way assumptions in their spec; the charters say so [US4.1, plan governance]

## Completeness

- [x] CHK007 Every file deleted and edited is listed, with what parts 12 and 13 already did [plan.md]
- [x] CHK008 Retired keys are listed for workspace.RETIRED [plan.md, RETIRED]
- [x] CHK009 What parts 16, 18, 22 and 23 inherit is named, including the relabelled LEFT row [plan.md, Handoff]
- [x] CHK010 The behaviour change under observe and guarded is documented [spec Assumption 1, plan Risks]

## Tests

- [x] CHK011 Each behaviour change has a red test before its code [T001, T003, T006 to T008, T010]
- [x] CHK012 No test is loosened; the day-walk tests answer the cards instead [SC-004, T011]
- [x] CHK013 Only touched test files run locally; CI runs the suite [tasks.md header]

## Writing

- [x] CHK014 No emojis, em-dashes, absolute local paths, or client, repository or people's names
