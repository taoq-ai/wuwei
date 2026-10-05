# Feature Specification: SubagentStop back under its latency budget

**Feature Branch**: `516-subagentstop-budget`
**Created**: 2026-10-05
**Status**: Draft
**Input**: GitHub issue #516: fix(latency): SubagentStop in a workspace is over its budget on
the runner (p95 117 ms wall, 50 ms CPU after #473, #477 and #496); bring it back under with
headroom without loosening the test.

## Root cause

The latency job asserts wall p95 under 100 ms for the workspace paths
(`tests/test_hooks.py`, `test_workspace_hook_latency`, `wall_budget=100`). On the runner
SubagentStop measures CPU 49.93 ms and wall 117.45 ms. Nothing on this path starts a
subprocess (`subprocess` is not in its module set), so the 67 ms between wall and CPU is time
the process spends blocked, and the only blocking calls on the path are `fsync`.

On the fixture path (a `wuwei:builder` seat, `last_assistant_message` present, the seat
reserved today, spec mode advisory) one SubagentStop does:

- Two full state writes. `cli/wuwei/guards/agent_launch.py:279` (`stop`) calls
  `state.stop_seat` (`cli/wuwei/state.py:449`), and `cli/wuwei/guards/lifecycle.py:143`
  (`subagent_stop`, through `_seen` at `:20` and `sessions.touch` at
  `cli/wuwei/sessions.py:77`) calls `state._write_state` again. Each `_write_state`
  (`state.py:198`) runs two `workspace.atomic_write` calls (`state.json` and
  `state.snapshot.json`, `state.py:221-222`), and each `atomic_write`
  (`cli/wuwei/workspace.py:244`) fsyncs the file and then the directory: 8 fsyncs per stop.
  On Linux ext4 each fsync waits for a journal commit; on macOS `fsync` returns without a
  flush, which is why the gap does not show on the owner's machine (measured: the same run
  with `os.fsync` replaced by a no-op has the same wall time locally).
- Four separately locked event appends (`seat stopped`, `discovery.requested`,
  `session.seen`, `spec.warned`), each an open, flock, two chmods, fstat, pread and write
  (`state.py:171`).
- Fourteen modules beyond the PreToolUse path's, five of them never executed on this path:
  `hashlib`, `_hashlib` and `_blake2` (imported at the top of `cli/wuwei/brief.py:3`, at the
  top of `cli/wuwei/commands/build.py:3`, and at the top of `check_retro` in
  `cli/wuwei/guards/verdict.py:102` before its charter check returns), `wuwei.decision`
  (imported at module level by `cli/wuwei/guards/decision.py:7` though `check_stop` needs
  it only when the message asks a question) and `wuwei.commands.build` (imported at
  `agent_launch.py:276` for every builder stop, though `build.stopped` returns at once when
  the item has no build record).

## Profile (top five costs)

Measured on the fixture workspace of `test_workspace_hook_latency` with the plugin copy
warm, medians of 30 runs (macOS arm64, a loaded host; `python -X importtime` minimum of 16
runs for imports; one `cProfile` run for the call counts). The hook process takes about
18 ms in process here and CPU p95 36 to 44 ms with a 17 ms interpreter floor.

| # | Cost | Count per stop | Local time | Runner |
|---|------|----------------|------------|--------|
| 1 | Durable state writes (`_write_state` to `atomic_write` to `fsync`) | 2 writes, 4 atomic writes, 8 fsyncs | 1.0 ms CPU, fsync free on macOS | the wall to CPU gap, about 67 ms |
| 2 | Imports beyond PreToolUse's | 14 modules (5 unused on this path) | 1.6 ms steady state; `_hashlib` 0.6 ms of it | about 2x |
| 3 | Repeated reads | `read_state` 8, `load_config` 4, `stopping_seat` 2 (transcript head read 2) | 0.5 + 0.7 + 0.4 ms | about 2x |
| 4 | Discovery request (`dispatch.discovery('seat-free')`: state read, config, append) | 1 | 0.6 ms | about 2x |
| 5 | Event appends, including `spec.warned` dedupe (`specmode.once` reads all of `events.jsonl`) | 4 appends, 1 full events read | 0.4 + 0.45 ms (1000 events) | about 2x |

Cost 1 is the root cause of the failing wall budget; costs 2 to 5 together are a few
milliseconds of CPU.

## User Scenarios and Testing

### User Story 1: a seat stop fits the hook budget with headroom (Priority: P1)

The planner's seats stop many times a day; each SubagentStop must stay inside the hook
budget on the runner without the test or the budget changing.

**Independent Test**: the latency fixture's SubagentStop run in a fresh interpreter with
`os.fsync` and the event append counted, and its loaded modules compared with the same
workspace's PreToolUse run.

**Acceptance Scenarios**:

1. **Given** the latency job on main (`WUWEI_BENCH=1`, quiet runner), **When** it runs,
   **Then** `test_workspace_hook_latency[SubagentStop]` passes on five consecutive runs,
   with `wall_budget=100` and the 50 ms CPU budget unchanged.
2. **Given** the fixture's SubagentStop (message present, seat known), **When** the hook
   runs, **Then** it performs one state write: 3 fsyncs (two files, one directory) instead
   of 8, and 3 event appends instead of 4.
3. **Given** the same stop, **When** the hook runs, **Then** the resulting `state.json`
   (seat `stopped`, `agent_id`, the session row with `last_hook`
   `SubagentStop:wuwei:builder`) and the event kinds and payloads (`seat stopped`,
   `session.seen`, `discovery.requested`, `spec.warned`, with `prs_seen` on the first two)
   are the same as before.
4. **Given** the same stop, **When** the hook runs, **Then** every module it loads is
   either loaded by the PreToolUse Bash call in the same workspace or in the allowlist
   `wuwei.guards.agent_launch`, `wuwei.guards.decision`, `wuwei.guards.lifecycle`,
   `wuwei.guards.spec`, `wuwei.guards.verdict`, `wuwei.brief`, `wuwei.dispatch`,
   `wuwei.sessions`, `wuwei.specmode` (the modules this path executes).

### User Story 2: the hand-back cases of #473 keep their behaviour (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the #473 cases (absent message, empty or blank message, unreadable or torn
   transcript, missing transcript bound through the recorded path), **When** SubagentStop
   runs, **Then** the outcomes are unchanged and the tests of #473
   (`tests/test_handback.py`) pass; the only edit to them is that
   `test_hook_reads_nothing_for_other_agents` also stubs the new tail reader, so it keeps
   guarding every report read.
2. **Given** an absent message and a transcript whose head is not readable (invalid UTF-8)
   but whose last assistant entry is, **When** `brief.stop_text` runs, **Then** it returns
   that entry's report, reading only the tail of the file (seek from the end).
3. **Given** an absent message and a last assistant entry followed by more than the first
   tail window of other lines, **When** `brief.stop_text` runs, **Then** the window grows
   until the entry is found and its report is returned.

### User Story 3: the session registry is still recorded on every stop (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a non-WUWEI subagent stop (agent type `Explore`), **When** SubagentStop runs,
   **Then** `lifecycle.subagent_stop` records the session as before (one state write).
2. **Given** a WUWEI seat stop that does not stop a seat of today (no reservation matches its
   brief), **When** SubagentStop runs, **Then** the session row and its `session.seen`
   event are still recorded.

### Edge Cases

- A seat stopped on an earlier day's state (`directory` is not today's day directory): the
  seat write goes to that day and the session touch stays separate (two writes, as today).
- A builder with a build record: `build.stopped` handles the stop as today (it records the
  result through its own write); the session touch stays separate.
- A payload without `session_id` (guards called directly, `wuwei seat stop` replaying the
  guards): no fold and no touch, as today.
- `lifecycle.subagent_stop` and `agent_launch.stop` resolve different workspaces (an
  unusual `WUWEI_WORKSPACE`): lifecycle touches its own workspace, as today.
- The latency fixture copies no `charters/`, so `check_retro` returns before its capture;
  real installs also pay the retro evidence write (see Deferred).

## Requirements

### Functional Requirements

- **FR-001**: A SubagentStop that stops a seat reserved in today's state through
  `state.stop_seat` MUST record the hook's session row in the same state write and append
  its `seat stopped` and `session.seen` events in one append; `lifecycle.subagent_stop`
  MUST then not write the session again.
- **FR-002**: `_write_state` MUST fsync the state directory once, after both the
  `state.json` and the snapshot renames, instead of once per file. Every other
  `atomic_write` caller keeps its own directory fsync.
- **FR-003**: On SubagentStop, `wuwei.decision`, `wuwei.commands.build` and `hashlib`
  MUST load only on the paths that use them: a message that asks a question, an item
  with a build record, a transcript completion hash, and a retro capture.
- **FR-004**: `brief.stop_text` MUST read an absent or blank message's report from the
  transcript's tail, growing the window from the end until it holds the last assistant
  entry or reaches the start, with the same parsing, the same report text and the same
  `ValueError` and `OSError` outcomes as `brief.last_turn` on well-formed files.
- **FR-005**: No guard result, exit code, refusal, event kind or payload changes; no refusal
  is added in any posture.
- **FR-006**: `test_workspace_hook_latency`, `assert_latency_budget` and the budgets (CPU 50
  ms, workspace wall 100 ms) MUST NOT change.

## Success Criteria

- **SC-001**: The two new SubagentStop tests (import allowlist; one state write, 3 fsyncs, 3
  appends) fail on the base and pass after the change.
- **SC-002**: The #473 tests, the existing hook import-graph tests and the full suite pass.
- **SC-003**: On the runner, SubagentStop p95 is under 100 ms wall on five consecutive
  latency jobs; the target is about 80 ms wall and 40 ms CPU (estimate: five of eight fsyncs
  removed, about 40 ms of the 67 ms blocked time, plus a few ms of CPU).

## Assumptions

- The runner's blocked time is attributed to fsync by elimination: no subprocess, network
  or contended lock on this path, and an interpreter start with no gap between wall and CPU
  (11.10 ms wall, 10.97 ms CPU). It cannot be reproduced on macOS, so the tests pin the
  fsync and append counts instead of a local wall time.
- "Adds no module beyond PreToolUse's" is read as: nothing beyond PreToolUse's except the
  SubagentStop guard modules and the four modules this path executes (`wuwei.brief` for the
  seat binding, `wuwei.sessions` for the registry row, `wuwei.specmode` for the advisory
  spec check, `wuwei.dispatch` for the discovery request), pinned as an allowlist so any
  new module fails the test. The literal reading cannot hold: the five guard modules
  themselves are not on the PreToolUse path, and moving the seat binding out of
  `wuwei.brief` would be a refactor for 0.13 ms.
- "Write the events in one append" is met where the events share a write (`seat stopped`
  and `session.seen`). `discovery.requested` and `spec.warned` stay separate appends: they
  are written by other guards after the seat write, carry no fsync, and cost about 0.1 ms
  each here; joining them would couple three guards for under a millisecond.
- "Read the transcript only when `last_assistant_message` is absent": with a message
  present the path already reads no report from the transcript; it reads only the
  transcript's head for the brief reference, which binds the stop to its seat and stays.
  The tail read applies to `stop_text`. `build.stopped` keeps the full `last_turn` read,
  because the build binding stores the line index and its hash.
- "Skip work that belongs to the heartbeat": the only heartbeat work reachable from this
  hook, the seat-free discovery intake, already runs on the watch tick
  (`watch.pending_discovery`); the hook only records the request. The #496 tier table is
  not reached on SubagentStop (`wuwei.outward` loads in the PreToolUse path as well).
- One directory fsync after both renames gives the same guarantee at return as two: both
  renames are durable before the event is appended, and a crash before that fsync leaves
  the previous `state.json` and snapshot, with no event, as a crash inside the first write
  does today.
- The fold marks the payload (`wuwei_session_recorded`, the workspace root it wrote) for
  `lifecycle.subagent_stop`; guards run in module order (`agent_launch` before
  `lifecycle`), and if the order ever changed the result would be a second write, never a
  lost one.
- The tail window starts at 64 KiB and grows four times per step; a line split at the
  window's start is dropped until the window reaches it.

## Deferred

- `brief.last_turn` splits the transcript with `str.splitlines`, which also breaks on raw
  U+2028, U+2029 and U+0085 inside a JSON string; such a transcript reads as torn. The tail
  reader splits on newlines only. A follow-up issue should decide whether `last_turn`
  changes (it would change stored build completion indexes).
- The latency fixture copies no `charters/`, so the benchmark skips `check_retro`'s
  evidence write (2 more fsyncs) that every real seat stop pays. Making the fixture match a
  real install tightens the test and belongs in its own issue.
- `specmode.once` reads the whole `events.jsonl` per builder stop to deduplicate
  `spec.warned`; the cost grows with the day.
