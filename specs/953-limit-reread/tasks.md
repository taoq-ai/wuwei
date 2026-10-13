# Tasks: Re-read GitHub quota after a zero-header refusal

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: Field reproduction

- [x] T001 [US1] Add the primary-worded zero-header versus full-quota replay in `tests/test_code_host.py`; run it and observe the expected failure.

## Phase 2: Shared behavior

- [x] T002 [US1] Re-read the same resource once in the refused call's environment and use the short hold on disagreement in `adapters/_http.py`.
- [x] T003 [US2] Test true zero and failed quota read against header reset in `tests/test_code_host.py`.
- [x] T004 [US3] Test and label GH_TOKEN, GITHUB_TOKEN, and gh keyring without leaking values in `adapters/_http.py` and `tests/test_code_host.py`.
- [x] T005 [US1] Update the command-level field replay in `tests/test_pr_actions.py`.

## Phase 3: Verification

- [x] T006 Run every explicit test file importing the changed module with the required offline pytest command.
- [x] T007 Check spec, plan, tasks, and implementation consistency; save findings in `analysis.md`.
- [x] T008 [US1] Reproduce and remove the unused secondary-limit quota read in `tests/test_code_host.py` and `adapters/_http.py`.
- [x] T009 [US3] Reproduce and correct the `token_scopes` source label in `tests/test_code_host.py` and `adapters/code_host/github.py`.
- [x] T010 Restore the #899/#938/#953 rationale in `adapters/_http.py` and rerun importing-file tests.

## Dependencies

T001 precedes T002. T003 to T005 follow the failing replay and shared fix. T006 and T007 follow implementation.
T008 to T010 are review follow-up work after T007, each with a failing regression before code.
