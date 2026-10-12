# Analysis: 862-scanner-seamless

CRITICAL 0, HIGH 0 open.

| ID | Severity | Summary | Resolution |
|---|---|---|---|
| A1 | HIGH | Caching every unmeasured reason would keep a fast "ZIRAN missing" all day after the owner installs it. | Resolved. FR-003 remembers measured results always and an unmeasured one only when the call took 10 s or more; T003 covers both. |
| A2 | HIGH | Diff-only S4 could let an item through on a finding it made reachable in an unchanged file. | Accepted with the owner's audit recommendation: findings in changed files keep blocking; pre-existing findings stay discovery candidates every morning. Recorded under Assumptions. |
| A3 | HIGH | Seat dedup could hide a new risky chain after a resume. | Resolved. The key is session plus chain; a different chain parks again (FR-006, T006). |
| A4 | MEDIUM | `test_seat_wins_over_registration` asserts four parks for four identical rows. | Its assertion pins S6; it changes to one, as T006 states. |
| A5 | MEDIUM | The S4 test fixture brief has no `Merge-base:` line and the fake vcs has no `diff_stat`. | The fixture gains both; a missing line is unmeasured (T008). |
| A6 | MEDIUM | The close card token changes for days with one critical finding (sorted list of one). | Accepted: only affects cards asked after the upgrade. |
| A7 | LOW | Two discoveries at once may both audit. | Accepted; ponytail comment in code. |
| A9 | MEDIUM | Found in implement: verdict lint refuses a FIX finding without `file:line`, so an S4 row for a null-line finding would make the receive unmeasured. | Resolved. The S4 row renders a file-level finding as `<file>:1`; T008 covers it. |
| A10 | MEDIUM | Found in implement: `tests/test_reasons.py` requires every reason literal to name a next step; f-string fragments hid it. | Resolved. One `scanner._unmeasured` with a literal next step; the sweep text says `retry ... or run ...`. |
| A8 | LOW | S9 sweep cost and P2 ZIRAN walk remain. | Deferred, follow-up issue. |

Review round (security FIX): F1, F2 and F3 (HIGH, blocking) resolved by T011 to T013; F5
resolved by T014; F4 and F6 recorded under Assumptions and Edge Cases; F7 deferred to S9.

Coverage: FR-001 to FR-013 map to T001 to T008 and T011 to T014, 100 percent. Constitution check: no conflict.
