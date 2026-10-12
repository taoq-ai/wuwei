# Specification Analysis Report: 901-reconcile

| ID | Severity | Summary | Resolution |
|----|----------|---------|------------|
| A1 | HIGH | The new guard refusal could loop with #892: a refused launch registers nothing, and the command it names must lead to a launch the guard accepts. | Resolved: `build next` records a `launch` of the same unused brief and the guard accepts it (US2-2); with `guards.enforce` off the seat registers as before, so #892 continues it (FR-006). |
| A2 | HIGH | At CAP the refusal's `build next` would record a new build, `wuwei next` would offer its launch, and the CAP refusal at launch only logs (#837 B5), so the seat would run unregistered. | Resolved: `build next` for a new build past the day's derived CAP waits (FR-009); `test_parallel_dispatch` shows the refusal, then the wait. |
| A3 | HIGH | Reconcile must never read as tested or approved. | Resolved: the record starts at `check`, the fast checks and the spec step check run, uncommitted files fail the build (`_unbuilt`), the gates follow from `next`, and the output lists what stays unmeasured (FR-001, FR-002). |
| A4 | HIGH | A rerun that reran the checks would count repeats and park unchanged dirty work. | Resolved: the record keeps the HEAD and uncommitted files it reconciled; unchanged means no write and no check (FR-003); the three-repository test repeats every call. |
| A5 | MEDIUM | `pr claim` moves a planned item to `raised`, past its checks and gates. | Resolved: `record_pr(built=True)` moves it to `implement` in the claim's own write, so a refused claim moves nothing (US3-1). |
| A6 | MEDIUM | A reconciled build on an older brief would make every later builder launch fail the guard's HEAD check. | Resolved: one brief per reconciled HEAD, `<item>-reconcile-<head12>`, reused on a rerun at that HEAD. |
| A7 | MEDIUM | Another repository or a competing worktree must not be absorbed silently. | Resolved: `adopt_worktree(repo=)` and `record_worktree` refuse before any write (US3-3). |
| A8 | MEDIUM | `pr claim`'s worktree listing failure exited 2; through the shared checkout it now prints the rerun and exits 0, like a fetch failure. | Accepted: the claim is recorded and the step names its rerun, as #879 does for the fetch. |
| A9 | LOW | Reconcile does not check CAP; a dirty reconciled item stays in `implement` and counts as building. | Accepted: the work exists and reconcile launches no seat; the builder `continue` follows the existing launch-set rules. |
| A10 | LOW | A builder seat that ran outside the record is not bound to the reconciled build. | Deferred: #892 already continues a registered stopped seat through `build next`. |
| R1 | HIGH | Review F1: a running builder seat with no build record kept committing after reconcile marked the build done. | Resolved: FR-010. |
| R2 | HIGH | Review F2: `--repo` or `--pr` replaced the item's recorded repository. | Resolved: FR-011. |
| R3 | HIGH | Review residual: no gate checked that it reviews the head the fast checks passed on. | Resolved for every build: FR-012. Records from before this change have no `checked` and keep the old rule. |
| R4 | MEDIUM | Review F3: counters reset on each reconcile, so a failing loop never parked. | Resolved: FR-013. |
| R5 | LOW | Review F4, F6, F5, F7. | Resolved: FR-014 to FR-016. |
| R6 | HIGH | Delta D1: a recheck at a gate ran fast checks only, so a committed private file or an uncommitted fix could be recorded as checked. | Resolved: FR-017. |
| R7 | MEDIUM | Delta D2: `checked` was HEAD at completion, not what the checks measured. | Resolved: FR-018; tests that call `complete_checks` directly now record the measured rows, as `build check` does. |
| R8 | LOW | The spec step is not rerun on a recheck at a gate. | Accepted: the gates read the spec; the dispatch backstop checks it before gates. |

Coverage: FR-001 to FR-018 each have tasks (T001 to T016), 100 percent. CRITICAL 0 open, HIGH 0 open.
