# Requirements Checklist: 831-owner-answers-in-session

**Purpose**: confirm the spec, plan and tasks are complete before implement.
**Created**: 2026-10-11

## The owner answers, nobody else

- [x] CHK001 One helper serves every converted step; each refuses without the answer and names the card [FR-001, FR-003]
- [x] CHK002 Only the hook writes an answer, from a main session's AskUserQuestion reply; seats never count [FR-002, US2]
- [x] CHK003 A Bash `wuwei hook` call is refused, so a session cannot forge the hook [FR-005, analysis S1]
- [x] CHK004 `state recover` can be answered while `state.json` is unreadable [US1 scenario 4, analysis S2]
- [x] CHK005 Each removed terminal prompt is (b) and its job moves to the card; each removed text is (a) [plan.md, Process control]

## Completeness

- [x] CHK006 Every `_host_confirm` caller and every terminal text is either converted or a LEFT row with its part [plan.md]
- [x] CHK007 The conflict with part 11's plan is named, with what part 11 must do instead [plan.md Handoff, analysis X1]
- [x] CHK008 Later parts that must keep or move a piece (14, 17, 23, the last caller's part) are named [plan.md Handoff]
- [x] CHK009 No config key is retired [plan.md, RETIRED at rebase]
- [x] CHK010 Generated agents are rebuilt, never hand edited [T010]

## Tests

- [x] CHK011 Each behaviour change has a red test before its code [T002, T004, T006, T008]
- [x] CHK012 No test is loosened; deleted tests cover only the deleted terminal path [SC-004, analysis T1]
- [x] CHK013 Only touched test files run locally; CI runs the suite [tasks.md header]

## Writing

- [x] CHK014 No emojis, em-dashes, absolute local paths, or client, repository or people's names in the artifacts
