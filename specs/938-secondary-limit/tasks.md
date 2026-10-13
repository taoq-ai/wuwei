# Tasks: Scope secondary GitHub rate limits to the refused endpoint

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: Field reproduction

- [X] T001 [US1] Add a replayed Actions jobs secondary 403 followed by a full core bucket and successful pulls read in `tests/test_code_host.py`; red: primary core reset was reported instead of the 30-second secondary retry.

## Phase 2: Shared fix

- [X] T002 [US1] Make secondary evidence take precedence over zero remaining in `adapters/_http.py`, with retry timing and endpoint wording from the refused reply.
- [X] T003 [US2] Preserve primary-reset behavior and update conflicting prior expectations in `tests/test_code_host.py` and `tests/test_tracker_adapters.py`.

## Phase 3: Verification

- [X] T004 Run every explicit test file importing `adapters._http` and confirm the issue's test command passes without network.
- [X] T005 Inspect the final diff and record any remaining risk in `specs/938-secondary-limit/analysis.md`.
- [X] T006 [US2] Use primary wording in `tests/test_doctor.py` for the primary-reset fixture and retain its no-wait assertion.
- [X] T007 [US1] Add a failing direct HTTP 403 with `Retry-After` and zero remaining in `tests/test_tracker_adapters.py`, then label it as secondary in `adapters/_http.py`.
- [X] T008 Run all importing test files plus `tests/test_doctor.py` with the required interpreter and offline replay.

## Dependencies

T001 must fail before T002. T003 follows T002. T004 and T005 follow T003.
T006 to T008 are review follow-up work after T005; T007's test fails before its code change.
