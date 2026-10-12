# Feature Specification: raised and claimed PRs share one post-PR path

**Feature Branch**: `903-post-pr`

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #903 (independent review, item 3, "Existing PR" and "Post-PR review"
contradictions), with two items folded in from the #907 review: "Unify the post-PR path for
raised and claimed PRs. Treat an item with a linked PR as an update. Extend
pr_actions._gated_push to owned PRs, and have raise_action select it for both ownership
origins. Explicitly require the promised post-PR architecture review; preserve the all-gate
reread for an unrelated moved head." Folded in: a raised or claimed PR with red checks raises a
`fix` whatever phase the item record holds; `pr act --complete` is leased on the head `--run`
started from.

## What happened

A WUWEI-raised PR whose CI went red got a fix round. After the fix, every initial gate verdict
was a PASS carried to the new head by the fix-head chain, so `dispatch.rechecks` selected no
gate: the fix reached the PR with no review, against the charter's post-PR architecture delta
(`charters/_common.md`, Evidence 4). `raise_action` then sent the item to the shepherd's raise,
which refuses an item that already links a PR. Claimed PRs had a gated push (#879); raised PRs
had none. Separately, an item recorded at `gate` with an approved PR whose Unit CI was red got
gates and a shepherd duty from `next`, never a fix; and `pr act --complete` leased its push on
the head it read at that call, so a teammate's push during a conflict resolution could be
overwritten.

## Claims checked against this branch

Base: `903-post-pr`, stacked on `902-one-action` (unmerged #902), main after #879, #901, #904,
#906 and #887. Each claim that holds has a failing test in `tests/test_post_pr.py`.

| Claim | Holds | Where (base) | Failing test |
|---|---|---|---|
| A normal PR fix selects no delta reviewer: every initial gate passed, the fix-head chain keeps them current | yes | `dispatch.py` `rechecks` | `test_a_raised_pr_fix_takes_its_arch_delta_and_the_gated_push[PASS]` (next returned `raise`, not `gates`) |
| A pre-PR delta PASS stands in for the PR fix's review: the delta record survives the raise and the fix-head chain carries it to the fix head | yes | `commands/build.py` `open_fix` rotates only from delta | same test, `[FIX]` |
| A linked, WUWEI-raised PR routes to the shepherd raise, which refuses an existing PR | yes | `dispatch.py` `raise_action`, `shepherd.py` `raise_pr` | same test (the `raise` action with a shepherd brief) |
| `_gated_push` refuses a raised PR | yes | `pr_actions.py` `_gated_push` | same test (the `--push` step) |
| Red checks on a PR whose item is at `gate` (or `delta`) give gates, not a fix | yes | `derive.py` `offers`, gate branch | `test_red_checks_on_a_pr_at_gate_raise_a_fix[gate]`, `[delta]` |
| At delta, `pr act` on red checks returns a non-executable `arch_delta` step even when the red head is the one the item holds | yes | `pr_actions.py` `_fix_round` | `[delta]` of the test above |
| `pr act --complete` pushes over a teammate's push made after `--run` | yes | `pr_actions.py` `_rebase` | `test_complete_refuses_when_the_pr_head_moved_since_run` |
| A seat's own `git push` from a raised PR's worktree is allowed (the claimed one is refused) | yes | `guards/edges.py` `_claimed` | `tests/test_edges.py::test_a_seat_push_from_a_raised_pr_worktree_is_refused` |

## User Scenarios & Testing

### User Story 1 - a PR fix always takes its delta review (Priority: P1)

**Independent Test**: raise a PR, receive all PASS verdicts, introduce a CI failure, fix it,
complete the architecture review and push: one PR, one required delta review, no raise.

**Acceptance Scenarios**:

1. **Given** an item with a linked PR whose gates all passed, **When** a fix round ends,
   **Then** `dispatch next` returns the arch gate (the item's one gate when its set has no
   arch) for the delta, and nothing raises until it passes.
2. **Given** arch asked for a pre-PR round and passed its delta, **When** a PR fix round ends,
   **Then** arch reviews the PR fix; the pre-PR delta does not count for it.
3. **Given** a PR head moved outside a fix round, **When** the round it opens ends, **Then**
   every gate re-reads the head (unchanged).

### User Story 2 - a linked PR is updated, never raised again (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a raised or claimed PR whose fix passed its gates, **When** `dispatch next` runs,
   **Then** it returns `wuwei pr act <ref> --push`, never the shepherd raise.
2. **Given** that step, **When** it runs, **Then** it pushes the gated head, leased on the PR
   head the worktree contains, and the item is raised again; one PR exists.
3. **Given** a seat in a raised PR's worktree, **When** it runs `git push`, **Then** it is
   refused with the `pr act --push` command.

### User Story 3 - red checks are a fix whatever the phase (Priority: P2)

**Acceptance Scenarios**:

1. **Given** an item recorded at `gate` or `delta` with a PR whose checks are red at the head
   the worktree holds, **When** `next` derives it, **Then** it offers the fix (`wuwei pr act`),
   and resolving it opens the fix round.
2. **Given** the worktree is past the red PR head (a fix in review), **When** `next` derives it,
   **Then** the gates read the new head first.

### User Story 4 - --complete never overwrites a teammate's push (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `pr act --run` hit a conflict, **When** a teammate pushes and the builder runs
   `pr act --complete`, **Then** nothing is pushed and the refusal names the moved head.
2. **Given** no `--run` started, **When** `--complete` runs, **Then** it refuses and names
   `--run`.

## Requirements

- **FR-001**: `dispatch.rechecks` selects the item's post-PR delta gate (arch, else the set's
  one gate) once the item has a PR; the moved-head rule that rereads every gate is unchanged.
- **FR-002**: A fix round opened from `raised` rotates the gates' delta records into initial,
  as a round opened from `delta` does, so a pre-PR delta never counts for the PR fix. Kept
  rounds take the next free `round<n>` key.
- **FR-003**: `raise_action` returns `wuwei pr act <ref> --push` for any linked PR.
- **FR-004**: `_gated_push` accepts a raised or claimed PR with a worktree; the lease, the
  fast-forward check, the checked-head rule and the clean-tree push check are unchanged.
- **FR-005**: The push guard refuses a seat's `git push` from the worktree of any item that
  links a PR (and to a claimed PR's recorded branch, as before).
- **FR-006**: `derive.offers` offers a fix (or the cap question) for an item at `gate` or
  `delta` whose PR checks are red at the head its worktree holds, unless its listing is
  unmeasured (#900).
- **FR-007**: `_fix_round` at `delta` opens the fix when the red head is the one the worktree
  holds; otherwise it keeps the delta step.
- **FR-008**: `pr act --run` records the PR head it starts from on the conflict episode;
  `--complete` refuses unless the PR head is still that head.

- **FR-009** (review F1): the red fix replaces only a step that would review that head (gates,
  fix, raise, polish); gone, recheck, build, ask, park and cap keep their path. `pr act` records
  a `base_red` head (`watch.base_red`), and a red head recorded there falls through to the gates.
- **FR-010** (review F2): a late initial verdict (received in the delta at the fix head) is not
  asked for the post-PR delta again until the next fix round.
- **FR-011** (review F3): `--complete` with no recorded run head says to reset the worktree to the
  PR head (`git rebase --abort`, or `git reset --keep <head>`) before `--run`.
- **FR-012**: `pr act` for a raised PR with a worktree is a seated launch, as a claimed PR's is: red
  checks resolve to the fix-round builder; a raised PR's conflict stays its rebase run.

## Assumptions

- The post-PR delta applies to every delta of an item with a PR, a claimed PR's first gate round
  included: the charter says delta checks are arch-only once a PR is open, and a claimed PR is
  open. A gate that asked for the fix still re-checks it. Overturn if claimed PRs should skip it.
- A docs or light item has no arch gate; its one gate takes the post-PR delta.
- The edge guard covers a raised PR through its worktree only; a raised PR's branch is not
  recorded (a claim records it), so a push of that branch from another checkout is left to the
  existing default-branch and force rules. Recording it would refuse the scripted day's pushes
  of `main` for an item raised from `main`.
- A conflict on a raised PR keeps the rebase path (`pr act --run`); a claimed PR keeps the merge
  fix round (a rebase would rewrite a teammate's commits). That split is about whose commits
  are on the branch, not the post-PR path, so it stays.
- `--complete` with no recorded `--run` refuses: an unknown start head cannot prove nobody
  pushed.
- The run head is written with the default `state.write` event kind; no new event kind.

## Success Criteria

- **SC-001**: The issue's scenario ends with one PR, one arch delta receipt, one push leased on
  the raised head and no shepherd raise seat.
- **SC-002**: The four claims' tests fail on the base and pass after the change; the full suite
  passes.
