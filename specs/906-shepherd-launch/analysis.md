# Specification Analysis Report: 906-shepherd-launch

Artifacts: spec.md, plan.md, tasks.md, constitution 2.4.0. Read together with 887-pr-wait (same
batch, same branch).

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| A1 | Coverage | HIGH | spec US2.6, plan 6 | "New activity during a reply": without a target the reply goes to whichever reply is owed first, which a fresh comment can take. | `--thread` names the target; a thread no longer owed is refused (exit 2). T004 covers it. Resolved. |
| A2 | Inconsistency | HIGH | spec FR-006, `closing.py` | The shepherd duty leaves `next`'s duty list, but `close` still names due duties by their record. | The record becomes `wuwei pr act <pr>`, which records it when nothing is owed; close stays correct. Resolved. |
| A3 | Ambiguity | MEDIUM | spec US2.4 | How a Yes on the scope card reaches the round: the card's record is the command the planner runs again. | The card's record is the exact `pr act <pr> --thread <id> --scope <reason>`; rerun with the owner's Yes opens the round. Resolved in plan 6. |
| A4 | Underspecification | MEDIUM | spec US3.1 | A `duty.done` stamped after the read can hide a comment that landed during the read. | `as_of` is the time before the read; `derive.duties` uses it. Resolved (FR-005). |
| A5 | Coverage | MEDIUM | spec US1.2 | A shepherd launch that stays offered after its seat starts keeps `next` in `set`, so `pr wait` is never offered. | Offers skip a registered revision seat (T001, T003). Resolved. |
| A6 | Constitution | LOW | plan 3 | III one behaviour, one function: the seat shape duplicated beside `raise_action`. | `_seat` is shared. Resolved. |
| A7 | Scope | LOW | spec Assumptions | Shepherd offered only while raised; a question during a fix round waits. | Recorded as an assumption; `pr wait` and `next` offer it once the round returns. Accepted. |
| A8 | Boundary | LOW | plan Constitution Check | #901 builder edits `guards/agent_launch.py`, `adopt_worktree`, `claim_pr`, reconcile. | Not touched. Accepted. |

No CRITICAL finding. HIGH findings A1 and A2 are resolved in the plan and tasks.

Coverage: every FR maps to a task (FR-001 T001/T007, FR-002 T003/T008, FR-003 T004/T009, FR-004
T004/T009/T010, FR-005 T002/T005/T009, FR-006 T003/T010).

## Review fix round

The review (906-findings) found F1 (a due duty with nothing in next), F3 (a second seat beside a
running one, the viewer's own replies as activity), F4 (P1 bot threads not answerable), F5 (pr wait
blind to a merge), F6 (a replayed scope Yes) and F7 (planner charter version shared with #901).
F2 was settled by a live probe: `latestReviews` carries thread replies. All are resolved per
tasks T014 to T019.
