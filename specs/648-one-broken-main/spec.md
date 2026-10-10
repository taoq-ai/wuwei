# Feature Specification: one broken main is one fix item

**Feature Branch**: `648-one-broken-main`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #648 (owner, 2026-10-10): a linter break on main made every item's
fast check fail separately, and WUWEI sent each builder back to fix the same thing in three
branches. Deliver: a check failure on files the item did not change is recorded as
`main_broken` with the check and the first failing path; the planner opens one small fix item
for it (no ticket needed) and the held items depend on it; the
held builders wait instead of fixing; when the fix lands, the held items rebase and rerun
their checks. The dispatch reason names the fix item.

## Root cause

Reproduced in-process on `main` with the `seat` fixture of `tests/test_build_next.py` (no
orchestrator notes or dry-run workspace exist for #648): item `A` launched and stopped, then
`build.complete_checks('A', [Result(1, {'test_ids': [], 'error': 'cli/untouched.py:3:1: F401
...'})])` on a file `A` never touched. Result: the build action is `continue` with that lint
error as the builder's feedback, and nothing records that the failure is not `A`'s.

In the code:

- `cli/wuwei/commands/build.py:374-381` (`complete_checks`): every exit-1 check result goes
  into `failures` as `(command, data)`. Nothing compares the failing location with the item's
  diff.
- `cli/wuwei/commands/build.py:393-408`: any failure becomes a `continue` action whose
  feedback is the failure text, so the builder is resumed to fix it in its own branch.
- Each item's build record is independent (`builds.<item>`), so N items failing on the same
  broken file get N builder rounds, and N branches carry the same fix.
- No record of a broken main exists in day state, and no item can wait on another
  (`depends_on`, #637, is not on `main`). Owner directive (2026-10-10): build on `main` now,
  without waiting for #646 or #637.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: What is "a failure on files the item did not change"? A: A fast-check failure whose
  output names lint locations (`path:line`, as ruff, flake8 and mypy print them, including
  ruff's ` --> path:line` form) only on files that exist in the worktree and are in neither
  the item's diff against its merge base with the remote default branch nor its uncommitted
  changes. The first such location is "the first failing path".
- Q: Test failures? A: Never classified. A failing test in an unchanged test file usually
  fails because of the item's own change, so it keeps today's builder round. A failure that
  carries test ids, or a pytest summary line (`FAILED ` or `ERROR ` at a line start, which
  covers collection errors), is a test failure.
- Q: Some failures on unchanged files, some on the item's own files? A: Not held: the builder
  gets today's round for all of them. The hold applies only when every failing check is a
  main-broken failure.
- Q: Which checks? A: The fast checks the build loop runs (`complete_checks`, reached from
  `build check` and from the builder's SubagentStop). CI checks are out of scope (see
  Deferred): the code host port reports a check's name and conclusion, never a failing path.
- Q: How is "the same failure across items" matched? A: By repository and failing path: one
  fix item per broken file per repository, whatever check names it. The fix item id is
  derived from them (`fix-main-<repo>-<path words>`), so two items that hit the same file
  find the same record even when their checks finish at the same moment.
- Q: Who opens the fix item? A: The hold itself, through the existing `plan.add` in
  `cli/wuwei/plan.py` (the owner-item path, under the held item's goal, title
  `Fix main: <path> fails <check>`, source `main-broken`). Below strict no ticket is needed
  first: #636 drafts it and #644 sends it. When `plan.add` refuses (no goal, strict without a
  ticket, a held tracker draft), nothing is held and the builder gets today's round.
- Q: How do the held items wait? A: On their own build record: the build action becomes
  `{'action': 'wait', 'fix': <fix id>, 'reason': ...}`, and the reason names the fix item, the
  check and the path and tells the builder not to fix it. `dispatch next --all` carries that
  reason. `state.held(data, item)` reads it: the fix id while the fix item has not ended
  (merged, parked or escalated), else `None`. A held item is not a build step in
  `wuwei next`, does not count toward CAP and takes no seat, so the fix item can start even
  when CAP is full of held items. No `depends_on` field (#637 is not on `main`).
- Q: What does the fix item's builder get? A: Its brief body comes from the `main_broken`
  entry (scope and evidence), through the same proposal-row lookup dispatch already uses for
  a planned item, extended to fall back to `main_broken`. `worktree add` reads its `repo`
  the same way.
- Q: What happens when the fix lands? A: When the fix item is `merged`, the next
  `build next` (or `dispatch next --all`) turns the held item's `wait` into a `continue` for
  its builder: rebase onto the base branch, change nothing else, hand back. The fast checks
  then rerun through the existing loop. This is a build iteration, not a fix round
  (`fix_rounds` is unchanged).
- Q: A second break on the same file after its fix merged? A: A new id with a numeric suffix
  (`-2`, `-3`), so a merged fix never releases a new hold.
- Q: The planner parks (or escalates) the fix item, for example because its builder finds main
  green? A: The held items are released the same way as on a merge: a parked or escalated
  dependency no longer holds anyone, so the day can still close. Their next check result is
  classified afresh, and a failure whose derived fix id names a parked or escalated item is
  never held again: the builder gets today's round, because the planner judged that failure
  not main's.
- Q: Can a fix item hold itself? A: No: when the derived id is the item's own name, the item
  gets today's builder round.
- Q: The diff cannot be read (no remote ref, a damaged reply)? A: No hold; the builder gets
  today's round. The classification never blocks on a read it could not make.

## User Scenarios and Testing

### User Story 1 - One broken main holds the items on one fix item (Priority: P1)

**Acceptance Scenarios**:

1. **Given** items `A` and `B`, each with a change to its own file, whose fast check fails
   with the same lint error on `cli/untouched.py` (a file neither changed), **When** both
   check results are recorded, **Then** `main_broken` has exactly one entry naming the check,
   `cli/untouched.py` and items `A` and `B`; exactly one fix item is admitted (one
   `plan.added` event); both build actions are `wait` with a reason naming the fix item;
   neither build action is `continue` and neither item's `fix_rounds` changes.
2. **Given** the fix item is planned, **Then** `wuwei next` offers it (the dispatch row) even
   when the held items fill CAP, while neither held item has a build row.
3. **Given** `dispatch next --all` while `A` and `B` are held, **Then** their entries are
   `wait` with a reason that names the fix item, and they take no seat.

### User Story 2 - The fix lands and the held items rerun (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the fix item is merged, **When** `build next A` and `build next B` run (or
   `dispatch next --all`), **Then** each returns `continue` with feedback naming the fix item
   and telling the builder to rebase and change nothing else, and the next check result is
   classified afresh.
2. **Given** the fix item is still open, **Then** `build next A` keeps returning the same
   `wait` and writes no event.
3. **Given** the fix item is parked instead of merged, **Then** `build next A` returns the same
   rebase-and-rerun `continue`, and when the same failure on the same path comes back, `A`
   gets today's builder round instead of a new hold.

### User Story 3 - An item's own failure is never held (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a lint failure on a file the item changed (committed or not), **Then** today's
   `continue` round, no `main_broken` record.
2. **Given** a test failure (test ids or a pytest `FAILED`/`ERROR` line), even in an
   unchanged test file, **Then** today's round.
3. **Given** two failing checks, one on an unchanged file and one on the item's own file,
   **Then** today's round with both failures.
4. **Given** a failure with no lint location, a location on a path that is not a file in the
   worktree, or an unreadable diff, **Then** today's round.

### Edge Cases

- The fix item's own check failing on the file it fixes: the file is in its diff, so a normal
  round; the self-hold guard covers a fix item that hands back without changing it.
- The same file broken in two repositories: two fix items (the repository is in the id).
- A held item's builder cannot be relaunched while held: the agent launch guard already
  accepts only `launch` or `continue` build actions.
- A Codex builder loop (`build <item> <brief> <worktree>`) reaching a held item exits 1 with
  the wait reason instead of failing on a missing feedback.
- The fix item cannot be admitted (`plan.add` refuses): no hold, today's round. When nothing
  else is due while items are held, `wuwei next` shows a wait row naming the fix item. To
  drop the fix item, the planner parks it, which releases the held items.
- The fix item parked or escalated: the held items are released (US2.3); the day close is
  never held by a dependency that ended.

## Requirements

- **FR-001**: One pure rule, `fast_checks.unchanged(failures, changed, tree)`, returns
  `[(check, first failing path)]` when every failure names only lint locations on existing
  worktree files outside `changed`, and `[]` otherwise (test failures, no location, any
  location in `changed`, `..` paths).
- **FR-002**: `build.complete_checks` computes the item's changed paths (diff against its merge
  base plus uncommitted changes) only when there are failures, applies FR-001, and on a
  non-empty result holds the item instead of opening a builder round. No hold when the diff
  is unreadable, when a derived fix id is the item itself, or when it names a parked or
  escalated item.
- **FR-003**: A hold first admits the fix item through `plan.add` (unless it is already an
  item), then, in one state write (kind `build.held`), records
  `main_broken.<fix id> = {repo, check, path, items, scope, evidence, at}` (adding the item to
  `items` when the entry exists) and sets the build to status `ready` with action
  `{'action': 'wait', 'fix': <fix id>, 'reason': ...}`.
- **FR-004**: `state.held(data, item)` returns the fix id of a `wait` build action while that
  item is not in an ended phase (`merged`, `parked`, `escalated`), else `None`.
- **FR-005**: `wuwei next` skips build-phase items that are held (no build row, not counted
  toward CAP) and, when nothing else is due, returns a wait row naming the item and its fix.
- **FR-006**: `dispatch.launch_set` does not count held items toward CAP or goal seats; their
  entries carry the build `wait` action and its reason.
- **FR-007**: `build.next_action` releases a held build once `held` is `None`: a `continue`
  action (event `build.released`) with feedback naming the fix item and its phase and the
  rebase-and-rerun instruction. One `continue` construction serves both this release and
  today's failure round. A failure whose derived fix id is a parked or escalated item is not
  held (FR-002).
- **FR-008**: `dispatch.candidate` falls back to today's `main_broken` row, so the fix item's
  builder brief and `worktree add --repo` read its scope, evidence and repository.
- **FR-009**: The Codex build loop exits 1 with the reason on a `wait` action.
- **FR-010**: Producers: state key `main_broken` and events `build.held`, `build.released`
  are named for `wuwei build`; both events are silent signals.
- **FR-011**: The builder charter (step 9) tells the builder not to fix a repository check that
  fails only on files its item does not change; `bin/wuwei agents build` regenerates
  `agents/builder.md`.
- **FR-012**: Invariant I57 in design 9.2 and `tests/test_invariants.py`:
  a check failure holds an item only when every failure names lint locations only on files
  the item did not change; a test failure, a failure on a changed file or one with no
  location goes back to the builder. A dated #648 line amends the build loop rule in design
  5.3.

## Success Criteria

- **SC-001**: In the two-item scenario, zero builder rounds are opened for the shared failure
  and exactly one fix item is proposed.
- **SC-002**: After the fix item merges, both held items are offered again with a rebase
  `continue` and no owner step.
- **SC-003**: Every existing build-loop test passes unchanged (a failure with no location keeps
  today's behaviour), and the full suite passes.

## Assumptions

- No orchestrator notes file (`notes/648-full.md`) exists, so no dry-run workspace was named;
  the reproduction used the `tests/test_build_next.py` fixture in a temporary workspace.
- Owner directive (2026-10-10): build on `main` without #646 or #637. The fix item opens
  through the existing `plan.add`; the hold lives on the held item's build record and in the
  dispatch reason, not in a `depends_on` field.
- #637 will later carry the hold as a field (`depends_on`) on the held item; `state.held` is
  the one reader to switch.
- The classification is a path heuristic for file-local linters, the owner's case. A
  cross-file checker (a type checker) that fails in an unchanged file because of the item's
  own change, or an item that changes the linter's configuration, reads as main broken. The
  fix item's builder then finds main green and reports it; the planner parks the fix item,
  which releases the held items, and the same failure then goes back to their builders. Marked with a `ponytail:` comment naming the ceiling and
  the upgrade (confirm across two items, or run the check at the merge base).
- Only the first lint location per failing check is recorded, as the issue asks; all
  locations are compared with the diff.
- The fix item is a light owner item admitted by `plan.add`; below strict its ticket is
  drafted (#636) and sent (#644) on the way in.
  Its PR turns the failing check green, so #668's base-fix rule lets it skip the soak.
- A held item's builder rebases itself on release; the CLI does not rebase a pre-PR worktree
  (no expected base SHA is known there, and a conflict needs the builder anyway).
- I57 is the next id after those taken on in-flight branches (I50, I54, I55, I56).

## Deferred

- Scope cut, stated plainly: the issue names "a fast check or CI check"; this feature covers
  the fast checks only. The owner's incident and both acceptance lines are the fast-check
  case, and a raised item's CI failure runs through a different flow (`pr_actions`,
  `open_fix`, phase `raised`).
- CI checks failing on a raised PR because main is broken: the code host port gives no failing
  path, so the path rule cannot apply. The reusable signal is the #668 one (the same check
  failing at the PR's base commit, `merge.checks_at`), and the release would need a PR
  rebase. Follow-up issue to file, linked to #648.
- #637 (`depends_on` on items and plans, `pr:<n>` references, validation, board and status
  listing of waiting items). The hold moves to that field when it lands.
