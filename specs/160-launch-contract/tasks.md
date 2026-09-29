# Tasks: Seat launch contract

## Setup

- [X] T001 Reproduce the operator failure read-only and record findings in specs/160-launch-contract/plan.md.
- [X] T002 Create and validate specs/160-launch-contract/spec.md and plan.md.

## US1: Briefed dispatch and continuation

Independent check: returned runtime instructions register the intended seat; continuation retains the reference; missing markers are refused with the required first line.

- [X] T003 [US1] Write tests/test_launch_contract.py for dispatch across roles, continuation, invalid handles and missing-marker guidance; run and confirm expected failures.
- [X] T004 [US1] Add the formatter and shared prefix in cli/wuwei/brief.py, use them in adapters/runtime/claude.py and cli/wuwei/guards/agent_launch.py, and pass the US1 tests.

## US2: Closing steward

Independent check: the steward command's launch prompt passes the same guard and registers its seat.

- [X] T005 [US2] Add and run a failing steward close integration test in tests/test_launch_contract.py before changing the shared dispatch path.
- [X] T006 [US2] Verify cli/wuwei/steward.py reaches the shared formatter through runtime dispatch and pass the US2 test without duplicate formatting.

## Documentation and verification

- [X] T007 Document generated prompts, first line, workspace-relative paths and agent types in docs/site/concepts.md and skills/wuwei-plan/SKILL.md; point charters/planner.md at generated instructions and regenerate agents if needed.
- [X] T008 Run focused regressions and the complete tests/ suite with the supplied interpreter; inspect all changed files for prohibited characters, local paths and scope drift.

## Dependencies and execution

T001 -> T002 -> T003 and T005 -> T004 -> T006 -> T007 -> T008.
Both stories share dispatch, so write both failing tests before implementation. No parallel implementation is useful for this small shared change. Validate US1 first, then US2, then the full suite. Extension hooks are skipped as requested.

## Verification evidence

- Regression tests failed first for missing brief prefixes, absent continuation prompts and missing refusal guidance.
- Focused launch, runtime and steward regression set: 117 passed.
- Full suite: 4950 passed, 5 skipped in 102.97s (0:01:42).
- Generated agents, diff whitespace and file hygiene checks passed.
- Independent correctness, security and simplicity review: no blocking findings.
