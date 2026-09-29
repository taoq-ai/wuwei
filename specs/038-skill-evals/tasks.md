# Tasks: Skill triggering evals

## Phase 1: Offline coverage

- [X] T001 [US2] Write `tests/test_skill_evals.py` to validate case structure, grader fields, skill references and minimum positive and near-miss coverage.
- [X] T002 [US2] Run `tests/test_skill_evals.py` and confirm it fails because cases are missing.
- [X] T003 [US1] Add five positive and five near-miss prompt and grader pairs per shipped skill under `evals/`.
- [X] T004 [US2] Rerun `tests/test_skill_evals.py` and confirm it passes.

## Phase 2: Hosted evaluation

- [X] T005 [US3] Add an offline test in `tests/test_skill_evals.py` for CI command, key gate, skip message and docs.
- [X] T006 [US3] Run the new CI test and confirm it fails for missing job and docs.
- [X] T007 [US3] Add the separate job to `.github/workflows/tests.yml` and local usage and secret setup to `README.md`.
- [X] T008 [US3] Rerun the CI test and confirm it passes.

## Phase 3: Final verification

- [X] T009 Run the full requested pytest command and check new files for absolute local paths, em-dashes and emojis.

## Dependencies

T001 and T002 precede T003. T005 and T006 precede T007. T009 follows all other tasks.
