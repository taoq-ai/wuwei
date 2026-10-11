# Feature Specification: delete discovery intake, the spec guard and rank; the spec check stays in dispatch

**Feature Branch**: `b7-leftovers` (feature directory `specs/843-discovery-rank-out/`)

**Created**: 2026-10-11

**Status**: Draft

**Input**: Issue #843, part 21 of the #789 deletion pass: "chore(discovery): delete discovery
intake, the spec guard and rank; the spec check stays in dispatch", with the lead note (owner
confirmed, 2026-10-11): ranking and prioritisation stay in code, `plan propose` orders the
queue by `prioritisation.framework` from the lead's evidence; morning discovery stays; only the
intraday intake machinery goes.

## Context

Three units.

1. **Intraday intake.** After the morning gate, the watch sweep runs `discovery.discover`,
   saves the candidates (`discovery_candidates`) and runs `discovery.intake`; a builder's stop
   requests a seat-free discovery when the queue is below `discovery.min_queue`, run on the
   watch's next tick (`pending_discovery`). Intake passes each candidate to `plan add`, whose
   discovery branch applies `discovery.autostart` (`start_decision`, a strict cut computed with
   `rank.rank`) and writes `intraday_proposals`; the next morning's `plan propose` carries the
   `tomorrow` ones. In practice every raw candidate lacks a score and goes to `owner`, and
   nothing surfaces `owner` proposals.
   **Morning discovery stays**: the lead runs `wuwei discover` (tracker backlog, red base
   checks, review and scanner findings, threads, metric regressions, PR follow-ups), and
   `plan propose` measures the same sources into the sweep and the plan's discovered list.
2. **The PreToolUse spec guard** (`guards/spec.check_edit`) refuses a source edit in an item
   worktree while a spec step before implementation is missing. The PostToolUse step recorder
   (`check_record`) and the SubagentStop artifact check (`check_stop`) are not the PreToolUse
   guard and stay. The process check the owner kept ("process control kept": spec before
   gates for non-light tiers) is `specmode.check` in `dispatch.next_step`, and the build loop's
   failing `spec` check before handoff (`commands/build.complete_checks`); both stay.
3. **`wuwei rank`**: a command that previews the order of a candidate JSON. `plan propose`
   already re-sorts the queue with `rank.rank` by `prioritisation.framework`, after
   `rank.validate` checks every component and its evidence line; the lead's order is never
   used. The command goes; its template helper moves to `plan template`, its only other user.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A non-light item never reaches its gates without its spec (Priority: P1)

**Why this priority**: the issue's acceptance, and a kept process control.

**Independent Test**: `tests/test_dispatch.py` with spec mode strict and `guards.enforce` on.

**Acceptance Scenarios**:

1. **Given** a standard-tier item at `gate` whose worktree lacks the spec artifacts, **When**
   `wuwei dispatch next <item>` runs, **Then** it refuses, naming the next spec step, and
   offers no gate.
2. **Given** the same item once the artifacts exist, **When** it runs again, **Then** it
   returns the gates.
3. **Given** a light-tier item (in `spec.skip_tiers`) whose computed tier is light, **When** it
   runs, **Then** it returns the gates without a spec.
4. **Given** a builder at `implement` with a spec gap, **When** `build check` runs, **Then** the
   `spec` check fails and the item stays out of the gates, as today.

### User Story 2 - Source edits are never refused for a missing spec (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an item worktree with no spec, **When** a seat writes a source file, **Then**
   PreToolUse refuses nothing and logs nothing about spec mode.
2. **Given** the spec artifacts appear, **When** PostToolUse runs, **Then** `spec.step` events
   are recorded as today.

### User Story 3 - No intraday intake (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a watch sweep after the gate, **When** it runs, **Then** it does not call
   `discovery.discover` or intake, and writes no `discovery.*` event or `discovery_candidates`.
2. **Given** a builder seat stops with the queue empty, **When** SubagentStop runs, **Then** no
   `discovery.requested` is written and the watch tick runs no pending discovery.
3. **Given** the CLI, **When** `wuwei dispatch discovery sweep` runs, **Then** argparse refuses
   it.
4. **Given** `wuwei plan add <item> --goal G-1` (owner) or `--from-finding`, **When** it runs,
   **Then** it admits the item as today; a name that is neither is refused with the `--goal`
   line.

### User Story 4 - Morning discovery and ranking stay (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the lead's brief, **When** it runs `wuwei discover`, **Then** the command lists
   the morning candidates as today.
2. **Given** `plan propose lead.json` with candidates in any order, **When** it runs, **Then**
   the queue in `proposal.json` and `plan.md` is ordered by the configured framework (ties by
   goal priority, then id), and a candidate missing a component or its evidence line is
   refused.
3. **Given** `wuwei plan template`, **When** it runs, **Then** it prints a lead JSON whose
   candidate carries the components of the configured framework.
4. **Given** the CLI, **When** `wuwei rank` runs, **Then** argparse refuses it.

### User Story 5 - `init --upgrade` removes the retired keys (Priority: P2)

1. **Given** a `[discovery]` table (`min_queue`, `autostart`), **When** `init --upgrade` runs,
   **Then** it is removed and reported.

### Edge Cases

- Yesterday's state may hold `intraday_proposals` with `tomorrow` rows. They are no longer
  carried; the lead's morning discovery finds the same work again from its sources.
- Today's state may hold `discovery_candidates`; nothing reads it after this part.
- With spec mode `advisory` (or `guards.enforce = false`), `dispatch next` warns once and
  offers the gates, as today: the owner chose that mode.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `discovery.start_decision`, `when_seat_frees` and `intake`, `dispatch.discovery`,
  the `dispatch discovery` subcommand, the seat-free request in `agent_launch.stop`, the sweep's
  discovery and intake in `watch.sweep`, `watch.pending_discovery` and its call in `tick`, the
  discovery branch of `plan add`, and the `intraday_proposals` carry in `plan propose` MUST go.
- **FR-002**: `discovery.discover`, `dedupe`, `SOURCES` and `wuwei discover` MUST stay
  unchanged in behaviour; `plan propose` keeps measuring them into the sweep.
- **FR-003**: `guards/spec.check_edit` MUST go with its `GUARDS` row and the `PreToolUse` entry
  of `MODULES['spec']`; `specmode.own` and `OWN` go if nothing else reads them. `check_record`,
  `check_stop` and `specmode.check` stay.
- **FR-004**: `dispatch.next_step` MUST keep refusing the gates to a non-light item with a spec
  gap under strict mode; `tests/test_dispatch.py` MUST cover the standard refusal, the pass
  with artifacts and the light pass.
- **FR-005**: `cli/wuwei/commands/rank.py` MUST go; `candidate_template` moves into
  `cli/wuwei/commands/plan.py`. `rank.py` (`validate`, `rank`) stays, used by `plan propose`
  and `_proposal`.
- **FR-006**: The `discovery` config table MUST leave the schema and template and join
  `workspace.RETIRED`.
- **FR-007**: The lead charter MUST say: discover at the morning plan with `wuwei discover`;
  give each component's evidence; `plan propose` orders the queue by
  `prioritisation.framework`, never a hand-ordered queue. The intraday autostart step goes. The
  builder charter MUST NOT say the hooks refuse source edits.
- **FR-008**: No module, charter, skill, design spec section, docs page or template MUST refer
  to discovery intake, intraday autostart, the PreToolUse spec guard or `wuwei rank`.

## Success Criteria *(mandatory)*

- **SC-001**: `grep -rnE "intake|intraday_proposals|discovery_candidates|start_decision|when_seat_frees|pending_discovery|dispatch discovery|discovery\.(min_queue|autostart)|check_edit|commands\.rank|wuwei rank"`
  over `cli/`, `adapters/`, `charters/`, `skills/`, `agents/`, `templates/`, `scripts/` and
  `docs/site/` returns nothing.
- **SC-002**: The three US1 cases pass in `tests/test_dispatch.py`.
- **SC-003**: `plan propose` orders a shuffled lead JSON by the framework
  (`tests/test_goals_rank.py::test_plan_proposal_orders_queue_by_score`, kept).
- **SC-004**: Every touched test file passes; no test is loosened.

## Assumptions

1. Intraday intake is (a): machinery that makes the planner and owner reason about mid-day
   candidates, and it routed every raw candidate to an `owner` proposal that nothing showed.
   The owner admits mid-day work with `plan add --goal`; seats' findings join with
   `--from-finding`. Both stay.
2. The PreToolUse spec guard is (a): it made a builder reason about spec steps before every
   edit. The process error it prevented (gates without a spec) is caught by
   `dispatch.next_step` and the build loop's `spec` check, which stay (b).
3. `check_record` and `check_stop` stay: the issue deletes only the PreToolUse guard. The
   recorder never refuses; the stop check makes the builder name its artifacts, which the gate
   briefs read.
4. `rank` the command is (a) plumbing the lead ran to preview what `plan propose` recomputes.
   Its job (ordering by the configured framework from the lead's evidence) is already in
   `plan propose` (owner confirmed); this part adds no ordering code.
5. `discovery.min_queue` and `discovery.autostart` are read only by intake, so the whole
   `[discovery]` table retires. `prioritisation.framework` stays.
6. `plan.md`'s "Discovery intake" heading is morning output; it is renamed "Discovered" so no
   text names intake.
7. Part 20 runs first on this branch: `plan add` no longer checks tickets, and
   `tracker._candidate` loses its `discovery_candidates` fallback here.
