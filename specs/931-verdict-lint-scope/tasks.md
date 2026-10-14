# Tasks: Verdict lint scope

**Input**: `spec.md`, `plan.md`

## Findings scope

- [X] T001 Add a failing test for cited notes outside Findings and malformed findings inside it in `tests/test_verdict.py`.
- [X] T002 Limit finding parsing to Findings sections in `cli/wuwei/verdict.py` and update existing fixture expectations.

## Scenario wording

- [X] T003 Add a failing test for natural failure wording and missing failure description in `tests/test_verdict.py`.
- [X] T004 Replace the fixed phrase check with prose validation in `cli/wuwei/verdict.py`.

## Written file scope

- [X] T005 Add a failing test for one written gate next to another seat's invalid gate in `tests/test_verdict.py`.
- [X] T006 Limit Bash PostToolUse lint to named write targets in `cli/wuwei/guards/verdict.py` and update old scan expectations.

## Validation

- [X] T007 Run all affected test files with the requested interpreter and command.
- [X] T008 Check changed files for forbidden characters and review the diff.

## Authorized review fix round

- [X] T009 F1: Restore the outside-section PASS refusal assertion, observe failure, and reject active blocking text outside parsed findings.
- [X] T010 F2: Test legacy label and bold sections and the missing-section diagnostic before fixing the shared parser; verify dispatch notes, why, and tracker consumers.
- [X] T011 F4: Observe closure-heading regressions fail, then require exact Findings titles while preserving ZIRAN findings.
- [X] T012 F3/F6: Observe missing Bash target regressions fail, then replace the program allowlist with argument/value targets and literal parse-error fallback.
- [X] T013 Run only test files importing changed modules with the requested interpreter, explicit paths, and cache provider disabled; check the final diff.

F5 remains unchanged as requested.

Validation: `python -m pytest -q -p no:cacheprovider tests/test_agents.py tests/test_close_branches.py tests/test_dispatch.py tests/test_loop.py tests/test_metrics.py tests/test_process_depth.py tests/test_retro.py tests/test_runtime.py tests/test_verdict.py`

Last summary: `978 passed in 12.72s`. `git diff --check` passed.
