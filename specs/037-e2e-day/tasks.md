# Tasks: Scripted delivery day

## Setup

- [X] T001 Read existing producers, adapters and CI and record design in specs/037-e2e-day/plan.md.

## User Story 1: Replay a delivery day

- [X] T002 [US1] Write failing scripted day scenario in tests/test_e2e_day.py and confirm the missing fixture failure.
- [X] T003 [US1] Implement temporary workspace, recorded ports and scripted seats in tests/fakes/day.py until the day scenario passes.
- [X] T004 [US1] Write failing absent-scanner and integrity-drift scenarios in tests/test_e2e_day.py.
- [X] T005 [US1] Extend tests/fakes/day.py only as needed to drive real fail-closed guards.

## Validation

- [X] T006 Run targeted and full pytest suites, inspect duration and hygiene, and record results in specs/037-e2e-day/tasks.md.

## Dependencies

T001 -> T002 -> T003 -> T004 -> T005 -> T006. One story, executed sequentially.
No parallel implementation is needed because scenarios share the same fixture.

## Verification results

- T002 red: the day test failed because fakes.day did not exist.
- T003 green: the complete scripted day passed with existing production code.
- T004 red: the scanner scenario lacked agent_surface fixture support and the
  integrity scenario lacked a pinned test installation.
- T005 green: three scenarios passed, with real integrity measurement and guards.
- Targeted run: 3 passed in 2.28s; main day call 1.26s, below the 20-second target.
- Final full run: 4766 passed, 3 skipped in 77.78s (0:01:17).
- The three skips are existing load-sensitive latency benchmarks; no new test skips.
- All six added files passed whitespace, machine-path, em-dash and emoji checks.
- Existing PR CI collects the tests through its default pytest command.
- No production changes, runtime trust records or CI configuration changes were needed.

## Deferred

None. External merge completion is replayed as documented in the spec; no scenario
requires an xfail or an upstream implementation change.
