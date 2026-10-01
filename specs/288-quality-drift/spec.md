# Feature Specification: quality by hour and by session age, and planned planner-session rotation

**Feature Branch**: `288-quality-drift`

**Created**: 2026-10-01

**Status**: Draft

**Input**: GitHub issue #288, "feat(metrics): quality by hour and by session age, and planned
planner-session rotation". Design spec sections 3.4 (three-state exits), 4.2.1 (Stop), 5.5
(steward), 5.6 (metrics), 6.4 (session start) and 10.6 (latency budget; the issue cites it
as 9.1). Builds on #211 (latency), #260 (session registry) and #223. Owner observation
2026-10-01: "in the midday and evening the quality deprecates".

## Evidence (read-only, scratch workspace on `main` at e4b3da0)

A scratch workspace (empty `config.toml`, `spine.md`, `index.md`, a `goals.md` with
`G-1 outcome: Ship checkout v2`, `plan.md`, state with `goals: ["G-1"]`, approved
`ITEM-1`, planner `P`, a running seat `builder-1` with brief
`.wuwei/days/<date>/briefs/builder-1.md`, and an unanswered routed decision `D-1`) was fed
`lifecycle.session_start({'cwd': <ws>, 'session_id': 'P', 'source': 'compact'})`. The
payload (974 bytes) does not contain the goal text `Ship checkout v2` and does not name
`plan.md`; `D-1` and the brief path appear only as keys buried in the raw state JSON, with
nothing saying the decision is open or the brief is current. Root causes on `main`:

1. `memory.session_payload` (`cli/wuwei/memory.py` lines 84 to 99) emits Spine, Index and
   the raw `Today state` JSON only. Goal text lives in `.wuwei/memory/goals.md`, which is
   never read; state carries only goal ids. The approved plan file is never named.
   `lifecycle.session_start` (`cli/wuwei/guards/lifecycle.py` lines 26 to 79) sends the
   same payload for every `source`, so a compacted planner gets no restated constraints.
2. `metrics.collect` (`cli/wuwei/metrics.py` line 418 onward) aggregates per day only.
   Every event carries `ts` (`state._append_event`, `cli/wuwei/state.py` line 157), but
   nothing groups quality counters by time of day or by the planner's session age.
3. `sessions.record` (`cli/wuwei/sessions.py` lines 26 to 41) stores `started`,
   `last_seen` and `last_hook` only; there is no turn or compaction count. The history
   exists: every planner turn end writes a `session.seen` event with hook `Stop`, and every
   compaction writes one with hook `SessionStart:compact` (`lifecycle._seen`, lines 16 to
   23), but nothing counts them.
4. `lifecycle.stop` (lines 92 to 106) only consumes the planner wake marker; nothing ends a
   long planner session on purpose.
5. `workspace.SCHEMA['owner']` (`cli/wuwei/workspace.py` line 41) has no time zone, so
   "hour of day" has no owner reference.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The owner sees when quality drops (Priority: P1)

The owner runs `wuwei report` at the end of a day and sees, per hour band (morning,
midday, afternoon, evening) and per planner session-age band, how many gate verdicts were
recorded, the gate FIX rate, fix rounds, verdict-lint rejections and owner interventions.
The retro compares the bands over the last seven days and names the worst one when it
stands out by the configured margin.

**Why this priority**: measuring comes before addressing; the owner's observation is
unverified until the counters are split by time and session age.

**Independent Test**: record events with timestamps across one day (gate verdicts, fix
transitions, lint rejections, planner `session.seen` Stop rows), run `metrics.collect` and
`wuwei report`, then `retro.compile`.

**Acceptance Scenarios**:

1. **Given** a recorded day with events across the day, **When** `wuwei report` runs,
   **Then** it shows a `## Quality by band` section with one table by hour band and one by
   session-age band, each row with gates, FIX rate, fix rounds, lint rejections and
   interventions, and `metrics` JSON carries the same numbers under `quality_by_band`.
2. **Given** recorded days in which the evening band's FIX rate exceeds every other
   measured band's by at least `metrics.band_margin`, **When** the retro compiles,
   **Then** it names `evening` as the worst hour band with both rates, and writes one
   planner charter proposal citing the retro as evidence.
3. **Given** no band exceeding the others by the margin, or fewer than two measured bands,
   **When** the retro compiles, **Then** it prints `Worst hour band: none` (and the same
   for session age) and writes no quality proposal.
4. **Given** `owner.timezone = "Europe/Amsterdam"` and an event at `10:30+00:00`, **When**
   bands are computed, **Then** the event counts in `midday` (12:30 local).

---

### User Story 2 - A long planner session is rotated at a clean boundary (Priority: P1)

The owner sets `sessions.rotate_after = { turns = 200 }`. At the first planner turn end
past 200 turns where no seat runs and no routed decision waits on the owner, the Stop hook
tells the planner to stop and prints the exact take-over command for a fresh session. The
rotation is an event and shows in `wuwei sessions`. The fresh session's SessionStart
payload carries the goals, the plan, open decisions and the current briefs.

**Why this priority**: it is the remedy the product can apply without the transcript,
because day state lives in `.wuwei/`.

**Independent Test**: seed a planner registry row at 199 turns with a running seat, run
the Stop hook twice (seat running, then seat stopped), then SessionStart for a new
session id.

**Acceptance Scenarios**:

1. **Given** `rotate_after = { turns = 200 }`, a planner at 199 turns and a running seat,
   **When** the planner's Stop hook runs, **Then** it exits clean with no rotation (turn
   200 is not a clean boundary).
2. **Given** the same planner after the seat stopped, **When** its next Stop hook runs,
   **Then** the hook blocks with a reason that names the trigger and contains
   `wuwei plan session "$WUWEI_SESSION_ID" --take-over`, one `session.rotated` event is
   appended, and the registry row carries `rotated`.
3. **Given** a rotated planner row, **When** later Stop hooks of that session run, **Then**
   none repeats the instruction.
4. **Given** the rotation, **When** a new session starts and its SessionStart payload is
   built, **Then** the payload text contains the goal text from `goals.md`, the plan path
   with the approved items, the open decision ids and the running seats' brief paths.
5. **Given** `rotate_after = { compactions = 1 }` or `{ clock = "13:00" }`, **When** the
   planner has seen one compaction, or the owner-zone clock passes 13:00 for a session
   started before it, **Then** the same rotation happens at the next clean boundary.
6. **Given** no `rotate_after` (the default), **When** Stop runs, **Then** behaviour is
   unchanged.

---

### User Story 3 - A compacted planner is re-anchored (Priority: P1)

After a compaction Claude Code restarts the context with a summary and fires SessionStart
with source `compact`. The payload now opens with an `Active constraints` block, so the
planner does not continue from the summary alone.

**Why this priority**: compaction is the other way a long session degrades, and it
happens without the owner choosing it.

**Independent Test**: pipe a SessionStart payload with `source: compact` through the hook
after a PreCompact, and assert on the `additionalContext` text.

**Acceptance Scenarios**:

1. **Given** today's state with goals, an approved plan, an unanswered routed decision and
   a running seat, **When** PreCompact then SessionStart (`source: compact`) run, **Then**
   `additionalContext` starts with `Active constraints:` and contains the goal outcome
   text, `plan.md`, the decision id under `Open decisions` and the brief path under
   `Current briefs`.
2. **Given** `goals.md` missing or unparseable, **When** SessionStart runs, **Then** the
   block says `Goals: unmeasured: <reason>` and the rest of the payload is still emitted.

---

### User Story 4 - Hooks stay within budget (Priority: P2)

**Why this priority**: the hook path carries the owner's 10.6 latency requirement.

**Acceptance Scenarios**:

1. **Given** the seeded workspace latency fixture with a `goals.md` and
   `rotate_after = { turns = 1 }`, **When** `test_workspace_hook_latency` runs for Stop and
   SessionStart with `WUWEI_BENCH=1`, **Then** both stay within the asserted budget.

### Edge Cases

- Outside a WUWEI workspace: every new hook path returns 0 with no write (existing scope
  helpers).
- Stop with `stop_hook_active` true: unchanged early return, so neither the turn count nor
  rotation advances.
- A pending planner wake wins: when `watch.wake` returns a message, the turn is not a clean
  boundary and rotation waits for a later turn.
- A rotation error (bad `clock` text, unknown time zone, lock timeout): Stop returns 0 with
  `planner wake unmeasured: <reason>`, as today, because a Stop that blocks on its own error
  traps the session.
- Day rollover: the registry is day state, so turn and compaction counts restart each day
  and a session rotated yesterday may be asked again today.
- Events with no registered planner yet count in session-age band `no planner`.
- Transcripts absent: `interventions` is `unmeasured` in every band; other counters are
  unaffected.
- No `events.jsonl`: `quality_by_band` is `unmeasured`, never zeros.
- A seat running as the owner can forge `session.seen` rows; that skews a measurement only
  and is not a trust anchor (design 9.1). `session.rotated` is still producer-only.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The session registry MUST count, per session row, `turns` (each Stop seen
  without `stop_hook_active`) and `compactions` (each `SessionStart:compact` seen), with
  one counting rule shared by the registry write and the metrics replay of `session.seen`
  events.
- **FR-002**: `wuwei sessions` rows MUST show `turns`, `compactions` (0 when absent) and
  `rotated` when set.
- **FR-003**: `metrics.collect` MUST return `quality_by_band` with `hour` and
  `session_age` tables; each band carries `gates`, `fix_verdicts`, `fix_rate`
  (`unmeasured` with no gates), `fix_rounds`, `lint_rejections` (deduplicated per file
  version as today) and `interventions` (owner human turns from transcripts, `unmeasured`
  when none are readable). Hour bands are fixed: morning 05:00 to 10:59, midday 11:00 to
  13:59, afternoon 14:00 to 17:59, evening 18:00 to 04:59, in the owner time zone.
  Session-age bands are fixed: `0-49 turns`, `50-199 turns`, `200+ turns`, `compacted`
  (any compaction seen), `no planner`, taken from the registered planner at each event's
  time.
- **FR-004**: Transcripts MUST be read once per `collect` (shared by `owner_intervention`
  and the bands).
- **FR-005**: `wuwei report` MUST show `## Quality by band` with both tables.
- **FR-006**: `wuwei retro` MUST show both tables over the last seven day directories and a
  `Worst hour band:` and `Worst session age band:` line; a band is named only when at least
  two bands have gates and its FIX rate exceeds every other measured band's by at least
  `metrics.band_margin`. A named band MUST produce one proposal
  `proposals/quality-<dimension>-<band>.json` targeting `.wuwei/charters/planner.md`,
  unless one with that name exists in any of those seven days.
- **FR-007**: The Stop hook for the registered planner MUST, when `sessions.rotate_after`
  is due and the turn is a clean boundary (no wake message, no seat with status `running`,
  no routed decision without an owner answer), block once with the take-over instruction,
  set `rotated` on the row and append `session.rotated` with session id, reason, turns and
  compactions, in one state write.
- **FR-008**: The SessionStart payload MUST open with an `Active constraints:` block:
  goals (id and outcome, target, date from `goals.md` for the ids in state), plan (path and
  approved items, or `not approved`), open decisions (routed and unanswered) and current
  briefs (item, seat and brief path of running seats); `none` when empty. The block counts
  in the printed payload size.
- **FR-009**: `session.rotated` MUST be reserved in `EVENT_PRODUCERS` (producer
  `wuwei hook Stop`) and silent in `signal.SILENT`.
- **FR-010**: New config keys: `owner.timezone` (string, default empty: the machine's
  local zone), `sessions.rotate_after` with `turns` and `compactions` (integers, minimum 0,
  default 0 = off) and `clock` (string `HH:MM`, default empty = off), and
  `metrics.band_margin` (float, default 0.2). Template and configuration page list them.
- **FR-011**: `docs/site/daily.md` MUST gain a short "Long sessions" section: what is
  measured, what rotation does, what the owner can set.

### Key Entities

- **Session row** (`state.sessions[<id>]`): adds `turns`, `compactions`, `rotated`.
- **Band table** (`quality_by_band.hour|session_age[<band>]`): the six counters above.
- **Quality proposal** (`proposals/quality-<dimension>-<band>.json`): the existing retro
  proposal shape (`target`, `action: add`, `text`, `reason`, `evidence`).

## Success Criteria *(mandatory)*

- **SC-001**: The four acceptance lines of issue #288 pass as tests: report bands and the
  retro's worst band; rotation at the first clean boundary past 200 turns with an event and
  a SessionStart payload carrying goals, plan, open decisions and brief; the post-compaction
  payload text; Stop and SessionStart latency with `WUWEI_BENCH=1`.
- **SC-002**: The full suite passes.

## Assumptions

- "Interventions" per band are the owner's human turns from the transcripts the
  `owner_intervention` metric already reads (design 5.6), counted per band; the same
  timestamps, not attended minutes, because a band is too short for the stretch estimator.
- "FIX rate" is FIX verdicts over all `gate.received` verdicts in the band. The worst band
  is judged on FIX rate only, the one counter normalised by volume; the others are shown
  for context.
- "Turns since SessionStart" is the count of the session's Stop hooks in today's registry
  (day state, as #260 decided). Compactions come from the `SessionStart:compact` rows the
  registry already records, which is the same signal as PreCompact without a new write.
- The "weekly retro" is the existing daily `wuwei retro` comparing the last seven day
  directories; there is no separate weekly command. "Consistently worse" means worse over
  that seven-day aggregate by the margin.
- The retro writes the charter proposal itself through the existing retro proposal path
  (promote or reject before close, as for role proposals), rather than waiting for a
  steward seat; the steward still sees `quality_by_band` in its metrics.
- Band boundaries and age bands are fixed constants, not config (ponytail: no config for
  values that never change); only the margin, the time zone and rotation are tunable.
- Rotation fires once per session per day and is advisory: the planner is told to stop and
  the owner starts the fresh session; nothing is killed. The new session's id comes from
  `WUWEI_SESSION_ID`, which SessionStart already exports (#260).
- The `Active constraints` block is always present, not only after compaction: the
  rotated-in session (source `startup`) needs it too, and one code path is smaller.
- The heartbeat idea in the owner's message is out of scope: the watch clock and its
  health check (design 4.2, 9) already report a dead or stale process at SessionStart and
  in `status --line`.
