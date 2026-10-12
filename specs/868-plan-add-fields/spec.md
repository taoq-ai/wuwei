# Feature Specification: plan add takes --repo, track, governed_by and flags, so an owner-admitted item can start in a multi-repo workspace

**Feature Branch**: `864-plan-admit` (feature directory `specs/868-plan-add-fields/`, shared
branch with #864: both change plan admission)

**Created**: 2026-10-12

**Status**: Draft

**Input**: Issue #868, "fix(plan): plan add takes --repo, track, governed_by and flags, so an
owner-admitted item can start in a multi-repo workspace".

## Context

With three repositories configured the owner admitted three items after the gate with
`plan add <item> --goal G-1 --note ...`. `next` returned `plan park <item> --reason 'names no
configured repository ...'` for each (`cli/wuwei/dispatch.py:791-797`): `_start` reads the
repository only from the proposal row, and `plan add` (`cli/wuwei/plan.py:441-501`) has no
`--repo`, writes no proposal row and hard-codes `track: SLICE` and all flags false
(`cli/wuwei/plan.py:471-472`). A trust-surface item re-admitted this way loses FULL and
trust_surface.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An owner-admitted item starts in a multi-repo workspace (Priority: P1)

**Independent Test**: two configured repositories; `plan add X --goal G-1 --repo acme/code`;
then `next`.

**Acceptance Scenarios**:

1. **Given** several repositories, **When** `plan add X --goal G-1 --repo owner/name` runs,
   **Then** the item records the repository and the next `next` returns `start` with
   `wuwei worktree add X --repo owner/name`.
2. **Given** several repositories, **When** `plan add X --goal G-1` runs without `--repo`,
   **Then** it exits 2 naming the configured repositories and writes nothing (the park can
   no longer happen for an owner item).
3. **Given** `--repo` names no configured repository, **When** `plan add` runs, **Then** it
   exits 2 naming the configured ones and writes nothing.

### User Story 2 - An owner-admitted item keeps its rigour (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `plan add X --goal G-1 --track FULL --trust-surface`, **When** it runs, **Then**
   the item records `track: FULL` and `flags.trust_surface: true` (the other flags false), and
   the `plan.added` event carries the flags.
2. **Given** `--track` other than SLICE or FULL, **When** `plan add` runs, **Then** it exits 2
   with the same message `plan propose` gives, and writes nothing.
3. **Given** `--governed-by <path>`, **When** `plan add` runs, **Then** it is checked by the
   same function as `plan propose` (#864) against the item's repository and recorded on the
   item; a reference that does not resolve exits 2 and writes nothing.

## Requirements *(mandatory)*

- **FR-001**: `plan add` takes `--repo`, `--track`, `--governed-by`, `--trust-surface`,
  `--boundary-relevant` and `--agent-surface`; the item records repo, track, flags and
  governed_by.
- **FR-002**: Track, flags and governed_by are validated by the same function `plan propose`
  uses; no second validation path.
- **FR-003**: `plan add` requires `--repo` for an owner item when several repositories are
  configured and refuses an unknown repository.
- **FR-004**: `dispatch._start` (and `worktree add` through it) reads the item's recorded
  repository before the proposal row.

## Success Criteria *(mandatory)*

- **SC-001**: `plan add X --goal G-1 --repo owner/name` in a multi-repo workspace starts on the
  next `next`; a `plan add` item can be admitted as FULL with trust_surface.

## Assumptions

- "Recorded on the owner's card": `plan add` has no Owner step card; the owner naming the item
  is the decision (design spec: work joins after the gate only when the owner names it) and `--note` records the owner's
  words. The new values are recorded on the item and the `plan.added` event, which already
  carries the flags. Raising track or a flag lowers no gate, so no card is added.
- The repository check applies to owner items only (`source` empty). A seat finding, an
  adopted PR or a main-broken fix item keep today's behaviour; their repository comes from
  their own records.
- In a single-repository workspace `--repo` is optional; when given it must name that
  repository.

## Deferred

- None.
