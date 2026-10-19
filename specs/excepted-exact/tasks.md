# Tasks: an owner's exception waives only the gap it names, matched exactly

## Phase 1: Tests first

- [x] T001 [US1] A short or partial gap waives nothing: acceptance 1 (tests/test_evidence.py)
- [x] T002 [US2] The printed gap waives itself alone, at its head only, and the report lists it: acceptance 2 (tests/test_evidence.py)
- [x] T003 [US3] A gate gap is waived by its exact gate list; a delta gap by its one gate (tests/test_evidence.py)
- [x] T004 [US4] Generated accepted gaps against printed gaps match the probe's oracle (tests/test_evidence.py, specs/excepted-exact/probe.py)
- [x] T005 Run the new tests red on 8c1939e's code

## Phase 2: Implementation

- [x] T006 `GATES` and the exact `excepted` (cli/wuwei/evidence.py)
- [x] T007 Copy the plugin into .claude/wuwei/ with `setup.vendor('.')`
- [x] T008 State the rule in docs/design.md, docs/site/concepts/decisions.md and docs/site/concepts/evidence.md
- [x] T009 Run the full suite green, runtime at 2,989 or fewer

## Phase 3: Checks

- [x] T010 Probe at main and at the head: pairs, holes, misses, every changed pair, questions through guard and hook
- [x] T011 Mutants of each new condition, run in a scratch copy, each fail a test
