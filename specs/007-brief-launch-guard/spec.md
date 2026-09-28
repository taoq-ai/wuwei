# Feature 007: Briefs and launch guard

## User scenarios

### US1: Trustworthy briefs (P1)
The planner writes a unique brief with current evidence before dispatching a seat.
Acceptance: unresolved ruling D-ABC-9 refuses; resolved D-ABC-1 stamps its ruling.
SLICE refuses declared, changed or untracked protected paths; FULL persists and is
honoured by subsequent briefs. A gate brief for an item in implement refuses.

### US2: Safe launches (P1)
Acceptance: a launch without a logged brief refuses; running seats at CAP refuse
with the count. A gate launch refuses a live builder or dirty worktree, even if the
brief was written before those conditions changed. Low or unmeasurable memory blocks.

## Requirements

- Write briefs under days/<date>/briefs with charter paths, clock time, seat policy,
  worktree status, HEAD, merge-base, prior branches, fresh PR head and gate row.
- Preserve source refusal order: existing name, inline verdict, repeated verdict path,
  invalid track, dirty gate tree, protected SLICE paths, gate phase/live builder,
  unresolved rulings. Failed reads are exit 2; findings are exit 1; success is exit 0.
- Resolve rulings from current/prior days, worktree specs and gate_policy, including
  numbered ranges; stamp ruling text and status. Gate verdicts are not ruling sources.
- Log brief written only after a complete file exists, using the state writer.
- Scope guards to a WUWEI workspace before parsing launch input. Only charter stems
  (optionally plugin-prefixed) or an explicit wuwei: prefix require a brief. Other
  Agent types, including a missing or empty subagent_type, pass before brief, state
  or configuration parsing.
- Bind launches to the exact logged brief and role; reject missing, modified or
  mismatched briefs and malformed relevant inputs. Log head with every worktree brief
  and refuse if its current HEAD differs. Recheck gate safety and host limits at launch.
- Default seats to an empty object. Check capacity and brief reuse, then record the
  running reservation under the state lock with id, role, item, brief, head and start time.
  Only SubagentStop releases reservations. Reserve seats through state.RESERVED so
  generic state writes cannot change them; reserve the seat stood down event kind.
- Reservation status is liveness evidence. Stale running reservations count toward
  capacity and are named in refusals after host.reservation_timeout_seconds (default
  14400). They do not independently block other items. Never silently expire a reservation.
- Available memory is free + inactive + speculative pages on Darwin and MemAvailable
  on Linux. Missing or unparseable measurements return exit 2.
- Reuse ports for external reads, with no external process calls from core code.
- Keep configurable repository refs, branch patterns and protected path patterns.

## Assumptions

- Current phases gate, delta, raised and merged replace the source's legacy gate phases.
  Unknown gate items refuse instead of bypassing the current state lifecycle.
- Sentinel roles always imply gate, preventing omission of --gate from bypassing checks.
- Agent prompt starts with `WUWEI brief: <workspace-relative brief path>`; its
  subagent_type matches the logged role, optionally prefixed by the plugin name.
- Seat ids are brief names. Runtime-generated ids are correlated at SubagentStop
  using the initial WUWEI brief marker in the agent transcript, including its day.
  Stop role must match. Missing transcripts and unmatched stops log an event and
  return 0 without releasing a reservation; reservation cleanup never blocks a stop.
  CAP counts builders, as section 5.3 requires; host.seats caps all running roles.
  A recorded seat name or seat-launched event prevents reuse of its brief.
- Worktree is supplied explicitly or via the item; gate worktrees are mandatory.
- Merge-base uses the configured local reference (default origin/main). Only PR
  reads require network freshness. repos[].default_branch supplies branch configuration.
  Body PR references use configured repository names. full_path_patterns defaults to
  an empty list in the schema; workspace owners supply their protected paths.
- Source engagement-specific test environments, login defaults and tool coaching are
  removed. The generic runtime/environment preflight belongs to its adapter issue.

## Success criteria

All acceptance cases pass without network or installed external tools. Refusals leave
no brief or brief-written event. Header evidence is reproducible with fake ports;
launch checks cover exits 0, 1 and 2 and metadata/path/role bypass attempts.

## Deferred

PR obligation sweeps, arch-delta scope generation and runtime-specific import preflight
belong to their own issues. Owner release of stale reservations needs a dedicated
command that refuses when run by a seat. That command is a follow-up outside #7;
SubagentStop remains the only automatic release.
