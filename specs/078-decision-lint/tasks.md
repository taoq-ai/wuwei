# Tasks: Decision lint and question guard

## Setup

- [X] T001 Read dependency contracts and write spec, plan and contracts in specs/078-decision-lint/.

## US1: Decision evaluation and write lint

- [X] T002 [US1] Add failing evaluation/file/CLI tables in tests/test_decision.py.
- [X] T003 [US1] Implement shared evaluation and file lint in cli/wuwei/decision.py and CLI lint in cli/wuwei/commands/decision.py.
- [X] T004 [US1] Add failing file/Bash/scope/event tables in tests/test_decision.py.
- [X] T005 [US1] Implement write guard in cli/wuwei/guards/decision.py.

## US2: Grounded questions

- [X] T006 [US2] Add failing current-day citation, malformed payload and scope tables in tests/test_decision.py.
- [X] T007 [US2] Implement reusable question check and registration in cli/wuwei/guards/decision.py.

## US3: Route and record decisions

- [X] T008 [US3] Add failing seat-routing/reserved-state tests in tests/test_decision.py.
- [X] T009 [US3] Implement seat-only route in cli/wuwei/commands/decision.py and reserve namespace in cli/wuwei/state.py.

## Verification

- [X] T010 Run full pytest suite, review scope/bypass behavior and check changed files for prohibited text.

## Dependencies and execution

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009 -> T010.
One seat executes sequentially since the tests and modules are shared. US1 is the first
independent increment; US2 and US3 reuse its evaluator. Tests always run red before code.

## Review fixes

- [X] T011 F1: Test and remove decision outcome and AlreadyDecided; route produces seat outcomes only.
- [X] T012 F2: Test and reserve every decision. kind in the generic event command.
- [X] T013 F3: Test multiline prose, scalar restrictions, trailing MADR sections and Markdown table variants.
- [X] T014 F4: Test attributable rejection events, feedback-only scans/questions and decision-specific parse hints.
- [X] T015 F5: Move scope beside find_workspace and share the interpreter table; retain commit/push target discovery.
- [X] T016 G1: Test and document morning gates and C-n clarification forms; preserve full D-n scoring.
- [X] T017 Run the supplied full pytest command and final diff hygiene checks.

## Verification result

Review regression tests were run red before each correctness fix, then green.
Full supplied-interpreter suite: 3021 passed in 23.99s. PreToolUse CPU p95 33.70 ms;
PostToolUse CPU p95 35.26 ms, both below 50 ms. Diff and new-file hygiene checks passed.
Changes remain uncommitted in this worktree.
