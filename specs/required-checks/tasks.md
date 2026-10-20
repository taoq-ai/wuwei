# Tasks: a required status check that never ran on the head is a gap

## Phase 1: Tests first

- [x] T001 The fake host answers the branch read and the rules read in their live shapes (tests/conftest.py)
- [x] T002 [US1] A required check with no run holds the merge, with or without auto-merge: acceptance 1 (tests/test_evidence.py)
- [x] T003 [US1] Protection and rulesets each require checks, named once; the merged release PR shows them post-merge (tests/test_evidence.py)
- [x] T004 [US2] Every required check green, one as a status, reads as on main: acceptance 2 (tests/test_evidence.py)
- [x] T005 [US3] No protection is not a gap; every unreadable or malformed read fails closed at the merge door (tests/test_evidence.py)
- [x] T006 [US4] Blocked with no safety gap is a gap; beside one, or in any other state, it is not (tests/test_evidence.py)
- [x] T007 [US5] The read is kept per repository and branch for PR_TTL; a failed read is read again (tests/test_evidence.py)
- [x] T008 Run the new tests red on 89e7064e's runtime

## Phase 2: Implementation

- [x] T009 `gh.rules` reads every page; `gh.required_checks`; `gh.pr` carries `mergeableState` (cli/wuwei/gh.py)
- [x] T010 The required and blocked gaps, cached by repository and branch (cli/wuwei/evidence.py)
- [x] T011 The replay case answers the two new reads (tests/replay/standard-pr-with-owner-paths/case.json)
- [x] T012 Copy the plugin into .claude/wuwei/ with `setup.vendor('.')`
- [x] T013 State the rule in docs/design.md and docs/site/concepts/evidence.md
- [x] T014 Run the full suite green, runtime at 3,218 or fewer

## Phase 3: Checks

- [x] T015 Route differential at main and at the head, under no protection and a required `test (3.11)`
- [x] T016 Mutants of each new rule on both trees, one at a time, each killed by a failing test

## Phase 4: Fix round 1 (arch and goal at 19ede00)

- [x] T017 Tests first, red at 19ede00: a required check not yet created while CI runs waits and lets auto-merge arm; the blocked gap waits and lets auto-merge arm; a release PR's gap names the way through; the base branch is encoded; the required rule on page 2 is read
- [x] T018 `evidence.AUTO` names what GitHub's auto-merge waits on; the merge door reads it (cli/wuwei/evidence.py, cli/wuwei/guards.py)
- [x] T019 `quote` the base branch in the branch and rules reads (cli/wuwei/gh.py)
- [x] T020 The release PR remedy (`RELEASE_PAT`, close and reopen, owner exception) in docs/site/concepts/evidence.md and docs/design.md; doors.md and design.md section 7 true for auto-merge again; the Done table names required checks
- [x] T021 Route differential with six hosts and mutants R1 to R17 on both trees
