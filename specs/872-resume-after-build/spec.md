# Feature Specification: a resumed item whose build finished goes on to its gates

**Feature Branch**: `872-resume-after-build`

**Created**: 2026-10-12

**Status**: Draft

**Input**: GitHub issue #872: "fix(resume): a resumed item whose build finished is stuck in
implement: build next says done, gates refuse"

## What happened

On 0.28.0 an item's builder finished and the item was parked by the scanner (#870) before the
build loop moved it to its gates. The owner resumed it with `wuwei plan resume`. Afterwards the
item sat in `implement` with a finished build record: `build next` returned `done`, `build
check` said the build was done, `next` listed `refused: <item>: done` every round, and `seat
brief <role> <item> --gate` refused because the phase was `implement`. No command moved the
item to its gates.

## Root cause

`complete_checks` (`cli/wuwei/commands/build.py`) saves the build record as `done` in one
state write, then reads the item's phase and moves `implement` to `gate` (or `fix` to `delta`)
in a second write. The move is looked up from the phase at that moment
(`{'implement': 'gate', 'fix': 'delta'}.get(phase)`), so when the item is parked or escalated
(the scanner parks on `dispatch receive`, which runs while the builder stops) the lookup
returns nothing and the move is dropped. The item keeps `resume_phase: implement`.
`plan.resume` (`cli/wuwei/plan.py`) then restores that phase as is, next to a build record
that is already `done`. From there every caller of `build.next_action` returns the stored
`done` action, and only `gate` or `delta` lead past it.

## User Scenarios & Testing

### User Story 1 - resume after a finished build (Priority: P1)

The owner resumes an item that was parked after its builder finished and its fast checks
passed. The next `wuwei next` round offers its gates.

**Independent Test**: park an `implement` item whose build record is `done`, answer Yes on
the resume card, resume it; `next` offers `wuwei dispatch next <item>` as a gates launch.

**Acceptance Scenarios**:

1. **Given** an item in `implement` whose build record is `done`, **When** it is parked and
   resumed, **Then** its phase is `gate` and the next `next` round offers its gates.
2. **Given** an item in `fix` whose build record is `done`, **When** it is parked and resumed,
   **Then** its phase is `delta` and the fix round's end head is recorded as the build loop
   records it.
3. **Given** an item parked in any other state (planned, mid-build with the record `ready` or
   `check`, at the gate, after a verdict), **When** it is resumed, **Then** it returns to the
   phase it paused in, as today.

### Edge Cases

- A build record `done` with the item paused in `gate`, `delta` or `raised`: the resume keeps
  that phase (only the build phases advance).
- No build record: the resume keeps the paused phase.

## Requirements

- **FR-001**: `plan resume` returns a paused item whose paused phase is `implement` or `fix`
  and whose build record is `done` to the phase the build loop would have moved it to: `gate`
  or `delta`, with the `delta` fix head recorded as `complete_checks` records it.
- **FR-002**: In every other case `plan resume` keeps today's behaviour: the paused phase,
  status `queued`.
- **FR-003**: The move after a passing build is written by one function that both the build
  loop and the resume call.

## Success Criteria

- **SC-001**: the acceptance of #872: park, then resume an item whose builder has finished;
  the next `next` round returns its gates action (test in `tests/test_next.py`).
- **SC-002**: park then resume in every phase returns the expected phase (table test in
  `tests/test_plan.py`).

## Assumptions

- The fix belongs in `plan resume`, the only path that unpauses an item (`resume_phase` is set
  only by a pause and read only by `plan.resume`). Moving `resume_phase` forward inside
  `complete_checks` was rejected: the state writer forbids changing `resume_phase` without a
  phase change, and the resume has the build record at hand.
- A build record `done` while the item is in `implement` or `fix` means the fast checks and
  the spec check passed for that build (`complete_checks` sets `done` only then), so moving to
  the gates needs no new check. The gates read the worktree head as always.
- Items already stuck on a 0.28.0 workspace (resumed into `implement` with a `done` build)
  recover by parking and resuming them again (`wuwei plan park <item>`, then `wuwei plan
  resume <item>`); no migration is added.
- The scanner parking an item between the builder's stop and its checks is #870's subject;
  this feature does not change when the scanner parks.

## Deferred

- None filed. A builder seat whose record is still `running` when the scanner parks it
  belongs to #870.
