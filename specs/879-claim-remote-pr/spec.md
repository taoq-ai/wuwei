# Feature Specification: pr claim on a remote-only PR creates its worktree

**Feature Branch**: `879-claim-remote-pr`

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #879: "fix(pr): pr claim on a remote-only PR creates no worktree, so a
taken-over PR cannot be worked through WUWEI"

## What happened

On 0.28.0 the owner took over three teammate PRs with `wuwei pr claim <owner/repo#n> --item X
--goal G`. Each item was recorded as `phase: raised, worktree: None`. The PR branches existed
only on the remote, so nothing was fetched and no worktree was made. The planner fetched and
added the worktrees by hand, outside the record, and launched builders without a WUWEI brief.
A claim earlier that day worked only because a local worktree on the branch already existed.

## Root cause

`claim_pr` (`cli/wuwei/shepherd.py:409-417`) looks for a local worktree on the PR branch
(`workspace.branch_worktree`) and adopts it; when there is none it does nothing. The only other
way to a checkout, the `bin/wuwei worktree add <item> --branch <branch>` command that `pr act`
prints (`pr_actions._adopt`), ends in `worktree_checkout` (`adapters/vcs/git.py:380-387`), which
runs `git worktree add -- <path> <branch>` without fetching, so a branch that exists only on
the remote is an invalid reference there too.

Second part: the derived next (`cli/wuwei/derive.py:328-330`) offers a claimed PR with red
checks or a conflict only as a `wuwei pr act` run, and threads only as the shepherd duty. The
launch set (`cli/wuwei/dispatch.py` `launch_set`) resolves only `build next` and `dispatch
next` steps into seats, so `next` never returns the builder launch `pr act` would print.

## User Scenarios & Testing

### User Story 1 - claim a teammate's PR whose branch is only on the remote (Priority: P1)

**Independent Test**: a bare repository as the remote holds a branch the local clone has never
fetched; `pr claim` on a PR with that head records `worktrees/<item>` on the branch at the PR
head.

**Acceptance Scenarios**:

1. **Given** a PR whose head branch exists only on the remote, **When** the owner claims it,
   **Then** the branch is fetched, `worktrees/<item>` is created on it at the PR head and the
   item records that worktree.
2. **Given** a PR whose head is on a fork, **When** the owner claims it, **Then** the claim is
   recorded, no worktree is made, and the command exits 1 naming a read-only fetch of it. The
   fork is read from the host's head and base repository names, not the ref text.
3. **Given** a local worktree already on the branch, **When** the owner claims the PR, **Then**
   it is adopted as today.

### User Story 2 - next offers the fix-round builder for a claimed PR (Priority: P1)

**Independent Test**: a claimed PR with its worktree, conflicting in the cached listing;
`launch_set` returns a builder launch for the item from the adopted fix-round brief.

**Acceptance Scenarios**:

1. **Given** a claimed PR with a worktree that conflicts with its base, **When** `next` runs,
   **Then** it returns a builder launch whose brief tells the builder to rebase through
   `wuwei pr act <pr> --run` and `--complete`.
2. **Given** a claimed PR with a worktree, red checks or review activity the shepherd duty has
   not answered, **When** `next` runs, **Then** the step resolves through `pr act`: a fix
   request is a builder launch; anything else stays the `wuwei pr act` run of today.
3. **Given** a claimed PR whose fix-round build is ready, running or checking, **When** `next`
   runs, **Then** no second fix round is offered: a ready build is offered as `wuwei build
   next <item>`.

### Edge Cases

- A local branch of the same name already exists: it is checked out as is (no fetch), as
  `worktree add --branch` does today.
- The fetch fails (network, unknown branch): `pr claim` exits 0 with `worktree not created:
  <cause>; rerun bin/wuwei pr claim <ref>`; the claim stays recorded.
- The morning gate is not approved: the claim is recorded and the worktree is not, as for an
  adoption today (`worktree not created: ...` on stderr).
- A WUWEI-raised PR (not claimed) keeps today's offers.

## Requirements

- **FR-001**: `pr claim`, when the item has no worktree and no local worktree is on the PR
  branch, creates `worktrees/<item>` on the PR branch through the `worktree add --branch` path.
- **FR-002**: `worktree add --branch <b>` fetches `<b>` from `brief.remote` when no local
  branch `<b>` exists, so the checkout tracks the remote branch.
- **FR-003**: A PR whose head repository differs from its base repository (or is gone) gets no
  worktree; `pr claim` exits 1 and prints the exact read-only commands.
- **FR-004**: The derived next offers a claimed PR with a worktree a `fix` step on red checks,
  a conflict, or unanswered review activity; the launch set resolves it through `pr act` into
  the builder launch when `pr act` prints one.
- **FR-005**: `pr act` on a conflicted claimed PR with a worktree opens the fix round (the
  adopted fix-round brief path) with rebase feedback, instead of printing the CLI rebase steps.
- **FR-006** (review F1): resolving `next` never merges, posts, replies or marks a PR ready; only
  a conflicted, ci_red, changes_requested or threads_unanswered claimed PR opens a fix round there.
- **FR-007** (review F2, G1): a claimed PR's first fix round builds in `implement`, so the normal
  gates run at the worktree head (FIX goes through fix and delta). Only after every gate passes does
  `wuwei pr act <ref> --push` push the branch, leased on the PR head, and raise the item again. A
  conflict round merges the base, so the teammate's commits keep their authors.
- **FR-008** (review G3, G4): a claimed PR's review activity is a `pr` step that resolves to a
  builder or a plain `pr act` run; the turn that parks at the round cap returns no run; a PR whose
  head branch is the default branch gets no worktree.

## Success Criteria

- **SC-001**: the first acceptance of #879, with a local bare repository as the remote
  (`tests/test_worktree_command.py`).
- **SC-002**: the second acceptance of #879, `launch_set` returns a builder launch for a
  claimed conflicting PR (`tests/test_worktree_command.py`).

## Assumptions

- The worktree is made by the existing `worktree add --branch` code (`commands/worktree.add`,
  `workspace.create_worktree`), so anchoring, identity and the checks bootstrap are the same
  as by hand. The fetch lives in the vcs adapter's `worktree_checkout`, the one place every
  existing-branch checkout passes.
- Fetching is a git read: `fetch --no-tags <remote> <branch>` is already on the adapter's argv
  allowlist and no guard edge names it, so a seat and the planner may run it.
- A fork PR is refused, not handled: WUWEI pushes only to `brief.remote`, so a fix could never
  reach the fork's branch. Reading it is the owner's call with the printed commands.
- A local branch that exists but is behind the PR head is checked out as is; `pr act` reports
  the head mismatch when it matters (`_rebase`). Updating it is out of scope.
- Review threads are read from the listing's `activity_at` against the shepherd duty's record,
  the same signal that makes the shepherd duty due; `pr act` classifies the threads.
- The conflict fix round reuses `pr act --run` and `--complete` inside the builder's brief
  rather than a new rebase path.
