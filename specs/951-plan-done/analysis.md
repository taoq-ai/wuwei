# Cross artifact analysis: issue 951

Reviewed spec, plan, tasks, constitution, and existing plan, dispatch, report, close, and Owner step paths.

| ID | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| A1 | HIGH | A done parked item would still appear under Parked. | Plan and T004 exclude done status. Resolved. |
| A2 | HIGH | Live checks and build loops may exist without a registered seat. | FR-002 and T003 use `state.in_flight`. Resolved. |
| A3 | MEDIUM | A Yes could be reused for another reason. | FR-003 binds the token to item and reason; T001 tests it. |
| A4 | MEDIUM | Worktree or branch could disappear from report. | FR-006 and T004 list both and preserve item fields. |

No unresolved CRITICAL or HIGH findings. All FRs map to T001 through T005.

## Fresh-context review follow-up

| ID | Severity | Consistency finding | Resolution |
| --- | --- | --- | --- |
| F1 | HIGH | `plan.done` emits but classifies as warn. | Register silent in signal and emitted-kind map, T006. |
| F2 | HIGH | Done implement retains a CAP slot; done fix retains a held build. | Apply status terminal checks to shared building and held helpers, T007. |
| F3 | HIGH | Done parked item still offers an unusable resume decision. | Skip it in ASK_PARKS loop, T007. |
| F4 | MEDIUM | Manual build next can launch a builder on done work. | Route step and next_action to dispatch's done action, T008. |
| F5 | LOW | Park or carry can relabel completed work. | Refuse done status in dispose, T009. |
| F6 | LOW | Why and reference omit completion. | Record the event in why and document the command, T010. |

The new requirements FR-007 through FR-010 map to T006 through T010. No design spec conflict was found. F1 through F6 have failing tests observed before their changes, then passing focused tests. The existing merged item park test now expects refusal because merged items have done status. No CRITICAL or HIGH finding remains open.

Verification: 5239 passed in 359.61s (0:05:59) across the explicit importing test files, test_signal_status.py, test_docs.py, and test_cli.py.
