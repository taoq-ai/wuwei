# Feature Specification: Heartbeat: the watch proves the system is alive and behaving, not only running

**Feature Branch**: `287-heartbeat`
**Created**: 2026-10-01
**Status**: Ready
**Input**: GitHub issue #287, "feat(ops): heartbeat: the watch proves the system is alive and behaving, not only running". Closes the scope of #59 (dead-man switch).

## Problem (reproduced)

Liveness today is a clock line and nothing else. Reproduced read-only on `main` (e4b3da0) in a
scratch workspace made with `bin/wuwei init`:

- `bin/wuwei watch --once` wrote its `watch: clock` line and exited 0 while every PreToolUse
  call through `bin/wuwei hook PreToolUse` exited 2 (`ls -la` included), because the cached
  integrity verdict was not clean. Between sweeps nothing on the status line said that tool
  calls were being refused; the only signal was the integrity page from the sweep, which runs
  every `watch.sweep_seconds` (7200 s).
- With a clean cached verdict, `git push --force origin main` exited 2 and `ls -la` exited 0,
  as they should. Nothing measures that either answer is still the right one.
- Each probe-style refusal through the hook appended a `hook.refusal` event (15 after a few
  manual runs), so a naive probe every tick would add about 2,900 refusal records a day and
  distort `promotion.adherence_counts` (`cli/wuwei/promotion.py` line 320).

Root causes, with file and line on `main`:

1. `watch.health` (`cli/wuwei/watch.py` lines 45 to 65) decides alive, dead, off or
   unmeasured from the age of the newest clock line only.
2. `watch.tick` (`cli/wuwei/watch.py` lines 396 to 397) writes the clock line unconditionally:
   a process that is up but whose hooks allow everything, refuse everything, or hang still
   writes it.
3. `status.scan` (`cli/wuwei/commands/status.py` lines 48 to 49 and 117 to 129) reads only
   the clock lines, so `status --line`, `nudges`, session start and the phone status cannot
   show behaviour.
4. Integrity is re-measured only at SessionStart and in the sweep (`cli/wuwei/watch.py` line
   203). In between, every guard trusts `integrity.cached` (`cli/wuwei/integrity.py` lines
   178 to 194), which in a release install (no `.git`) never re-hashes: a plugin file edited
   after the verdict passes every hook until the next sweep.
5. There is no external dead-man ping (`docs/site/remote.md` line 339 says so), so nothing
   off the host notices a host that stopped behaving.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Heartbeat on demand and on every watch tick (Priority: P1)

The owner runs `bin/wuwei heartbeat` and sees one line per probe with ok, failed or
unmeasured and the measured value. The watch runs the same probes on every tick and writes one
`heartbeat: clock` line carrying the results.

**Why this priority**: it is the measurement every other story reads.

**Independent Test**: in-process `heartbeat.measure` with the fixed probe adapter faked, plus
one smoke run through the real launcher on a seeded workspace.

**Acceptance Scenarios**:

1. Given a healthy workspace (clean cached verdict, valid config, no stuck lock, enough free
   memory), when `heartbeat` runs, then it prints every probe in the table as `ok` with its
   value and exits 0.
2. Given the watch tick, when it runs, then it appends exactly one `heartbeat: clock` event
   whose payload carries `health`, every probe's `result` and `value`, `drift`, `page` and
   `ping`, and stores the same record under the reserved `watch.heartbeat` state key.
3. Given any probe that cannot be measured (for example `adapters.host = "none"`), then that
   probe is `unmeasured`, never `ok`, and `heartbeat` exits 2 when nothing failed.
4. Given the on-demand command, then it writes no state, appends no event and sends no ping.

### User Story 2 - Health on the status line, one page per failure (Priority: P1)

`status --line` gains `health ok`, `health degraded` or `health unmeasured`. The first failed
probe pages once with its name and value; the page clears when the probe passes again.

**Why this priority**: the owner reads the status line, the cockpit and the phone, not the
watch log.

**Independent Test**: `status.snapshot` and `status.line` over hand-written day events, plus
the tick tests above.

**Acceptance Scenarios**:

1. Given a healthy workspace after one heartbeat, then `status --line` shows `health ok` and
   there is no heartbeat page.
2. Given a plugin file tampered after the cached verdict, when the next heartbeat runs, then
   the integrity probe is `failed` naming the file, `status --line` shows `health degraded`,
   `nudges` lists exactly one heartbeat page whose reason names `integrity`, the dead-man ping
   is not sent, and a later heartbeat with every probe ok clears the page.
3. Given a guard stubbed to allow everything (the mutation harness: the copied plugin's hook
   discovers no guards), when the heartbeat runs through the real launcher, then the
   `refused` probe fails with value `exit 0` and the page names `refused`.
4. Given a probe that was `ok` in the previous heartbeat and is `failed` now, then the record
   lists it under `drift` and the page reason starts `behaviour drift:`.
5. Given no heartbeat line today, then the status line has no `health` part (the watch part
   already says `watch off` or `watch dead`). Given a heartbeat line while the watch is not
   alive, then health is `unmeasured` and there is no heartbeat page.

### User Story 3 - Dead-man ping only when healthy (Priority: P2)

With `watch.ping_url` set, each heartbeat whose health is `ok` sends one HTTPS GET to it, so
an external cron monitor alerts the owner's phone when the host is down or misbehaving.

**Why this priority**: the only liveness signal trusted while the owner is away (spec 15.8).

**Independent Test**: fake adapter `ping`; assert calls and the recorded `ping` field.

**Acceptance Scenarios**:

1. Given `watch.ping_url` set and every probe ok, then exactly one ping is sent and the record
   says `ping: sent`.
2. Given any probe failed or unmeasured, then no ping is sent and the record says
   `ping: withheld`.
3. Given the ping endpoint unreachable or answering an error, then the heartbeat still writes
   its record with `ping: failed`, prints `heartbeat ping failed: <host>: <error>` to the watch
   log, and the tick goes on. The URL path and query never appear in a log, event or state.
4. Given `watch.ping_url` empty (the default), then nothing is sent and the record says
   `ping: off`.

### User Story 4 - Cheap, side-effect free, off the hook path (Priority: P1)

**Acceptance Scenarios**:

1. Given the watch tick on an M-series Mac, then the heartbeat adds under 200 ms wall p95
   (asserted with `WUWEI_BENCH=1`, printed and skipped otherwise; ping off).
2. Given any hook path, then nothing is added: no hook or guard module imports the heartbeat,
   and the hook latency benchmarks are unchanged.
3. Given the probes, then they write only inside `.wuwei/`, run no git write, touch no
   configured repository, make no code-host or model call, and spend no tokens. Their hook
   refusals are not recorded as `hook.refusal` events.

### Edge Cases

- A stuck `state.lock`: the `state` probe fails after 1 s naming the lock. The record write
  then waits on the same lock (30 s bound in `state.lock_ex`); if that times out, the tick
  prints `heartbeat unmeasured: ...` and returns 2 instead of stopping the watch.
- A launcher call that hangs: killed after 10 s; the probe is `unmeasured` with value
  `timeout`.
- First heartbeat of the day: no prior record in today's state, so no drift is reported.
- `adapters.host = "none"`: the memory probe is `unmeasured` without calling the adapter (the
  none adapter appends an `adapter: none` event, a nudge, on every call).
- A malformed `heartbeat: clock` payload in events: health `unmeasured`, no page.
- A ping URL that is not `https://`: `ping: failed` with reason `ping URL must be https`,
  nothing sent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The probe table is module data in `cli/wuwei/heartbeat.py`, in this order, and
  `docs/site/reference.md` lists every row:

  | Probe | ok when | value |
  |---|---|---|
  | `refused` | `hook PreToolUse` with Bash `git push --force origin main` exits 2 | `exit N`, plus the first stderr line when not ok |
  | `allowed` | `hook PreToolUse` with Bash `ls -la` exits 0 | `exit N`, plus the first stderr line when not ok |
  | `state_write` | `hook PreToolUse` with Write to today's `.wuwei/days/<day>/state.json` exits 2 | `exit N` |
  | `state` | `state.lock` taken within 1 s and today's state reads | milliseconds waited, or the error |
  | `integrity` | cached verdict clean and no installed plugin file newer than it | the integrity reason |
  | `config` | `config.toml` loads and every selected adapter has its credential variables | missing names |
  | `clocks` | watch and listener health are alive or off | the dead or unmeasured message |
  | `status_line` | `status --line` exits 0 within 200 ms wall | milliseconds |
  | `planner` | no planner today, or the planner session is registered and not stale | idle seconds |
  | `memory` | free memory at or above `host.free_memory_mb` | MiB free |

- **FR-002**: Hook probes run through the real launcher (`bin/wuwei hook PreToolUse`) as
  separate processes started together, with payload `session_id` `wuwei-heartbeat` and cwd
  `<workspace>/.wuwei`. `status --line` runs the same way. Process launches live only in the
  fixed adapter `adapters/watch_service.py`, with a closed argument allowlist.
- **FR-003**: Each probe result is `ok`, `failed` or `unmeasured` with its value. Health is
  `degraded` when any probe failed, else `unmeasured` when any probe is unmeasured, else `ok`.
- **FR-004**: `bin/wuwei heartbeat` prints one `<probe>: <result> <value>` line per probe and
  exits 0 ok, 1 degraded, 2 unmeasured or could not run. It writes nothing and sends nothing.
- **FR-005**: Every watch tick runs the heartbeat after the clock step and writes one
  `heartbeat: clock` event with the record through the shared writer, storing it under
  `watch.heartbeat`. The tick's return code includes the heartbeat code. Any error is printed
  as `heartbeat unmeasured: <reason>` and returns 2; it never stops the watch.
- **FR-006**: Drift: a probe `ok` in the stored previous record and `failed` now is listed in
  `drift`, printed as `heartbeat: behaviour drift: <probe>`, and prefixes the page reason with
  `behaviour drift: `.
- **FR-007**: `status.scan`, still one pass over the day's events, keeps the last
  `heartbeat: clock` payload. Snapshot field `health` is that payload's health while the watch
  is alive, `unmeasured` when the watch is not alive or the payload is malformed, and None with
  no heartbeat line today. When health is `degraded` there is exactly one page with source
  `heartbeat` and the payload's `page` reason. `status --line` appends `health <value>` after
  the watch and listen parts when the field is not None.
- **FR-008**: `heartbeat: clock` is silent in `signal.SILENT`, attributed to `wuwei watch` in
  `EVENT_PRODUCERS`, and documented.
- **FR-009**: `watch.ping_url` (string, default empty) is a new config key. A heartbeat with
  health `ok` and a non-empty URL sends one GET through the fixed adapter with a 5 s timeout;
  only the host name is ever logged. Failures are recorded and printed, never fatal.
- **FR-010**: `bin/wuwei hook` does not append `hook.refusal` for a PreToolUse refusal whose
  payload `session_id` is `wuwei-heartbeat`. Nothing else on the hook path changes.
- **FR-011**: `integrity.fresh(root)` returns `integrity.cached(root)` unless that is clean and
  the cached verdict records no checkout; then it walks the installed plugin (skipping `.git`,
  `__pycache__` and `.pyc`, as `inventory` does) and returns exit 1 naming the first file whose
  mtime is newer than `verdict.json`. `cached` itself (the hook path) is unchanged.
- **FR-012**: The `config` probe uses the same credential requirements as `config check`,
  through one shared helper in `cli/wuwei/commands/config.py`; it makes no code-host call.

### Key Entities

- **Heartbeat record**: `{health, probes: {name: {result, value}}, drift: [name], page, ping}`;
  the payload of `heartbeat: clock` and the value of `watch.heartbeat` in day state.

## Success Criteria *(mandatory)*

- **SC-001**: A tampered plugin file, a hook that allows everything, or a hook that refuses
  everything shows as `health degraded` with one named page within one watch tick (60 s by
  default), not at the next sweep (up to 2 h).
- **SC-002**: The heartbeat adds under 200 ms wall p95 to a watch tick on an M-series Mac.
- **SC-003**: The hook latency benchmarks are unchanged.
- **SC-004**: An external monitor stops receiving pings within one tick of any probe failing.

## Assumptions

- "On every tick" means every watch loop iteration (60 s with default settings). The record
  is small (ten probes); the watch already appends about two events a minute.
- "`state get` round trip" is implemented in process as taking `state.lock` with a 1 s bound
  and reading today's state; a CLI subprocess would add about 50 ms for no extra coverage.
- "`config check` passes" covers the offline part of `config check` (schema, credential
  variables, `codex.command`, `control_plane.owner` when inbound is set). The code-host parts
  (gh auth, branch protection, token scopes) are network calls and stay in `config check`.
- "`status --line` within its budget": the documented budget is 50 ms CPU p95 over many runs.
  A single run measured next to three concurrent hook probes cannot be held to a p95, so the
  probe fails above 200 ms wall (a module constant, not config). The p95 budget stays enforced
  by the latency benchmarks.
- The refused probe asserts exit 2 only. With cwd `.wuwei`, which is not a configured
  repository, the commit/push guard refuses the push as "repository is not configured"; the
  probe still catches an allow-all or crashed hook, which is its purpose, and never needs a
  real repository.
- Integrity freshness uses file mtimes: tamper evidence for accidental and third-party edits,
  consistent with spec 7.1 and 9.1 (a process running as the owner can also reset mtimes). In
  a development checkout the existing git HEAD and clean-tree comparison in `integrity.cached`
  already covers freshness, so the walk is skipped there.
- A stale planner session (no hook activity for `sessions.stale_seconds`) degrades health,
  pages and withholds the ping, as the issue lists it; the existing stale-planner nudge stays.
- The ping URL comes from config (`watch.ping_url`), as the orchestrator notes require; the
  docs say to keep it private. No environment override is added.
- The ping is sent on every healthy tick (60 s) instead of every 5 minutes (spec 15.8); hosted
  cron monitors accept this, and it ties the ping exactly to the heartbeat. The 200 ms budget
  is measured with the ping off; the ping is bounded by its 5 s timeout.
- The ping moves from the listener (spec 15.8, #59) to the watch heartbeat, as the issue says.
  #59's docs item (naming hosted monitors) is a short paragraph in the reference.
- No drift detection across midnight: the first heartbeat of a day has no prior record.
- The on-demand command is read-only, so the owner can run it any time without moving pages.
