# Tasks: Build environment failures and seat usage

**Input**: [spec.md](spec.md), [plan.md](plan.md)  
**Tests**: Required, failing before each implementation task.

## Phase 1: Environment failures (US1)

- [X] T001 [US1] Add failing adapter tests for missing runner, interpreter, and development dependency in tests/test_fast_checks.py.
- [X] T002 [US1] Classify environment failures in adapters/checks/local.py.
- [X] T003 [US1] Add failing build tests for first check park and ordinary code feedback in tests/test_build.py and tests/test_build_next.py.
- [X] T004 [US1] Park environment results immediately in cli/wuwei/commands/build.py.

## Phase 2: Seat usage (US2)

- [X] T005 [US2] Add failing Codex payload usage test in tests/test_runtime.py.
- [X] T006 [US2] Copy stored Codex result usage in adapters/runtime/codex.py.
- [X] T007 [US2] Add failing measured and unmeasured usage tests in tests/test_build.py and tests/test_build_next.py.
- [X] T008 [US2] Normalize seat usage from runtime results and SubagentStop in cli/wuwei/commands/build.py.

## Phase 3: Role runtime (US3)

- [X] T009 [US3] Add failing builder and other-role policy tests in tests/test_build.py and tests/test_runtime_cli.py.
- [X] T010 [US3] Select the approved role runtime at launch in cli/wuwei/commands/build.py and cli/wuwei/commands/runtime.py.
- [X] T011 [US3] Add failing steward role policy test in tests/test_steward.py.
- [X] T012 [US3] Select the steward role runtime in cli/wuwei/steward.py.

## Phase 4: Verification

- [X] T013 Run the full required pytest suite and inspect changed files for forbidden content.

## Dependencies

T001 before T002; T003 before T004; T005 before T006; T007 before T008; T009 before T010; T011 before T012. Each phase can be checked independently before final verification.

## Deferred

Historical usage events are not migrated.
