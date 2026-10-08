# Feature Specification: The CLI owns the path and the model walks it

**Feature Branch**: `551-path`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #551: `wuwei next` returns the exact next action for every step of the
day (command or Agent call, why, then), the plan and report skills shrink to the loop, and a
smaller model closes the fixture day with no off-path step. Builds on #358 (next), #476
(guide), #477 (availability), #212 (hook-routed day), #38 (skill evals), #530 (autonomous by
default).

## Root cause

The planner reasons its way through the day from prose because the CLI stops one step short
of an action:

- `cli/wuwei/commands/next.py:66` and `:72` return the skill pointer `/wuwei:wuwei-plan` as
  the command for the `plan` and `gate` states, and `:142` returns `/wuwei:wuwei-report` for
  `close`. The model has to open a 71-line skill and pick the step itself.
- `cli/wuwei/commands/next.py:100`, `:108` and `:115` return the delegate's command
  (`wuwei build next <item>`, `wuwei dispatch next <item>`, `wuwei dispatch next --all`)
  instead of the action that command returns, so the model must know from the skill what to
  do with a `launch`, `gates` or `set` answer.
- `cli/wuwei/commands/next.py:149-162` (`steps`) copies the first sentence of each numbered
  skill step into the SessionStart orientation (`:178`, `:181`): the session starts from a
  step list, not from one action.
- `cli/wuwei/dispatch.py:312-313` (`launch_set`) returns a `start` entry whose second command
  holds the placeholders `<name>` and `<path>`, and `cli/wuwei/dispatch.py:335` (`_seats`)
  drops a role whose brief is not logged or whose seat already stopped, so `gates` names no
  brief command, and no `receive` command once the seat has stopped: the model has to
  remember the earlier action or read the skill.
- Nothing in the day files says which command the planner was told to run, so nothing can
  measure whether it walked the path (`cli/wuwei/metrics.py:521` `collect` has no planner
  measure).

## User Scenarios and Testing

### User Story 1: Every day state returns one exact action (Priority: P1)

The planner runs `wuwei next --json` and gets one action in one shape. It never opens a skill
paragraph to learn the command, the order or the Agent call.

**Independent Test**: neutral fixture workspaces in `tmp_path`, one per day state; run
`wuwei next --json` in process.

**Acceptance Scenarios**:

1. **Given** each of these workspaces: fresh (no workspace), setup done (calibrated, no day
   state), no plan, gate open, approved with planned items, builder running, gate seats
   due, verdicts in, PR raised, all items terminal, report written, **When** `wuwei next
   --json` runs, **Then** it prints one JSON object with `state`, `action`, `why` and `then`,
   and either an exact `command` (no `<...>` placeholder except a widget's `<label>`), or a
   `prompt` with an `agent_type`, or an action that carries them (`set`, `gates`, `card`
   with `widget`); no field names a skill (`/wuwei:`, `SKILL.md`, the word skill).
2. **Given** an item in a build phase, **When** next runs, **Then** it returns the action
   `wuwei build next <item>` returns (`launch`, `continue` or `check`), with its `prompt`,
   `agent_type`, `resume` or `command` unchanged.
3. **Given** an item at the gate with no gate brief logged, **When** next runs, **Then** the
   `gates` action carries one exact brief command per role; **Given** a sentinel that has
   stopped with no verdict received, **Then** it carries that role's `receive` command.
4. **Given** approved planned items under CAP, **When** next runs, **Then** it returns the
   `set` from `wuwei dispatch next --all`, whose `start` entries hold exact commands.
5. **Given** a card already returned today (a decision, calibration, telemetry, provisional
   goals, the PR-flow and MCP checks, promote), **When** next runs again, **Then** it moves
   on to the next due step; the morning gate card is the one card that repeats until
   approved, and a decision that holds the close is asked again at close.
6. **Given** `wuwei next` without `--json`, **Then** it prints `<state>: <why> <then>` as one
   paragraph and the command on its own line.

### User Story 2: The fixture day closes driven only by `next` (Priority: P1)

A loop that only calls `wuwei next --json`, executes the returned command, simulates the
returned launch, answers the returned card with its first option, and calls next again,
takes the #212 hook-routed day from an empty plan to a closed day.

**Independent Test**: `tests/test_path_day.py` on the `fakes.day.Day` fixture.

**Acceptance Scenarios**:

1. **Given** the hook-routed fixture day with no plan, **When** the loop runs, **Then** the
   day reaches `done`, item A is merged, the retro and report exist and the day has a
   `day.closed` event.
2. **Given** the same run, **Then** `wuwei metrics` reports `off_path` 0, a positive
   `planner_turns` and `planner_asks` equal to the cards the loop answered.
3. **Given** the loop executor, **Then** it reads only fields of the returned action (plus
   the fixture's simulation of seats and the code host), so no step needs information
   outside the returned actions.

### User Story 3: The skills are the loop (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the plan and report skills after the change, **Then** each file is under 25
   lines and holds the loop and the two harness mechanics (passing a widget to
   AskUserQuestion, passing a launch or continue to Agent), and the docs and charter tests
   that pin skill content pass.
2. **Given** the planner charter, **Then** it states the rules of judgement only (what the
   planner decides, what it records, what goes to the owner) and no command sequence.
3. **Given** a planner SessionStart, **Then** the orientation prints the next action and the
   loop line, not a step list.

### User Story 4: Measure the lift (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a day with a registered planner session, **When** `wuwei metrics` runs, **Then**
   it reports `planner_turns` (the planner's Stop count), `planner_asks` (its
   AskUserQuestion calls) and `off_path` (its Bash commands that the last `next` did not
   name); each is `unmeasured` when no planner is registered or the evidence is missing.
2. **Given** the day report, **Then** its process metrics carry the three values.
3. **Given** the opt-in headless run `scripts/headless_e2e.py --start --model haiku`,
   **Then** it passes only when the fixture day closes and no planner command is off the
   path except the one park command the fixture prompt names.

### Edge Cases

- A delegate refuses (`dispatch.Refused`, `PortExit` 1): next prints the coarse row with the
  refusal as `why` and exits 1; unreadable input exits 2 as today.
- A widget command prints `[]`: next records the state as passed and returns the next due
  step in the same call.
- The build loop returns `done` or `park`, or the gate returns `fix` (the item moved): next
  asks the day again in the same call, so the planner never receives a transitional answer;
  the day's own `done` means only that the day is closed.
- A gate returns `escalate`: next returns `wuwei plan park <item> --reason "<reason>"`.
- Two `next` calls without a change return the same action (the delegates are idempotent).
- No workspace or no day state: next writes nothing.

## Requirements

### Functional Requirements

- **FR-001** `wuwei next --json` prints one action: `{state, action, item?, command?,
  prompt?, agent_type?, resume?, widget?, why, then}` plus the fields a delegate returns
  (`seats`, `entries`, `commands`, `receive`, `brief`, `worktree`, `feedback`, `notes`).
  `action` is one of `run`, `check`, `launch`, `continue`, `set`, `gates`, `card`, `wait`,
  `done`. The field `step` is replaced by `why`.
- **FR-002** Every day state in the plan's state table has a row with an exact `command` or
  `prompt` plus `agent_type`, a one-line `why` and a one-line `then`. No row names a skill.
- **FR-003** `next` delegates and never re-implements: build phases call
  `build.next_action`, gate phases `dispatch.next_step`, dispatch `dispatch.launch_set`,
  widgets come from the widget commands run in process, and lead, shepherd and steward
  launches come from `brief.seat_action`.
- **FR-004** The hook path stays as it is: `step(root)` writes nothing and imports no new
  module; delegation and the event write happen only in the `next` command.
- **FR-005** Each `wuwei next` that returns an action in a workspace with day state appends
  one `next.action` event (`state`, `action`, `item`, `named` commands, `traces` line count,
  `passed` states). The kind is reserved to `wuwei next`.
- **FR-006** Cards other than the morning gate and a close-holding decision are returned
  once per day per state and key; the path then moves on (autonomous by default, #530).
- **FR-007** Without `--json`, next prints one paragraph and the command on its own line.
- **FR-008** SessionStart orientation prints the action and the loop line; `steps()` is
  deleted.
- **FR-009** `dispatch.next_step`'s `gates` action carries `commands`: an exact gate brief
  command for each role without a logged brief, and the `receive` command for each stopped
  sentinel whose verdict is not received. `launch_set`'s `start` entry holds exact
  commands (worktree add only while `worktrees/<item>` is missing, then the builder brief
  with its name, worktree and body).
- **FR-010** `wuwei close` appends `day.closed` when it exits 0; the kind is reserved.
- **FR-011** `wuwei metrics` (and so the day report's process metrics) carries
  `planner_turns`, `planner_asks` and `off_path`.
- **FR-012** The plan and report skills are under 25 lines each; the planner charter keeps
  only rules of judgement; `agents/` and the guide block in `docs/site/agent.md` are
  regenerated; anything removed is returned by next or stated in `wuwei guide`.
- **FR-013** A fixture test drives the hook-routed day only through `next --json`.
- **FR-014** The headless runner takes `--model` (default `sonnet`) and, under `--start`,
  fails on any off-path planner command other than the fixture's named park command.
- **FR-015** No new refusal under observe or guarded (#530): next never refuses; it exits 1
  only when a delegate it ran reports a finding.

### Key Entities

- **Action**: the one object next returns (FR-001).
- **`next.action` event**: what next named; read for once-per-day cards and `off_path`.
- **Path metrics**: `planner_turns`, `planner_asks`, `off_path`.

## Success Criteria

- **SC-001** Each acceptance state in US1.1 has a test row; all pass.
- **SC-002** The fixture day closes through the loop with `off_path` 0.
- **SC-003** `wc -l` of each of the two skills is below 25 and the full suite passes.
- **SC-004** No existing test assertion changes except the shape (`step` to `why`), the
  added `commands` key on `gates`, the exact `start` commands, and the skill pins moved to
  next, the guide or the charter (the plan lists each).

## Assumptions

- Clarify is non-interactive: each open question is answered here with the recommendation.
- Rank is reached through `plan propose`, which already ranks (`cli/wuwei/plan.py:181`); the
  path has no separate `wuwei rank` step.
- The PR-flow and MCP checks run once each before the lead brief; `plan propose` already
  repeats both into the sweep (`cli/wuwei/plan.py:169-180`), and a pending MCP decision is
  asked in the same card as the morning gate (`mcp.widget`).
- The lead's JSON answer is saved by the planner with the Write tool to
  `.wuwei/days/<date>/lead.json`, as today; next says so in the lead launch's `then`. A Write
  is not a Bash command and does not count toward `off_path`.
- The shepherd raises the PR (its charter owns the raise): `raise` becomes the shepherd's
  brief command and launch. A shepherd that stops without raising returns a card naming
  `wuwei why <item>`.
- Registration covers only a day with no planner session; a second session the same day
  takes over through the refusal `plan session` already prints.
- The carry-over flag of the morning gate stays on the separate questions after `Change
  something`; carried items come back through the lead's candidates.
- `off_path` exempts `wuwei next`, `wuwei status --line` and `wuwei plan session <id>` (the loop's
  own commands; registration runs before the day has state for next to record in), ignores
  the text after `--body` (the brief text is the planner's to write), and treats a widget's
  `<label>` as any value. A command a refusal names is counted; refining that is deferred.
- The headless start prompt keeps naming no command (tests/test_headless_e2e.py pins it,
  #476), so the runner exempts the fixture's own park forms (`wuwei plan park A --reason ...`,
  `wuwei decision route D-1`, `cp park.md ...`) instead of the prompt naming one park command.
- The fixture day (tests/test_path_day.py) is a second day (an earlier day directory exists),
  so the first-day calibration card does not run; answering it would queue interview charter
  proposals that need a real `.wuwei` history to promote. The calibrate card is tested in
  tests/test_next.py.
- The traces redact a `--body` value, so path matching drops `--body` and its value on both sides.
- The model eval is the opt-in headless `--start` run with `--model haiku`: the offline skill
  eval contract (`tests/test_skill_evals.py`) pins triggering evals only, so a paid day run
  cannot live there. CI stays offline.
- The design spec is amended only by its owner (constitution, Governance); this item changes
  no design section, and the base has no `tests/test_invariants.py`.
- Codex-runtime lead or shepherd seats keep the `runtime dispatch` recovery path; the path
  launches Claude seats.

## Deferred

- Counting a command named by a refusal or held reason as on the path.
- A `docs` value step that needs no planner judgement (today's `docs` row keeps its choice).
