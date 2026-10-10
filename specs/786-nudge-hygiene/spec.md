# Feature Specification: nudges expire, repeats combine and the list is capped; under observe a would-be refusal goes to the shadow report, not the nudge list

**Feature Branch**: `786-nudge-hygiene`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #786 (owner, 2026-10-10, item 76): 885 open nudges by evening, up from
255 in the morning; nobody reads or clears them. Deliver: a nudge expires when its subject
changes or after `nudges.ttl_hours` (default 24); repeats on one subject combine into one with
a count; the open list is capped (`nudges.max_open`, default 20, oldest dropped with a
`nudges.dropped` count); under observe a would-be refusal is a shadow-report line, not a nudge;
`nudges` prints the open ones with age and count; the status line shows the count only when
`nudges.mode` is on (#742).

## Root cause (read on main at cb33150, reproduced read-only)

Reproduction: the owner's study workspace (posture `observe`, `autonomy.mode = autonomous`),
day 2026-10-10, read with this worktree's `bin/wuwei nudges --json` and `--all --json` from the
workspace root (nothing written). `nudges` (mode `off`, #742) shows 1 row, a page.
`nudges --all` shows 885 rows: 884 nudges and 1 page. By source: `watch: read-failed` 554,
`merge.unmeasured` 198, `draft.created` 63, `retro.gap` 40, `decision.rejected` 9,
`spec.warned` 7, `tracker.call` 7, `negotiation.loop` 2, one each of `config.newer_template`,
`calibration.drift`, `steward.due`, `watch: sweep:visibility`. The 554 `watch: read-failed`
rows are 9 subjects (one per PR, 65 to 67 repeats each, same redacted reason); the 198
`merge.unmeasured` rows are 3 PRs, 66 repeats each; the 40 `retro.gap` rows are one subject.

1. `status.scan` keys every event that has no dedicated key by its line number
   (`cli/wuwei/commands/status.py:164`, `key = (kind, number)`), so every repeat is a new open
   row for the rest of the day. The same key makes the existing clearing rule dead for these
   kinds: a later event of the same kind classified `silent` pops `(kind, its own number)`
   (`status.py:165-166`), never the earlier row (a `tracker.call` that later succeeds for the
   same item leaves its failure open).
2. Nothing ages a row out or bounds the list: rows live until midnight (the day directory
   rolls over; `status.py:92` drops other days' events), and `scan` returns every row
   (`status.py:252`).
3. `wuwei nudges` (`cli/wuwei/commands/nudges.py:55-60`) merges identical text with a count
   but prints no age, and its JSON is one row per event.

Observe and would-be refusals: the same day holds 1173 `guard.would_refuse` events, all with
`posture: observe`, and none is a nudge. `signal.classify` returns `silent` for
`guard.would_refuse` and `traces.unmatched` unless the payload's posture is `guarded` or
`strict` (`cli/wuwei/signal.py:48-49`), and `report.shadow_lines`
(`cli/wuwei/report.py:30`) groups them into `bin/wuwei shadow report`. So that part of the
issue already holds on main; this feature pins it with an acceptance test and changes no code
for it. The 885 come from repeats, not from refusals.

The status line half also holds on main: `status._groups` drops the `nudges N` token when
`nudges_mode` is `off` (`status.py:441-442`, #742), pinned by
`tests/test_nudges_mode.py::test_status_line_and_json_follow_the_mode`.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: What is a nudge's subject? A: For an event without a dedicated key in `scan`, the
  payload's `pr`, else its `item`, else its `reason`, else the event kind; as text. Rows key on
  `(kind, subject)`. Kinds that already have a dedicated key (`pr.action`,
  `merge.policy_blocked`, `pr.changed` by PR; `decision.one_way`, `draft.created`,
  `remote.refused` by id; `guard.would_refuse` by guard; `watch: sweep`) keep it. Page-tier
  rows keep one row per event: pages are outside this issue and stay as loud as today.
- Q: What does "combine with a count" mean? A: The row carries `count`, the number of events
  folded into it, and `ts`, the timestamp of the newest one; its reason is the newest event's.
  `nudges --json` rows gain these two fields; rows derived from state (pending decisions,
  health, escalations, the shadow-days nudge) have neither.
- Q: When does a nudge expire because its subject changed? A: When a later event on the same
  subject clears it: the same kind classified `silent` (a `tracker.call` that succeeds for the
  item, a `shepherd.finished` with exit 0, a `budget.usage` back under 80 percent), effective
  now because the key is the subject, plus every clearing rule `scan` already has (a draft sent
  or dropped, a decision decided, a merge policy nudge when its PR merges or closes,
  `pr.changed` after `session: wake-seen`). No new clearing rule.
- Q: What does the TTL measure? A: Time since the row's newest event (`ts`): a cause that keeps
  repeating is still live; one quiet for `nudges.ttl_hours` is gone. Rows without `ts` (state
  derived) never expire by age; they clear when their state does.
- Q: Where are "recorded as expired" and "a `nudges.dropped` count"? A: In one summary row
  that `scan` appends when anything expired or was dropped: tier `nudge`, source
  `nudges.dropped`, lane `Work`, integer fields `expired` and `dropped`, reason
  `<e> expired after nudges.ttl_hours = <h>, <d> dropped over nudges.max_open = <n>`. `scan`
  is read-only (status line, board, doctor), so it writes no event; the row is the record on
  every surface that reads `scan`.
- Q: How does the cap count? A: Over nudge-tier rows after expiry, the summary row included,
  so the open nudge list never exceeds `nudges.max_open`. When anything expired or the list is
  over the cap, `scan` keeps the newest `max_open - 1` nudge rows by `ts` (rows without `ts`
  count as newest) plus the summary row. Pages are never dropped or counted.
- Q: Where does this apply? A: In `status.scan`, the single source of `attention`; every
  surface (status line count, `status --json`, `nudges` and `nudges --all`, board, doctor,
  session start) reads the same tidied rows. `surfaced` (#742) filters them by mode afterwards,
  unchanged.
- Q: A day with no `config.toml`? A: The schema defaults (24 hours, 20 rows) apply.
- Q: What does `wuwei nudges` print? A: One line per cause as today, with the summed count and
  the age of the newest event: `nudge: <text> (<n> times, last <age> ago). Run: <command>`;
  `<age>` is whole minutes under an hour (`7 min`), whole hours otherwise (`3 h`). A row without
  `ts` prints as today. The `nudges.dropped` row prints its reason with no command.
- Q: Observe? A: No code change: see Root cause. The acceptance test pins it.

## User Scenarios and Testing

### User Story 1 - Repeats are one nudge with a count (Priority: P1)

**Acceptance Scenarios**:

1. **Given** 50 `watch: read-failed` events on one PR (same kind, same `pr`), **When**
   `status.attention` runs, **Then** one open nudge with `count` 50 and `ts` the newest
   event's; `wuwei nudges --all` prints one line with `(50 times, last <age> ago)`.
2. **Given** the same 50 events on two PRs (25 each), **Then** two rows, 25 each.
3. **Given** a failing `tracker.call` for item A, then a `tracker.call` with exit 0 for item A,
   **Then** no `tracker.call` row for A (the subject changed); a failure for item B stays open.
4. **Given** two `mcp.checked` events with exit 2, **Then** one row with count 2, and
   `nudges` prints `(2 times)`.

### User Story 2 - Old nudges expire and the list is capped (Priority: P1)

**Acceptance Scenarios**:

1. **Given** `nudges.ttl_hours = 1` and a nudge whose newest event is two hours before now,
   **Then** it is gone from `attention` and the `nudges.dropped` row records `expired` 1 and
   `dropped` 0.
2. **Given** the same nudge with a repeat ten minutes before now, **Then** it is open.
3. **Given** `nudges.max_open = 5` and 8 nudges on distinct subjects with increasing `ts` plus
   one page, **Then** `attention` holds the 4 newest nudges, the `nudges.dropped` row with
   `dropped` 4, and the page; the status line (mode `all`) shows `nudges 5` and `pages 1`.
4. **Given** 20 or fewer nudges and nothing expired, **Then** no `nudges.dropped` row.
5. **Given** `nudges.ttl_hours = 0` or `nudges.max_open = 0`, **Then** config load refuses it
   as below its minimum of 1.

### User Story 3 - Under observe a would-be refusal is a shadow line, not a nudge (Priority: P2)

**Acceptance Scenarios**:

1. **Given** `security.posture = "observe"`, `nudges.mode = "all"` and one
   `guard.would_refuse` event with posture `observe`, **When** `wuwei nudges --all --json` and
   `bin/wuwei shadow report` run, **Then** no row has source `guard.would_refuse`, and the
   report has exactly one guard line (`- <guard>: 1 (...)`).

### Edge Cases

- An event without `ts`, or a malformed or unreadable line, still folds into its subject's row;
  a row whose newest event has no `ts` never expires by age.
- A payload whose `pr`, `item` or `reason` is not a string (a list, a dict) keys by its text, so
  `scan` cannot fail on an unhashable key.
- A page and a nudge of the same kind on the same subject stay two rows (pages keep one row
  per event).
- Doctor's trace gap and untraced subagent counts and `status`'s `trace_gaps` add up the rows'
  `count`, so the numbers they print do not fall when repeats combine.

## Requirements

- **FR-001**: `status.scan` keys a non-page event without a dedicated key on
  `(kind, str(subject))`, subject as in Clarifications; page-tier events keep
  `(kind, number)`. A `silent` event pops the same key, so it clears its subject's row.
- **FR-002**: Each event-derived row carries `count` (events folded into it) and `ts` (the
  newest event's timestamp, or `None`); the reason is the newest event's.
- **FR-003**: `workspace.SCHEMA['nudges']` gains `ttl_hours` (int, default 24, minimum 1) and
  `max_open` (int, default 20, minimum 1).
- **FR-004**: At the end of `scan`, nudge rows whose `ts` is more than `ttl_hours` before the
  scan's `now` are removed; if any were removed or the remaining nudge rows exceed
  `max_open`, the newest `max_open - 1` stay and one `nudges.dropped` row with `expired` and
  `dropped` is appended. Pages are untouched.
- **FR-005**: `wuwei nudges` sums `count` per printed cause and prints the age of the newest
  event; `nudges.line(row, count)` keeps working for rows without `ts`.
- **FR-006**: Counts that read `scan` rows by source (doctor's traces and untraced subagents,
  `status.snapshot`'s `trace_gaps`) sum `count`.
- **FR-007**: Under `observe`, `guard.would_refuse` stays `silent` and appears in
  `shadow report` (no change; pinned by a test).
- **FR-008**: The template's commented `[nudges]` block and `docs/site/configuration.md` name
  `nudges.ttl_hours` and `nudges.max_open`; the nudges paragraph says repeats combine with a
  count and an age, old ones expire and the list is capped with a `nudges.dropped` row.

## Success Criteria

- **SC-001**: On the reproduction day's events, `nudges --all` lists at most 20 nudge rows
  (19 newest causes plus the `nudges.dropped` row) instead of 884, with no subject listed twice.
- **SC-002**: The three acceptance scenarios from the issue pass as written.
- **SC-003**: The full suite passes; `status --line` reads no new file (the config it already
  loads carries the limits), so its latency budget holds.

## Assumptions

- No `_pipeline/notes/786-full.md` exists; the issue, the code on main and the read-only
  reproduction above are the inputs.
- "Subject" is the PR, else the item, else the reason text (Clarifications). Two events of one
  kind on one PR with different reasons are one cause; the row shows the newest reason.
- "Recorded as expired" is the `expired` field on the `nudges.dropped` summary row, not an
  event: `scan` runs on every status line refresh and must stay read-only.
- The default TTL of 24 hours rarely fires because `scan` reads only today's events; it matters
  when the owner sets a shorter TTL. Kept as the issue specifies.
- "Age" is time since the newest event of the cause (the same clock the TTL uses).
- The observe requirement already holds on main for every would-be refusal the guards record
  (`guard.would_refuse`); this feature adds the acceptance test only. `traces.slow` (a slow
  trace hook, refused only under strict, #659) stays a nudge in every posture below strict; it
  now combines into one counted row.
- The status line requirement (count only when `nudges.mode` is on) is #742's, already on
  main and tested; no change.
- `heartbeat.py` and `commands/shadow.py`, named in the issue's references, need no change.
- Not a guard or decision rule, so no design spec 9.2 invariant row is owed.
- Existing tests that count repeated rows by multiplicity (`tests/test_signal_status.py`
  `test_scan_reads_the_day_with_universal_newlines`, `test_scan_skip_matches_decoding_every_line`,
  `test_issue_acceptance_nudges_print_lines`) switch to summing `count`; what they check (line
  decoding, skipped runs, printed counts) is unchanged.

## Deferred

- `watch` keeps reading PRs after they merge and records a `watch: read-failed` for each failed
  read (the reproduction day: every read-failed PR but one had merged a minute before its last
  failure). That is the rate-limit and polling problem of owner items 65 and 73, its own issue.
- Routing `traces.slow` under observe to the shadow report needs the posture on its payload and
  a shadow-report line for it; a follow-up if the owner wants it.
