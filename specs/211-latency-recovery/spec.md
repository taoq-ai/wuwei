# Feature Specification: Hook latency budget and corrupt state recovery

**Feature Branch**: `211-latency-recovery`
**Created**: 2026-09-30
**Status**: Ready for implementation
**Input**: Issue #211, fix(core). Design sections 3.4, 9 and 10 (10.6 latency). Evidence:
the v0.5.0 operator dry run of 2026-09-30.

## Root cause (reproduced read-only on a copy of the dry-run workspace)

Measured through `bin/wuwei hook <event>` on the dry-run day (one approved item, one
claimed PR, worktree inside the workspace, fake `gh` on PATH), host load about 6 on 10 CPUs:

| Path | Wall median | Where the time goes |
|---|---|---|
| PreToolUse `ls` (baseline) | 52 to 66 ms | interpreter start and imports |
| Stop, planner turn | 230 to 310 ms | 6 sequential code-host subprocess reads per owned PR |
| SubagentStop, builder | 216 ms | 5 sequential code-host reads for seat-free discovery |
| PreToolUse `git commit` in worktree | 147 ms | 8 sequential git processes |
| PreToolUse `git push` | 221 ms | 16 sequential git processes |
| SessionStart | 114 ms | 3 sequential subprocesses, config parsed 5 times |

- Stop: `cli/wuwei/guards/stop.py:36` calls `pr_actions.check(root)`, which calls
  `evaluate` (`cli/wuwei/pr_actions.py:55`), which reads fresh code-host evidence for
  every owned PR on every planner turn end (`cli/wuwei/pr_actions.py:218` into
  `cli/wuwei/watch.py:276`: pr, reviews, comments, review threads, check runs, statuses).
  With a real code host each read is a network call, so the turn end costs seconds. The
  watch already polls the same evidence every `pr.poll_seconds` and persists each action
  episode with its deadline (`cli/wuwei/pr_actions.py:139-190`, `cli/wuwei/watch.py:305`).
- SubagentStop (builder): `cli/wuwei/guards/agent_launch.py:236` runs
  `dispatch.discovery('seat-free')`, which runs `discovery.intake` synchronously
  (`cli/wuwei/dispatch.py:211`), which reads code-host threads, PRs and checks
  (`cli/wuwei/discovery.py:66`).
- Commit and push: `cli/wuwei/guards/commit_push.py:62` and `:68` each call
  `vcs.commit_context`, which starts four git processes one after another
  (`adapters/vcs/git.py:342-354`); push adds `push_context` (head, symbolic-ref, three
  config reads, check-ref-format, all sequential, `adapters/vcs/git.py:357-434`) and
  `push_commits` (two). Each git process costs about 10 ms on the owner's host.
- SessionStart: `integrity.workspace_check` runs `git status` then `git log` one after the
  other (`adapters/vcs/git.py:573-583`); `workspace.load_config`
  (`cli/wuwei/workspace.py:373`) parses and validates the same TOML five times per hook.
- Corrupt state: a truncated `state.json` makes `state.read_state` raise
  `<path>: Unterminated string ...` (`cli/wuwei/state.py:120`) in every hook and command,
  with no way out: the writer keeps no snapshot (`cli/wuwei/state.py:211`), the events log
  holds write summaries, not state, and `wuwei state` has no recover action
  (`cli/wuwei/commands/state.py:10-21`). Stop then blocks every planner turn.

## User Scenarios & Testing

### User Story 1 - Hooks inside the latency budget (Priority: P1)

The owner works in a WUWEI workspace without the hooks slowing every turn: Stop,
SubagentStop, SessionStart and the commit and push checks answer within the budget.

**Independent Test**: the hook benchmark runs each path through `bin/wuwei` inside a seeded
workspace and prints p95 CPU and wall time for each.

**Acceptance Scenarios**:

1. Given the benchmark on a quiet host (or `WUWEI_BENCH=1`), when each of Stop (planner
   turn), SubagentStop (builder seat), SessionStart, PreToolUse `git commit` in a worktree
   and PreToolUse `git push` runs 20 or more times, then no path's p95 wall time reaches
   100 ms.
2. Given the watch measured every owned PR within two poll intervals and no action episode
   is past its deadline, when a planner turn ends, then Stop passes without any code-host
   call.
3. Given the watch record is missing, stale, incomplete, or shows an episode past its
   deadline, when a planner turn ends, then Stop reads fresh code-host evidence exactly as
   today and blocks on an overdue action.
4. Given a builder seat stops with the queue below `discovery.min_queue`, then SubagentStop
   records the discovery request without a code-host call, and the next watch tick runs
   the discovery intake once.
5. Given a busy host or CI, then the benchmark prints its measurements and load and skips,
   as the existing latency benchmark does.

### User Story 2 - Recover a corrupt state file (Priority: P1)

The owner can get the day going again after `state.json` is truncated or otherwise
unreadable, and a seat cannot do it for them.

**Independent Test**: truncate today's `state.json`, observe the message, run
`wuwei state recover` with host confirmation, then read state and run a hook.

**Acceptance Scenarios**:

1. Given a truncated state file, when any hook or command reads state, then the message
   names `wuwei state recover`.
2. Given a truncated state file and a usable snapshot, when the owner runs
   `wuwei state recover` in a host terminal and confirms, then today's state equals the
   last state the writer wrote, a `state.recovered` event is appended, and later state
   reads and hooks succeed (the day continues).
3. Given a seat, when it runs `wuwei state recover` through agent tools inside a workspace,
   then the call is refused with a message that recovery is an owner action on the host.
4. Given no terminal to confirm on, then recover exits 2 and changes nothing; given the
   owner declines, it exits 1 and changes nothing.
5. Given no snapshot, or an unreadable or invalid snapshot, then recover exits 2 naming
   the reason and leaves `state.json` untouched.
6. Given a readable `state.json`, then recover exits 1 ("nothing to recover") and changes
   nothing.

### Edge Cases

- Day close (`close_requested`) keeps fresh code-host reads for every closing check.
- A PR raised after the last watch poll is not in the watch record, so Stop reads live.
- A watch poll with any unreadable PR does not refresh the record's measured time.
- A parked PR whose episode is past its deadline keeps the live path (correct, slower).
- A failed deferred discovery is recorded once as `discovery.unmeasured` by the watch and
  is not retried until the next request.
- Writes and edits of the snapshot through agent tools are refused like `state.json`.
- A concurrent writer during recovery: the restore happens under the state lock after
  re-checking that `state.json` is still unreadable and the snapshot is unchanged.

## Requirements

- **FR-001**: The hook benchmark covers Stop, SubagentStop, SessionStart and PreToolUse
  commit and push inside a seeded workspace and asserts p95 wall time under 100 ms under
  the existing quiet-host rule; it prints p95 CPU and wall for every path.
- **FR-002**: Stop at a planner turn end uses the watch's persisted measurement when it
  covers every owned PR, is at most two poll intervals old, and has no episode past its
  deadline; otherwise it evaluates fresh evidence as today. Day close is unchanged.
- **FR-003**: The watch records when a poll measured every owned PR; a poll with an
  unreadable PR does not.
- **FR-004**: A builder seat stop records the seat-free discovery request; the watch runs
  a pending request on its next tick and records failures as `discovery.unmeasured`.
- **FR-005**: Independent git reads in one adapter operation run concurrently
  (commit context, push context, workspace changes). Results and errors are unchanged.
- **FR-006**: Configuration is parsed and validated once per content per process.
- **FR-007**: Every state read failure message names `wuwei state recover`.
- **FR-008**: Every state write also writes a read-only snapshot of the written state.
- **FR-009**: `wuwei state recover` restores today's state from the snapshot after host
  confirmation, appends `state.recovered`, and fails closed (exit 2) when the snapshot is
  missing or unusable or confirmation cannot be asked; exit 1 when declined or when state
  is readable.
- **FR-010**: Agent tools cannot run recovery or write the snapshot inside a workspace.
- **FR-011**: No guard refuses less than today; every existing test passes unchanged,
  except where its expected message gains the recovery hint.

### Key Entities

- Watch measurement: the time the watch last read every owned PR, stored in the watch's
  reserved state with its PR fingerprints and action episodes.
- State snapshot: today's last written state, next to `state.json`, read-only, written
  only by the state writer.

## Success Criteria

- SC-001: On the owner's quiet host, each of the five benchmarked paths has p95 wall time
  under 100 ms (owner target 50 ms where reachable).
- SC-002: A planner turn end with a fresh watch record makes zero code-host calls.
- SC-003: A builder seat stop makes zero code-host calls.
- SC-004: A truncated state file is recovered by one owner command, after which the next
  hook and state read succeed; a seat attempt is refused every time.

## Assumptions

- The budget is wall time, the latency the owner feels and the unit of the dry-run
  evidence. CPU p95 is printed, not asserted, for these paths; the existing 10.6 CPU
  50 ms assertion for the bare PreToolUse and PostToolUse fixtures stays as it is. Git is
  a subprocess on every commit and push check, so CPU cannot fall under 100 ms without
  dropping checks; concurrency lowers wall time without dropping any.
- The benchmark seeds a fresh watch record, so Stop measures the fast path; the live path
  stays covered by the existing Stop and PR action tests.
- Day close is once a day and must be exact, so it is outside the per-turn budget.
- Deferring seat-free discovery to the watch is allowed by design 5.7 (the lead discovers
  when a seat frees, not inside the hook). With a dead watch it waits until the watch
  runs; SessionStart already flags a dead watch.
- `events.jsonl` payloads are summaries and cannot rebuild state, so recovery uses the
  writer's snapshot of the last written state; the event log records the recovery.
- Recovery covers today's day directory, the one hooks and the day use. A missing
  `state.json` with a snapshot present is also recoverable.
- Owner-only follows the existing pattern for `wuwei integrity reconfirm`: the Bash guard
  refuses the call from agent tools inside a workspace, and the command asks the owner to
  type a short token on the host terminal. A same-user process can still forge files
  (design 9.1).
- No new config keys: the freshness window is two `pr.poll_seconds`.

- A missing `state.json` next to a snapshot is treated as unreadable (the read names the
  recovery command) so the next write cannot overwrite the snapshot with fresh defaults.
- FR-011 exception: existing tests that counted atomic renames or relied on the arrival
  order of git reads in replay fakes were updated for the snapshot write and concurrent
  reads; no refusal or finding they assert changed.

## Deferred

- Day close still reads the same PR evidence twice (closing and obligations); not in the
  per-turn budget.
- A development checkout install measures git on every PreToolUse (integrity cache); the
  owner runs release installs, so it is not in this benchmark.
- On macOS `/usr/bin/git` is the Xcode shim, about 5 ms more per process than the real
  binary; the push check still starts 13 git processes in 4 rounds.
