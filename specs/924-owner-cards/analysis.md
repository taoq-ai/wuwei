# Specification Analysis Report: 924-owner-cards

| ID | Severity | Summary | Resolution |
|----|----------|---------|------------|
| A1 | CRITICAL | Security review F1: a first build accepted an approval outside the card that a session could supply itself (`script` plus `env -u`). | Resolved: removed; the card is the only approval. `test_a_pty_wrapped_run_without_an_answered_card_is_refused` was red against the first build and is green now. |
| A2 | HIGH | Design 9.1 (#831) says nothing runs in a terminal. | Resolved: it stays true; the 9.1 amendment describes only the #856 binding and is labelled for owner review. |
| A3 | MEDIUM | The fix must not hide the root cause. | Resolved: the binding is fixed in #856; the field replay test was red first. |
| A4 | LOW | The deploy guard appends `owner.approved` per approved call, which spends the Yes (#856 FR-005). | Accepted: a deploy is one action; a retry asks the card again. |
| A5 | LOW | `dispatch next` and `pr act` read the card answer directly and never spend it. | Accepted: unchanged planner steps; their tokens change with the verdict or the thread. |

Coverage FR-001 to FR-004, 100 percent; CRITICAL 0, HIGH 0 open.
