# Feature Specification: A slow traces hook is a warning, the trace read uses the writer's digest, and the status line keeps its budget

**Feature Branch**: `659-traces-slow`

**Created**: 2026-10-10

**Status**: Draft

**Input**: GitHub issue #659, "fix(guards): the traces PostToolUse hook never fails a tool
call because it ran slowly: a timeout is a warning with the measured time, the check is
skipped under load, and the status line stays within its budget".

## Root cause

Reproduced read-only on a scratch workspace (`[security] required = true`,
`posture = "observe"`), calling `traces.check` in process on a day with N spans in
`traces.jsonl` and N events in `events.jsonl`, and `status.snapshot(day, line=True)`.
Line numbers are `main` at 35306d9.

1. **A timeout reads as "could not read" and fails the call in every posture.**
   `state.lock_ex` (`cli/wuwei/state.py:13-22`) is the one bounded wait on the traces
   path; it raises `TimeoutError`, a subclass of `OSError`. In the inspect block the inner
   `except (OSError, ValueError, TypeError, KeyError, RuntimeError)` at
   `cli/wuwei/guards/traces.py:116-117` catches it and returns
   `(2, 'wuwei traces: cannot inspect or record workspace security evidence; ...')`, the
   same sentence as unreadable security material. On the record path the outer handler at
   `traces.py:121-133` names only the exception type and returns 2 when security material
   is in use. The hook levels both under the guard's area `records`
   (`cli/wuwei/guards/__init__.py:43`), a floor in every posture
   (`cli/wuwei/workspace.py:46`), so a lock wait that ran out under load is a failed tool
   call under observe and guarded, indistinguishable from a real finding, and it passes on
   retry once the load drops. That matches the owner's report.
2. **Every tool call rescans the whole day.** `_record` counts every line of
   `traces.jsonl` (`traces.py:76-78`) and `steward.maybe_run_for_tool_calls`
   (`cli/wuwei/steward.py:253-266`) parses all of `events.jsonl` through `watch.records`
   (`cli/wuwei/watch.py:19-41`) to decide one advisory nudge. Measured: 144 ms per call at
   N = 20000 and 560 ms at N = 80000, 88 to 90 percent of it in `watch.records`; the cost
   is linear in the day and multiplies with every agent running at once.
3. **Every seat tool call rewrites state.** `_record` calls `state._write_state(bind)`
   (`traces.py:60-74`) whenever the transcript names a brief, even when that seat already
   holds this transcript and session. Each call rewrites `state.json` and its snapshot
   (two fsyncs) while holding `state.lock`, the lock every hook and command waits on, and
   appends a `state.write` event. Measured: 9.5 ms per call on an empty day and 50
   `state.write` events for 50 calls of a bound seat. That is the lock contention behind
   finding 1 and the event growth behind findings 2 and 4.
4. **The status line has no fallback.** `status --line` parses the whole `events.jsonl` on
   every refresh (`cli/wuwei/commands/status.py:63-72`, through `snapshot` at `:255`):
   71 ms at N = 20000 and 264 ms at N = 80000 in process, before interpreter start,
   against the 200 ms wall budget the heartbeat probes (`cli/wuwei/heartbeat.py:30`).
   Under eight agents the CPU contention takes it to seconds and nothing short-circuits.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A traces hook that ran out of time warns instead of failing the call (Priority: P1)

A seat's tool call completes while the machine is loaded; the traces hook's lock wait runs
out. Under observe and guarded the call is not failed: the seat sees a warning that names
how long the hook ran, and the day records `traces.slow`. Under strict the refusal stays.
An unreadable file is still reported as before, as a real finding (`traces.gap`).

**Why this priority**: it is the reported defect: builders lost tool calls to a hook that
was only slow.

**Independent Test**: a security-enabled fixture workspace per posture; a PostToolUse
payload through `hook.run` with the traces read replaced by a fake that raises
`TimeoutError`; assert the exit, the stderr warning with its milliseconds and the
`traces.slow` event.

**Acceptance Scenarios**:

1. **Given** posture observe or guarded and a traces read that exceeds its bound
   (`TimeoutError`), **When** PostToolUse runs, **Then** it exits 0, stderr carries
   `wuwei traces: did not finish in time after <N> ms` and `events.jsonl` gains one
   `traces.slow` event with `elapsed_ms` N, the span and the session.
2. **Given** posture strict and the same read, **When** PostToolUse runs, **Then** it
   exits 2 with that reason and the records floor line, and `traces.slow` is recorded.
3. **Given** any posture and a read that raises anything other than `TimeoutError` (for
   example unreadable security material), **When** PostToolUse runs, **Then** the result
   and the record are exactly today's (today's reasons, exits and `traces.gap` path).

---

### User Story 2 - The trace read uses the writer's digest instead of rescanning (Priority: P1)

The traces hook keeps a small digest next to `traces.jsonl` that it updates when it
appends a span: the day's tool call count and the steward checkpoint. A call reads the
digest, not the day's files; `events.jsonl` is read only when a steward boundary can be
due, at most once per `steward.every_tool_calls` calls. Under load, once the hook has spent
its budget, the steward check is skipped for that call. A seat already bound to its
transcript costs no state write.

**Why this priority**: it removes the cost that grows with the day, which is what made the
hook slow under load in the first place.

**Independent Test**: tool calls through `traces.check` with `watch.records` counted:
no events read below a boundary; the digest counts calls and recovers when missing; the
existing steward tests keep their exact due counts.

**Acceptance Scenarios**:

1. **Given** a day with spans and events and `steward.every_tool_calls = 250`, **When**
   five tool calls are traced, **Then** `events.jsonl` is not parsed and the digest's
   `tool_calls` grows by five.
2. **Given** a day whose `traces.jsonl` has spans but no digest (a day begun before this
   change, or a damaged digest), **When** one call is traced, **Then** the digest holds
   the file's span count including the new span.
3. **Given** `steward.every_tool_calls = 2` and a `steward.run` at 3, **When** calls are
   traced, **Then** `steward.due` lands at 2 and 5, as today.
4. **Given** the hook has already spent its budget when it reaches the steward check,
   **When** the call is traced, **Then** no steward check runs and the next call within
   budget makes it.
5. **Given** a seat already bound to this transcript and session, **When** its tool calls
   are traced, **Then** no `state.write` event is appended for them.

---

### User Story 3 - The status line answers within its budget from the tick's cache (Priority: P2)

Each heartbeat tick renders the status line in the watch process and keeps the text with
its time. When `status --line` cannot compute within its budget, it prints that text,
marked with the time it was rendered, instead of making the owner wait.

**Why this priority**: the owner saw 3 to 4 s against a 200 ms budget; the line is the
owner's view and must not stall, but it is display only.

**Independent Test**: a cached line in the day's watch state and a slow fake reader in
place of `status.snapshot`; `status.run` returns the cached text within the budget.

**Acceptance Scenarios**:

1. **Given** a cached status line and a compute that does not finish within the budget
   (slow fake reader), **When** `status --line` runs, **Then** it prints the cached text
   and exits 0 well within one second.
2. **Given** no cached line and a slow compute, **When** `status --line` runs, **Then** it
   waits for the compute and prints it, as today.
3. **Given** a compute that fails within the budget, **When** `status --line` runs,
   **Then** it prints `WUWEI ? unmeasured`, as today, never the cache.
4. **Given** a heartbeat tick, **When** `heartbeat.beat` runs, **Then** the day's watch
   state holds the rendered line ending ` · as of HH:MM`, within 100 columns.

### Edge Cases

- A `TimeoutError` while recording `traces.slow` itself: the record waits at most 1 s for
  the lock, then stderr says `could not log traces.slow`, and the exit follows the
  posture as above.
- The steward check runs on the record path inside the existing catch-all; a timeout
  there never reaches the slow path (no change: the nudge never fails a call).
- A hook killed between the span append and the digest update leaves the digest one low
  for the day; the steward nudge is then one call late. Accepted (see Assumptions).
- Sustained load above the hook budget defers the steward nudge until a call fits.
- No running watch: no cache, and `status --line` computes as today.
- `status --line --width N` with N other than the default computes as today; the cache
  serves the Claude Code status line call only.
- A new day has no cache until the first tick of that day.
- Security material not in use (`security.required` false): the slow path still warns
  below strict and returns today's exit under strict.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The traces guard MUST classify a `TimeoutError` raised in its inspect or
  record steps as "did not finish in time": the inner handler at `traces.py:116` does not
  take it, and the outer handler builds the reason
  `wuwei traces: did not finish in time after <N> ms (TimeoutError); the tool ran and its span may be missing; run bin/wuwei doctor`,
  N being the wall milliseconds since `check` began. The exception message is never
  interpolated.
- **FR-002**: The slow reason MUST be printed to stderr and recorded as `traces.slow` with
  `reason`, `span` and `session` redacted as `traces.gap` does, and `elapsed_ms`; the
  append waits at most 1 s for `state.lock`.
- **FR-003**: Below strict a slow traces guard MUST return `(0, '')`; under strict it MUST
  return what today's tail returns (2 when security material is in use). The posture is
  read with `_strict(root)`; an unreadable config counts as strict.
- **FR-004**: Every other failure MUST keep today's behaviour and record (`traces.gap`,
  today's reasons and exits).
- **FR-005**: `traces.slow` MUST be reserved to `wuwei hook PostToolUse` in
  `EVENT_PRODUCERS` and classified `nudge`.
- **FR-006**: After appending a span the guard MUST update the day's
  `traces.digest.json` (`{"tool_calls": N, "steward": B}`) under `state.lock`: N plus one
  when the digest is valid; when it is missing or invalid, N is the newline count of
  `traces.jsonl` and B is 0. `protect_state` MUST refuse agent writes to it like the other
  day files.
- **FR-007**: `steward.maybe_run_for_tool_calls(count, root, base)` MUST return `base`
  without reading `events.jsonl` when `count - base` is below the interval, and otherwise
  decide exactly as today and return the new base: `count` when it appended
  `steward.due`, else the largest of the last `steward.run` count and any `steward.due`
  count above it. The guard persists a changed base in the digest.
- **FR-008**: The guard MUST skip the steward check, leaving the base unchanged, when it
  has already run for `BUDGET_MS` (1000 ms wall) at that point. The security inspection
  is never skipped.
- **FR-009**: The seat bind MUST write state only when a seat whose brief the transcript
  names lacks this transcript path or this session id.
- **FR-010**: `heartbeat.beat` MUST render the status line in process once per tick and
  save it as `status_line` in the same `watch.save` call as the heartbeat record, as the
  line at `WIDTH` minus the suffix width followed by ` · as of HH:MM`; a render failure
  leaves the previous text.
- **FR-011**: `status --line` at the default width MUST wait for its compute at most
  `LINE_BUDGET_MS` (100 ms) and then print the cached text when one exists; with no cache
  it waits for the compute; a compute error within the budget prints today's unmeasured
  line.
- **FR-012**: The changed guard rule MUST get a design spec 9.2 row and its check in
  `tests/test_invariants.py`, memoised per posture.

### Key Entities

- **Trace digest** (`.wuwei/days/<date>/traces.digest.json`): `tool_calls` (int, the day's
  spans), `steward` (int, the count below which no steward boundary can be due). Written
  only by the traces guard; a cache, never evidence.
- **`traces.slow` event**: `reason`, `span`, `session`, `elapsed_ms`.
- **Cached status line** (`watch.status_line` in the day's state): the rendered line with
  its ` · as of HH:MM` suffix, written by the heartbeat tick.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Under observe and guarded no `TimeoutError` on the traces path makes
  `bin/wuwei hook PostToolUse` exit non-zero; under strict it exits 2.
- **SC-002**: A traced tool call below a steward boundary parses neither `traces.jsonl`
  nor `events.jsonl`, whatever the day's size.
- **SC-003**: A bound seat's traced tool call appends no `state.write` event.
- **SC-004**: With a cached line and a compute that blocks, `status --line` returns in
  under one second (budget 100 ms plus margin in the test).
- **SC-005**: The existing steward, traces and status tests pass unchanged.

## Assumptions

- The orchestrator notes for this item were not available, so no dry-run workspace was
  named; the failure was reproduced on a scratch workspace as above. The exact exception
  each builder hit was not captured; the spec fixes the one timeout on the path and the
  costs that cause the contention.
- "A timeout" is `TimeoutError`, today raised only by `state.lock_ex`'s bounded wait
  (30 s, unchanged). No new deadline is put on the hook: Python cannot interrupt a
  blocking read, and a shorter lock wait would lose more spans. "Exceeds the budget" in
  the acceptance is that bound.
- "Could not read" stays a finding with today's exits on `main`. #601 (committed on its
  branch, not on `main`) makes every traces failure a warning below strict; after both
  land the two cases still differ by event kind (`traces.gap` against `traces.slow`) and
  reason. `_strict(root)` is #601's helper: reuse it when `main` has it, otherwise add it
  with the same body so the later rebase is trivial.
- "The check is skipped under load" means the steward due check, an advisory nudge. The
  security inspection (canary and honeytoken) always runs: skipping it under load would
  let induced load hide a finding.
- "Under load" for the hook is `BUDGET_MS = 1000` of wall time already spent in `check`:
  a warm call takes 5 to 20 ms, the owner saw seconds, and a lower bound (design 10.6's
  50 ms is a CPU p95 benchmark, not a wall bound) would let one CI stall move a steward
  due in tests that pin its exact count. `LINE_BUDGET_MS = 100` leaves the other half of
  the status line's 200 ms wall for interpreter start and printing.
- The digest is a performance cache, not a trust surface: only the traces guard writes it
  and `protect_state` refuses agent writes; a forged or damaged value can at worst move a
  steward nudge. It is updated in its own `state.lock` hold right after the span append,
  because existing tests replace `state.append_jsonl` with two-argument fakes; a hook
  killed between the two leaves the digest one low.
- "Caches its text per heartbeat tick" means the watch's heartbeat writes the cache. The
  status line process never writes it, so there is no write per refresh and a stalled
  compute cannot leave the cache stale forever. Without a running watch there is no cache.
- `traces.slow` is a nudge like `traces.gap`, since both can mean a missing span. Doctor's
  `traces` row and the status gap count stay as they are (not asked).
- Companion issues: #645 does not touch these functions; #626's walk cost is respected by
  memoising the new invariant per posture with one workspace per posture.

## Out of scope

- Doctor reporting load or `traces.slow` counts.
- Other readers that count `traces.jsonl` lines once per command (`steward run`,
  `wuwei next`); they do not run per tool call.
