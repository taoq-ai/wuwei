# Feature Specification: ZIRAN live traces

**Feature**: 034-ziran-traces, issue #34
**Date**: 2026-09-29
**Status**: Ready for implementation

## User Scenarios & Testing

### US1: Reliable scanner measurements (P1)
As an owner I need the released scanner contract so an incompatible tool cannot report clean.
Acceptance: version 0.39.0 or newer returns all audit findings using severity low,
with the configured severity and trust rules applied locally;
older, absent, failed, timed out or malformed tools return unmeasured (2).
Audit findings use the released rule, severity, file, line and message fields.

### US2: Session trace fidelity (P1)
As an owner I need tool spans grouped by their originating session without leaking secrets.
Acceptance: a recorded line meets every field and type in the Claude Code span contract;
Read and WebFetch share a session, distinct sessions remain distinct even after redaction,
and canary and honeytoken material never reaches the trace file.

### US3: Park dangerous sessions at sweep (P1)
As an owner I need a dangerous session stopped from progressing and presented for decision.
Acceptance: a fixture containing Read of .env followed by WebFetch in one session causes
the affected reserved item to park and queues an owner decision. A scanner.finding event
contains only tool chain, risk level and session identity, never argument values.
Unmapped sessions still record the finding, page and queue a decision.

## Functional Requirements

- FR-001: Require ZIRAN >= 0.39.0 for external scanner measurements.
- FR-002: Replace obsolete CI invocation with audit JSON and severity; validate all output.
- FR-003: At each watch sweep analyze the day's nonempty trace file through the adapter.
- FR-004: Missing or zero-line traces mean no sessions and require no scanner call.
- FR-005: Errors, unreadable input and malformed reports return 2; findings return 1;
  clean measurements return 0. Error precedence is 2 > 1 > 0.
- FR-006: Associate session evidence with seat reservations, park active affected items,
  and publish valid pending owner decisions through the existing queue.
- FR-007: Record only chain, risk level and session id in trace finding events; never persist
  commands, arguments, report bodies or scanner output logs.
- FR-008: Keep guard scope, dedicated state/event producers and existing security redaction.
- FR-009: Repeated sweeps remeasure, without duplicating pending decisions.

## Key Entities

- Measurement: validated audit or trace report, exit and sanitized failure reason.
- Session: opaque grouping identity associated with zero or more seat reservations.
- Finding: ordered tool names, risk level, session identity.
- Decision: existing D-numbered pending owner decision, linked to the finding.

## Success Criteria

- The offline acceptance trace parks its item and appears as a valid owner decision.
- All failure cases are unmeasured rather than clean.
- Empty days cause zero external trace measurements.
- Recorded traces retain distinct session grouping and contain no workspace secret markers.
- The complete repository test suite passes without real ZIRAN or network access.

## Assumptions

- Binding notes supersede the obsolete S4 CI command in design section 7.
- Only critical chains cause exit 1, parking and decisions, matching the released CLI.
- A transcript's logged brief reference binds a session to an existing reservation; no
  item is inferred from a tool argument, role alone or working directory alone.
- Subagents share the planner's session_id and main transcript_path. Their trace identity
  is session_id:agent_id; binding reads the agent transcript under the session's subagents
  directory. Unreadable or incomplete transcripts leave sessions unmapped without failing
  an already recorded span.
- Redacted session identities use a deterministic digest to prevent collisions. Ordinary
  identities pass through when safe. Reservations store the same trace identity.
- Already paused or terminal items remain paused or terminal; their finding still pages.
- Each distinct session and chain gets one pending decision per day, even across sweeps.

## Deferred

- MCP scanning (#35), role audits (#36 and its open upstream dependencies).
- Runtime session discovery without a hook transcript is not invented here; unmatched
  sessions remain visible and demand an owner decision.
