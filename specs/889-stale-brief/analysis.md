# Specification Analysis Report: 889-stale-brief

| ID | Severity | Summary | Resolution |
|----|----------|---------|------------|
| A1 | HIGH | Moving `start` to the current HEAD on the replacement would park a hand-back whose work is already committed (no change over the start head). | Resolved: the start head is kept (FR-002); test asserts it and the item reaches `gate`. |
| A2 | HIGH | Commits made outside the record could skip checks or gates. | Resolved: the replaced build still runs a seat, the fast checks and `_unbuilt` (private files since the kept start), then moves to `gate`. |
| A3 | HIGH | Relaxing the refusal for every unfinished build would drop an in-flight continue, wait or pending check. | Resolved: only `ready` with `launch` on the same worktree and a stale brief HEAD (FR-003); unmoved case tested. |
| A4 | MEDIUM | A fresh record would reset `fix_rounds`, lifting the round cap for a stale fix-round launch. | Resolved: the previous record is spread into the replacement. |
| A5 | MEDIUM | A pre-start-head record (0.29.0) would carry no start, so the outside commits would skip the private-file check. | Resolved: the old brief's logged HEAD is the start (legacy test case). |
| A6 | LOW | The guard message still says "write the brief again" without naming `build next`. | Accepted: the next launch is refused with "seat brief differs from active build", which names `build next`. |
| A7 | MEDIUM | Review F4: a hand-back on a later day has no record, so a fresh start at HEAD hides the outside commits and parks on no change. | Resolved: a fresh record starts at the brief's merge base (FR-005). |
| A8 | LOW | Review F1, F2: a headless old brief made an unmoved build replaceable; a stale fix launch lost its feedback. | Resolved: FR-003, FR-004. |
| A9 | HIGH | Delta D1: a record on a brief another seat ran unmeasured looped between "write a fresh brief" and "cannot replace". | Resolved: such a record is stale (T008). |
| A10 | LOW | Delta D2, D3: a seat of another item could be adopted; a rebased-away base would widen the private-file scan. | Resolved: item match (T009); ancestor check (T010). |

Coverage: FR-001 to FR-005 each have tasks (T001 to T010), 100 percent. CRITICAL 0 open, HIGH 0 open.
