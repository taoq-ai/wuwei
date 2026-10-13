# Tasks: Ad-hoc launch

## Setup and foundation

- [x] T001 Read repository rules and trace shared launch, binding and recovery in cli/wuwei/guards/agent_launch.py and cli/wuwei/brief.py.
- [x] T002 Complete specify, clarify and plan artifacts in specs/955-adhoc-launch/.

## US1: Direct launch

- [x] T003 [US1] Add field-case, privacy and explicit-reference tests in tests/test_agent_launch.py; run them and observe expected failure.
- [x] T004 [US1] Register private prompt metadata through the shared reservation in cli/wuwei/guards/agent_launch.py.

## US2: Guard preservation

- [x] T005 [US2] Add role, capacity, protected-path, gate and symlink tests in tests/test_agent_launch.py before implementation.
- [x] T006 [US2] Reuse shared launch checks and extract protected-path validation in cli/wuwei/brief.py.

## US3: Stop and recovery

- [x] T007 [US3] Add stop, trace and CLI recovery tests in tests/test_agent_launch.py before implementation; retain explicit seat start coverage.
- [x] T008 [US3] Extend prompt binding in cli/wuwei/brief.py and stop handling in cli/wuwei/guards/agent_launch.py without a new lifecycle.

## Verification

- [x] T009 Update obsolete missing-marker assertions in tests/test_agent_launch.py and tests/test_launch_contract.py.
- [x] T010 Run explicit affected test files, review correctness/security/simplicity, update docs/site/recovery.md and docs/site/reference.md, and record evidence in specs/955-adhoc-launch/analysis.md.

## Dependencies and execution

T001 -> T002 -> tests T003/T005/T007 -> implementation T004/T006/T008 -> T009 -> T010.
The tests share a file, so execute sequentially. US1 provides the registration
used by US2 and US3; all three are required for completion. No parallel agents
are needed. Each story has an independent targeted pytest selection.

## Authorized review corrections

- [x] T011 [US2] Reproduce HIGH-1 in tests/test_dispatch.py, then refuse prompt-backed gate receipts in cli/wuwei/dispatch.py.
- [x] T012 [US2] Reproduce HIGH-2 in tests/test_agent_launch.py, then preserve #901 in cli/wuwei/guards/agent_launch.py.
- [x] T013 [US1] Reproduce MEDIUM-3 in tests/test_agent_launch.py, then restrict item inference in cli/wuwei/guards/agent_launch.py.
- [x] T014 [US3] Reproduce continued-prompt rebinding in tests/test_agent_launch.py, then fix the shared helper in cli/wuwei/brief.py.
- [x] T015 [US2] Reproduce nested-seat and planner launches in tests/test_agent_launch.py, then refuse them in cli/wuwei/guards/agent_launch.py.
- [x] T016 Correct the #937 claim, update docs and spec-kit artifacts, and run explicit affected tests including tests/test_signal_status.py.

## Round 2

- [x] T017 Reproduce ambiguous metadata builders with missing and running records; inspect all matches under the launch lock (FR-010).
- [x] T018 Reproduce nested Explore and general-purpose registration; limit refusal to typed launches (FR-009).
- [x] T019 Reproduce cross-item prompt collisions; refuse ambiguous pending bindings with an Item: retry (FR-013).
- [x] T020 Reproduce prompt sentinel gate batching and missing-worktree advice; fix existing checks (FR-011, FR-012).
- [x] T021 Run all requested module importers explicitly, review the delta and record pytest summaries.
