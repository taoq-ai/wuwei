# Feature 016: day-close Stop guard

## User stories

### US1 (P1): Close only after obligations and retro land

As planner I need a refusal naming unfinished work so day close cannot silently drop it.

Acceptance scenarios:
1. Given one owed thread, closing refuses and names its PR and thread.
2. Given a retro claiming an applied charter amendment without a matching commit today,
   closing refuses even though the retro file exists.
3. Missing Applied or Proposed sections, empty collected notes, or more verdict retro
   notes than collected sentinel notes each refuse, in that order after commit checks.
4. Applied amendments require a committed changelog line dated today. With no amendments,
   close does not require a Git repository for the workspace.
5. Read errors, malformed evidence and unavailable ports return 2 with a reason.

### US2 (P1): Anchor owned PRs at every planner turn

Acceptance scenarios:
1. An owned PR with an overdue action and no verified parking decision refuses Stop,
   naming the PR, observed state and action.
2. At day close each owned PR must be merged, parked or explicitly carried tomorrow.
3. A closed, unmerged PR is not treated as merged. A local owner claim is not approval.
4. Repeated Stop, watch restart and repeated observations cannot reset an overdue action.
5. Without a recorded action, waiting for review does not block turn end. Watch neither
   synthesizes inspection actions nor inherits yesterday's actions.

### US3 (P1): Apply only to WUWEI work

Acceptance scenarios:
1. Unrelated projects and non-planner turns pass without measuring day-close conditions.
2. Configured repos and worktrees remain in scope. Hook refusals translate to block JSON.
3. Stop retry flags and generic state/event writes cannot bypass the guard.

## Requirements

- Reuse the obligation evaluator, watch ownership union, shared scope helpers, locked state
  writer, decision reader, retro capture and ports.
- Preserve source retro-check refusal order. Report every applicable finding.
- Runtime uses Python standard library only. Core does not invoke external tools.
- Guard and CLI results are 0 clean, 1 findings, 2 unmeasured; failures block.
- Scope contains no Bash matcher or shell parsing; unrelated Bash remains untouched.

## Assumptions

- `bin/wuwei close` is the explicit close request because no report/close producer exists.
  It records a reserved day-close request, checks immediately and makes later planner Stops
  recheck fresh evidence. Only the recorded close request triggers day-close checks.
- Existing retro.captured events and their evidence files are the collected note ledger,
  replacing the old harness notes.jsonl. Duplicate captures count once.
- Retro is today's retro/YYYY-MM-DD.md. Exact `none` in Applied means no amendment; it
  cannot suppress other listed amendments. Config selects charter repository, paths,
  and changelog. Defaults use workspace charters and `.wuwei/memory/CHANGELOG.md`.
- Action production, completion and rearming belong to #120. Missing actions are not overdue;
  explicitly recorded actions are checked without resetting their deadlines.
- Parking and carry require an owner-routed decision with `Decided-by: owner`, no seat
  outcome in `decision_outcomes`, and a fresh non-bot comment authored by the
  configured owner, containing exactly `WUWEI <parked|carried> <PR> <decision> <day> <decision-fingerprint>`.
  The fingerprint binds the complete decision text. Carry applies to day close only and does not waive an already overdue turn-end action.
- PreToolUse refuses raw parking/carry markers in any tool input, including Bash and body
  file writes, within workspace scope. Markers must be posted by the owner.
- Stop retry flags do not waive these correctness checks. Every planner session registered
  today remains covered after a handoff; the existing reserved plan.session log identifies them.

## Success criteria

Both issue acceptance cases have failing-first in-process tests. All applicable retro refusals,
0/1/2 exits, scope and bypass cases pass without network or real git/gh. The full suite passes.

## Deferred

#120 owns precise PR action classification, action completion/rearming, review windows,
escalation, cockpit and carry-forward scheduling. This issue supplies the action consumer
and verified disposition entry point. Weekly consolidation belongs to its own feature.
Report skill integration belongs to its own feature; it must invoke the close command.
