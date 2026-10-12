# Analysis: 870-scanner-builder-loop

CRITICAL 0, HIGH 0 open.

| ID | Severity | Summary | Resolution |
|---|---|---|---|
| A1 | HIGH | `Bash` in the local set could hide shell egress. | Resolved. ZIRAN traces name only `Bash`, so a Bash-only chain never showed egress anyway. Any chain with a non-local tool still parks. Bash egress and deploys stay on the edges floor (`edges.check_send`, `edges.check_deploy`). |
| A2 | HIGH | Editing `test_seat_wins_over_registration` could read as loosening a test. | Resolved. Its assertion was the bug; it keeps its subject with an outward chain, and T001 adds the parking assertion. |
| A3 | MEDIUM | Writes outside the worktree are not decided, because ZIRAN gives no paths. | Accepted, recorded as an assumption and under Deferred. This was never decided before either. |
| A4 | MEDIUM | Adding `reason` changes the `closing.scanner_hold` token for new events. | Accepted. It only affects new events. |
| A6 | HIGH | Review F1: the edges floor does not cover Bash egress, so a credential read then curl then write was dropped. | Resolved by T006 and T007: an all-local chain parks when the session's spans name a private file. |
| A7 | HIGH | Review D1: redact's broad private-file check re-parked 22 of 59 real builder sessions. | Resolved by T009: the scanner has its own narrow credential-location check over path-like words; redact is unchanged. |
| A5 | LOW | Grouping also lowers the page count on the status line. | Intended. |

Coverage: FR-001 to FR-004 each map to T001-T004, 100 percent.
