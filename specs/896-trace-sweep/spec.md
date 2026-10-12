# Feature Specification: the trace sweep reads only new spans, and the scanner audit's polish

**Feature Branch**: `896-trace-sweep`
**Created**: 2026-10-12
**Status**: Implemented
**Input**: GitHub issue #896: "fix(scanner): incremental trace sweep and the audit's remaining
polish", the follow-up of the live ZIRAN audit behind #862 (findings S9, P3, P6, P8, P9).

## Root cause

- S9: `scanner.trace_sweep` hands the whole day's `traces.jsonl` to `ziran analyze-traces`
  on every `dispatch receive` and `close`. ZIRAN builds one multigraph per session and
  enumerates paths and cycles over it, so its time grows steeply with a session's span
  count: one session of varied tools takes 0.37 s at 40 spans, 1.29 s at 60, 6.04 s at 80;
  40 sessions take 56 s at 2000 spans and 317 s at 3000, past the adapter's 60 s timeout.
  On a timeout `trace_sweep` prints to stderr only, so the day's trace checks are silently
  unmeasured.
- S9: `scanner._private_read` parses the whole trace file once per finding, and
  `_trace_response` reads `events.jsonl` and `state.json` once per finding.
- S6 known limit (#862 F4): the dedup is session plus chain for the whole day, because the
  sweep re-reads the whole day. A resumed seat that repeats the same chain is never seen.
- P3: `discovery.discover` turns every ZIRAN finding into a candidate, at every severity
  (the adapter runs `--severity low`), with ZIRAN's absolute path in the id and evidence.
- P6: `why <item>` names a scanner park `wuwei dispatch receive` only; close and the
  honeytoken hook park too.
- P8: `ziran._version` runs `ziran --version` before every audit and trace call.
- P9: `docs/site/security.md` does not say how to switch the scanner off.

## User Scenarios & Testing

### User Story 1 - A busy day keeps its trace checks measured (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a measured sweep, **When** the next sweep runs, **Then** ZIRAN receives only the
   spans recorded since, plus the last earlier span of each tool their sessions used (so a chain across
   the boundary is seen); with no new span ZIRAN is not run and the sweep is measured.
2. **Given** new spans where one session has more than 20, **When** the sweep runs, **Then**
   ZIRAN runs once per window in which no session has more than 20 new spans, and a day of
   3000 varied spans over 40 sessions is measured.
3. **Given** a ZIRAN failure or timeout, **Then** the sweep offset stays at the last measured
   span, the next sweep retries from there, one `scanner.unmeasured` event is appended per
   distinct reason, and `bin/wuwei doctor` shows an unmeasured `trace sweep` row with the
   reason and the fix until a sweep is measured again.
4. **Given** a damaged, forged or out-of-range offset file, **Then** the sweep starts from
   the beginning of the day (fail closed).

### User Story 2 - A resumed seat that repeats a chain is seen again (Priority: P1)

1. **Given** a seat parked by a chain and resumed by the owner, **When** the same chain runs
   again in new spans, **Then** it parks again; **When** no new chain runs, **Then** it stays
   resumed (S6 kept).
2. **Given** the same chain reported twice in one window, or a window retried after a failed
   park, **Then** it parks and pages once.
3. **Given** a credential read earlier today and no park of that session since, **When** a
   local chain runs (#870), **Then** it parks. **Given** a park of that session after the
   read, **Then** a later local chain parks only after a new credential read.
4. `traces.noted`, `traces.unmatched`, #878 honeytoken parks and the one close card behave as
   before.

### User Story 3 - One read of the day per sweep (Priority: P2)

1. A sweep reads `traces.jsonl` once, `events.jsonl` at most once and `state.json` at most
   once, whatever the number of findings.

### User Story 4 - Discovery candidates are short and relative (Priority: P2)

1. **Given** ZIRAN reports an absolute path under the checkout, **Then** the candidate id and
   evidence carry the path relative to the checkout.
2. **Given** `scanner.discovery_threshold = "high"`, **Then** medium and low findings are not
   candidates. The default `"low"` keeps every finding, as today.
3. **Given** more findings in one repo than `scanner.discovery_rows` (default 50), **Then** the
   most severe rows are kept and the scanner source line names how many more there were.

### User Story 5 - Small fixes (Priority: P3)

1. `why <item>` names a scanner park as the trace sweep (`wuwei dispatch receive` or
   `wuwei close`) or the honeytoken hook.
2. One process runs `ziran --version` at most once while it succeeds; a failed check is
   retried at the next call.
3. `docs/site/security.md` says how discovery, the trace sweep and the doctor row work, and
   how to switch the scanner off.

### Edge Cases

- A partial last line (the recorder mid-write) is left for the next sweep.
- A truncated or replaced `traces.jsonl` (shorter than the offset, or the offset not at a
  line start) restarts from 0.
- Two sweeps at once may both analyze the same window and both page; the dedup reads events
  once per sweep. Same ceiling as the discovery cache.
- A chain whose steps are split across two windows is seen through the carried spans: each
  window starts with the last span of every tool its sessions used before (review F1). Carried
  spans alone can form a chain already recorded; it parks again only when its source and sink
  tools both ran in the window's new spans.

## Requirements

- **FR-001**: `trace_sweep` keeps `days/<date>/trace-sweep.json` (`offset`, and `unmeasured`
  while the last sweep failed). It is a protected day file.
- **FR-002**: The sweep reads `traces.jsonl` once, parses only the lines since the offset, and gives
  ZIRAN windows of new lines in which no session has more than 20 spans, each preceded by
  the last earlier line of each tool each of its sessions used (kept in the mark as byte ranges). After each measured window the offset moves
  to the window's end.
- **FR-003**: A seat finding's `scanner.finding` payload carries `since` and `until`, the
  window's byte range. The dedup skips a finding with the same session, chain and `since`.
- **FR-004**: The #870 credential check is one pass over the day's spans: a local chain parks
  when the session's last credential read is at or after the `until` of its latest recorded
  `scanner.finding` for the same chain whose reason names a credential read (0 when none;
  review F2, D1). Any park of a session that read a credential today says
  `after a credential read` (review D2). The last
  read per session is kept in the mark (review F3).
- **FR-005**: An unmeasured sweep appends `scanner.unmeasured` (`source: traces`, `reason`)
  when the reason differs from the stored one; doctor's day section reads the offset file.
- **FR-006**: `discover` renders paths relative to the checkout, keeps rows at or above
  `scanner.discovery_threshold`, sorts by severity, keeps `scanner.discovery_rows` per repo and
  names the rest in the source line.
- **FR-007**: `why` names `scanner.finding` as the trace sweep or the honeytoken hook.
- **FR-008**: `ziran._version` remembers a successful check per process in
  `registry.CHECKED` (`registry.load` executes a fresh adapter module per call).
- **FR-009**: `docs/site/security.md` and `docs/site/configuration.md` document the above.

## Success Criteria

- **SC-001**: Each acceptance scenario is a test in `tests/test_traces_seats_only.py`,
  `tests/test_ziran.py`, `tests/test_plan.py` or `tests/test_protect_state.py`.
- **SC-002**: The audit's tracescale driver, run through `trace_sweep` on a day of 3000
  varied spans, is measured, and a second sweep with a few new spans costs time in
  proportion to them (quickstart.md).

## Assumptions

- The window cap is 20 spans per session. ZIRAN's time grows with a session's spans and,
  measured live, a window of 40 sessions at 40 spans each took 17 s, at 25 each 3.8 s, at 20
  each 1.8 s (ZIRAN 0.40.0). With the per-tool carry (review F1) a day of 3000 varied spans
  takes about 24 s in windows of about 6 s each, and the window size barely matters (5: 20 s,
  10: 18 s, 20: 24 s). A constant, not
  a config key: it tracks ZIRAN's cost, not an owner preference.
- Carrying the last span of each earlier tool keeps every direct pair across a boundary. Every
  edge in a window then has a new span at one end, so a reported chain always involves new
  activity; carrying each tool's last span keeps every path from an earlier tool into new spans.
- Discovery threshold default `"low"` keeps today's behaviour; the row cap default 50 is a
  change, because the wuwei repo alone gives 1148 rows (390 KB) in the lead brief.
- Old `scanner.finding` events without `since` keep the day-long dedup for their chain; without
  `until` they count as `until` 0.

## Deferred

- P2: ZIRAN prunes ignored directories during its walk (a ZIRAN release).
- P5: doctor fix text and docs link for scanner pages, and dropping rows of resumed items.
- P7: `config set` keeps a key's inline comment.
- P9 second half: the morning gate card naming an unmeasured scanner source.
