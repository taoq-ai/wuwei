# Feature Specification: a new worktree fetches first and branches from origin/<base>, never from a stale local main

**Feature Branch**: `681-worktree-from-origin`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #681 (owner, 2026-10-10, item 47): an item's worktree started at a
commit minutes behind origin/main although a PR had just merged there; the builder
fast-forwarded it by hand. Deliver: `wuwei worktree add` (and every path that creates an
item worktree: dispatch, build start) runs `git fetch origin <base>` first and branches from
`origin/<base>`; when the fetch fails it says so and refuses rather than branching from the
local ref; the record names the start commit and `why` shows it; `doctor` warns when a
running item's worktree base is behind origin by more than the configured commits.

## Root cause

Reproduced read-only in a scratch repository (bare origin, a clone whose local `main` is one
commit behind, `git fetch origin` already run so `origin/main` is current), running the exact
command the adapter runs:

```text
local main:  41f54d3...
origin/main: 86ea3c8...
new worktree HEAD (adapter form, no start point): 41f54d3...
```

`adapters/vcs/git.py:363` to `370`, `worktree_add`, runs
`git worktree add -b <branch> -- <path>` with no start point, so git branches from the main
checkout's `HEAD`: the local default branch, however stale. Nothing fetches first:
`cli/wuwei/workspace.py:825`, `create_worktree`, calls `vcs.worktree_add(repo, branch, path)`
straight after the gate check and the claim. Even a fresh `origin/main` would not help, as
the repro shows: the start point is the local branch.

`create_worktree` is the one place an item worktree is created. `wuwei dispatch next` and
`wuwei next` do not create worktrees; `dispatch._start` (`cli/wuwei/dispatch.py:481`) returns
the `wuwei worktree add <item>` command for the planner to run, and `wuwei build` reads a
worktree that already exists (`cli/wuwei/commands/build.py:136` names `worktree add` when it
is missing). So fixing `worktree_add` and its one caller fixes every path the issue names.
`wuwei worktree add --branch` and `pr claim` check out an existing branch
(`worktree_checkout`) and do not pick a start point; they are not part of this defect.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which remote and which base? A: The configured ones: `brief.remote` (default `origin`,
  already what briefs and dispatch use for `<remote>/<default_branch>`) and the selected
  repository's `repos.default_branch`. No new config key.
- Q: Branch from `origin/<base>` or from the fetched commit? A: From the commit the fetch
  returned (`FETCH_HEAD`), by its SHA. It is exactly `origin/<base>`'s head at that moment,
  works whether or not the clone has a remote-tracking refspec, and does not make the new
  branch track `origin/<base>` (today's branch tracks nothing; a tracking upstream of
  `origin/main` would point a bare `git push` at main).
- Q: What does the record name? A: A `worktree.created` event with the item, worktree path,
  branch, base (`origin/main`) and start SHA, and the printed JSON gains `start`. `why <item>`
  prints one line from it.
- Q: Does a fetch failure leave anything behind? A: No worktree and no branch: the fetch runs
  before `git worktree add`. The item claim written before it (an existing step) stays, as it
  does today for any failed add.
- Q: What about the `doctor` warning for a running item's base behind origin by more than
  the configured commits? A: Deferred (see Deferred). The owner's failure is the start point
  at creation, which this feature fixes. A base that falls behind while the item runs is
  normal as other PRs merge, and the PR flow already handles it (`mergeable_state=behind`
  updates the base before merge). The warning needs a new config key, a new git read and a
  doctor row: real code for a need nobody has reported.

## User Scenarios and Testing

### User Story 1 - the builder starts from what is on origin (Priority: P1)

The planner runs `wuwei worktree add <item>` minutes after a PR merged to origin/main, while
the workspace's clone still has the old local main. The new worktree starts at origin/main's
head, so the builder never fast-forwards by hand and never builds on a stale base.

**Why this priority**: it is the owner's reported defect.

**Independent Test**: real git in `tmp_path`, no network: a bare origin one commit ahead of
the clone's local main; run `main(['worktree', 'add', 'X'])`.

**Acceptance Scenarios**:

1. **Given** a local main behind origin, **When** `wuwei worktree add X` runs, **Then** the
   new worktree's merge-base with origin/main is origin/main's head (the worktree's HEAD is
   origin main's tip), the exit is 0 and the printed JSON's `start` is that SHA.
2. **Given** no network (the remote cannot be reached), **When** `wuwei worktree add X`
   runs, **Then** it exits 2 with the fetch error on stderr, and no worktree is created: no
   `worktrees/X`, no branch `x`, no new entry in `git worktree list`.

### User Story 2 - the record names where the worktree started (Priority: P2)

After the add, `bin/wuwei why <item>` shows the branch, the base and the start commit, so the
owner can tell from the record which commit the builder started from.

**Independent Test**: append a `worktree.created` event in a why fixture and read
`why <item>`; the add test above reads the event from `events.jsonl`.

**Acceptance Scenarios**:

1. **Given** a successful `worktree add X`, **Then** today's `events.jsonl` has one
   `worktree.created` event with `item`, `worktree`, `branch`, `base` and `start`.
2. **Given** that event, **When** `why X` runs, **Then** it prints a line
   `worktree: branch x from origin/main at <start, 12 characters>`.

### Edge Cases

- The remote has no branch named the base (misconfigured `default_branch`): the fetch fails,
  exit 2, nothing created; the message names the remote and base.
- The fetch times out (adapter `TIMEOUT`, 30 seconds): exit 2 with the reason, nothing
  created.
- `--branch <existing>`: unchanged, no fetch (it checks out an existing branch).
- A remote or base that looks like an option (`-x`, `--upload-pack=...`): refused by the
  adapter allowlist before any process starts (exit 2).
- Two concurrent adds in one repository with different bases share `FETCH_HEAD`; recorded as
  a `ponytail:` ceiling (one base per repository today, so both fetch the same ref).

## Requirements

### Functional Requirements

- **FR-001**: The vcs port `worktree_add` takes `remote` and `base`, fetches
  `<remote> <base>` (`git fetch --no-tags`, already allowlisted), reads the fetched commit and
  creates the new branch at that commit; it returns `branch`, `path` and `start`.
- **FR-002**: A failed or timed-out fetch makes `worktree_add` return exit 2 with a reason
  that names the remote and base and says no worktree was created; `git worktree add` is not
  run.
- **FR-003**: `workspace.create_worktree` passes the configured remote (`brief.remote`) and
  the selected repository's `default_branch` for a new branch; `--branch` (existing branch)
  is unchanged.
- **FR-004**: `wuwei worktree add <item>` exits 2 with the reason on a fetch failure (the
  existing `ValueError` path through `_call`) and prints `start` in its JSON on success.
- **FR-005**: After a successful add, `create_worktree` appends one `worktree.created` event
  (`item`, `worktree`, `branch`, `base`, `start`), produced only by `wuwei worktree add`
  (listed in `EVENT_PRODUCERS`, so `wuwei event` cannot forge it).
- **FR-006**: `why <item>` prints one line per `worktree.created` event of the item:
  `worktree: branch <branch> from <base> at <start[:12]>`.
- **FR-007**: The owner docs (`docs/site/reference.md`, `worktree add` paragraph) and the
  design spec's vcs port row (section 8 adapters table) state the new behaviour and
  signature.

### Key Entities

- **`worktree.created` event**: `{item, worktree, branch, base, start}`; `base` is
  `<remote>/<default_branch>`, `start` a full commit SHA.

## Success Criteria

- **SC-001**: With origin one commit ahead of local main, the new worktree's HEAD equals
  origin main's head (real-git test).
- **SC-002**: With an unreachable remote, `worktree add` exits 2, stderr names the fetch,
  and neither the worktree directory nor the branch exists.
- **SC-003**: `why X` shows the start commit from the record.

## Assumptions

- The orchestrator notes file named for this issue does not exist; the issue text is the
  whole input. No dry-run workspace was named, so the failure was reproduced in a scratch
  repository with the adapter's exact git command.
- "No network" is tested with a remote URL pointing at a missing path: the fetch fails the
  same way (exit 128, a `fatal:` line) without touching the network, per the engineering rule
  that tests never need network.
- Every configured repository has the configured remote with the default branch on it. A
  repository with no remote now refuses `worktree add` (exit 2) instead of branching from a
  local ref, which is what the issue asks for. An owner with a local-only repository can set
  `brief.remote = "."` (git fetches from the repository itself; the allowlist accepts it).
- The design spec section 8 vcs row is amended to `worktree_add(repo, branch, path, remote,
  base)`; precedent: #631, #633 and #641 amended the design for owner issues.
- The claim (`item.claimed`) written before the fetch stays on a failed fetch, as it does
  today for any failed `git worktree add`; the claim is the calling session's and a retry
  reuses it.
- Item 48 of the owner's message (the secret redactor blocking a docs page) is a separate
  issue and not part of this feature.

## Deferred

- `doctor` warning when a running item's worktree base is behind `<remote>/<base>` by more
  than a configured number of commits (issue #681, last clause). Needs a new config key, a
  `rev-list --count` read in the git adapter and a doctor row. To be filed as a follow-up
  issue linked to #681.
