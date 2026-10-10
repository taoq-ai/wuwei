# Feature Specification: setup creates the tracker labels the lifecycle uses, and pr raise says which label is missing instead of failing the move

**Feature Branch**: `670-tracker-labels`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #670: fix(tracker): setup creates the tracker labels the lifecycle
uses, and pr raise says which label is missing instead of failing the move.

Owner, 2026-10-10 (item 34): `pr raise` could not move an issue to In Review because the
label does not exist on the tracker. Deliver: `setup` and `init --upgrade` create the
lifecycle labels the configured tracker port needs (idempotent, through the port); `pr raise`
and `tracker move` create a missing label on the owner's own tracker under observe and
guarded, and otherwise print the label and the command; `doctor` lists missing labels.

## Root cause

Reproduced in a scratch workspace (`adapters.tracker = "github"`, `tracker.project =
"acme/app"`, no `tracker.board`) with the adapter of this worktree and a recorded GraphQL
reply whose `repository.label` is `null`:
`github.transition('acme/app#1', 'In Review')` returns
`Result(exit=2, reason='github.transition: could not run: GitHub label for that state not found')`.

- `adapters/tracker/github.py:126-160` (`transition`): without `tracker.board`, the in-review
  move adds the label named `tracker.states.in_review` (default `In Review`) and raises
  `Failure('GitHub label for that state not found')` at line 156 when the repository has no
  such label. Nothing anywhere creates that label: the port has no operation for it, and
  neither `setup` nor `init --upgrade` nor `doctor` looks at labels.
- `cli/wuwei/dispatch.py:235-262` (`tracker_call`): the shared transition path (pr raise,
  `tracker done`, the merge path) records the failed result as a `tracker.call` event and
  returns it; it does not know which label is missing.
- `cli/wuwei/shepherd.py:363` (`raise_pr`): `dispatch.tracker_call(item, 'in_review', root)`
  ignores the result, so `pr raise` exits 0 with only the adapter's stderr line, which names
  neither the label nor a fix.
- There is no `tracker move` command (`cli/wuwei/commands/tracker.py` has `create`, `log` and
  `done`), so after a failed in-review move nothing re-runs it.

Linear and Jira move workflow states, not labels; with `tracker.board` set, GitHub moves the
Projects v2 Status field; `done` on GitHub closes the issue. The only lifecycle label any
configured port needs today is the GitHub `in_review` label without a board.

## User Scenarios and Testing

### User Story 1: setup and init --upgrade create the lifecycle labels (Priority: P1)

**Independent Test**: `init --upgrade` on a workspace whose GitHub tracker has no labels, then
`doctor`.

**Acceptance Scenarios**:

1. **Given** `adapters.tracker = "github"`, no `tracker.board`, and a repository without the
   `In Review` label, **When** the owner runs `bin/wuwei init --upgrade`, **Then** the label is
   created through the tracker port, the output has the line
   `Upgraded tracker label "In Review"`, and `doctor`'s `tracker labels` row is `ok`
   (issue acceptance 1).
2. **Given** the label already exists, **When** `init --upgrade` runs again, **Then** nothing
   is created, no label line is printed, and the rest of the upgrade output is unchanged
   (idempotent).
3. **Given** the same tracker, **When** the owner runs `bin/wuwei setup` and its doctor ending
   runs, **Then** the label exists before the doctor rows are computed.
4. **Given** `init --upgrade --dry-run`, **Then** the tracker is not contacted and nothing is
   created (doctor runs this dry run for its template row).
5. **Given** `adapters.tracker` is `none`, `linear` or `jira`, or `tracker.board` is set,
   **Then** no label is needed, nothing is created and no line is printed.

### User Story 2: pr raise creates a missing label on the owner's tracker, or names it (Priority: P1)

**Independent Test**: `pr raise` with a tracker whose in-review move fails for a missing
label.

**Acceptance Scenarios**:

1. **Given** the posture is `observe` or `guarded`, the tracker is the owner's own (its
   `tracker.project` and `tracker.board` owners are in `outbound.code_host_orgs`), and the
   `In Review` label is missing, **When** `pr raise` moves the ticket, **Then** the label is
   created through the port, the move runs again and succeeds, and the `tracker.call` event
   records exit 0 (issue acceptance 2).
2. **Given** the posture is `strict`, or the tracker is external, and the label is missing,
   **When** `pr raise` runs, **Then** nothing is created, the pull request is still raised
   (exit 0), and stderr has one line naming the label and the commands:
   `tracker: ITEM-1 not moved to In Review: the tracker label "In Review" is missing; the owner
   runs bin/wuwei init --upgrade in a host terminal, which creates it, then bin/wuwei tracker
   move ITEM-1 in_review`. The `tracker.call` event records exit 1 with that reason.
3. **Given** the move fails for any other reason (the label exists, or the label read itself
   fails), **Then** the result is the original failure, unchanged, and `pr raise` prints it
   on stderr.
4. **Given** `adapters.tracker = "none"`, **Then** `pr raise` prints no tracker line.

### User Story 3: tracker move re-runs a lifecycle move (Priority: P2)

**Acceptance Scenarios**:

1. **Given** an item whose in-review move failed, **When** `bin/wuwei tracker move ITEM-1
   in_review` runs, **Then** it runs the same shared transition (`dispatch.tracker_call`), with
   the same label rule as User Story 2, and prints `ITEM-1: ticket in_review` on success
   (as `tracker done` prints `ITEM-1: ticket done`) or the reason on stderr, with the
   result's exit.
2. **Given** `bin/wuwei tracker move ITEM-1 done`, **Then** it behaves as `tracker done
   ITEM-1` (which stays).

### User Story 4: doctor lists missing labels (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a GitHub tracker without `tracker.board` and no `In Review` label, **When**
   `doctor` runs, **Then** a `tracker labels` row in the `day` section is `warn` with value
   `missing: "In Review"` and fix `wuwei init --upgrade`, and doctor creates nothing.
2. **Given** the label exists, or the adapter needs no label (Linear, Jira, a GitHub board),
   **Then** the row is `ok` with value `none missing`.
3. **Given** the label read fails, **Then** the row is `unmeasured` with the port's reason.
4. **Given** `adapters.tracker = "none"`, **Then** there is no `tracker labels` row (the day
   rows of a default workspace are unchanged).

### Edge Cases

- `tracker.states.in_review` renamed by the owner (for example `Review`): the needed label is
  the configured name, everywhere (create, check, message).
- A ticket in another repository than `tracker.project`: the label is created in
  `tracker.project` (the port's configured repository); if the retried move still fails, its
  failure is returned unchanged.
- Creating the label fails (no permission on the token): the port returns exit 2 naming the
  label; the move keeps its original failure; `setup` and `init --upgrade` print a warning
  and keep their exit.
- `tracker done` and the merge path never need a label (GitHub closes the issue), so the label
  rule runs only for the `in_review` action.

## Requirements

### Functional Requirements

- **FR-001**: The tracker port gains one operation, `labels(create)`, implemented by every
  tracker adapter. It returns `{'created': [names], 'missing': [names]}`: the lifecycle labels
  the configured port needs and the tracker lacks, after creating them when `create` is true.
  GitHub without `tracker.board` needs `[tracker.states.in_review]` in `tracker.project` (or
  the first configured repository); GitHub with a board, Linear and Jira need none and make no
  request; `none` records an unavailable call like its other operations.
- **FR-002**: `init --upgrade` (not `--dry-run`) and `setup` call `labels(create)` through
  one shared CLI function and print `<prefix> tracker label "<name>"` per created label, or a
  warning with the port's reason; neither changes its exit for a label failure. `setup` passes
  True; `init --upgrade` passes `creates_labels(config) or stdin is a tty`, because a seat may
  run `init` (it is not owner-held) and must not reach past the FR-004 rule.
- **FR-003**: The shared transition path, `dispatch.tracker_call`, on a failed `in_review`
  move, asks the port which labels are missing, creating them only when WUWEI may (FR-004);
  when it created one it runs the move once more and returns that result; when a label is
  still missing it returns exit 1 with the reason of User Story 2 scenario 2; otherwise it
  returns the original failure.
- **FR-004**: WUWEI creates a lifecycle label on its own only when the posture is not
  `strict` and the tracker is not external (`outward._external_tracker`, the rule the outward
  policy already uses for tracker writes). One function decides this.
- **FR-005**: `pr raise` prints `tracker: <reason>` on stderr when the in-review move did not
  succeed and `adapters.tracker` is not `none`; its exit is unchanged.
- **FR-006**: `bin/wuwei tracker move <item> in_review|done` runs `dispatch.tracker_call` for
  that action and reports like `tracker done`.
- **FR-007**: `doctor` adds a `tracker labels` row (FR-001 with `create=False`) for any
  tracker adapter other than `none`, per User Story 4.
- **FR-008**: The decision rule of FR-004 is invariant I49 in design spec 9.2 and in
  `tests/test_invariants.py` (constitution, Workflow).

## Success Criteria

- **SC-001**: The issue's acceptance passes as tests: `init --upgrade` on a tracker without
  labels creates them and the `tracker labels` doctor row is `ok`; a missing label at `pr
  raise` on the owner's tracker under `guarded` is created and the move succeeds.
- **SC-002**: Under `strict` or on an external tracker, no label is created and the printed
  line names the label, `bin/wuwei init --upgrade` and `bin/wuwei tracker move`.
- **SC-003**: The tracker port contract test passes for every adapter with `labels`, and the
  existing tracker, dispatch, shepherd, doctor and init tests pass.

## Assumptions

- No orchestrator notes file exists for #670 (`notes/670-full.md` is absent); the issue text
  is the brief. The reproduction used a scratch workspace and a recorded GraphQL reply, not a
  named dry-run workspace.
- "The lifecycle labels the configured tracker port needs" is decided by the adapter: only
  GitHub without a board uses a label (design 5.11 adapter table). Linear and Jira workflow
  states and the GitHub board's Status options are not labels and are not created; a missing
  state stays the adapter's existing failure.
- "`tracker move`" does not exist on main; it is added as the small re-run command the strict
  message needs, routed through the existing shared `dispatch.tracker_call`. `tracker done`
  stays.
- "The owner's own tracker" is the existing outward rule: a GitHub `tracker.project` or
  `tracker.board` owned outside `outbound.code_host_orgs` is external; Linear and Jira are
  internal (design 5.11, Approval).
- `setup` (owner-held) and `init --upgrade` from a host terminal create the
  label on any configured tracker, external included; `init --upgrade` without a tty follows
  FR-004; the posture and ownership rule applies
  only to the automatic path (pr raise, tracker move).
- The label is created with the GraphQL `createLabel` mutation (repository id, name, a fixed
  color), the API the adapter already uses for every other call, with the token or the gh
  login. The label name comes from config, not free text, so `labels` is not an outward
  (text-bearing) operation.
- A missing label at the move is a finding with a fix (exit 1), not a could-not-run (exit 2).
- `init --upgrade --dry-run` does not contact the tracker: doctor runs that dry run for its
  template row, and the `tracker labels` row covers the plan.

## Deferred

- Creating Linear or Jira workflow states and GitHub board Status options: not asked; a
  missing one keeps the adapter's existing failure.
