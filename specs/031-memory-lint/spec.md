# Feature Specification: Memory lint

**Feature Branch**: `031-memory-lint`  
**Created**: 2026-09-28  
**Status**: Draft  
**Input**: Issue #31 and amendment #75.

## User Scenarios & Testing

### User Story 1: Detect stale and oversized notes (Priority: P1)

A seat runs `wuwei memory lint` before using memory and sees actionable findings.

**Acceptance Scenarios**:

1. Given a body dated after its summary, when lint runs, then it reports the stale summary.
2. Given a note above `memory.note_line_cap`, when lint runs, then it reports the size; at the cap it stays clean.
3. Given a state note with more than `memory.state_entry_cap` dated entries, when lint runs, then it reports log-shaped content.
4. Given an intake note without outbound links or a promoted proposal, when lint runs, then it reports unrouted intake.

### User Story 2: Identify unused notes (Priority: P1)

After probation, a never-loaded note is reported as an archive candidate.

**Acceptance Scenarios**:

1. Given an active note created more than `memory.probation_days` working days ago and no trace of a seat reading it, lint reports an archive candidate.
2. Given a recorded seat Read of that note, lint does not report the candidate.
3. Given an unreadable note, configuration, or trace, lint exits 2 with a reason.

## Requirements

- FR-001: Export `memory.lint(root=None)` returning a list of findings for SessionStart reuse.
- FR-002: `wuwei memory lint` exits 0 clean, 1 with findings, 2 if it could not run.
- FR-003: Reuse `parse_note`, `workspace.load_config`, and the trace shape from PostToolUse.
- FR-004: Ignore archived notes for active-memory findings.

## Assumptions

- Dates are ISO `YYYY-MM-DD` tokens; a summary is stale only when it has an ISO date earlier than the latest valid ISO date in the body. Undated summaries cannot be compared.
- State and intake notes are identified by slug `state` or `intake`, or slugs ending `-state` or `-intake`.
- A dated entry is a Markdown heading or line beginning with an ISO date. The default threshold is three entries.
- An outbound link is a Markdown link or wiki link pointing to another note. A proposal counts as promoted when its evidence path names the intake note and action `add`, `patch`, or `fold` appears in `memory/ledger.jsonl`.
- Probation uses Monday through Friday, excluding the creation day; no holiday calendar is available. A note without `created` is not eligible for the archive-candidate finding.
- Missing day trace files and a missing ledger mean no loads or promotions; malformed existing files are unreadable.

## Deferred

- SessionStart hook wiring: issue #15.
- Automatic archiving and promotion: consolidation and issue #81.
