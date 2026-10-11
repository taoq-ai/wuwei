# Requirements Checklist: 844-derived-next

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-11

## Process control stays in code

- [x] CHK001 Every (b) unit changed names where its job goes [plan.md, Process control]
- [x] CHK002 Never past the round cap, never a gate before the builder stops, never a raise without a pass at head, never a merge without the policy, never done with an open duty: each is a test [test_loop.py, T012]
- [x] CHK003 An owner decision is one Owner step card in the session; no host-terminal text [spec, FR-007, T023]
- [x] CHK004 PARK parks in code with no card [decision table, T007]
- [x] CHK005 `next` offers; the planner does every launch and duty [FR-005, FR-015]

## Outward duties

- [x] CHK006 PR raised ping, review shepherd, merged tracker or page, day-end summary each have a row, a due rule and a record [spec, Duties]
- [x] CHK007 Duties are configured per workspace and default from the configured channels [FR-009]
- [x] CHK008 `close` waits on open duties [FR-011, T019]

## Derived state

- [x] CHK009 Deleting state.json changes no answer [US5, T006]
- [x] CHK010 Writers never write a derived fact back [FR-002, T002]
- [x] CHK011 #669 and #729 drift handled by overlays [T007, T018]

## Completeness

- [x] CHK012 Every file created and edited is listed; the modules replaced here and deleted in part 23 are named [plan.md]
- [x] CHK013 Dependencies on parts 16 to 21 are marked [spec Assumption 9, plan Handoff, T000]
- [x] CHK014 No retired key [plan.md, RETIRED]

## Tests

- [x] CHK015 Each behaviour change has a red test before its code [tasks.md]
- [x] CHK016 The changes to `materialise`, `answer`, `configure` and the two stricter assertions are listed [plan.md, T006, T011, T018, T021]
- [x] CHK017 No test is loosened; tests go only with their code [tasks.md rules]

## Writing

- [x] CHK018 No emojis, em-dashes, absolute local paths, or client, repository or people's names
