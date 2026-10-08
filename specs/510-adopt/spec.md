# Feature Specification: gradual adoption of open PRs, branches and worktrees

**Feature Branch**: `510-adopt`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #510: feat(adopt): gradual adoption: the shepherd and pr act work on a
pull request without a WUWEI worktree, wuwei worktree adopt registers an existing worktree or
branch as an item's, and a PR opened outside WUWEI can be claimed.

Owner, real day on 0.16.0: with `owner.handles` set, `pr act` stopped at "linked item has no
worktree", and the existing worktrees did not count because WUWEI only accepts worktrees it
created. WUWEI could not shepherd any open PR it did not raise, so a team cannot adopt it on
day one. Part of the autonomy push (#530: no new refusal under observe or guarded) and #551
(the CLI returns the next step as a command).

## Root cause

- `cli/wuwei/pr_actions.py:253-264` (`_item`) raises `linked item has no worktree` for any
  linked item without a recorded worktree. `act` calls it at `:492` before it branches on the
  PR state, so `changes_requested` and `threads_unanswered`, whose triage and replies
  (`_thread`, `:357-460`) read and write only through the code host, are blocked by a
  checkout they never use. `cli/wuwei/shepherd.py:441` (`headless`) calls the same helper and
  fails the same way for a headless shepherd seat.
- `cli/wuwei/commands/pr.py:24` makes `--item` required on `pr claim`, and
  `cli/wuwei/state.py:410-411` (`record_pr`) refuses an item outside the approved plan. A PR
  opened outside WUWEI has no item, and nothing creates one from the PR.
- An item's worktree is recorded only by `brief.write` (`cli/wuwei/brief.py:430-432`).
  `cli/wuwei/workspace.py:769-789` (`create_worktree`) always makes a new branch
  (`adapters/vcs/git.py:359`, `git worktree add -b`), so no command can register an existing
  worktree or check out an existing PR branch, and the hooks (#472) and the workspace anchor
  (`cli/wuwei/commands/git_hook.py:26-71`) are installed only on worktrees WUWEI created.
- A claimed item stays at `planned` (`state.py:425-426` moves only a raised item), so
  `dispatch next --all` would start a fresh build for it, and an observed merge
  (`pr_actions.py:222-224`, which moves only `raised`, `fix` or `delta`) never closes it.

## User Scenarios and Testing

### User Story 1: claim an open PR on day one and shepherd it with no checkout (Priority: P1)

The owner has an open PR in a configured repository, raised before WUWEI. One command makes
it a WUWEI item and the shepherd works it through the code host.

**Independent Test**: the shepherd fixture (`tests/test_shepherd.py`, fake code host, one
configured repository, goal `G-1`, gate approved), no worktree anywhere.

**Acceptance Scenarios**:

1. **Given** a configured repository with an open PR `acme/widget#8` by the owner and no item,
   **When** `wuwei pr claim acme/widget#8 --goal G-1` runs, **Then** it exits 0, the day has a
   new approved item `PR-8` with goal `G-1`, `source` `adopted`, phase `raised` and `pr`
   `acme/widget#8`, the PR is in `claimed_prs`, and the `plan.added` event carries
   `source: adopted`.
2. **Given** that item, **When** the PR is `review_stale` and `pr act` runs, **Then** it
   re-requests review and posts in the review channel with no worktree; **When** `pr state`
   runs, **Then** the row shows the state; **When** `pr disposition` runs with a valid owner
   decision and comment, **Then** it records it.
3. **Given** that item and an unanswered review question, **When** `pr act` runs, **Then** it
   prints the `reply` action (exit 1), and `pr act --reply "<answer>"` drafts or sends the
   reply, with no worktree.
4. **Given** exactly one configured repository, **When** `pr claim 8 --goal G-1` runs, **Then**
   it claims `acme/widget#8` as in scenario 1.
5. **Given** a day with exactly one goal, **When** `pr claim <ref>` runs without `--goal`,
   **Then** the item takes that goal; **Given** two goals and no `--goal`, **Then** it exits 1
   naming `bin/wuwei pr claim <ref> --goal <one of G-1, G-2>` and writes nothing.
6. **Given** a local worktree already checked out on the PR's branch and clean, **When** the PR
   is claimed, **Then** the claim also adopts that worktree (User Story 3) and prints its path.

### User Story 2: a fix round names the adopt step, then the builder runs in the checkout (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a claimed item with no worktree and a PR in `ci_red` (or a review fix request, or
   `conflicted`), **When** `pr act` runs, **Then** it exits 1 printing
   `{"action": "adopt", "pr", "item", "command", "why", "then"}` where `command` is
   `bin/wuwei worktree adopt <path> --item <item>` when a worktree of that repository is on
   the PR branch, else `bin/wuwei worktree add <item> --branch <pr branch> --repo <repo>`,
   and `then` is `bin/wuwei pr act <ref>`.
2. **Given** that command was run, **When** `pr act` runs again on the `ci_red` PR, **Then** it
   writes a builder brief for the item with the failed checks as feedback on the adopted
   worktree and prints the `build next` launch action whose `worktree` is the adopted path;
   the item stays `raised`.
3. **Given** the builder commits in that worktree, **Then** the chained WUWEI pre-commit hook
   runs (User Story 3).

### User Story 3: adopt an existing worktree or branch (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an existing linked worktree of a configured repository whose repository sets a
   husky-style `core.hooksPath`, **When** `wuwei worktree adopt <path> --item A` runs, **Then**
   it exits 0, a commit in the worktree runs WUWEI's pre-commit and then the repository's own
   hook (#472), the workspace anchor (`wuwei-workspace`) is written in the worktree's git
   directory, the configured identity is written, the item records the path, and a
   `worktree.adopted` event records item, path and the current HEAD.
2. **Given** an adopted worktree with modified or untracked files, **When** adopt runs, **Then**
   it exits 1 naming each file and the commit or stash command, and changes nothing.
3. **Given** a path that is not a git worktree, a worktree of an unconfigured repository, or the
   repository's main checkout, **When** adopt runs, **Then** it exits 1 with the reason and
   changes nothing.
4. **Given** an existing branch `feature-x` and item `A`, **When**
   `wuwei worktree add A --branch feature-x` runs, **Then** it creates `worktrees/A` on
   `feature-x` (no new branch), installs hooks, anchor and identity as `worktree add` does,
   and records the path on item `A`.

### User Story 4: the day shows adopted items; docs explain starting with work in progress (Priority: P2)

**Acceptance Scenarios**:

1. **Given** an adopted item, **When** the board renders, **Then** its Work row names the item
   with `(adopted)`.
2. `docs/site/daily.md` has a section "Starting with work in progress"; `docs/site/concepts.md`
   defines Adopted; `docs/site/reference.md` documents `worktree adopt`, `worktree add
   --branch` and `pr claim` without `--item`, and its phase table shows `planned` to `raised`.

### Edge Cases

- `pr claim --item A` where `A` is already in the plan keeps today's behaviour (link only, and
  refuse an unapproved item); a claim now also moves a `planned` item to `raised`.
- `pr claim` with no `--item` uses `PR-<number>`; if that id is already in the plan linked to
  another PR, the existing `record_pr` refusal names it.
- A branch worktree found by the claim is dirty: the claim still succeeds (exit 0), prints the
  adopt refusal on stderr and leaves the item without a worktree; `pr act` names the adopt
  command when a checkout is needed.
- Adopting onto an item that already records a different worktree exits 1 (records floor);
  adopting the same path again is idempotent.
- The worktree listing or any adapter read fails: exit 2 with the reason (fail closed).
- With a tracker in force, an item created by claim follows `plan add`'s existing ticket rule.

## Requirements

### Functional Requirements

- **FR-001**: `pr act` reads the linked item without requiring a worktree. Only the rebase step
  (`conflicted`) and a fix round need one; with none recorded they return the `adopt` action
  (exit 1) instead of an error.
- **FR-002**: A fix round on a linked item with no build record writes a builder brief
  (feedback from the failed checks or the review) on the recorded worktree and returns
  `build next`'s launch action. An item in `raised` stays `raised`.
- **FR-003**: The headless shepherd seat runs with the workspace as its directory when the item
  has no worktree.
- **FR-004**: `pr claim <ref|number> [--item ID] [--goal G-n]` creates the item when the id is not
  in the plan, through `plan.add` with `source='adopted'`, the PR title and the goal from
  `--goal` or the day's only goal; it then links the PR. A bare number resolves when one
  repository is configured.
- **FR-005**: `record_pr` for a claim moves a `planned` item to `raised`; `state.PHASES` allows
  `planned` to `raised`.
- **FR-006**: After linking, `pr claim` adopts the worktree already on the PR branch, if one
  exists and is clean (FR-007), and prints it.
- **FR-007**: `worktree adopt <path> --item ID` validates (configured repository, linked
  worktree, clean), claims the item for the session, installs hooks, anchor and identity
  through the same helper `worktree add` uses, and records the path and HEAD.
- **FR-008**: `worktree add ID --branch NAME` checks out an existing branch through the normal
  create path and records the path like adopt.
- **FR-009**: The vcs port gains `worktrees(repo)` (read) and `worktree_checkout(repo, branch,
  path)` (write) with fixed git argument lists.
- **FR-010**: `worktree.adopted` is a reserved event kind; `items.<id>.source` and the item
  worktree name their producers.
- **FR-011**: The board's Work table marks adopted items.
- **FR-012**: Docs as in User Story 4.

### Key Entities

- **Adopted item**: an item whose `source` is `adopted`, created by `pr claim` from a PR opened
  outside WUWEI; it starts at `raised` with its PR linked.
- **Adopted worktree**: an existing worktree registered by `worktree adopt` (or checked out by
  `worktree add --branch`), recorded on the item with the HEAD it was adopted at.

## Success Criteria

- **SC-001**: On a day with open PRs raised before WUWEI, approving the morning gate claims the owner's
  open PRs (or one `pr claim` per PR after the gate) before `pr act` shepherds them; no worktree is needed for ping, state, replies, disposition
  or the merge decision.
- **SC-002**: A fix round on an adopted PR reaches a builder launch in two commands: the
  returned adopt command, then `pr act` again.
- **SC-003**: No new refusal under observe or guarded beyond adopt's own preconditions.
- **SC-004**: The full suite passes.

## Assumptions

- "Goal from the gate card" is read as the day's approved goals: `--goal` names one, and a day
  with exactly one goal needs none. The morning sweep lists the configured repositories' open
  PRs authored by an `owner.handles` login (code host `open_prs`) as `PR-<n>` rows; the gate
  card names them and approving claims each under the first goal (review finding F1).
- `pr claim <n>` keeps the `owner/repo#n` reference every `pr` subcommand takes; a bare number
  is accepted when exactly one repository is configured (reusing `merge.reference`).
- The default item id for a claim without `--item` is `PR-<number>`.
- No author check is added to `pr claim`: it already claims any open PR of a configured
  repository, and an author check would be a new refusal (#530). The issue's "author is the
  owner or a configured handle" describes the intended use.
- Adopt's refusals (not a linked worktree of a configured repository, dirty tree, a different
  worktree already recorded) are preconditions of the item's record that the issue asks for,
  not guards on the owner's tools; they apply under every posture. A dirty tree is refused so
  hooks and the anchor never attach to work nobody has recorded.
- The pre-push anchor is the existing `wuwei-workspace` file plus the HEAD recorded in the
  `worktree.adopted` event. The push guard already checks only the commits a push adds to an
  existing remote branch, so an adopted branch's earlier commits are not re-checked.
- An item created or linked by claim moves to `raised` (one new phase edge, `planned` to
  `raised`): its PR exists, so `dispatch next --all` must not start a fresh build and an
  observed merge must close it. Phase is not gate evidence; merge still requires verdicts or
  the owner's merge decision.
- Plain `worktree add <item>` is unchanged: it still records nothing on the item (the brief does).
- With a tracker in force, a claim with no ticket follows `plan add`'s rule; `pr claim` gains no
  `--ticket` option.

## Deferred

- A second fix round on an adopted item (`open_fix` then leads to a delta that needs initial
  gate verdicts) and taking an adopted item through pre-PR gates are not designed here; the
  first fix round runs the builder in `raised` and the PR's own review takes over.
