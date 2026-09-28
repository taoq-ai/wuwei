# Feature 015: Watch process and session lifecycle

## User Scenarios & Testing

### US1: Continuous supervision (P1)
The owner runs one watch per workspace. It writes a clock every 600 seconds,
observes active worktree HEADs through VCS, reports staleness after 900 seconds
without a commit or report, and runs obligations and trace scanning every 7200 seconds.

Acceptance: given no clock for 20 minutes, SessionStart and the next watch sweep
report the watch dead. Given a sweep, exactly one `watch: sweep` event carries
reply, visibility, staleness, unreadable and total owed counts. Missing scanner
support is unmeasured. Read failures never become zero obligations.

### US2: PR ownership wake (P1)
Every 120 seconds, poll only the union of raised and claimed day PRs. Compare head, checks,
mergeability, reviews, comments and threads against the persisted baseline.
Changes append reserved `pr.changed` events and set a persistent planner wake
marker. Stdout announces the change. The watch continues without re-arming.

Acceptance: new, gone, edited and changed PR evidence wakes once per change;
restart retains the baseline; a failed snapshot preserves that PR and records a
reserved read-failed event naming it, while other PRs are still compared. Only
whole-discovery failures increase the streak; the first failure before a baseline
or the fifth consecutive discovery failure ends the watch with exit 2.

### US3: Session continuity (P1)
SessionStart displays the existing memory payload and UTF-8 byte/token size,
watch health, prior-day unresolved process reservations and the wake marker.
PreCompact checks synchronous state/event consistency and records a flush event.
Stop blocks once per unseen wake marker and records its timestamp through a
reserved producer. It honours stop_hook_active; read failures remain non-blocking. Lifecycle checks only act in workspace scope.

Acceptance: clean, findings and unreadable cases return 0, 1 and 2 from checks;
SessionStart always exits 0 at the hook boundary, with diagnostics inside
additionalContext. PreCompact diagnostics never issue blocking decisions. Invalid
state/events fail closed as unmeasured with a reason. Unrelated projects pass.

## Requirements

- Stdlib Python 3.11+, external reads only through registered ports.
- Preserve harness check order: initial baseline before comparisons, successful
  reads before replacement, reset failure streak on success, clock before periodic
  obligations, failed discovery before any claim of an empty PR set.
- Reserve watch state and all producer events against generic CLI writes.
- Reuse locks, atomic writes, scope helpers and existing obligations evaluation.
- Configure intervals and owner/repository identities; ship service templates.
- Keep existing shell guards untouched and test the irrelevant-command bypasses.

## Key Entities

Reserved day `watch` state holds PR fingerprints, worktree observations, scheduler
marks, consecutive failures and a `wake` marker. Events carry counts and changed
field names, never comment bodies. A workspace process lock prevents duplicate watches.

## Success Criteria

Deterministic tests cover timing boundaries, restart, midnight, failures, source
harness changes, lifecycle exits, scope and trusted-writer refusals without network
or real external tools. The full repository suite passes.

## Assumptions

- New scope supersedes harness exit-on-change and omitted mergeability behavior.
- A successful empty discovery is valid; unlike an empty shell pipeline, the port
  provides typed evidence. Empty configured repositories require recorded day PR state.
- Active worktrees are running items with a `worktree`, plus worktrees in the
  logged briefs of running seats. `report_at` is an item report timestamp.
  The first observation starts the inactivity timer.
- Previous days' still-running seat reservations are orphan candidates, not proof
  that a PID remains alive. Do not kill or infer liveness from a reused PID.
- Wake markers accumulate changed PRs until Stop acknowledges wake.at in reserved
  watch.wake_seen_at. They grant no approval. Waking an idle session requires M5
  headless launch; this feature reaches a planner when its Stop hook runs.
- Call memory.lint(root) directly: it returns list[str]. A ValueError, including
  missing notes, becomes an unmeasured payload line. Until rebase brings the main
  implementation, tests use its list[str] signature.
- Any nonzero watch health forces a sweep in the same tick before the old clock
  gap is forgotten. SIGTERM sets an event so an active tick finishes its writes.

## Deferred

Memory lint implementation, process inventory/close reconciliation, PR action-deadline
policy and headless shepherd launch belong to their owning features. This feature
exposes the wake mechanism and orphan candidates needed for their integration.
