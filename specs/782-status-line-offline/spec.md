# Feature Specification: the status line never waits on the network, and doctor names a slow probe instead of suggesting a reinstall

**Feature Branch**: `782-status-line-offline`
**Created**: 2026-10-10
**Status**: Draft
**Input**: GitHub issue #782 (owner, 2026-10-10, item 71): the status line took 6.6 s against
its 200 ms budget while GitHub calls were failing on a secondary rate limit; doctor's fix
said "the hook no longer behaves as shipped; reinstall", while the integrity check was
clean. Deliver: the status line and the SessionStart hook read only local state and the
last cached host answer, never a live GitHub call; a probe that exceeds its budget is
recorded with its name and elapsed time; doctor's finding names the slow probe and the
matching step, and suggests a reinstall only when the integrity check fails.

## Root cause (read on main at cb33150)

1. **The status line makes no host call, on main or in the owner's 0.24.1.**
   `cli/wuwei/commands/status.py` `snapshot(directory, line=True)` returns at line 330
   (`if line: return result`), before the only port call in the module, the calendar read
   at lines 341-346. `scan`, `surfaced`, `integrity.restart` and `watch.health` read files
   only. The installed 0.24.1 copy has the same early return (its line 298, calendar at
   314). SessionStart (`cli/wuwei/guards/lifecycle.py` `session_start`, lines 39-128) reads
   state, memory, events and the session registry, and calls no port either. The watch tick
   already makes the host calls in the background and caches their answers under `watch` in
   day state (`watch.prs`, `watch.reviews`, `watch.facts`). Main also has #659's cached line:
   `heartbeat.beat` saves `watch.status_line` and `status._line_or_cache` (status.py
   366-392) prints it when the compute overruns 100 ms. The installed 0.24.1 predates #659,
   which is why the owner's day state has no `watch.status_line`.

2. **The 6.6 s is the launcher under host load, not GitHub.** Reproduced read-only from a
   copy of the owner's live workspace day (2026-10-10, 892 `heartbeat: clock` records). In every
   heartbeat where `status_line` was slow, the four hook probes started beside it were just
   as slow, for example 15:53:28 `status_line` 9142 ms with `allowed` 7465, `state_write`
   7727 and `read_loop` 8940 ms; 12:24:44 `status_line` 6704 ms with `allowed` 5865 ms. The
   hourly median tracks seat activity (09:00 to 12:59: 1116 to 3926 ms, while seats launched
   and stopped), not rate-limit failures: 14:00 to 18:59 logged 553 `watch: read-failed`
   events (gh rate limit) with hourly medians of 126 to 812 ms. Each probe is a fresh
   `bin/wuwei` interpreter (`adapters/watch_service.py` `probe`), so its wall time measures
   process start-up on a busy host. A cache cannot shorten interpreter start-up.

3. **Doctor's fix ignores why the probe failed.** `cli/wuwei/commands/doctor.py` `_guards`
   (lines 714-718) gives every failed probe row the same fix, `the hook no longer behaves as
   shipped; run wuwei integrity check and reinstall the signed release`, unless the value
   mentions `plugin integrity`. A `status_line` value of `6600 ms over 200 ms`, or a hook
   probe that timed out, gets reinstall advice although the files are intact (the integrity
   row is clean) and a reinstall changes nothing.

So the owner's hypothesis (the line waits on rate-limited GitHub calls) does not hold. The
fix this issue needs is in doctor, plus a regression test that pins the status line and
SessionStart offline.

## Clarifications

### Session 2026-10-10

Answered with the recommendation (AGENTS.md: no clarifying questions).

- Q: Does any status line or SessionStart code move to the watch tick? A: No. Neither path
  calls a port today (root cause 1); the watch tick already owns the host calls and their
  cache. This feature adds a test that fails if either path ever calls a network port.
- Q: Which "slow probe" does doctor name, given the line has no sub-probe such as
  `github.pr_state`? A: The row itself names the probe (`status_line`) and its value already
  carries the elapsed time (`6600 ms over 200 ms`). The fix adds the cause doctor can
  measure: when every other hook probe in the same run was also over 200 ms or timed out,
  the host was busy, and the fix names the fastest of them with its milliseconds. When only
  `status --line` was slow, the fix points at the watch row, because the line falls back to
  the line the watch heartbeat caches and a dead watch caches nothing.
- Q: Does doctor name a rate limit on this row? A: No. The status line makes no GitHub call,
  so a rate limit is never its cause. A rate limit doctor meets stays on the tracker row
  (#738).
- Q: Which rows lose the reinstall advice? A: The six guard probe rows (`refused`,
  `allowed`, `state_write`, `read_loop`, `git_read`, `status_line`) when the failure is
  about time: a `status_line` value `N ms over 200 ms`, or any value `timeout`. A wrong exit
  code (for example `refused` answering `exit 0`) keeps today's text: that is behaviour,
  not time. Reinstall advice for damaged files stays on the integrity row.
- Q: What counts as slow for another hook probe? A: Its value is `timeout`, or its `ms` is
  over `heartbeat.STATUS_LINE_BUDGET_MS` (200). The hook probes have no budget of their own;
  a healthy one takes about 50 ms, so 200 ms is a clear sign of load. The probes compared
  are the four that carry `ms` (`refused`, `allowed`, `state_write`, `read_loop`), minus the
  row's own probe.

## User Scenarios and Testing

### User Story 1 - The status line and SessionStart never call a network port (Priority: P1)

The owner's status line and session start stay quick when GitHub hangs or is rate limited,
because neither calls GitHub.

**Independent Test**: with the code host, tracker, calendar, chat, inbound and review bot
ports replaced by a fake whose every call records itself and sleeps, `status --line` returns
in under a second and SessionStart's guard completes, and the fake records no call.

**Acceptance Scenarios**:

1. **Given** a host port that hangs and a cached line in `watch.status_line`, **When** the
   status line runs, **Then** it returns within one second, prints a line, and no port call
   was made.
2. **Given** the same hanging ports, **When** SessionStart's guard runs in the workspace,
   **Then** it returns and no port call was made.
3. **Given** `status --line` took longer than 200 ms, **Then** the heartbeat records the
   `status_line` probe as `failed` with `<ms> ms over 200 ms` (on main already, pinned by
   `tests/test_heartbeat.py` `test_launcher_probe_outcomes`).

### User Story 2 - Doctor names a slow probe and the step that helps (Priority: P1)

The owner runs doctor while seats run; the `status_line` row says it was slow, why, and
what to do, and does not tell the owner to reinstall intact files.

**Independent Test**: doctor with a `status_line` probe of `6600 ms over 200 ms` returns a
`fail` row whose value names the time and whose fix names the cause and contains no
`reinstall`.

**Acceptance Scenarios**:

1. **Given** `status_line` `6600 ms over 200 ms` and the hook probes `refused`, `allowed`,
   `state_write`, `read_loop` at 7100, 5865, 7020 and 6490 ms, **When** doctor runs,
   **Then** the row is `fail` with value `6600 ms over 200 ms` and the fix says every
   launcher call was slow, names `fastest hook probe allowed 5865 ms`, says the host is busy,
   and asks to rerun doctor when fewer seats run; it has no `reinstall`.
2. **Given** `status_line` `6600 ms over 200 ms` and the hook probes at 40 ms, **Then** the
   fix says only `status --line` was slow and points at the watch row (the line prints the
   heartbeat's cached line, and a dead watch caches nothing); it has no `reinstall`.
3. **Given** `allowed` `timeout` and every other hook probe `timeout`, **Then** the fix says
   every hook probe timed out and the host is busy; no `reinstall`.
4. **Given** `allowed` `timeout` and the other hook probes at 40 ms, **Then** the fix says
   only this probe timed out in this run and to rerun doctor; no `reinstall`.
5. **Given** `refused` `exit 0` with a clean integrity row, **Then** the fix is today's
   (the hook no longer behaves as shipped; integrity check and reinstall).
6. **Given** a probe value naming `plugin integrity`, **Then** the fix is
   `fix the integrity row first`, as today.

### Edge Cases

- The doctor test fixture's probes carry no `ms`: a probe with neither `ms` over 200 nor
  `timeout` is not slow, so a fixture where only `status_line` is slow takes the line-only
  branch.
- `status_line` itself `timeout`: a timing failure, handled like the line-only or busy cases.
- The hook probes could not run at all (`unmeasured` with an adapter error, not `timeout`):
  not a timing failure, today's fix.
- No workspace: `_guards` returns no probe rows, as today.

## Requirements

### Functional Requirements

- **FR-001**: `status --line` and the SessionStart lifecycle guard MUST make no call to a
  network port (`code_host`, `tracker`, `calendar`, `chat`, `inbound`, `review_bot`); a test
  MUST fail if either does.
- **FR-002**: The heartbeat MUST keep recording a slow `status_line` probe as `failed` with
  `<ms> ms over 200 ms` (unchanged).
- **FR-003**: Doctor's guard probe rows MUST, for a timing failure (value `timeout`, or a
  value containing ` ms over `), give a fix that names the cause and contains no reinstall
  advice: the busy-host text naming the fastest other hook probe and its ms (or that every
  one timed out) when every other hook probe was slow; else, for `status_line`, the
  watch-row text; else the rerun text.
- **FR-004**: Doctor's guard rows MUST keep `fix the integrity row first` for a value naming
  `plugin integrity`, and today's reinstall text for every other failure.
- **FR-005**: The heartbeat section of `docs/site/reference.md` MUST say that the status line
  and SessionStart make no code-host call and how doctor words a slow probe's fix.
- **FR-006**: Probe names, values, results, `ms` fields, the heartbeat record, the status
  line text, its cache and its 100 ms compute budget MUST NOT change.

## Success Criteria

- **SC-001**: The issue's acceptance holds: with a hanging host port the status line returns
  within budget and makes no port call; a slow probe is named with its time in doctor, and
  a clean integrity check gets no reinstall advice.
- **SC-002**: No new test reaches the network or waits on the fake port's hang.
- **SC-003**: The full suite passes; no existing assertion changes.

## Assumptions

- The orchestrator notes file named in the task (`notes/782-full.md`) does not exist and no
  dry-run workspace was named. The failure was reproduced read-only from a copy of the
  owner's live workspace day state and events; the figures under Root cause come from it.
- The owner's attribution of the slowness to GitHub rate limits (items 65 and 71) is not
  supported by the code or the data; this feature moves no host call, because none sits on
  the status line or SessionStart path.
- The issue's example text (`github.pr_state 6.3 s, rate limited until <time>`) names a
  sub-probe that does not exist; doctor names what it can measure: the slow probe, its time
  and its slow peers.
- 200 ms (`heartbeat.STATUS_LINE_BUDGET_MS`) is the threshold for a slow hook probe; no new
  config key (constitution V).
- "The SessionStart heartbeat" in the issue means the SessionStart hook's lifecycle guard,
  which reports watch and listen health from recorded clocks.
- Upgrading from 0.24.1 brings #659's cached line; nothing in this feature depends on it.

## Deferred

- A `status_line` budget miss of a few milliseconds (225 ms over 200 ms, seen in the owner's
  day at 18:56 and 19:00) pages as `behaviour drift`, since the probe flips between ok and
  failed. Whether a timing miss counts as drift is a heartbeat page rule, not a doctor fix;
  to be filed as its own issue if the owner wants it.
