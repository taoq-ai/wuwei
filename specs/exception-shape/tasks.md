# Tasks: an exception: question names its gap after its refs, or it is refused

## Phase 1: Tests first

- [x] T001 [US1] Questions the hook cannot record are refused with the shape (tests/test_guards.py)
- [x] T002 [US2] Questions in the shape pass (tests/test_guards.py)
- [x] T003 [US2] An accepted exception records kind, pr, head and gap (tests/test_hook.py)
- [x] T004 [US3] Generated questions: every guard pass is one the hook records (tests/test_hook.py)
- [x] T005 Run the new tests red

## Phase 2: Implementation

- [x] T006 The exception branch of the owner-class regex in `pre_tool` (cli/wuwei/guards.py)
- [x] T007 Copy guards.py into .claude/wuwei/cli/wuwei/
- [x] T008 Run the full suite green, runtime at 2,978 or fewer

## Phase 3: Checks

- [x] T009 [US4] Route corpus at main and at the head: sha256 and every moved route
- [x] T010 Generated probe at main and at the head: generated, recorded, holes
- [x] T011 Mutants of each new condition, run in a scratch copy, each fail a test
