# Tasks: the owner may accept a full-tier spec gap, and a finding row is recorded whole

## Phase 1: Tests first

- [x] T001 [US1] Spec gap questions reach the owner (tests/test_guards.py)
- [x] T002 [US1] A full-tier spec-only PR: the door holds, the yes is recorded with its follow-up item, the door opens (tests/test_guards.py)
- [x] T003 [US2] A whole finding row opens the door; its first sentence alone does not (tests/test_guards.py)
- [x] T004 [US2] `exception_refs` keeps a row's sentence breaks for each question tail (tests/test_hook.py)
- [x] T005 [US3] Template, size and age questions are still sent back (tests/test_guards.py)
- [x] T006 Run the new tests red on 6828776's code

## Phase 2: Implementation

- [x] T007 Drop the spec words from the question guard's process pattern (cli/wuwei/guards.py)
- [x] T008 Cut the gap after the last `|` (cli/wuwei/hook.py)
- [x] T009 Apply both to .claude/wuwei/cli/wuwei/
- [x] T010 State the rule in docs/design.md section 5 and docs/site/concepts/decisions.md
- [x] T011 Run the full suite; runtime within the budget

## Phase 3: Checks

- [x] T012 Route corpus through the guards at main and at the head (route_probe.py)
- [x] T013 Generated question probe at main and at the head (question_probe.py)
- [x] T014 Mutants of each changed expression on both copies, one at a time (mutants.py)

## Phase 4: Fix round 1 (gates at b6d0635)

- [x] T015 [US2] A gap with no finding row reads as on main whatever the tail; a row reads to its end (tests/test_hook.py)
- [x] T016 [US1] Each open finding row and each checklist with an unchecked box is its own gap (tests/test_evidence.py)
- [x] T017 [US1] A yes to the first row or checklist leaves the next holding the merge door until it is named (tests/test_guards.py)
- [x] T018 [US2] A long row is printed to its last cell edge within 100 characters and its yes opens the door (tests/test_evidence.py, tests/test_guards.py)
- [x] T019 Run the round's tests red on b6d0635's code
- [x] T020 Print each row and checklist as its own gap and cut a row at a cell edge (cli/wuwei/evidence.py)
- [x] T021 Read a row to its end only when the gap holds one (cli/wuwei/hook.py)
- [x] T022 Apply both to .claude/wuwei/cli/wuwei/ and state them in docs/design.md and docs/site/concepts/evidence.md
- [x] T023 Route corpus at main and at the head, plain, with approved exceptions and with a two-row spec PR (route_probe.py)
- [x] T024 Question probe with the gates' tail and row classes, and the exception_refs differential (question_probe.py, refs_differential.py)
- [x] T025 Mutants of each changed expression on both copies, one at a time (mutants.py)
- [x] T026 [US1] Rows whose cuts are the same print whole, so one yes never waives two rows (tests/test_evidence.py, tests/test_guards.py)
