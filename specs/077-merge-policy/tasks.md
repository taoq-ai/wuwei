# Tasks: 077 merge policy

## US1: Fresh eligibility

- [X] T001 [US1] Add failing adapter tests for rulesets, files, merge identity and outcome reads in tests/test_merge_ports.py.
- [X] T002 [US1] Implement measured evidence in adapters/code_host/github.py and update port contracts, fakes and recordings.
- [X] T003 [US1] Add failing policy tables covering eligibility, source refusals and malformed evidence in tests/test_merge.py.
- [X] T004 [US1] Implement config and the single check function in cli/wuwei/merge.py, reusing verdict and obligation readers.

## US2: Pinned mutation

- [X] T005 [US2] Add failing CLI, guard, race, reservation and journaling tests in tests/test_merge.py and tests/test_pr_guards.py.
- [X] T006 [US2] Implement cli/wuwei/commands/merge.py, guard delegation and reserved merge journal/events.

## US3: Post-merge protection

- [X] T007 [US3] Add failing tests for red checks, revert recovery, rollover and mature outcome rates in tests/test_merge.py.
- [X] T008 [US3] Implement watch reconciliation, breaker and metric comparison in cli/wuwei/merge.py and cli/wuwei/watch.py.

## Verification

- [X] T009 Run the full pytest suite, inspect changes for scope, trust, portability and hygiene; update specs/077-merge-policy/tasks.md with results.

## Adversarial review fixes

- [X] T010 [F1] Reproduce expired monitoring and repeated outcome reads; stop host reads at 28 days, persist the outcome at 14 days, and use compare messages without patch fetches for other revert polls. Verify expired monitor errors clear and later reverts still trip the breaker.
- [X] T011 [F2] Reproduce ruleset checks with omitted integration_id; accept any source while retaining integer validation for a supplied integration id.

## Verification result

- Full suite after F1 and F2 fixes: `4104 passed, 1 skipped in 38.34s` using
  `python -m pytest -q`.
- Every new behaviour began with a failing in-process or recorded-transport test.
- Independent review and delta review findings were reproduced and fixed, including
  breaker reset, per-incident pages, incomplete mature metrics and independent revert detection.
- Final diff and changed-file hygiene checks passed. No real forge calls or network were
  used; all changes remain in the working tree.
