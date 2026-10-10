# Feature Specification: a PR waiting on people never hides work that can run now, and build next and dispatch next give one answer

**Feature Branch**: `666-next-runnable-first`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #666 (owner, 2026-10-10, items 23 and 24): every `wuwei next`
returned "act on PR" for one waiting PR while two other items had rounds ready; the owner
found them through `dispatch next --all`. `build next` first returned done, `dispatch next`
said fix, and a second `build next` returned the right step. Deliver: `next` ranks runnable
work first and lists a PR that waits on people as one informational row at the end;
`next --json` lists every runnable row; `build next` and `dispatch next` read the same
function so their answers agree, and a stale cached answer is never returned.

## Root cause

### Defect 1: the first raised item in queue order wins every `next`

Reproduced in-process on `main` (`next_command.step` on a day with `approved_items`
`['P', 'A', 'B']`, P `raised` with PR `example/project#7`, A in `fix`, B in `delta`,
cap 2, the once rows done). Three calls in a row print:

```text
pr wuwei pr act example/project#7
pr wuwei pr act example/project#7
pr wuwei pr act example/project#7
```

`cli/wuwei/commands/next.py:244` walks the approved items in queue order and returns the
first item row it builds. A `raised` item returns its `pr` row at once
(`next.py:263-266`), so no item after it in the queue is looked at, whatever it could run.
The `pr` row has no done state (it must come back when the PR changes), so it is returned
on every call: A's fix round (`build next A`) and B's delta gates (`dispatch next B`) stay
hidden until the PR merges. The same early return also hides a due steward review and the
wait rows behind the PR.

### Defect 2: `build next` returns the cached `done` of an item that moved to its gates

`cli/wuwei/commands/build.py:141` (`next_action`) returns `record['action']`, the action
stored on the build record, whenever the brief and worktree match. When fast checks pass,
`complete_checks` stores `{'action': 'done'}` and moves `implement` to `gate` (or `fix` to
`delta`). From then on `build next <item>` answers `done` although the gates may already
have asked for a fix round. `dispatch next <item>` (`cli/wuwei/dispatch.py:280`,
`next_step`; the issue calls it `dispatch.decide`) reads the verdicts live, opens the
builder's fix round through `build.open_fix` (`dispatch.py:365` from the initial gates,
`dispatch.py:378` from a blocking delta) and answers `fix`. Only then does `build next`
return the round's `continue` or `launch`: the sequence the owner saw (done, fix, then the
right step).

`next` itself already avoids this: its `build` row maps `done` to "ask the day again"
(`next.py:368`), and the item then reaches `dispatch.next_step` through its `verdicts` row.
The disagreement is only in the `build next` command (`build.py:40`).

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: What is runnable work? A: The item rows that ask the planner to do something now:
  `build`, `docs`, `verdicts` and the one `dispatch` launch-set row. A `pr` row is
  informational: it runs `pr act`, which prints nothing while the PR waits on people.
- Q: Rank order? A: Runnable rows in queue order (as today), then the `pr` rows in queue
  order. No other reordering.
- Q: Where does the `pr` row go when nothing is runnable? A: After the steward rows and
  before the wait rows: a due steward review is runnable work too, and a PR that may need a
  rebase or a merge still comes before "end the turn". Close, retro and report stay
  unreachable while an item is raised, as today.
- Q: Shape of "lists every runnable row"? A: The returned row keeps its shape and gains
  `rows`, a list of `{state, item, command}` for every item row in rank order (runnable
  first, `pr` rows last), present only when there is more than one item row. Text mode adds
  one `Queue:` line naming them. One-row output is unchanged.
- Q: Does `next` return more than one action? A: No. It still returns one action; `rows`
  only names the others. The loop (do the one action, run `next` again) is unchanged.
- Q: How do `build next` and `dispatch next` agree? A: When `build next <item>` would answer
  `done` and the item is at `gate` or `delta`, it asks `dispatch.next_step` (the one
  decision function) and answers from it. A `fix` answer means the fix round was just
  opened; `build next` then prints that round's builder action read live from the build
  record (`continue` or `launch`), which is the step `dispatch next`'s `fix` names
  (`wuwei build next <item>`). Any other answer (`gates`, `raise`, `escalate`) is printed
  as `dispatch next` prints it, with the same exit code; a refusal exits 1 with its reason.
- Q: Does the Codex polling loop (`build.run_loop`) change? A: No. It relies on
  `next_action` answering `done` to end its loop, so the delegation lives in the
  `build next` command only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Runnable rounds come before a PR that waits on people (Priority: P1)

The planner runs `wuwei next --json` on a day where one item has a PR waiting on review and
two items have rounds ready. It gets a round first and sees every row, the PR last.

**Why this priority**: the reported defect; the planner loop stalls on the PR while seats
could work.

**Independent Test**: build the day state in a temporary workspace and call
`next_command.step` and `wuwei next`.

**Acceptance Scenarios**:

1. **Given** one PR waiting on review (item P, `raised`, first in queue order) and two
   items with rounds ready (A in `fix`, B in `delta`), **When** `next` runs, **Then** it
   returns A's `build` row and its `rows` list the two rounds first and the PR last:
   `build A`, `verdicts B`, `pr P`.
2. **Given** the same day, **When** `wuwei next` runs in text mode, **Then** the output
   carries a `Queue:` line naming `build A`, `verdicts B`, `pr P` in that order.
3. **Given** a day with only the raised item P, **When** `next` runs, **Then** it returns
   P's `pr` row with no `rows` key (unchanged output).
4. **Given** P raised and a steward review due, nothing runnable, **When** `next` runs,
   **Then** it returns the steward row before the `pr` row.

### User Story 2 - `build next` and `dispatch next` name the same step (Priority: P1)

The planner asks `build next <item>` for an item whose gates asked for a fix and gets the
fix round's builder action, the step `dispatch next` names, never a stale `done`.

**Why this priority**: the reported defect; a stale `done` sends the planner to the wrong
command.

**Independent Test**: a completed build at `gate` with a FIX verdict (the existing
`built`, `gate_fix` and `record` helpers in `tests/test_dispatch.py`), then
`main(['build', 'next', ...])` and `main(['dispatch', 'next', 'A'])` in each order.

**Acceptance Scenarios**:

1. **Given** item A at `gate` with a completed build (`done`) and an initial FIX verdict,
   **When** `build next A` runs, **Then** it prints the fix round's builder action
   (`continue` with the gate feedback), the item is in `fix`, and a following
   `dispatch next A` answers `fix` with command `wuwei build next A`.
2. **Given** the same state, **When** `dispatch next A` runs first, **Then** it answers
   `fix`, and a following `build next A` prints the same builder action as in scenario 1.
3. **Given** item A at `delta` after one fix round, build `done`, and a blocking delta
   verdict below the round cap, **When** `build next A` runs, **Then** it prints the next
   round's builder action and the item is in `fix` at round 2, the step `dispatch next A`
   names.

### Edge Cases

- A build `done` on an item at `raised`, `merged` or `parked` still answers `done`: the
  build is done and no gate step applies.
- `dispatch.next_step` answers `gates`, `raise` or `escalate`: `build next` prints that
  answer; `escalate` exits 1.
- `dispatch.next_step` refuses (builder still running, steward note): `build next` exits 1
  with the refusal on stderr, as `dispatch next` does.
- Two raised items: both `pr` rows are listed last in queue order; the first one is
  returned when nothing is runnable.
- An item a running seat holds is skipped as today and is not listed.
- The Codex `build <item> <brief> <worktree>` loop still ends on `done`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `next.step` MUST collect the item rows of every non-terminal, non-running
  approved item in queue order instead of returning the first one, with `pr` rows after
  every runnable row.
- **FR-002**: `next.step` MUST return the first runnable item row when one exists. When none
  exists it MUST return the steward rows first, then the first `pr` row, then the wait
  rows.
- **FR-003**: When more than one item row exists, the returned row MUST carry `rows`, the
  list of `{state, item, command}` in rank order; `wuwei next --json` MUST print it,
  including after the row is resolved to its delegate's action, and text mode MUST print
  one `Queue:` line naming each row.
- **FR-004**: `wuwei build next <item>` MUST answer from `dispatch.next_step` when
  `next_action` returns `done` and the item is at `gate` or `delta`; a `fix` answer MUST
  print the opened round's builder action from the build record.
- **FR-005**: `build next` MUST exit as `dispatch next` does for a delegated answer: 1 on
  `escalate` or a refusal, 0 otherwise.
- **FR-006**: `build.next_action`, `build.run_loop`, `dispatch.next_step` and
  `dispatch.launch_set` MUST NOT change.
- **FR-007**: `docs/site/reference.md` (the `bin/wuwei next` row) MUST name the `rows` key,
  and the design spec step loop amendment (`docs/specs/2026-09-24-wuwei-design.md`, "Step
  loop amendment") MUST say that `build next` on an item at its gates answers what
  `dispatch next` decides.

## Success Criteria *(mandatory)*

- **SC-001**: A test pins US1.1: `step` returns `build A` and `rows` is `build A`,
  `verdicts B`, `pr P`.
- **SC-002**: A test pins US2 for a fix round from the initial gates and for a round from a
  blocking delta: `build next` and `dispatch next` name the same step in both call orders.
- **SC-003**: Existing `next`, `build` and `dispatch` tests pass unchanged; the full suite
  passes.

## Assumptions

- No orchestrator notes file exists for #666 and no dry-run workspace was named; the
  defect was reproduced in-process from a temporary workspace (Root cause).
- `dispatch.decide` in the issue is `dispatch.next_step` (the function at
  `dispatch.py:280`, the line the issue cites as 281); it is reused, not renamed.
- "A PR that waits on people" cannot be told apart from a PR with an action due without a
  network read, which `next` (hook-safe, read-only) does not do. Every `pr` row is ranked
  last and stays the command `wuwei pr act <pr>`, whose own output says whether anything is
  due.
- "Lists every runnable row" is met by a `rows` field on the one returned row, not by
  returning several actions: the planner loop and every consumer that reads one action stay
  unchanged.
- "A stale cached answer is never returned" refers to the `done` stored on the build
  record; the state read itself is already live on every call.
