# Tasks: Preserve seat results and recover committed builds

T001-T010 describe the original implementation. T011-T015 supersede its payload
aliases, prose classifier, path-form fix and explicit completion bypass.

## Setup and foundations

- [x] T001 Read governing documents and trace shared callers in cli/wuwei/brief.py, cli/wuwei/commands/build.py and cli/wuwei/guards/agent_launch.py.
- [x] T002 Record scope, assumptions and root causes in specs/937-seat-results/spec.md and plan.md.

## US1: Final report in default mode

- [x] T003 [US1] Add stop compatibility fixture and failing replay regressions in tests/test_handback.py and tests/payloads/SubagentStop/.
- [x] T004 [US1] Normalize stop evidence in cli/wuwei/brief.py, cli/wuwei/commands/hook.py and cli/wuwei/guards/agent_launch.py; pass replay tests.

## US2: Live tasks and tooling gaps

- [x] T005 [US2] Reproduce refused hand-back live-seat and tooling Blocked cases in tests/test_handback.py.
- [x] T006 [US2] Require terminal evidence in cli/wuwei/brief.py and classify tooling gaps through cli/wuwei/verdict.py and cli/wuwei/guards/verdict.py.

## US3: Committed build recovery

- [x] T007 [US3] Reproduce clean new HEAD without a result through next/check and reconcile in tests/test_build_next.py and tests/test_reconcile.py.
- [x] T008 [US3] Recover at the shared build checkpoint in cli/wuwei/commands/build.py; retain recorded worktree identity and name its recovery path in cli/wuwei/state.py.

## Verification and review

- [x] T009 Run every test file importing changed modules; record exact outcomes in specs/937-seat-results/analysis.md.
- [x] T010 Review correctness, identity, race protections and minimal scope; record findings in specs/937-seat-results/analysis.md and leave changes uncommitted.

## Dependencies and strategy

T001 -> T002 -> T003 -> T004 -> T005 -> T006 -> T007 -> T008 -> T009 -> T010.
Each story has its own regression check before implementation. Source edits are
sequential because US1 and US2 share transcript code. Independent test reads may
run concurrently; no parallel implementation is needed. US1 is the smallest
useful increment, followed by live-seat protection and committed recovery.

## Field follow-up

- [x] T011 Reproduce both field failures and the manual stopped-seat refusal.
- [x] T012 Fix delayed final text and shared continued-round recording.
- [x] T013 Correct terminal evidence; delete payload aliases and prose classification.
- [x] T014 Require completion for reconcile, add confirmed same-repo rebind, correct stale advice and launch blockers.
- [x] T015 Verify all importing tests, record findings and final diff size.

## Round 2

- [x] T016 Reproduce torn transcript rows and unauthorized manual continuation.
- [x] T017 Bound all transcript retries and record only bound continued reports.
- [x] T018 Test missing-old-tree recovery; resolve small nits and document LOW decisions.
- [x] T019 Run all importing test files and update analysis with exact outcomes.
