# Feature Specification: fix rounds complete from a fresh Agent launch, and seats save analysis.md through the CLI

**Feature Branch**: `614-fix-round-fresh-launch`
**Created**: 2026-10-09
**Status**: Draft
**Input**: GitHub issue #614 (owner report, 2026-10-09): wuwei v0.23.0 ran a full autonomous
day under Claude Code desktop and hit two bugs. (A) After a gate FIX, `wuwei next` and
`build next` return `continue` with a `resume` agent id (`build.open_fix`,
`build.complete_checks`; the sentinel delta round in `dispatch._seats`). Claude Code's Agent
tool has no resume parameter. Resuming through SendMessage runs the agent but no PreToolUse
Agent or SubagentStop binds it. A fresh Agent launch with the same brief is not bound
either: `agent_launch.reserve` treats a launch as a continuation only with `resume`, so the
fresh launch is "brief already used for a seat launch" (below strict a warning, so the agent
runs unbound), and at SubagentStop `build.stopped` sees status `ready`, not `running`, and
records nothing. The build stays `ready` with action `continue` for ever; `seat stop
--verdict` refuses a stopped seat and gate briefs are refused in phase `fix`. The owner's only
way out was `plan park` plus `plan add` of a new item. (B) Claude Code refuses a subagent's
write of `specs/*/analysis.md` (its report-file heuristic), so the spec-kit `analyze` step
(`specmode.STEPS`) always needs the planner.

## Clarifications

### Session 2026-10-09

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Which fresh launches bind a pending continue? A: Only the launch of the brief whose
  continue is pending. Builder: the item's build is `ready` with action `continue`, the
  build's `seat` is the logged brief's name, and that seat is `stopped`. Sentinel: the seat
  is the first-model gate seat whose initial verdict is FIX, the item is in `delta`, no
  delta verdict is recorded, and the seat is `stopped` with an agent id at the initial head
  (the exact condition `dispatch next` uses to offer the delta `continue`, kept in one
  function). Any other reuse of a brief stays refused.
- Q: Does `resume` still work? A: Yes, unchanged: with `resume` the launch must still match
  the stopped agent, and a builder `resume` that does not match is refused as today.
- Q: How does SubagentStop accept the fresh agent's new id? A: The bind drops the build's
  recorded `agent_id` and `completion` (they belong to the replaced agent and its own
  transcript) and keeps the replaced id as `replaced`. A later stop from the replaced agent
  is ignored, so a late or replayed stop cannot complete the fresh round. The sentinel seat
  is re-reserved by the launch and `stop_seat` records the fresh agent id, as for a resumed
  seat.
- Q: What does the planner do with a `continue`? A: Launch a fresh Agent in the background
  with the returned `prompt` and `agent_type`; pass `resume` only where the harness offers
  it. The `continue` actions keep their `resume` field for such a harness. The `then` line of
  `wuwei next`, the skills and the docs say so.
- Q: Exit codes of `wuwei spec analysis`? A: 0 written (it prints the path relative to the
  worktree), 2 when it could not run (unknown item, no worktree, no or two spec directories,
  no `spec.md`, a symlink, an empty report, an unreadable file). A refusal is not a finding,
  so there is no exit 1.
- Q: Which item id does the command take? A: The id as the brief names it. The step line
  formats `{item}` lowercased (as for every spec step), so the command matches the day's item
  case-insensitively when exactly one item matches.
- Q: Event? A: None. The builder's own Bash PostToolUse already records `spec.step analyze`
  through the spec guard once the file exists; the builder commits the file itself.

## User Scenarios and Testing

### User Story 1 - A fix round completes from Claude Code (Priority: P1)

After a gate FIX the planner launches a fresh Agent with the `continue` prompt. The launch
binds the build, the SubagentStop records the result, and the round proceeds to checks, done,
and the delta.

**Acceptance Scenarios**:

1. **Given** a gate FIX opened the fix round (build `ready`, action `continue`, its seat
   `stopped`), **When** an Agent PreToolUse launch without `resume` carries the same brief,
   **Then** it exits 0, the build is `running` and the seat is `running`.
2. **Given** that bound launch, **When** SubagentStop arrives with a new agent id, **Then**
   the result is recorded (build `check`, the new agent id recorded), and `build check` then
   leads to `done` and the item moves to `delta`.
3. **Given** the fresh bind, **When** a stop from the replaced agent id arrives, **Then**
   nothing is recorded and the build stays `running`.
4. **Given** the delta round offers a sentinel `continue`, **When** a fresh Agent launch
   without `resume` carries the seat's brief, **Then** it binds at the current HEAD, the
   SubagentStop records the new agent id, and `dispatch receive --round delta` records the
   verdict.
5. **Given** a used brief with no pending continue (a done build, a sentinel outside its
   delta), **When** it is launched again without `resume`, **Then** it is refused with
   `brief already used`.
6. With `resume`, the existing behaviour holds: a matching id continues, a builder id that
   does not match is refused.

### User Story 2 - A builder seat saves its analysis report (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an item worktree with exactly one spec directory holding `spec.md`, **When**
   `bin/wuwei spec analysis <item>` reads a report on stdin (or `--file PATH`), **Then** it
   writes `analysis.md` there atomically, prints the relative path and exits 0, and the
   specmode `analyze` step reads as done for a clean report.
2. **Given** no spec directory, two matching directories, a directory without `spec.md`, a
   symlinked `analysis.md`, or an empty report, **Then** it exits 2 with a reason naming the
   fix and writes nothing.
3. **Given** a builder seat, **When** it runs the command through Bash with stdin redirected
   from a file or a heredoc, **Then** no guard refuses it.
4. The builder brief's spec line names the command for the `analyze` step.

## Requirements

- **FR-001**: `agent_launch.reserve` binds a launch without `resume` to the pending continue
  of the logged brief's own stopped seat, under the conditions of the first Clarification;
  with `resume` it behaves as today; every other reuse of a brief stays refused.
- **FR-002**: `dispatch.delta_due(data, item, role, name)` is the one rule for "this seat's
  delta continue is due", used by `dispatch._seats` and by the launch guard.
- **FR-003**: `build.started(..., fresh=True)` drops the build's `agent_id` and `completion`
  and keeps the replaced id; `build.stopped` ignores a stop from the replaced id and accepts
  the fresh agent's id.
- **FR-004**: The HEAD check stays skipped for a continuation (fresh or resumed); the seat
  records the current HEAD.
- **FR-005**: `wuwei next` gives a `continue` row its own `then` line (a fresh Agent in the
  background with the returned prompt; `resume` only where the harness offers it), and the
  `set` line says the same; the skills `wuwei-plan` and `wuwei-report` and the docs
  (reference.md, daily.md, concepts.md) match.
- **FR-006**: `bin/wuwei spec analysis <item> [--file PATH]` writes the report as
  `analysis.md` in the item's single spec-kit directory (the specmode speckit location
  rules), refusing as US2.2; it is a `WRITES` command in the plumbing group and listed in the
  reference.
- **FR-007**: The specmode speckit `analyze` command text names `bin/wuwei spec analysis
  {item}`; configuration.md and the builder charter say a seat saves the report through it.

## Success Criteria

- **SC-001**: The scripted day completes its fix round and delta with fresh Agent launches
  and new agent ids, with no `seat stop unmatched` event.
- **SC-002**: A builder seat finishes the spec-kit `analyze` step without the planner.

## Assumptions

- Claude Code assigns a fresh Agent a new agent id and a new transcript; its first user turn
  starts with the `WUWEI brief:` line, so SubagentStop binds by brief as for any launch.
- A planner that both resumes through SendMessage and launches fresh would leave the
  replaced agent unbound; its later stop is ignored (FR-003), never recorded as the round.
- The cycle budget is unchanged: the fresh launch is the same single fix round.

## Design spec conflict (raised, not resolved)

- Design 5.3 (line "A re-gate continues the same sentinel with the delta; a fresh seat only
  for a lost agent") and the step loop amendment ("`continue` with feedback and the stopped
  agent identity ... The planner executes launch and continue with Agent") assume the
  harness can resume an agent. Under Claude Code every continuation is a fresh agent on the
  same brief and seat. Proposed text: "A re-gate continues the same sentinel seat and brief
  with the delta; the harness resumes the stopped agent where it can, else a fresh agent
  launches with the continue prompt and binds the same seat."
- The launch guard's brief reuse rule changes (constitution, Workflow: a changed guard rule
  adds its 9.2 invariant). `tests/test_invariants.py` pins the table to the design, which only
  the owner amends, so this feature asserts the property in `tests/test_agent_launch.py` and
  `tests/test_build_next.py` and proposes the row for the owner: "I25 | A used brief binds a
  second seat launch only as the pending continue of its own stopped seat (a builder whose
  build awaits `continue`, a sentinel whose delta is due); any other reuse is refused, and a
  stop from the replaced agent never records the round | the launch guard on a fresh and a
  resumed continue, a done build and a sentinel outside its delta; `build.stopped` on the
  replaced agent id | #614".

## Deferred

- None.
