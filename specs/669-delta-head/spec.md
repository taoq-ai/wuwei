# Feature Specification: the delta round refreshes the reviewer's recorded head so an in-session reviewer can re-review a fix without a new seat

**Feature Branch**: `669-delta-head`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #669 (owner, 2026-10-10, item 33): the delta round did not refresh
the reviewer's recorded head, and `dispatch receive` checks two heads no truthful verdict
can pass together (the stale brief head and the live worktree head). The only working path
was a new reviewer under a new seat name, a second full security review of a one-line fix.
The reviewer refused to write a false head. Deliver: `dispatch` records the delta head on
the reviewer's seat when the fix round closes; `receive` checks the verdict's `Head:`
against that delta head only; the delta brief names it; a verdict with the pre-fix head is
refused with the two heads named.

## Root cause

Reproduced read-only on `main` (d3b7066) with a scratch workspace outside the repository:
three gate seats received at the initial head `abc1234...`, quality said FIX, the fix round
committed `def5678...` (the live worktree head), the item moved to `delta`, and the
quality seat was continued in-session (resumed, not relaunched through the Agent tool), so
no hook touched its seat record. Then `dispatch.receive('A', 'quality', 'quality-1',
'delta')`:

```text
def5678 REFUSED: verdict HEAD differs from dispatched brief; have the sentinel write the verdict with the Head from its brief, then receive it again
abc1234 REFUSED: verdict HEAD differs from current worktree HEAD; write a fresh gate brief for the current HEAD and run bin/wuwei dispatch next A
```

- `cli/wuwei/dispatch.py:661` to `663`, in `receive`: the verdict's `Head:` must appear in
  the seat's brief text (`HEAD: <sha>`) or prefix the seat's recorded `head`. In a delta
  round both still hold the initial head: the brief file is the initial gate brief, and the
  seat's `head` is written only by the launch guard
  (`cli/wuwei/guards/agent_launch.py:204` to `209` and `240` to `243`), which runs on an
  Agent launch. An in-session resume of the same reviewer fires no launch hook (nothing in
  `cli/` handles a resume), so the seat keeps the initial head.
- `cli/wuwei/dispatch.py:664` to `673`, the next check in `receive`: the verdict's `Head:`
  must prefix the live worktree head, which after the fix round is the new head.
- So the new head fails the first check and the old head fails the second. Only a fresh
  Agent launch (which rewrites the seat with the live head) or a new seat name passes.
- `cli/wuwei/dispatch.py:547` to `561`, the delta branch of `_seats` (the issue's "line
  582" on an older main), builds the delta `continue` action but records nothing, and
  `_delta_feedback` (`cli/wuwei/dispatch.py:598` to `606`) names only `<initial head>..HEAD`,
  so the reviewer is never told which head its delta verdict must carry.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Where is "when the fix round closes" in code? A: In `dispatch next` for an item in
  `delta`, at the point it builds the reviewer's delta `continue` action (`_seats`, delta
  branch). The fix round closes when the build loop moves the item from `fix` to `delta`;
  the first `dispatch next` after that is the step that hands the reviewer its delta work,
  so it reads the live worktree head there and records it on the reviewer's seat as
  `delta_head`. Recording it in the build loop instead would make the builder's code write
  reviewer seats, and would miss a head that moved after the checks.
- Q: Why a new seat field and not the seat's `head`? A: `delta_due`
  (`cli/wuwei/dispatch.py:568`) and the launch guard read `head` equal to the initial head
  as "this seat is still due its delta continue". Overwriting `head` would make the
  continue disappear before it runs.
- Q: What does `receive` compare in a delta round? A: The verdict's `Head:` against the
  seat's `delta_head`, else the seat's `head` (an Agent relaunch rewrites the seat with the
  live head and no `delta_head`). Never against the brief text when either is recorded; a
  fresh delta seat with neither keeps the brief check (amended during implementation). The live worktree check that
  follows is unchanged: the delta head is the live head, so the two agree.
- Q: Does the second-opinion (`<role>@<runtime>`) delta change? A: No. `wuwei dispatch
  opinion` already rewrites its seat with the live head when it continues the job
  (`cli/wuwei/dispatch.py:780` to `783`), and `_seats` skips `@` roles before the delta
  branch.

## User Scenarios and Testing

### User Story 1 - the same reviewer re-reviews the fix (Priority: P1)

A gate said FIX; the builder fixed it and the item is in `delta`. The planner runs
`wuwei dispatch next <item>`, continues the same reviewer in its session with the delta
feedback, and the reviewer writes its verdict with the head the feedback names.
`wuwei dispatch receive <item> <role> <seat> --round delta` records it under the same seat
name. No second seat, no second full review.

**Why this priority**: it is the owner's reported defect.

**Independent Test**: in-process, `tests/test_dispatch.py`, with a fake VCS whose head is
the post-fix head; the seat record is not relaunched (its `head` stays the initial head).

**Acceptance Scenarios** (from the issue's Acceptance):

1. **Given** a fix round that moved the head from `abc1234...` to `def5678...` and a
   stopped reviewer seat still recording the initial head, **When** `dispatch next` runs in
   `delta`, **Then** the seat records `delta_head` `def5678...` and the `continue`
   feedback names `def5678...`.
2. **Given** that recorded delta head, **When** the reviewer's delta verdict carries
   `Head: def5678` and `receive --round delta` runs with the same seat name, **Then** it is
   accepted and recorded with head `def5678`.
3. **Given** that recorded delta head, **When** the delta verdict carries the pre-fix
   `Head: abc1234`, **Then** `receive` refuses (exit 1), the reason names both `abc1234` and
   the delta head `def5678...`, and no delta verdict is recorded.

### Edge Cases

- The reviewer is relaunched as a fresh Agent (the path that works today): the launch guard
  rewrites the seat with the live head and no `delta_head`; `receive` uses the seat's
  `head`, so the same verdict is accepted as before.
- `dispatch next` runs again with the head unchanged: no second state write or event.
- The builder commits again after the delta head was recorded and before the reviewer
  stops: the next `dispatch next` (the seat is still due) records the newer head; a verdict
  with the older head is refused by the delta-head check or the unchanged live check.
- The live head cannot be read (VCS adapter exit 2): `dispatch next` fails closed (exit 2
  through the existing `ValueError` path; `next --all` lists the item as refused); nothing
  is recorded.
- A seat with neither `delta_head` nor a fresh `head` (state from before this change):
  `receive` refuses a new-head verdict naming both heads and pointing to `dispatch next`,
  which records the delta head.
- The initial round is unchanged: brief text or seat `head`, then the live check.

## Requirements

### Functional Requirements

- **FR-001**: When `dispatch next` builds a reviewer's delta `continue` action, it reads the
  item worktree's live head through the VCS port and records it on that seat as
  `delta_head`, in one state write with a `gate.delta_head` event (`item`, `seat`, `head`),
  only when the recorded value differs.
- **FR-002**: The delta feedback (both the delta review and the light re-read text) names
  the delta head: the fix range ends at it and the reviewer is told to write it on the
  `Head:` line.
- **FR-003**: In a delta round, `receive` accepts the verdict's `Head:` only when it is a
  prefix of the seat's `delta_head` (else the seat's `head`), and refuses otherwise with a
  reason naming the verdict head and the delta head. The brief text is not consulted in a
  delta round when either head is recorded on the seat; a fresh delta seat with neither
  keeps the existing brief check.
- **FR-004**: The initial-round head check, the live worktree check, the sibling-head check
  and the scanner path in `receive` are unchanged.
- **FR-005**: `gate.delta_head` is listed in `EVENT_PRODUCERS` as produced by
  `wuwei dispatch next` (so `wuwei event` cannot forge it) and in `signal.SILENT`
  (bookkeeping, no attention).
- **FR-006**: `docs/site/daily.md` step 5 (Delta) says the continue feedback names the delta
  head and the same seat may be continued in its session.

### Key Entities

- **Seat `delta_head`**: full SHA of the item worktree at the delta dispatch; written only by
  `dispatch next`; read only by `receive` in a delta round.

## Success Criteria

- **SC-001**: An in-session reviewer's delta verdict with the post-fix head is recorded
  under the initial seat name (acceptance test passes).
- **SC-002**: A delta verdict with the pre-fix head is refused and the reason contains both
  heads.
- **SC-003**: The full suite passes, including the existing relaunch-path test
  (`test_continued_sentinel_delta_head_matches_seat_head`, message updated).

## Assumptions

- The orchestrator notes file named for this issue (`669-full.md`) does not exist and no
  dry-run workspace was named; the failure was reproduced with an in-process scratch
  workspace outside the repository, built the way `tests/test_dispatch.py` builds one.
- "The delta brief names it" means the delta `continue` action's feedback, which is
  appended to the seat's prompt (`prompt = launch prompt + feedback`). The gate brief file
  itself is not rewritten: it is hash-bound to its `brief written` event and the launch
  guard refuses a modified brief.
- The live worktree check stays in the delta round. "Against that delta head only" is read
  as: the delta round no longer compares against the stale brief head. The live check
  still guards against a worktree that moved after the delta dispatch, and it never
  conflicts with the delta head because the delta head is the live head when recorded.
- `delta_head` is a field in `state.json`, which seats cannot write directly (the state
  guard). A forged value could only make `receive` accept a head that still has to match
  the live worktree, so no new reservation is needed beyond the event producer entry.
- `dispatch next` emitting the `receive` command for a seat continued in-session (today it
  appears only when the seat's `head` moved, `cli/wuwei/dispatch.py:551`) is not part of
  this issue: the delta `continue` action already carries its `receive` call.
