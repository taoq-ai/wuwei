# Deletion checklist: 800-any-wuwei-command

**Purpose**: requirement quality for a deletion pass that must keep process control in code.
**Created**: 2026-10-11

## Completeness

- [ ] CHK001 Is every deleted unit classed as (a) process reasoning or (b) a process check, with the new home of each (b)? [plan.md, Unit table]
- [ ] CHK002 Is every file to delete and every file to edit named, with what changes? [plan.md, Files]
- [ ] CHK003 Are the helpers the state-file check still needs (`_wuwei_action`, `_READERS`, `_INTERPRETER`) named as kept? [plan.md, Unit table]
- [ ] CHK004 Is the stale guide block in existing workspaces handled? [Spec FR-006]

## Clarity

- [ ] CHK005 Is "in an agent session" defined by observable values (`WUWEI_SESSION_ID`, `WUWEI_SEAT_ROLE`)? [Spec FR-008, FR-009]
- [ ] CHK006 Is the exit code of each moved refusal stated (1, a finding)? [Spec Assumptions]
- [ ] CHK007 Is the owner answer a session needs for `drafts approve` stated as an exact topic? [Spec FR-008]

## Consistency

- [ ] CHK008 Do the moved checks match what the guard enforced before, no wider and no narrower? [Spec US3; analysis A7]
- [ ] CHK009 Does the issue acceptance ("no subcommand refused because of who runs it") agree with FR-009, as the Assumptions explain? [analysis A9]
- [ ] CHK010 Are the deviations from the pass plan's PR 3 detail (`_wuwei_action` kept, `RECORDS_FLOOR` untouched) recorded with the reason? [analysis A2, A3]

## Measurability and tests

- [ ] CHK011 Does each behaviour change have a failing-first test task? [tasks.md T001, T003, T005a, T006, T008, T009, T011, T013, T014]
- [ ] CHK012 Is it explicit that no test, budget or floor is loosened (reason corpus floor, tone budget)? [Spec FR-010, SC-003; plan.md Risks]
- [ ] CHK013 Is the precondition on #798 and #799 stated with what to do if it fails? [tasks.md T000]

## Style

- [ ] CHK014 No emojis, no em-dashes, no absolute local paths, no client, repository or people's names in the artifacts or the planned text.
