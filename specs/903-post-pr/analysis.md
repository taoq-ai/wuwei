# Specification Analysis Report: 903-post-pr

| ID | Severity | Summary | Resolution |
|----|----------|---------|------------|
| A1 | HIGH | Requiring arch on every delta of an item with a PR could add a review to a claimed PR's first gate round. | Accepted and recorded (spec Assumptions): the charter makes delta checks arch's once a PR is open; the claimed e2e test now runs the arch delta. |
| A2 | HIGH | Rotating from `raised` changes which records merge reads. | Resolved: `_recorded_gates` reads delta else initial and excludes rotated records (round `delta`) from the round-one head agreement; the full suite passes. |
| A3 | HIGH | The gated push for raised PRs must keep the lease, fast-forward and checked-head protections. | Resolved: only the ownership condition is removed; the push in the issue's test is leased on the raised head and goes through `push_check`. |
| A4 | HIGH | A red listing row could open a fix while the fix that answers it is in review. | Resolved: the offers branch fires only when the PR head is the worktree HEAD; `_fix_round` keeps the delta step otherwise; `test_red_checks_on_an_older_pr_head_leave_the_gates_to_read_the_new_one`. |
| A5 | MEDIUM | `--complete` with no recorded `--run` now refuses; a planner that skipped `--run` must run it. | Accepted: the rebase action names `--run` then `--complete`; an unknown start head cannot be leased. |
| A6 | MEDIUM | Extending the push guard could refuse a legitimate push from a raised PR's worktree. | Resolved: after the link no step pushes from the worktree; the rebase pushes through the vcs port, not a seat's Bash. Before the link (the raise) no PR is recorded. |
| A7 | MEDIUM | An unmeasured listing (#900) must not drive the red branch. | Resolved: the branch skips a repository whose last read failed. |
| A8 | LOW | Kept round keys could collide once the round count resets at raise. | Resolved: `rotate` takes the next free `round<n>`. |
| A9 | LOW | #896 (scanner) works in parallel. | No overlap: no scanner file changes. |
| A10 | LOW | The conflict split (rebase for raised, merge round for claimed) remains. | Accepted (spec Assumptions): it follows whose commits are on the branch. |

Coverage: FR-001 to FR-008 each have tasks (T001 to T012), 100 percent. CRITICAL 0 open, HIGH 0 open.
