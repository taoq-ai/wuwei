# Feature Specification: Process depth follows the tier

**Feature Branch**: `567-process-depth`
**Created**: 2026-10-08
**Status**: Draft
**Input**: GitHub issue #567: process depth follows the tier: a light item has no class sweep,
no mutation step and no delta round, a standard item sweeps only the classes its diff touches
and mutates only guard code, Routine records read as one line, and the report measures cycle
time per tier.

Owner, 2026-10-08: "We are moving too slowly. [...] Must be adaptive: less complex items don't
require all gates. I want WUWEI autonomous and agile, not only bureaucracy added."

## Root cause

The tier exists (#280) but only decides the gate count. Every other step of the process runs
at full depth whatever the tier, because nothing past the gate set reads it:

- `cli/wuwei/dispatch.py:99-100` (`tier`): the computed record sets `roles` and nothing else;
  no brief, prompt, lint or charter reads `gates.tier` (only `docs.py` does, for the docs
  obligation).
- `cli/wuwei/brief.py:14-60` (`launch_prompt`, `mandate`): the mandate block is the same for
  every item; `brief.py:321-404` (`write`) writes no line that tells a seat how deep to go, so
  the seat applies its whole charter.
- `charters/_common.md:18` (Evidence and gates 2): gate step zero (whole-tree detached copy,
  mutation sweep, KILLED and SURVIVED proof, stop line) is unconditional;
  `charters/_common.md:21` (budget) and `:30` (retro note on every hand-off) likewise.
- `charters/builder.md:20` (item 11): the builder sweeps every class with a command per row,
  whatever the diff touches. There is no CLI command that lists the classes a diff touches.
- `cli/wuwei/verdict.py:87-140` (`lint`): every arch, quality and security verdict must carry
  a probe or mutation row (`:107`), a class-sweep line (`:108`), the quality `Simplicity:` and
  `Design:` rows (`:133`) and the three retro lines (`:113`); `lint_file` (`:166`) has no item
  and no tier.
- `cli/wuwei/guards/verdict.py:100-130` (`check_retro`): SubagentStop records a retro gap for
  any seat whose last message lacks the three lines, whatever the tier.
- `cli/wuwei/dispatch.py:402-404` (`_delta_feedback`): after a fix round every FIX gate gets the
  same full delta review.
- `cli/wuwei/commands/decision.py:138-140` (`show`): a Routine record taken under mandate
  prints the multi-line owner view like any open decision.
- `cli/wuwei/metrics.py:576` (`collect`): no cycle time per item or per tier; `lead_time`
  (`:334`) starts at the tracker claim and is not split by tier, so nobody can see whether
  lighter process makes light items faster.

## User Scenarios and Testing

### User Story 1: A light item runs a light process (Priority: P1)

A one-line fix in a repository whose floor is light goes through the day with the builder
skipping the class sweep, one quality sentinel writing a three-row verdict, and a FIX re-read
by the same sentinel without the delta review procedure.

**Independent Test**: the hook-routed fixture day (`tests/test_path_day.py`) with the repo
floor `light` and lead tier `light`, driven only by `wuwei next --json`.

**Acceptance Scenarios**:

1. **Given** a light item on the fixture day, **When** the builder brief is written, **Then**
   its header has `Depth: light` and names what the seat skips (the class sweep, and the retro
   note when every line would be `none`), and the builder launch prompt's mandate block carries
   the same `Depth:` line.
2. **Given** that item, **When** the builder runs `wuwei sweep classes <worktree>`, **Then** it
   prints `Depth: light; no class sweep` and lists no class.
3. **Given** the light quality gate, **When** the sentinel writes `Verdict: PASS`, `Head:
   <sha>` and `Findings: none` (three rows, no probe row, no class line, no `Simplicity:` or
   `Design:` row, no retro lines), **Then** the PostToolUse lint, the SubagentStop checks,
   `dispatch receive` and the PR raise gate check all accept it.
4. **Given** a light quality FIX, **When** the fix round is done, **Then** `wuwei next`
   returns a `continue` of the same sentinel seat whose feedback asks it to re-read the diff
   and rewrite the `Verdict:` and `Head:` lines (marking closed findings `blocks: no`), and
   does not say `Delta review`.
5. **Given** that day, **When** the item merges, **Then** `wuwei metrics` has
   `cycle_minutes["A"]` and `cycle_by_tier["light"]`, and the light median is under 60.

### User Story 2: A standard item mutates only guard code (Priority: P1)

A standard item gets the three gates as today, but gate step zero (the detached copy and the
mutation sweep) runs only when the diff touches guard code or a trust path.

**Independent Test**: `wuwei brief quality <item> <name> --gate` on a fixture worktree, one diff
touching `cli/wuwei/guards/x.py`, one touching only `cli/wuwei/report.py`.

**Acceptance Scenarios**:

1. **Given** a standard item whose diff touches `cli/wuwei/guards/`, **When** a gate brief is
   written, **Then** it has `Depth: standard; step zero: run (cli/wuwei/guards/x.py matches
   guards/*)`.
2. **Given** a standard item whose diff touches no guard code or trust path, **When** a gate
   brief is written, **Then** it has `Depth: standard; step zero: skip (no guard code or trust
   path in the diff); write Mutation: skipped (depth standard)`, and a verdict with that row
   passes the lint.
3. **Given** a standard item, **When** the builder runs `wuwei sweep classes <worktree>`,
   **Then** it prints `Depth: standard` and one line per class whose file patterns the diff
   touches (for example `AUTH: cli/wuwei/guards/x.py`), and no other class.
4. **Given** a full item, **Then** the gate brief says `step zero: run` and `sweep classes`
   lists every class.
5. **Given** a standard item, **Then** the verdict lint, the retro check and the delta round
   behave exactly as today.

### User Story 3: Routine records read as one line (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a Routine record taken under mandate (`decision_outcomes[D-n].decided_by ==
   "mandate"` and `cisr == "Routine"`), **When** `wuwei decision show D-n` runs at the brief or
   standard verbosity, **Then** it prints exactly one line: id, class, question, option taken
   and the `--full` command.
2. **Given** the same record, **When** `wuwei decision show D-n --full` runs, **Then** it prints
   the record text as today.
3. **Given** the same record, **Then** the two-hourly digest shows one line for it (as today)
   and the report's "Taken under mandate" section shows one line for it (as today); the
   record file is unchanged.
4. **Given** a Consequential record taken under mandate, or any record not taken under
   mandate, **Then** `decision show` prints as today.

### User Story 4: The report measures cycle time per tier (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a day where an item was approved (`plan.approved`) or admitted (`plan.added`) and
   later merged (a `phase_changes` value `merged`), **When** `wuwei metrics` runs, **Then**
   `cycle_minutes` maps the item to the minutes between the two, `gate_minutes` maps it to the
   minutes from its first sentinel `seat launched` to its last `gate.received`, and
   `cycle_by_tier` maps its tier to `{"median_minutes": m, "items": n, "target": t}` (`t` is 60
   for light, 180 for standard, absent for full).
2. **Given** an item approved on one day and merged on a later day, **Then** its cycle spans
   both days.
3. **Given** no merged item, **Then** the three keys are `unmeasured`, never zero.
4. **Given** the report at any verbosity, **Then** a `## Cycle time` section lists one line per
   tier (median, items, target) and one line per merged item (tier, cycle minutes, gate
   minutes).
5. **Given** merges in this ISO week and the previous one, **When** the retro compiles,
   **Then** it names the tier whose median moved most week over week, or says unmeasured when
   no tier merged in both weeks.

### Edge Cases

- An item with no recorded gate tier yet (builder stage): depth is the tier the builder brief
  computed and recorded; with no brief, `standard`. A gate brief, verdict or re-read before
  `dispatch next` has tiered the item is `standard`: a builder prediction never lightens a
  gate.
- The diff grows past the light ceiling during the build: the gate tier is recomputed at
  dispatch as today (`dispatch.tier`), and the gate seats follow the recorded gate tier;
  `sweep classes` computes live, so the builder's sweep follows the real diff.
- A verdict file whose seat or item cannot be resolved from state: the lint applies today's
  full shape (never lighter by accident).
- A light seat that writes a partial retro note: the existing per-key checks apply (the note
  is optional only as a whole).
- A light item with an `agent_surface` flag cannot exist: flags already raise the tier to
  standard (`dispatch.py:52-54`).
- `sweep classes` on a path that is no item's worktree, or with an unreadable diff: exit 2
  with the reason.

## Requirements

### Functional Requirements

- **FR-001** One depth per item: `dispatch.depth(row)` returns the recorded gate tier, else
  the builder brief's recorded `depth`, else `standard`; `dispatch.depth(row, gate=True)`
  returns the recorded gate tier, else `standard`, so only the tier `dispatch next` recorded
  from the real diff can lighten a gate. Every reader below uses it; there is no second tier
  computation.
- **FR-002** `brief.write` for a builder computes the tier with the existing `dispatch.tier`
  on the briefed worktree, writes a `Depth:` header line naming what the seat skips and the
  `wuwei sweep classes <worktree>` command, and records `items.<item>.depth` in the same state
  write (producer `wuwei brief`).
- **FR-003** `brief.write` for a gate seat writes a `Depth:` header line from
  `dispatch.depth(row, gate=True)`: at light, the skips and the three-row verdict shape; at standard,
  `step zero: run (<path> matches <pattern>)` or `step zero: skip (...)` with the exact
  `Mutation: skipped (depth standard)` row; at full, `step zero: run`. Step zero runs at
  standard when a changed path matches the repository's `gates.trust_paths` or the guard-code
  patterns `guards/*`, `grants*`, `outward*`, `hooks/*`.
- **FR-004** `brief.launch_prompt` appends the brief's `Depth:` line to the mandate block, so
  every launch and continue prompt names what the seat skips.
- **FR-005** `wuwei sweep classes <worktree>` (read-only) resolves the item from state by its
  worktree, computes the tier with `dispatch.tier`, and prints `Depth: <tier>` then: nothing
  at light (`Depth: light; no class sweep`), one `CLASS: <paths>` line per class whose file
  patterns the diff touches at standard, every class at full. Exit 0 when measured, 2 with
  the reason when it cannot read the item or the diff.
- **FR-006** `verdict.lint` takes `light`; at light it does not require the probe or mutation
  row, the class-sweep line, the quality `Simplicity:`/`Design:` rows, or the retro note when
  all three retro keys are absent. Every other check is unchanged.
- **FR-007** `verdict.light(path, data)` resolves a gate file's seat and item from the day
  state and returns whether `dispatch.depth(row, gate=True)` is `light`; `False` when anything cannot be
  resolved. `lint_file` and `obligations._gate_recorded` pass it; `guards/pr.py`
  (`_recorded_gates`) passes `dispatch.depth(row, gate=True)` of the candidate item it
  already holds.
- **FR-008** `check_retro` (SubagentStop) treats a seat of a light item (`gate=True` for a
  sentinel, the builder's recorded depth for a builder) with no retro lines
  as a note of `none` on every line (`retro.captured`, fields all `none`); a partial note is
  checked as today.
- **FR-009** `dispatch._seats` gives a light item's post-fix continue the re-read feedback
  (rewrite `Verdict:` and `Head:`, mark closed findings `blocks: no`); the state round key
  stays `delta` so receive and the PR gate check are unchanged.
- **FR-010** `decision show D-n` prints one line for a Routine record taken under mandate at
  the brief or standard level; `--full` (or the `full` level) prints the record.
- **FR-011** `metrics.collect` adds `cycle_minutes`, `gate_minutes` and `cycle_by_tier` from
  existing events across day directories; the report adds `## Cycle time`; the retro names
  the tier whose median moved most week over week.
- **FR-012** Charters: `_common.md` and `builder.md` point to the design 5.3 depth table once
  and follow the brief's `Depth:` line; step zero applies when the brief says run; the
  sentinel charters say when step zero applies. Neither file grows in line count. Generated
  agents are rebuilt with `bin/wuwei agents build`.
- **FR-013** Docs: design 5.3 gains the amendment with the depth table; `concepts.md` (tier
  gains the depth columns), `daily.md` (one paragraph), `reference.md` (`sweep classes`,
  `decision show` one line, the metrics keys).
- **FR-014** No new refusal under any posture (#530): every change makes a check lighter or
  adds a read-only command; under strict the lighter verdict shape applies too, because the
  tier is computed by the CLI, never claimed by the seat.

### Key Entities

- **Depth**: the tier value (`light|standard|full`) that sets process depth; stored as
  `items.<item>.gates.tier` (dispatch, existing) or `items.<item>.depth` (builder brief, new).
- **Class pattern table**: a constant in `dispatch.py` mapping each class to path globs, matched
  with the existing `merge.matched` (the same matcher as `gates.trust_paths`).
- **Cycle row**: item, tier, start, merged at, gate minutes; derived, never stored.

## Success Criteria

- **SC-001** The light fixture day closes through `wuwei next` with the builder reporting no
  class line, a three-row quality verdict, and `cycle_by_tier.light.median_minutes < 60`.
- **SC-002** The standard fixture day still closes, with `cycle_by_tier.standard.median_minutes
  < 180`.
- **SC-003** `charters/_common.md` plus `charters/builder.md` have no more lines than before.
- **SC-004** The full suite passes; no existing verdict, retro or delta test changes its
  expectation for a standard item.

## Assumptions

- The "eleven-row" sweep in the issue is the builder charter's class list; the CLI table
  covers the ten classes `builder.md` lists (AUTH, VAL, DOC, TEST, INF, RET, ERR, STATE, CON,
  BUD). Full lists all of them. Overturn: the owner names an eleventh class.
- `sweep classes` takes the worktree as the issue says and resolves the item from state by its
  recorded worktree, because the tier needs the item's flags, track and lead tier.
- Mutation at standard runs on the union of the issue's guard-code patterns (`guards/*`,
  `grants*`, `outward*`, `hooks/*`) and the repository's configured `gates.trust_paths`, so the
  rule also works in repositories that are not WUWEI. Overturn: the owner wants only the fixed
  patterns.
- "Without a delta round" for light means without the delta review procedure: the same
  sentinel seat is continued with re-read feedback, and the state keeps the `delta` round key
  so `receive`, the PR gate check and the budget stay one code path. Overturn: a reviewer
  shows a light item paying a second full review.
- The one-line decision view applies to every Routine record taken under mandate, not only
  records of light items, because decision records are not tied to an item tier. The digest
  and report lines are already one line each (#544, #530) and stay as they are.
- "Retro note only when not `none` on every line" makes the note optional as a whole at
  light; an absent note is recorded as `none` on every line so the retro compile reads it
  unchanged.
- Cycle start is the item's first `plan.approved` or `plan.added` event; `state.import` and
  carry do not restart it. Gate minutes run from the first sentinel `seat launched` to the last
  `gate.received` of the item. No new event kind.
- The targets (light 60, standard 180 minutes) are constants in `metrics.py` reported beside
  the medians; nothing refuses when a target is missed.
- The builder's predicted depth is computed at brief time, when the diff is usually empty, so
  it reflects floor, flags, track and lead tier; the gate tier recomputed at dispatch wins once
  recorded.
- The default repository floor stays `standard` (#280), so light depth needs `gates.floor =
  "light"` on the repository; under the default floor the gain comes from the standard
  column (classes by diff, mutation only on guard code). Overturn: the owner lowers the
  default floor, a one-line change in `workspace.py` outside this item.
- The standard step-zero skip is told to the sentinel with the exact `Mutation: skipped`
  row; the lint does not refuse a verdict that omits it, because #530 forbids a new refusal
  under observe and guarded.
- `tests/test_invariants.py` does not exist on this base, so no invariant row is added.

## Deferred

- Tier-aware CAP or shorter fast checks for light items: not asked here.
