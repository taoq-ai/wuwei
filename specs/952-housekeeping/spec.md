# Feature Specification: Background housekeeping

**Feature Branch**: `952-housekeeping`
**Created**: 2026-10-13
**Status**: Implemented and verified after round 3
**Input**: GitHub issue #952, record background work and safely find leftovers.

## User Scenarios & Testing

### User Story 1 - Reap owned leftovers (Priority: P1)
The planner records background commands and retires them when their purpose ends.
Independent test: a recorded wait remains after its PR merges and receives TERM, then
KILL only if the same process survives the grace period.
Acceptance scenarios:
1. A merged, parked or done item, closed day, or cached non-open PR makes its recorded process obsolete.
2. Live PR waits share one purpose within the current session and day; keep the oldest and reap obsolete waits.
3. A missing process is harmless; a reused PID or changed command is never signalled.

### User Story 2 - Surface unowned leftovers (Priority: P1)
The owner sees workspace orphans and finished worktrees in one plain listing with exact commands. No approval is requested or spent.
Independent test: the hung-init git cat-file child with parent 1 inside a worktree is
listed with its exact kill command and receives no signal. Outside processes are ignored.
Current stale seats use seat stop --verdict, never process termination. Prior-day seats are listed for inspection.

### User Story 3 - Integrate the day loop (Priority: P2)
SessionStart and next show actionable current findings; doctor processes and close show historical findings. Next offers a housekeeping duty,
and close reaps owned background work before invoking the retro steward.
Independent test: lifecycle callers reach the same check; close invokes cleanup first.

### Edge Cases
Missing cached PR evidence is not evidence of closure. An unreadable process table
is an unmeasured finding (housekeeping exit 2); next still derives its normal action. Command and process start identity are checked before every
signal. Missing or unreadable transcripts are not activity. Worktrees are never deleted.

## Requirements
- FR-001: Record PID, observed command, purpose and start identity/time for next PR waits and sleep timers only in the day directory.
- FR-002: Derive obsolete processes and duplicate waits from local state across retained days without GitHub calls.
- FR-003: TERM only matching owned processes, wait a bounded grace period, recheck identity before KILL.
- FR-004: List unowned workspace/worktree orphans and terminal-item worktrees with exact commands in one plain owner listing.
- FR-005: Flag running seats whose age and latest transcript inactivity exceed the configured timeout, with the existing recovery command.
- FR-006: Reuse the shared check in SessionStart, next, doctor processes and close before retro.
- FR-007: Preserve three-state exits and record successful reaping for reports.

## Key Entities
Process start event: PID, command, process start identity, purpose, timestamp, session id and day.
Finding: kind, reason, exact command, day and optional owned process identity.

## Success Criteria
All seven issue scenarios pass with fake OS and adapter boundaries, without network
or signals to real processes. Only PR waits and sleep timer rows use the recording entry.
No unowned process or worktree is automatically changed.

## Assumptions
- Clarify completed without questions, as instructed. No owner design file changes.
- Use existing host.reservation_timeout_seconds (default four hours) for age and inactivity.
- Grace period is one second, bounded for the planner. No process groups are killed.
- The wrapper accepts only exact wuwei pr wait and integer sleep timers; one-shot commands remain direct.
- Live PR waits duplicate the same polling purpose only within their session and day; no PR snapshots are recorded.
- Process start identity supplements PID and exact command, protecting same-command PID reuse.
- macOS uses native lsof for orphan cwd (ps lacks cwd); Linux uses procfs. Failed reads are unmeasured.
- External cleanup and prior-day seats are a plain listing, with no Yes or fabricated clock. Prior-day Codex-only jobs are omitted.
- Current Codex-only builds retain the existing saved-job resume path.
- Orphan cwd reads run only in doctor processes and close. Active worktrees and our ancestors are excluded.
- Per-process read errors remain findings; next continues deriving the day. Failed cleanup is recorded once and is no longer an automatic duty.
- Signal checks inspect only the target PID with a C locale; signalled zombies are reported honestly.
- Close checks unresolved work before treating all recorded background purposes as ended.
- Cleanup receipts belong to the current day and identify the source day.
- Explicit impacted test files replace the constitution's bare full-suite command as instructed.

## Round 2 requirements
- FR-008: A live needed recorded PR wait suppresses new waits across repeated next calls. Duplicate reaping keeps that oldest wait.
- FR-009: Historical seats and finished worktrees appear only in doctor --section processes and close, never next (including --housekeeping) or SessionStart.
- FR-010: The background flag takes no item or purpose. Runtime accepts only exact PR waits and ASCII integer timers; forged hook payloads are refused before recording or dispatch.
- FR-011: SessionStart prints the same recorded wrapper as next without resolving seats or writing state. Host none skips optional fast process inspection without events or a failing orientation exit; explicit inspection remains unmeasured.
- FR-012: Unrecorded orphans require a resolved cwd inside the workspace. Those outside recorded worktrees are listed at most once per identity per day across doctor and close. Worktree orphans remain inspectable. No outside-workspace process receives a kill suggestion.

## Round 2 assumptions and design reconsideration
- Owner explicitly requested this additional fix round. Keep the existing implementation and narrow the shared check rather than grow a subsystem.
- Proposed design clarification: historical cleanup belongs to explicit process inspection and close; optional host none inspection does not fail SessionStart. The owner-only design document stays unchanged.
- A needed live PR wait is status, not a finding. Its identity is returned from the shared housekeeping scan for next to consume.
- Daily orphan listing receipts use existing day events and PID plus start identity. Receipts are written only during explicit inspection; normal next and SessionStart stay read-only.
- Workspace containment applies even to recorded worktrees outside the root. New process records have no constant item; old item fields remain readable for existing timers.

## Deferred
None.

## Owner-authorized design reconsideration
The review follow-up replaces the broad background trampoline with ownership of only
PR waits and timers. Broad wrapping leaked guard authority and interrupted one-shot
state writers. The owner explicitly authorized this narrower design and removal of
native exec and fabricated prior-day recovery clocks. The owner design spec is unchanged.

## Round 3 requirements and assumptions
- FR-013: Close prints unmeasured housekeeping findings and continues to the steward and closing.check. Only current seat/build findings or a reap that failed during this invocation stop this stage of close. Historical cleanup failures remain informational.
- FR-014: Each new background record includes the calling session id and day. Only a live PR wait from the current session and day suppresses another wait. Other-session and prior-day waits are obsolete and may be reaped only after the existing recorded identity checks.
- FR-015: Next housekeeping refuses positional arguments even when background is also set, before measurement, recording or cleanup.
- Clarify completed by recommendation: use the existing session identity helper; missing session ids compare as None outside a session. Legacy records use their containing day and an absent session id. With a known current session, a legacy wait cannot suppress it.
- The owner explicitly authorized round 3 and the close exception to the general exit-2 rule for optional process inspection. Housekeeping still returns unmeasured; close prints it and follows its own obligations. The owner design spec stays unchanged.
- Design reconsideration: workspace-wide polling deduplication ignored the session that receives completion. Scope the existing record to its notification recipient and day, without a new scheduler or subsystem.
