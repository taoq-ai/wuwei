# Feature Specification: build next never hands out a brief a seat already used

**Feature Branch**: `889-stale-brief` (stacked; feature dir `specs/892-used-brief`)

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #892: "After a builder seat stops with the build unfinished, the next
build next must return an action whose launch registers cleanly; no path returns the same brief
name for two seats."

## What happened

On the owner's 0.29.0 day, three builders (TIN-916, REVIEW-3140 for ai-stacks#3140, TIN-929)
were launched straight from their `seat brief` output, before any `build next`. The Agent guard
registered each seat, but with no build record nothing bound it to a build. After each seat
stopped, `build next` created a record whose action was a `launch` of that same brief. The guard
refused that launch ("brief already used for a seat launch"), so the relaunched seats ran
unregistered.

## Root cause

`next_action` (`cli/wuwei/commands/build.py:233-237` and `:258` on the base branch) takes the
latest logged builder brief and builds a launch for it without asking whether a seat already ran
it. With a record already on that brief, `:244-247` returns the recorded launch again. The guard
lets a builder launch with no build record through (`started`, `build.py:355-356`, returns when
there is no record), so the first seat ran outside the record. One brief is one seat
(`cli/wuwei/guards/agent_launch.py:234-237`), so the second launch can never register.

## User Scenarios & Testing

### User Story 1 - a seat that ran its brief outside the record (Priority: P1)

**Independent Test**: launch a builder from its brief with no build record, let it stop; `build
next` returns a `continue` of that seat; its launch registers; checks pass; the item reaches
`gate`.

**Acceptance Scenarios**:

1. **Given** a builder brief a stopped seat already ran and no build record, **When** `build
   next` runs, **Then** it returns a `continue` bound to that seat (its agent id as `resume`),
   and launching it registers.
2. **Given** the same seat and a record an older `build next` wrote (a `launch` of the used
   brief), **When** `build next` runs, **Then** the record is replaced by the same `continue`.
3. **Given** that seat still running, **When** `build next` runs, **Then** it says to wait for
   the seat's stop hook.
4. **Given** the continue, **When** the seat stops and checks pass, **Then** the commits it made
   since its launch HEAD count as the build's change and the item moves to `gate`.

### Edge Cases

- A seat on the brief that is `unmeasured`: the guard cannot continue it, so `build next` asks
  for a fresh brief.
- A record already bound to the seat (`record.seat` is it): unchanged; its own action stands.

## Requirements

- **FR-001**: `next_action` finds the builder seat that ran the brief it is about to use.
- **FR-002**: a stopped seat not bound to the build becomes the build's seat: the record binds
  its name and agent id and returns a `continue`, starting at the seat's launch HEAD.
- **FR-003**: a running seat answers "wait for its stop hook"; any other status asks for a fresh
  brief. No path returns a `launch` of a used brief.

## Success Criteria

- **SC-001**: `test_a_brief_a_seat_already_ran_continues_that_seat` (both cases) passes.

## Assumptions

- The fix is in `next_action`, the one place every `build next` caller (`next`, `dispatch`,
  `pr act`) routes through. The guard keeps letting a builder launch without a record: the
  guard's own message tells the planner to launch what `seat brief` returns, and refusing it
  would be a flow change outside this issue.
- A continue, not a fresh brief name: the stopped seat holds the work and its agent id, and the
  guard already binds a fresh agent to a stopped seat's pending continue (#614).
- The start head is the seat's recorded launch HEAD, so its commits count as the change.

## Deferred

- Whether the Agent guard should refuse a builder launch with no build record (send the planner
  to `build next` first). Not filed; raised in the report.
