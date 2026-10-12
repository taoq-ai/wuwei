# Feature Specification: repo, goal, parent item, scope and title carry through automatic admission and briefing

**Feature Branch**: `908-admit-context`

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #908 (independent review, item 8): "Carry repo, goal, parent item, scope
and evidence from the originating seat or build into the existing item record. Have _start
prefer that record's worktree and promise. Retain title regardless of admission source. Generate
adopted IDs with repository identity instead of PR number alone." Risk: "Inherit only known
provenance. Ambiguous provenance should produce one explicit selection, not silently choose the
first repository or goal."

## Claims checked against the base branch

Base: main at 0.30.0 plus #901 reconcile. `plan add --repo/--track/--governed-by` and flags
(#864, #868) were already there and are not this item.

| Claim | Holds | Where | Failing test |
|---|---|---|---|
| `seat note` records no repository or originating item | yes | `commands/seat.py` `run_fix` | `test_a_seat_finding_keeps_its_items_repository_and_goal` |
| `plan add --from-finding` takes the first goal | yes | `plan.py` `add`, `goal or day['goals'][0]` | same test (A is under G-2) |
| `build._admit` does not pass the repository it knows | yes | `commands/build.py` `_admit` | `test_one_broken_main_holds_both_items_on_one_fix_item` (repo line) |
| An owner item admitted with `--title` loses the title | yes | `plan.py` `add`, title stored only with a source | `test_an_owner_item_admitted_by_title_keeps_it` |
| `_start` ignores a recorded worktree outside `worktrees/ITEM` | yes | `dispatch.py` `_start`, `tree = f'worktrees/{name}'` | `test_start_uses_the_recorded_worktree_outside_worktrees` |
| Adopted ids are the PR number alone | yes, worse than stated | `shepherd.claim_pr` used `PR-<n>`; `plan._owner_prs` used the short repository name, so `acme/app`, `beta/app` and `gamma/app` gave one row and silently dropped the other two PRs | `test_one_pr_number_and_one_file_in_three_repositories`, `test_claim_of_one_number_in_three_repositories_gives_three_items` |
| Identical filenames in several repositories pick the first | no (already fixed by #603) | `plan.propose` derives `repo` only when the paths exist in exactly one repository | kept as a guard in `test_one_pr_number_and_one_file_in_three_repositories` |

## User Scenarios & Testing

### User Story 1 - a seat finding belongs where it was found (Priority: P1)

**Independent Test**: three repositories that share a short name and a file, two goals, item A
under G-2 in `beta/app`. A builder notes a fix with `--item A`; the planner admits it.

**Acceptance Scenarios**:

1. **Given** `wuwei seat note --fix "<title>" --item A`, **Then** the finding records `item: A`,
   A's goal and A's repository (from the item, else its proposal row), and the evidence `seat
   finding in A`.
2. **Given** `plan add <id> --from-finding`, **Then** the item takes the finding's goal and
   repository and records `parent: A`, its title and evidence.
3. **Given** a finding with no item on a day with several goals, **Then** `plan add` refuses and
   names `bin/wuwei plan add <id> --from-finding --goal <one of ...>`; with the goal but several
   repositories it names `--repo <one of ...>`. One goal or one repository is taken as it is.
4. **Given** `--item Z` that is not today's, **Then** `seat note` refuses and records nothing.

### User Story 2 - automatic admissions keep what they know (Priority: P1)

1. **Given** a broken main held by a build in repository R, **Then** the fix item records R.
2. **Given** `pr claim <owner/repo#n>` with no item, **Then** the new item records the PR's
   repository and its id names the repository when several are configured.
3. **Given** an owner item admitted with `--title`, **Then** the item keeps the title, and its
   builder brief body says `Implement <item>: <title>.`

### User Story 3 - the start uses the item's record (Priority: P1)

1. **Given** a planned item whose recorded worktree is outside `worktrees/ITEM`, **Then**
   `_start` adds no worktree and briefs the builder on the recorded one.
2. **Given** an item with a recorded title and evidence (finding, adopted, owner title), **Then**
   the brief body uses them before the proposal row's scope.

### User Story 4 - one PR number in three repositories (Priority: P1)

1. **Given** three configured repositories with PR #12 each, two of them sharing a short name,
   **Then** the gate proposes three distinct ids, `PR-<owner>_<repo>-12`, and approve claims
   each one with its own reference.

### Edge Cases

- One configured repository: ids stay `PR-<n>`; nothing to disambiguate.
- An originating item under `unplanned` or a goal not on today's list: the finding records no
  goal and the admission asks when there are several goals.
- A finding whose repository is no longer configured: the existing `--repo` refusal.

## Requirements

- **FR-001**: `seat note --fix` takes `--item ITEM`; the finding records the item, its goal when
  it is one of today's goals, and its repository when known (item record, else proposal or
  main-broken row via `dispatch.candidate`). An unknown item is refused.
- **FR-002**: `plan.add(source='finding')` takes goal and repository from the finding; with none,
  the only goal or repository; otherwise one refusal naming the exact flags. It records `parent`
  and `evidence` on the item.
- **FR-003**: `build._admit` passes the held build's repository to `plan.add`.
- **FR-004**: `plan.add` keeps `title` whenever one is given, with or without a source.
- **FR-005**: `dispatch._start` uses the item's recorded `worktree`, else `worktrees/ITEM`, and
  the item's recorded title and evidence before the proposal row's.
- **FR-006**: one helper, `plan.adopted_id`, names an adopted PR: `PR-<n>` with one repository,
  `PR-<owner>_<repo>-<n>` with several. `_owner_prs` and `claim_pr` use it; `claim_pr` passes the
  PR's repository to `plan.add`.
- **FR-007**: `plan.add` refuses a missing repository with several configured for every source,
  not only the owner's; every automatic caller now passes the one it knows.
- **FR-009** (review F1): `claim_pr` uses the item a PR already links. An explicit different
  `--item` (or a gate id such as today's `PR-acme_widget-12` for yesterday's imported
  `PR-widget-12`) is refused before anything is written, so no orphan planned item is admitted.
- **FR-010** (review F3): `wuwei next` offers a finding's `plan add` with `--goal <one of ...>`
  and `--repo <one of ...>` when the finding names none and the day has several, so the offered
  step is the one explicit selection, never a step `plan add` refuses.
- **FR-008**: the builder charter names `--item <item>`; the reference and daily docs show the
  option and the id shape.

## Success Criteria

- **SC-001**: the failing tests above pass; every test file passes under 3.12, and the changed
  areas under 3.11.

## Assumptions

- The seat names its item with `--item`: a CLI call from a seat carries no item identity
  (`WUWEI_SESSION_ID` is the planner's; the subagent transcript is visible to hooks only). The
  builder knows its item from its brief. The lead has no item and records findings without it;
  their admission asks for the goal and repository when the day has several.
- `--item` is self-declared (review F2): the CLI has no caller-seat identity, so a seat can file
  a finding under any of today's items. Its reach is today's approved goals and configured
  repositories, the planner still runs the admission, and a seat could already write any title,
  so it grants no new authority; at worst it records a misleading `parent`. Binding `--item` to
  the seat's recorded item in a PreToolUse guard is left for later.
- The id separator is `_` between owner and repository: GitHub logins hold no underscore, so
  `owner_repo` cannot be read two ways. Ids are per day, so a changed id shape breaks nothing
  recorded.
- `wuwei next` keeps proposing `plan add <id> --from-finding`; when that is ambiguous the
  refusal names the exact command, which is the one explicit selection the issue asks for.
- The gate's adopted rows still default to the first goal: the plan text shows `(claimed under
  G-1)` and the owner approves it on the gate card, so that choice is not silent.
- "Promise" is the brief body's scope line. A recorded title is the item's own promise and wins
  over the proposal row; items approved from a proposal record no title, so they keep the row's.

## Deferred

- Detecting the item from the seat's working directory instead of `--item`.
