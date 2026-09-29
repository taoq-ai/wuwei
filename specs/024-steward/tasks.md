# Tasks: Steward seat and process metrics

## User Story 1: Measure the day

- [X] T001 [US1] Write failing metrics tests in tests/test_metrics.py for named counts, unmeasured sources and corrupt input.
- [X] T002 [US1] Implement recorded-source metrics and CLI in cli/wuwei/metrics.py and cli/wuwei/commands/metrics.py.

## User Story 2: Steward steering

- [X] T003 [US2] Write failing steward tests in tests/test_steward.py for third round, acknowledgement, run triggers, and queue.
- [X] T004 [US2] Implement producer-owned notes, queue and seat run in cli/wuwei/steward.py and cli/wuwei/commands/steward.py.
- [X] T005 [US2] Write failing integration tests in tests/test_steward.py for sweep, close, trace threshold and next-plan finding.
- [X] T006 [US2] Connect cli/wuwei/watch.py, cli/wuwei/commands/close.py, cli/wuwei/plan.py and cli/wuwei/dispatch.py.

## Polish

- [X] T007 Run full pytest suite, check written files for prohibited characters, and document deferred scope in specs/024-steward/spec.md.

## Review fixes

- [X] T008 Test and create third-round notes at planner dispatch.
- [X] T009 Test and signal tool-call due from the hook without launching a seat there.
- [X] T010 Test and deduplicate close retries and concurrent note reviews.
