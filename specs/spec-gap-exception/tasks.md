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
