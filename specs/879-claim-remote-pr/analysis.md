# Specification Analysis Report: 879-claim-remote-pr

| ID | Severity | Summary | Resolution |
|----|----------|---------|------------|
| A1 | HIGH | Creating the worktree only inside `claim_pr` would leave the `worktree add --branch` command that `pr act` prints broken for remote-only branches. | Resolved: the fetch is in `worktree_checkout`, which every existing-branch checkout calls; `claim_pr` reuses `worktree.add` (FR-001, FR-002). |
| A2 | HIGH | `next` resolving `pr act` on every call could open a second fix round while the first adopted build is ready or running (`open_fix` accepts a `ready` record on a `raised` item). | Resolved: a ready build is offered as `build next`; running or check gets no offer (test_derive table). |
| A3 | HIGH | A fork head cannot be fetched from `brief.remote` by branch name, and a fix cannot be pushed back. | Resolved: refused with the exact read-only commands, exit 1, claim kept. |
| A4 | MEDIUM | Fetching from a seat or the planner might hit a guard. | Resolved: on the adapter allowlist; `edges.py` refuses only irreversible actions; the fetch runs inside the CLI. |
| A5 | MEDIUM | `worktree_checkout` gains a `remote` argument. | Resolved: registry, fake and contract test updated; the default None keeps old callers working. |
| A6 | MEDIUM | After an adopted fix-round builder stops, nothing pushes for red checks or threads (the conflict round pushes through `--run`/`--complete`). | Accepted, deferred. |
| A7 | LOW | The listing has no thread count. | Accepted: the step is offered only while the shepherd duty is due, and `pr act` classifies the threads. |

Coverage: FR-001 to FR-005 each have tasks (T001 to T009), 100 percent. CRITICAL 0 open, HIGH 0 open.
