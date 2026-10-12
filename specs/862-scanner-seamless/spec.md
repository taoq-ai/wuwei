# Feature Specification: the scanner runs once per repository per day and never re-parks a resumed item

**Feature Branch**: `862-scanner-seamless`
**Created**: 2026-10-12
**Status**: Implemented
**Input**: GitHub issue #862: "fix(scanner): a scanner timeout is paid once per repository per day",
widened by the live ZIRAN audit of 2026-10-12 (findings S1 to S8 and P1, P4).

## Root cause

- S1: `adapters/scanner/ziran.py` `_report` requires `type(line) is int`. ZIRAN emits
  `line: null` by design for SA002 (no input validation in a tool definition), so every
  agent repo is unmeasured. `tests/test_ziran.py` pins `('line', None)` as invalid.
- S2: `_report` treats `files_analyzed < 1` as invalid; a TypeScript or Go repo with no
  Python file is exactly that. `tests/test_ziran.py` pins it.
- S3: `cli/wuwei/discovery.py` `discover` sets the scanner source to the first unmeasured
  repo's reason and `break`s, discarding every other repo's rows.
- S4 (#862): `discover` runs `scanner.audit` for every repo on every call (lead brief,
  every `plan propose`). Nothing is remembered, so a 60 s timeout is paid on every call.
- S5: `brief.write` computes the lead's `candidates(root)` (the audit) inside `brief.lock`,
  so a parallel brief waits 30 s and fails while a slow audit runs.
- P4: `plan.propose` runs discovery before it refuses an approved day.
- S6: `scanner._trace_response` parks a seat's items on every sweep. The sweep reads the whole
  day's `traces.jsonl` each time, so a chain the owner already resumed parks the item again
  at the next receive or close, and pages again.
- S7: `closing.scanner_hold` returns at the first unanswered critical finding, one Owner step
  card per finding, one `close` run each.
- S8: `scanner.rows` blocks an `agent_surface` item on every finding in its worktree,
  including findings already on main, so such an item loops to FIX and parks.
- P1: scanner errors say "run bin/wuwei doctor", but doctor never runs ZIRAN;
  `scanner.py` even claims doctor "tests the scanner".

## User Scenarios & Testing

### User Story 1 - The morning scanner is measured on real repos (Priority: P1)

An agent repo with an SA002 file-level finding and a TypeScript repo with no Python file are
both measured; one repo's failure does not drop another repo's findings.

**Acceptance Scenarios**:

1. **Given** ZIRAN reports a finding with `line: null`, **When** the adapter audits, **Then**
   the result is measured, discovery lists it as `<file>` (id ends `:<file>:0`), and an S4
   row names `<file>:1`, the `file:line` a verdict finding needs.
2. **Given** ZIRAN reports `files_analyzed: 0` and no findings, **Then** the audit is measured
   and clean. `files_analyzed: 0` with findings stays invalid.
3. **Given** two repos, one measured with a finding and one unmeasured, **When** discovery
   runs, **Then** the finding is a candidate and the source line reads
   `measured: 1; unmeasured: <repo>: <reason>; ...`.

### User Story 2 - A scanner timeout is paid once per repository per day (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a repo whose audit timed out, **When** a second `plan propose` (or lead brief)
   runs the same day at the same HEAD, **Then** it spends under 2 s on the scanner and shows
   the same unmeasured reason. (#862)
2. **Given** a measured repo, **When** discovery runs again at the same HEAD, **Then** ZIRAN
   is not run again; **When** the HEAD moves, **Then** it is.
3. **Given** a lead brief with a slow audit, **When** another brief is written meanwhile,
   **Then** it is not held by `brief.lock` for the audit.
4. **Given** an approved morning gate, **When** `plan propose` runs, **Then** it refuses
   without running discovery.

### User Story 3 - A resumed item stays resumed (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a seat's critical chain parked its item, **When** the owner resumes it with
   `plan resume` and the next sweep runs, **Then** the item is not parked again and no new
   `scanner.finding` is appended.
2. **Given** the same chain reported several times in one sweep, **Then** it parks and pages
   once.
3. #878 honeytoken reads and #870 credential-path checks behave as before.

### User Story 4 - Close asks one card for today's critical chains (Priority: P2)

1. **Given** two distinct critical chains today, **When** `bin/wuwei close` runs, **Then** one
   Owner step card names both; one Yes lets the next `close` pass. A critical chain recorded
   after that Yes asks a new card.

### User Story 5 - The S4 gate judges the item's own change (Priority: P1)

1. **Given** an `agent_surface` item whose worktree has findings only in files it did not
   change, **When** the security verdict is received, **Then** no ZIRAN row is merged, the
   verdict keeps its PASS and no `scanner.finding` is appended.
2. **Given** a finding in a file the item changed, **Then** it blocks as today.

### User Story 6 - Scanner errors name the fix (Priority: P2)

1. A discovery, S4 or trace-sweep scanner error names the repo, worktree or trace file and
   the fix (`bin/wuwei config set adapters.scanner '"none"'` switches it off where that
   applies), never `run bin/wuwei doctor`.

### Edge Cases

- A fast unmeasured audit (ZIRAN missing, unsupported version) is not remembered, so
  installing ZIRAN mid-day takes effect on the next call. Only a slow failure (10 s or more,
  a timeout) and measured results are remembered.
- A repo whose HEAD cannot be read is remembered under no HEAD for the day.
- A damaged or forged cache entry is ignored and the repo re-audited.
- The cache key is the checkout's HEAD, but ZIRAN audits the working tree: uncommitted or
  untracked changes in a configured checkout (and item worktrees nested under it, audit P2)
  keep the day's cached result until HEAD moves. A cached slow failure is retried only on a
  new HEAD, the next day, or after switching the scanner off. This is discovery only, never a
  gate (review F6).
- A security brief without a `Merge-base:` line is unmeasured, never PASS.

## Requirements

- **FR-001**: `ziran._report` accepts `line` null or an int of at least 1, and
  `files_analyzed` 0 when `findings` is empty.
- **FR-002**: `discovery.discover` keeps every measured repo's rows and names each unmeasured
  repo; a null line renders without `:line` in discovery and as line 1 in an S4 row.
- **FR-003**: `discover` remembers each repo's audit in `days/<date>/scanner-audit.json`,
  keyed by repo name and HEAD: measured findings always, an unmeasured reason when the call
  took 10 s or more.
- **FR-004**: `brief.write` computes the lead's candidates before taking `brief.lock`.
- **FR-005**: `plan.propose` refuses an approved gate before discovery.
- **FR-006**: `scanner._trace_response` skips a seat finding when today's events hold a
  `scanner.finding` with the same `session_id` and `chain`.
- **FR-007**: `closing.scanner_hold` asks one card listing today's distinct critical chains,
  its token over the sorted set of critical findings.
- **FR-008**: `dispatch.receive` passes the item's changed files (`vcs.diff_stat` from the
  brief's `Merge-base:` to the measured HEAD) to `scanner.rows`, which keeps only findings
  in those files.
- **FR-009**: Scanner error texts name the place and the fix; none says doctor.
- **FR-010** (review F1): `scanner-audit.json` is a protected day file (a seat cannot write
  it); a cache entry is used only when every row passes the scanner adapter's own `_report`
  shape check, else the repo is re-audited; candidate evidence and reasons are one line.
- **FR-011** (review F2): the S4 filter keeps a finding when its resolved path or its own
  reported path (relative to the worktree) is in the changed files, so a new symlink to an
  existing dangerous file blocks.
- **FR-012** (review F3): a seat finding's `scanner.finding` event and its park are one state
  write, so a failed park leaves no dedup marker and the next sweep parks.
- **FR-013** (review F5): when ZIRAN analyzed no file in the worktree, the S4 verdict carries a
  non-blocking note saying so.

## Success Criteria

- **SC-001**: Each acceptance scenario is a test in `tests/test_ziran.py`,
  `tests/test_plan.py`, `tests/test_brief.py`, `tests/test_traces_seats_only.py`,
  `tests/test_close_parked.py` or `tests/test_dispatch.py`.
- **SC-002**: The audit's live drivers for S1 to S8 and P4 show each fixed (quickstart.md).

## Assumptions

- Only slow failures are remembered: the issue is the 60 s timeout, and remembering a fast
  "ZIRAN missing" would keep the day unmeasured after the owner installs it.
- Diff-only S4 judges findings in files the item changed, including ones already in those
  files on main; pre-existing findings elsewhere are the morning discovery's job, which
  still lists them as candidates.
- Dedup is by session and chain for the day, the same rule the non-seat branch has. A new
  chain from the same seat after a resume still parks. The same chain repeated by the same session after a resume is not
  detected again (review F4): the sweep re-reads the whole day's traces, so a per-cycle key
  would bring S6 back. The edges guards (#870) and #878 honeytokens still stand; S9's
  since-last-sweep offset is the real fix.
- The close card lists at most five chains and counts the rest.
- Concurrent discoveries may both audit and the last write wins; that costs one audit, no data.

## Deferred

- S9: incremental trace sweep (spans since the last sweep), one read of the trace file
  for `_private_read`, and one read of the day's events per sweep (review F7).
- P2: ZIRAN prunes ignored directories during its walk (a ZIRAN release).
- P3, P5 to P9 of the audit (candidate paths and threshold, doctor rows, `why` kind,
  config comment, version probe once per process, docs).
