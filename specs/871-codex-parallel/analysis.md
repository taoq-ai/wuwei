# Analysis: 871-codex-parallel

CRITICAL 0, HIGH 0 open.

| ID | Severity | Summary | Resolution |
|---|---|---|---|
| A1 | HIGH | `test_opinion_rerun_polls_the_running_job` asserted that a rerun after a failed job polls the same failed job, the bug in the issue. | Resolved. It now covers what it should: a rerun while the job still runs polls it (no dispatch). The failed case moved to `test_failed_opinion_frees_its_seat_and_the_rerun_relaunches`, which asserts the error text, the stopped seat and the fresh `dispatch`. |
| A2 | HIGH | The start lock could serialize whole jobs, not starts, and starve parallel seats. | Resolved. The lock holds only until the job reports `threadId` or ends (the companion patches `threadId` into its job index on `turn/started`), bounded by `START_SECONDS` (60 s); the job itself runs unlocked. |
| A3 | MEDIUM | `threadId` as the readiness sign is companion internals, not a documented contract. | Accepted with a `ponytail:` note. A companion that never reports it costs at most 60 s per start; a status error ends the wait at once. |
| A4 | MEDIUM | The lock is per workspace; two workspaces on one host can still start app-servers together. | Resolved in fix round 1 (review F2): the lock is `wuwei-start.lock` in the Codex home. |
| A5 | MEDIUM | A failed delta continuation: should the rerun dispatch fresh? | Decided: the delta round continues again (the initial thread is the one to resume, and `--resume-last` skips a job without a thread); only the initial round dispatches fresh. |
| A6 | MEDIUM | A turn that fails inside Codex has no `errorMessage`; the refusal would still say only `failed`. | Resolved. `status` falls back to the failed job's `summary`, which the companion sets to the first line of the failure (test covers both and a running job without either). |
| A7 | LOW | The retro line is a Codex-only prompt addition. | Accepted. Claude seats get the contract from the charter and the stop hook, and their launch prompt is matched by digest; one table (`verdict.FORMAT`) renders both. |
| A9 | LOW | Review F3: an owner's unmeasured stop leaves the old job running, and the relaunch would put two jobs on one verdict file. | Resolved in fix round 1: the relaunch reads the old job and cancels it while it is queued or running (new port operation `cancel`). |
| A8 | LOW | A second-opinion brief keeps the `Model:` line it was written with, so a model changed after the first launch is not picked up on relaunch. | Pre-existing, outside this issue; recorded under Deferred in the spec. The quickstart forces its failure with `CODEX_HOME`, not a bad model, for this reason. |

| A10 | HIGH | L1: a Codex gate seat cannot write the day's decisions directory; its prose was linted and rejected. | Resolved: FR-006, T014-T015. The verdict is the final message, the prompt carries `verdict.section()`. |
| A11 | HIGH | L2: a Codex builder cannot commit (git metadata outside the sandbox) and the build was marked done on an unchanged head. | Resolved: FR-007, FR-008, T016-T017. WUWEI commits with the repo identity; `complete_checks` refuses a dirty tree or an unchanged head for every runtime. |
| A12 | MEDIUM | L2: `git add --all` may take stray files the job left. | Accepted with a `ponytail:` note: the prompt forbids other writes, the repository's hooks and `.gitignore` apply, and the gates review the diff. |
| A13 | LOW | L3: a broker started under a broken `CODEX_HOME` is reused by the relaunch. | Quickstart note; the companion has no stop command. |

Coverage: FR-001 T001-T002, FR-002 T003-T004, FR-003 T003-T004, FR-004 T005-T006, FR-005
T007-T008, FR-006 T014-T015, FR-007 and FR-008 T016-T017, 100 percent. SC-001 and SC-002 are also exercised by `quickstart.md` against the
real companion.
