# Feature Specification: the steward no longer starts every 50 tool calls, and never mid-round

**Feature Branch**: `624-steward-trigger`
**Created**: 2026-10-09
**Status**: Ready
**Input**: GitHub issue #624, "fix(steward): review agents no longer start every 50 tool calls:
the tool-call trigger defaults to 250, generated data and fixtures are excluded from the size
trigger, and a sweep never starts while a seat is mid-round". Owner's day, 2026-10-09: "Review
agents also kept starting every 50 tool calls." Ask: "Raise the review-agent interval, and
exclude generated data from the size limit."

## Problem (reproduced)

Reproduced read-only on `main` (e0fa1f5) in a scratch workspace with the default config,
in-process through the real trace guard (`wuwei.guards.traces.check`) and `wuwei next`:

- 250 `Write` tool calls (two in three to `data/out.json`, one in three to `src/a.py`), with a
  `steward.run` recorded after each due nudge as `wuwei next` would, produced 5 `steward.due`
  events, so 5 steward seats.
- Item `A` in phase `fix` with its builder seat running and a `steward.due` pending:
  `wuwei next` returned `wuwei steward run --trigger tool-calls`, launching a steward in the
  middle of `A`'s fix round.

Root causes, with file and line on `main`:

1. `cli/wuwei/workspace.py` line 145: `steward.every_tool_calls` defaults to `50`.
   `cli/wuwei/guards/traces.py` line 78 counts every trace line and
   `cli/wuwei/steward.py` lines 250 to 263 (`maybe_run_for_tool_calls`) mark the steward due
   at each multiple of that interval.
2. `cli/wuwei/commands/next.py` line 244 skips an item whose seat is running, and lines 271 to
   279 offer the due review or the steward launch whenever no steward seat runs; nothing reads
   whether an item is between a FIX verdict and its delta verdict.
3. `cli/wuwei/watch.py` lines 294 to 299 run `steward.run(trigger='sweep')` on the sweep timer
   alone, and `cli/wuwei/steward.py` lines 197 to 209 (`run`) check no item phase either.
4. `cli/wuwei/report.py` `build` shows no steward runs, so the owner cannot see how often the
   steward ran or tune the interval from the number.

Corrected premise: there is no steward size trigger on `main`. The steward starts on three
triggers only: the watch sweep timer (`watch.sweep_seconds`), the tool-call count and close.
No code counts changed files or lines to start a steward seat. The owner's "exclude generated
data from the size limit" is the merge size rule (`merge.max_changed_lines`), and #615 already
shipped that as `repos.merge.size_exclude` (merged in 03fa30d). This feature therefore adds no
`steward.ignore` setting (see Assumptions).

## Clarifications

### Session 2026-10-09

- Q: Which setting name: the issue's `steward.tool_calls` or the existing
  `steward.every_tool_calls`? A: Keep `steward.every_tool_calls`; only its default changes to
  250. Renaming would break every workspace config that sets it.
- Q: What does "mid-round" mean in state? A: An item in phase `fix` or `delta`: after a FIX
  verdict (pre-PR gate or post-PR review) and before the delta verdict moves it on. Those are
  the only two phases between a FIX and its delta (`state.PHASES`).
- Q: Which steward starts wait? A: `sweep` and `tool-calls`. The `close` review runs once at
  close whatever the phases, so every day still has a steward run.
- Q: What does a waiting `steward run` do? A: Writes no brief, launches nothing, records no
  `steward.run`, prints one line naming the items and exits 0. A pending `steward.due` stays
  pending, so the review starts after the round.
- Q: Does a written but unlaunched steward brief wait too? A: Yes. Launching it is a sweep
  starting, so `wuwei next` offers neither the due review nor the launch while an item is
  mid-round.
- Q: Which "two settings" does the report name? A: The two steward cadences the owner can
  tune: `steward.every_tool_calls` and `watch.sweep_seconds`.

## User Scenarios and Testing

### User Story 1 - One steward review per 250 tool calls (Priority: P1)

A study day writes generated data and fixtures through many tool calls. The steward reviews
once per 250 completed tool calls, not once per 50.

**Independent Test**: in-process `steward.maybe_run_for_tool_calls` with the default config.

**Acceptance Scenarios**:

1. **Given** the default config and 250 tool calls in a day, with generated data written and a
   steward run recorded after each due nudge, **When** each call is recorded, **Then** exactly
   one `steward.due` is appended (at 250), not five.
2. **Given** `[steward] every_tool_calls = 100`, **When** 250 calls are recorded the same way,
   **Then** two `steward.due` events are appended (100 and 200): the setting stays configurable.

### User Story 2 - No steward starts mid-round (Priority: P1)

While an item is between a FIX verdict and its delta, no steward sweep starts; it waits for the
round to end.

**Independent Test**: in-process `steward.run`, `next_command.step` and `watch.sweep` on a day
with one item in `fix` or `delta`.

**Acceptance Scenarios**:

1. **Given** an item in `fix` with its builder running and a `steward.due` pending, **When**
   `wuwei next` runs, **Then** it offers no steward row; **When** the item leaves `fix` and
   `delta`, **Then** the due row returns.
2. **Given** an item in `delta` and an unlaunched steward brief, **When** `wuwei next` runs,
   **Then** it does not offer the launch.
3. **Given** an item in `fix` or `delta`, **When** `wuwei steward run --trigger sweep` or
   `--trigger tool-calls` runs, **Then** it prints `steward: waits for <items> to finish the
   fix round`, writes no brief, records no `steward.run`, does not load the runtime adapter
   and exits 0.
4. **Given** an item in `fix`, **When** `wuwei steward run --trigger close` runs, **Then** the
   close review runs as today.
5. **Given** an item in `fix` and the steward sweep window elapsed, **When** the watch sweeps,
   **Then** it does not run the steward and does not save `steward_at`; **When** the next sweep
   finds no item mid-round, **Then** the steward runs.

### User Story 3 - The report shows steward runs per trigger (Priority: P2)

The owner reads how many steward reviews ran today and why, beside the two settings, and tunes
them from the number.

**Independent Test**: `report.build` on a day with recorded `steward.run` events.

**Acceptance Scenarios**:

1. **Given** today's events hold one `tool-calls`, two `sweep` and one `close` steward run,
   **When** the report is built, **Then** its `## Steward runs` section lists `- close: 1`,
   `- sweep: 2`, `- tool-calls: 1` and a line naming `steward.every_tool_calls` and
   `watch.sweep_seconds` with their configured values.
2. **Given** no steward run today, **When** the report is built, **Then** the section says
   `none` and still names the two settings.
3. **Given** `owner.verbosity.report = "brief"`, **Then** the section is shown too.

### Edge Cases

- An item stuck in `fix` all day holds the sweep and tool-call reviews; the close review still
  runs, and the stuck seat is already its own `wuwei next` row (`brief.stuck`).
- A `steward.due` appended while an item is mid-round stays pending and is offered after the
  round; no second due is appended for the same interval (unchanged `maybe_run_for_tool_calls`).
- A steward seat already running when an item enters `fix` is not stopped; only new starts wait.
- An item in `parked` or `escalated` is not mid-round.

## Requirements

- **FR-001**: `steward.every_tool_calls` defaults to 250 (minimum 1, configurable as today).
- **FR-002**: `state.mid_round(data)` returns the sorted names of items in phase `fix` or
  `delta`; it is the one test for "between a FIX verdict and its delta".
- **FR-003**: `steward.run` with trigger `sweep` or `tool-calls` and a non-empty `mid_round`
  prints `steward: waits for <comma-separated items> to finish the fix round`, returns 0 and
  writes, records and launches nothing. Trigger `close` is unchanged.
- **FR-004**: `wuwei next` offers neither steward row (due review, brief launch) while
  `mid_round` is non-empty; the due nudge is not cleared.
- **FR-005**: The watch sweep neither runs the steward nor saves `steward_at` while
  `mid_round` is non-empty.
- **FR-006**: The report (brief and full) has a `## Steward runs` section: one line per trigger
  with today's `steward.run` count, sorted by trigger, or `none`; then one line naming
  `steward.every_tool_calls` and `watch.sweep_seconds` with their configured values.
- **FR-007**: Docs: `docs/site/configuration.md` shows the 250 default and the mid-round wait;
  `docs/site/reference.md` says `steward run` waits mid-round; `docs/site/daily.md` names the
  report's `## Steward runs` section.
- **FR-008**: No steward size trigger and no `steward.ignore` setting are added (corrected
  premise above).

## Success Criteria

- **SC-001**: 250 tool calls on the default config give one steward review, not five.
- **SC-002**: No steward brief is written or launched by a sweep or the tool-call trigger while
  an item is in `fix` or `delta`.
- **SC-003**: The day report shows the steward run count per trigger with the two settings.

## Assumptions

- The issue's size trigger does not exist on `main`; the owner's size-limit ask is the merge
  rule, delivered by #615 (`repos.merge.size_exclude`). Adding `steward.ignore` would configure
  a trigger nothing reads (constitution V). Excluding generated-file writes from the tool-call
  count was considered and rejected: it contradicts the issue's own acceptance ("250 tool calls
  with generated data written, then one sweep"), needs a per-call path match on the trace hook
  path, and `.gitignore` matching needs git, which the core never runs. If the owner wants
  tool calls on generated paths not to count, that is a follow-up issue.
- The issue says `steward.tool_calls`; the existing key `steward.every_tool_calls` is kept.
- The post-PR `fix` round (from `wuwei pr act`) counts as mid-round, like the pre-PR one: both
  are between a FIX and its delta.
- The wait is not recorded as an event: the report counts runs, and a waiting run prints why.
- `wuwei next` already returns an item's own rows first when its seat is not running, so the
  new condition matters when the mid-round item's seat runs.
- The design spec 5.5 says "(default 50)". It is amended only by its owner (see below).

## Design spec conflict (raised, not resolved)

Design 5.5 says the steward runs "after every `steward.every_tool_calls` tool calls counted
from `traces.jsonl` (default 50)". The pull request asks the owner for (proposed text):
"(default 250), and never starts a sweep or tool-call review while an item is in `fix` or
`delta`; the review waits for the round to end." The steward cadence is not a guard or a
decision rule, so no 9.2 invariant row is proposed.

## Deferred

- None.
