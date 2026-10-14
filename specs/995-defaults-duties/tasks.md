# Tasks: Safer defaults and finite duties

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Trust paths

- [X] T001 [US1] Add failing default and gate brief tests in `tests/test_workspace.py` and `tests/test_process_depth.py`.
- [X] T002 [US1] Extend trust path defaults in `cli/wuwei/workspace.py`.

## Terminal PR pings

- [X] T003 [US2] Add failing merged and closed duty tests in `tests/test_derive.py`.
- [X] T004 [US2] Suppress terminal PR pings in `cli/wuwei/derive.py`.

## Durable acknowledgements

- [X] T005 [US3] Add failing rollover and newer comment tests in `tests/test_obligations.py`.
- [X] T006 [US3] Read prior day acknowledgements in `cli/wuwei/obligations.py` and update its readers.

## Memory floor

- [X] T007 [US4] Add a default and explicit override regression test in `tests/test_workspace.py`.
- [X] T008 [US4] Confirm the existing zero default and template already meet the lowered-default requirement.

## Verification

- [X] T009 Run all test files importing changed modules and inspect the diff and authored text.
