# Feature Specification: a red check that is also red on the base is base_red, not ci_red

**Feature Branch**: `728-base-red`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #728 (owner, 2026-10-10, item 54): `pr state` marked a PR `ci_red` and
asked for a fix round when the failure was a new CVE in the base branch's lockfile, which the
PR did not touch. Deliver: `pr state` compares the PR's failing checks with the same checks on
the base commit (code host port, `checks_at`); a check failing on both is `base_red` with the
base commit named, the item waits, and no fix round is asked for the PR; a check failing only
on the PR stays `ci_red`.

## Root cause (read on main at 871f5a1, reproduced read-only)

Reproduction: an in-process run from this worktree with the test fakes (`tests/test_stop.py`
`case`, `tests/test_pr_actions.py` `linked`), nothing written outside `tmp_path`. The code host
fake answers check `audit` with conclusion `failure` both at the PR head (`a...a`) and at the
PR's base commit (`b...b`). `bin/wuwei pr state acme/widget#7` prints the row with state
`ci_red` and action `start a fix round`; `bin/wuwei pr act acme/widget#7` exits 1 and opens
the fix round (`build.open_fix`). The base commit is never read.

Two facts on main make this happen:

1. `pr_actions.classify` (`cli/wuwei/pr_actions.py:113`) sees only the head's checks
   (`measured['checks']`, read by `watch.evidence`, `cli/wuwei/watch.py:361`) and returns
   `ci_red` for any completed check whose conclusion is not success, neutral or skipped
   (`cli/wuwei/pr_actions.py:126-136`). It has no host and no base evidence.
2. `pr_actions.observe` (`cli/wuwei/pr_actions.py:151`) maps the state through `ACTIONS`
   (`cli/wuwei/pr_actions.py:195`), where `ci_red` is `start a fix round`; `act`
   (`cli/wuwei/pr_actions.py:558`) then calls `_fix`, and the headless shepherd picks the
   episode up (`shepherd.HEADLESS['ci_red']`, `cli/wuwei/shepherd.py:432`).

The comparison #728 needs already exists for the merge soak (#668): `merge.checks_at`
(`cli/wuwei/merge.py:106`) reads and validates the checks at any commit, and `merge.execute`
reads them at `pr['base_sha']` (`cli/wuwei/merge.py:395`). The fix reuses that read in
`observe`, the one place every caller (`pr state`, `pr act`, `next`, the watch poll, the
overnight sweep, the stop check, day close) gets its PR state from.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which base commit? A: The PR's `base_sha` as the code host reports it (GitHub `base.sha`),
  the commit #668 already reads for "fails at the base". No new port operation.
- Q: When is a PR `base_red` rather than `ci_red`? A: When every red check at the head is also
  red, by name, at the base commit. Red means what `classify` means today: completed with a
  conclusion other than success, neutral or skipped. One red check that is not red at the base
  keeps the PR `ci_red` (the PR has something of its own to fix).
- Q: When is the base read? A: Only when `classify` returns `ci_red`. Every other state reads
  nothing new.
- Q: What if the base read fails or returns damaged evidence? A: The PR state is unmeasured
  (exit 2 with the reason), as for any other failed read in `evaluate`. A PR is never blamed
  without evidence and never cleared without it.
- Q: What does `pr state` print? A: The row's `state` is `base_red` and its `reason` is
  `base_red: <check> fails at <base sha> too`; several checks are joined with `, ` in name
  order. The full base SHA is printed, as #668's soak line does.
- Q: What is the action? A: None. `base_red` has no `ACTIONS` entry: no action episode, no
  deadline, no nudge or page, row exit 0, and an earlier `ci_red` episode for the PR is
  dropped. `pr act` returns 0 without a fix round, the headless shepherd has nothing to run and
  the stop check finds nothing overdue. Day close still requires the PR merged, parked or
  carried, as for `waiting`.
- Q: Does #648's `main_broken` fix item open? A: Not here. #648 is not on main; the item waits.
  When #648 lands it can key off `base_red`.
- Q: The overnight sweep? A: It skips `base_red` like `waiting`; there is nothing to queue for
  the morning on the PR's behalf.

## User Scenarios and Testing

### User Story 1 - A base failure is not blamed on the PR (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an owned PR whose check `audit` failed at its head and failed at its base commit,
   **When** `bin/wuwei pr state <ref>` runs, **Then** the row's state is `base_red`, the output
   contains `base_red: audit fails at <base sha> too`, the row has no action and no deadline,
   and the exit is 0.
2. **Given** the same PR, **When** `bin/wuwei pr act <ref>` runs, **Then** it exits 0, prints
   no fix action, the item stays in phase `raised` and no build fix round is opened; the watch
   ledger has no action episode for the PR and `shepherd.pending` returns nothing for it.
3. **Given** the same PR with an earlier `ci_red` action episode recorded, **When** `pr state`
   runs, **Then** the episode is gone.

### User Story 2 - A failure of the PR's own stays ci_red (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a check red at the head and green (or absent, or still running) at the base,
   **When** `pr state` runs, **Then** the state is `ci_red` with action `start a fix round`,
   as today.
2. **Given** two red checks at the head, one also red at the base and one green at the base,
   **Then** the state is `ci_red`.
3. **Given** a PR in any state other than `ci_red`, **Then** the base commit is not read.

### User Story 3 - An unreadable base fails closed (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a red check at the head and a base read that fails (port exit 2) or returns
   checks for another commit, **When** `pr state` runs, **Then** the PR's row has exit 2 and
   a `PR state unmeasured:` reason, and the command exits 2.

## Requirements

- **FR-001**: When the head state is `ci_red`, `pr_actions.observe` reads the checks at the
  PR's `base_sha` through `merge.checks_at` and sets the state `base_red` when every red head
  check name is red at the base.
- **FR-002**: A `base_red` row carries `reason` `base_red: <names> fails at <base sha> too`.
- **FR-003**: `base_red` has no action: no episode, no deadline, exit 0, no fix round from
  `pr act`, nothing for the headless shepherd.
- **FR-004**: Any other outcome of the comparison leaves `ci_red` and its fix round unchanged.
- **FR-005**: A failed or damaged base read makes the PR state unmeasured (exit 2).
- **FR-006**: The overnight sweep skips a `base_red` PR as it skips a `waiting` one.
- **FR-007**: The design spec's PR state list (4.2.1) names `base_red`.

## Success Criteria

- **SC-001**: The owner's item 54 case (a check red on the PR and on the base head) produces no
  fix round and names the failing check and base commit.
- **SC-002**: Every existing `ci_red` test keeps its outcome; the full suite passes.

## Assumptions

- No orchestrator notes for this issue were available and no dry-run workspace was named; the failure was reproduced in-process with the test fakes
  instead (Root cause above).
- `base_sha` from the code host is the base head for this purpose, as #668 assumes. If the
  host reports an older base commit, the comparison is against that commit.
- Checks are matched by name only, as `merge.fixes_base` does; app id is not compared.
- A mixed PR (some red checks shared with the base, some its own) is `ci_red`, and its fix
  round feedback still lists every red check, as today. Filtering the shared ones out of the
  feedback is not asked for.
- Recovery needs nothing new: once the base turns green, the PR's checks rerun on its next push
  or rebase, and `pr state` reclassifies from fresh evidence.
- `base_red` is a row state only; it is never written to the action ledger, so no `ACTIONS`,
  `HEADLESS` or event-kind table changes.

## Deferred

- #648: one `main_broken` fix item for a broken base, with the waiting items depending on it.
