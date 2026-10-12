# Feature Specification: an unfinished build whose worktree moved past its brief takes a new brief

**Feature Branch**: `889-stale-brief`

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #889: "build next and seat brief refuse each other when the worktree
moved past an unfinished build's brief"

## What happened

On 0.29.0 an item was built outside the record by an ad-hoc seat (15 commits, pushed). Handing
it back looped with no exit: `build next` returned `launch` with the original brief; the Agent
guard refused that launch because the worktree HEAD changed since the brief was written and
told the planner to write the brief again; after `seat brief` wrote a new one, `build next`
refused it as a replacement of an unfinished build and pointed at itself.

## Root cause

`next_action` (`cli/wuwei/commands/build.py:248-249` on the base branch) refuses any new brief
while the build record is not `done` or `parked`. A record that is `ready` with a `launch`
action has never run a seat, but it is still "unfinished", so the newer brief is refused. The
Agent guard (`cli/wuwei/guards/agent_launch.py:250-251`) refuses to launch the old brief
because its logged HEAD is no longer the worktree HEAD. Each refusal sends the planner to the
other one.

## User Scenarios & Testing

### User Story 1 - hand back an item built outside the record (Priority: P1)

**Independent Test**: a build record is `ready` with a `launch` of brief B1 logged at HEAD H1;
the worktree moves to H2; the B1 launch is refused; a new builder brief B2 is logged at H2;
`build next` returns the B2 launch, the seat runs, checks pass and the item moves to `gate`.

**Acceptance Scenarios**:

1. **Given** an unlaunched build whose worktree HEAD is no longer its brief's logged HEAD,
   **When** a new builder brief for the same item and worktree is written and `build next`
   runs, **Then** it returns the launch of the new brief and the record points at it.
2. **Given** that replacement, **When** the builder stops and the fast checks pass, **Then**
   the build is done and the item moves to its gates; the commits made outside the record
   count as the build's change (the start head is kept), so the no-change rule does not
   demand another commit, and the private-file check covers those commits.
3. **Given** an unlaunched build whose worktree HEAD still equals its brief's logged HEAD,
   **When** a new brief is written, **Then** `build next` still refuses the replacement.

### Edge Cases

- A record from before start heads (no `start`): the replacement takes the old brief's logged
  HEAD as its start, so the outside commits still get the private-file check.
- The old brief is not logged today (a brief from another day): the guard refuses its launch
  too, so it counts as stale and the new brief replaces it.
- The old brief was logged with no HEAD (no worktree): the guard never refuses it, so the
  refusal stands (review F1).
- A stale fix-round launch: the replacement keeps the fix feedback and CI block in its prompt
  (review F2).
- A hand-back on a later day has no build record: the fresh record starts at the brief's
  `Merge-base:` line, so the branch's outside commits count as the build's change and go
  through the private-file check and the gates (review F4). A brief with no merge base
  (no worktree) starts at HEAD as before.
- The merge base is no longer an ancestor of HEAD (the branch was rebased after the brief):
  the start is HEAD (review D3).
- A record whose own brief another builder seat already ran (a seat launched straight from
  the brief, then ended unmeasured): the guard refuses it, so it counts as stale and a fresh
  brief replaces it at the same HEAD (review D1).
- A build that is `running`, `check`, or `ready` with a `continue` or `wait` keeps the refusal:
  a builder or its feedback is in flight.
- A new brief on a different worktree keeps the refusal.

## Requirements

- **FR-001**: `next_action` replaces a `ready` build whose action is `launch` with a newer brief
  for the same worktree when the old brief's logged HEAD is not the worktree HEAD (or is not
  logged today).
- **FR-002**: the replaced record keeps the previous record's fields (start head, fix rounds);
  a missing start head takes the old brief's logged HEAD.
- **FR-003**: every other unfinished build keeps the refusal, including an old brief logged
  with no HEAD.
- **FR-004**: a replaced fix-round launch carries its feedback and CI block.
- **FR-005**: a build record created with no previous record starts at the brief's merge base
  when the brief names one, else at HEAD.

## Success Criteria

- **SC-001**: the issue's sequence ends with the item in `gate` (test
  `test_a_new_brief_replaces_an_unlaunched_build_past_its_brief_head`).
- **SC-002**: the refusal stands when the HEAD did not move, and when the old brief has no
  logged HEAD (same test, unmoved and headless cases).
- **SC-003**: a fresh build on a branch ahead of its base, whose seat adds nothing, is done and
  moves to `gate` (`test_a_fresh_build_starts_at_the_brief_merge_base`).

## Assumptions

- The exit is on the `seat brief` side: the guard's own message already says to write the brief
  again, so `build next` accepts that brief. `build next` writing a brief by itself was not
  chosen: it would need a body the planner writes.
- The right start head is the build's original one, not the current HEAD. Moving it to the
  current HEAD would make the no-change rule park a hand-back whose work is already committed.
- Staleness is read with the vcs adapter's head, the same read the Agent guard compares, so the
  refusal yields in exactly the case the guard refuses.
- The guard's message is unchanged: after `seat brief`, a launch of the new brief before `build
  next` is refused as "seat brief differs from active build", which names `build next`.

## Deferred

- None.
