# Feature Specification: A disposed item never blocks the close through a measurement

**Feature Branch**: `517-close-parked`
**Created**: 2026-10-05
**Status**: Draft
**Input**: GitHub issue #517: fix(close): a parked or carried item never blocks the close through a measurement (missing worktree, branch without commits), the retro launches once every item has a disposition, worktree records are repaired by doctor --fix, and close --why names what is missing per item.

## Root cause

- `cli/wuwei/closing.py:223-238` (`unresolved`): for every approved item with a recorded
  `worktree` and no owned PR, close reads `vcs.branch` and `vcs.pushed_branches` through
  `root / item['worktree']`, whatever the item's disposition. When the directory was
  removed by hand git fails (`No such file or directory`); when the branch has no commits
  the evidence check raises `invalid pushed branch evidence`. Either error reaches
  `unmeasured(f'item {name}', exc)` (`:157-160`), which sets the exit code to 2.
- `cli/wuwei/commands/close.py:50-53`: the steward retro launch (`steward.run(root,
  trigger='close')`) runs only when `unresolved` returns 0, so an exit 2 from a parked
  item's measurement also means no retro.
- `closing.check` (`closing.py:248`) calls `unresolved` again, so the same exit 2 would
  return there.
- No command updates `items[<item>].worktree` after the directory is gone, and the record is
  protected state, so nothing on the owner's side can repair it.

## User Scenarios and Testing

### User Story 1: a day of parked items closes (Priority: P1)

Every item was parked or carried with its decision recorded; some worktrees were deleted
by hand and some branches have no commits. Close finishes, lists the facts and launches the
retro.

**Independent Test**: a neutral workspace with a real git repository in `tmp_path`, three
parked items whose worktree directories were deleted, run `wuwei close`.

**Acceptance Scenarios**:

1. **Given** three parked items whose worktrees were deleted by hand and branches with no
   commits, **When** `wuwei close` runs, **Then** it exits 0, the output lists each as
   `parked` with `unmeasured: worktree missing` and the park reason recorded by
   `plan park --reason`, and the steward retro launch (`steward_launch`) is printed.
2. **Given** one open item with no decision, **When** `wuwei close` runs, **Then** it exits 1
   naming that item and both `bin/wuwei plan carry <item>` and `bin/wuwei plan park <item>`.
3. **Given** a carried item with a measurable branch pushed without a PR, **When** close
   runs, **Then** the finding `pushed branch <b> has no raised or claimed PR` is unchanged.
4. **Given** a carried item whose branch measurement fails, **When** close runs, **Then**
   the failure is printed as `<item>: carried, unmeasured: <reason>` and does not set exit 2.

### User Story 2: the retro is not gated behind measurements (Priority: P1)

**Acceptance Scenarios**:

1. **Given** every approved item merged, parked or carried and a disposed item that cannot
   be measured, **When** close runs, **Then** `steward.run(trigger='close')` is called.
2. **Given** an open item without a decision, **When** close runs, **Then** the steward is not
   launched (unchanged).

### User Story 3: `close --why` (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the open-item workspace of US1.2, **When** `wuwei close --why` runs, **Then** it
   prints one line per item: the open item with what close needs and the `plan carry` /
   `plan park` commands, each disposed item with its disposition and any `unmeasured` fact;
   it exits 1, and it writes no state and no `day.close_requested` event.
2. **Given** a day with every item disposed, **When** `close --why` runs, **Then** it exits 0.

### User Story 4: gone worktrees are repaired (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the US1.1 workspace, **When** `wuwei doctor` runs, **Then** a `day` row
   `worktrees` warns naming the three items with fix `wuwei doctor --fix` and apply id
   `worktree-gone`.
2. **Given** that workspace, **When** `wuwei doctor --fix --apply worktree-gone` is confirmed,
   **Then** each of the three items has `worktree: null` and `worktree_gone: {path, branch,
   last_commit}` (`last_commit` the branch tip SHA, or null when the branch does not
   exist), a `worktree.gone` event is written per item, `wuwei state get` shows the record,
   and `wuwei next` names none of the old paths.
3. **Given** an item with a live worktree, **When** `wuwei worktree remove <item>` runs,
   **Then** the worktree is removed with git and the item record is updated the same way.
4. **Given** the preview changed before apply, **Then** nothing is written and the fix exits 1
   (the `trace-decisions` rule).

### Edge Cases

- An item with `worktree_gone` and `worktree: null` is not measured at all; close prints
  `unmeasured: worktree gone` for it when disposed. An open item with a gone worktree still
  blocks as open (exit 1), never 2.
- A measurement failure on an open item keeps exit 2 (fail closed; unchanged).
- Failures outside the item loop (`day work`, `decisions`, a decision file) keep exit 2.

## Requirements

### Functional Requirements

- **FR-001**: `closing.unresolved` MUST treat a branch measurement failure on an item whose
  disposition is parked or carried (PR disposition or seat decision) as a fact line
  `<item>: <parked|carried>[ (<reason>)], unmeasured: <reason>`, never as exit 2.
- **FR-002**: a disposed item whose recorded worktree directory does not exist MUST yield
  `unmeasured: worktree missing` without calling the VCS adapter.
- **FR-003**: `wuwei close` MUST launch the steward retro whenever no approved item is open
  and `unresolved` returned below 2, then run `closing.check` as today.
- **FR-004**: close MUST print the fact lines whatever its exit code.
- **FR-005**: `close --why` MUST print the per-item lines and exit with `unresolved`'s code,
  writing nothing.
- **FR-006**: `doctor` MUST warn on recorded worktrees whose path is gone and `doctor --fix`
  MUST mark them `worktree: null` plus `worktree_gone` via the preview/apply pattern.
- **FR-007**: `wuwei worktree remove <item>` MUST remove the worktree and write the same
  record through the same helper.
- **FR-008**: the event kind `worktree.gone` MUST be reserved to its producers.

## Success Criteria

- **SC-001**: the four acceptance scenarios of the issue pass as tests on neutral fixtures
  with a real git repository in `tmp_path`.
- **SC-002**: the full suite passes; no existing close, doctor or worktree test changes
  expectations except where this spec changes the behaviour.

## Assumptions

- No dry-run workspace was named; the root cause is stated from the code on `main`
  (lines above) and the owner's report, and reproduced by the US1.1 test.
- "The report" in the issue is close's own output; the daily `report.md` is unchanged.
- The park reason is the `Reason:` text in the decision record's Context line written by
  `plan.dispose`; with no reason only the disposition prints.
- In the US1.1 test the other close obligations (retro file, docs, PRs) are satisfied by the
  fixture so close can exit 0; close still blocks on a missing retro, as the issue says.
- A pending owner decision is not an item disposition question; it keeps exit 1 but does
  not stop the retro launch once no item is open.
- `last_commit` is the tip of `refs/heads/<item lowercased>` in the configured repository,
  read by a new one-function VCS read; a missing branch records null.
- `worktree remove` takes the single configured repository, or `--repo`, like `worktree add`.
