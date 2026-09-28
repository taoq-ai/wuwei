# Feature Specification: Proposal promotion and ledger

**Branch**: `081-promote-ledger`  
**Created**: 2026-09-28  
**Status**: Draft  
**Input**: Issue #81.

## User Scenarios & Testing

### User Story 1: Promote reviewed memory (Priority: P1)

Seats place JSON proposals in `days/<date>/proposals/`. The CLI validates each one, changes only workspace charter overrides or existing notes, and records one result per proposal.

**Acceptance Scenarios**:

1. Given a proposal targeting a plugin charter, when promote runs, then it is rejected and the ledger records why.
2. Given an `add` duplicating an existing rule, when promote runs, then it is rejected in favour of a patch.
3. Given valid add, patch, fold, or archive proposals, when promote runs, then the intended workspace file changes atomically and the ledger records landed.
4. Given invalid evidence, path, survivor, contradiction or line cap, when promote runs, then it records rejected without changing the target.

### User Story 2: See the last run (Priority: P1)

Session payloads show one line summarizing the most recent promotion run by run id, including rejected reasons.

### User Story 3: Maintain useful notes (Priority: P2)

Consolidate lists archive candidates using note loads in traces, probation and note capacity. An archive proposal moves the note into `memory/archive/`.

**Acceptance Scenario**: Given a note past probation never loaded, when consolidate runs, then it lists the note as an archive candidate.

## Requirements

- FR-001: Proposal JSON has target, action, reason, evidence and text or delta; actions are add, patch, fold, archive.
- FR-002: Promote alone writes overrides and existing notes through the shared atomic writer, and appends ledger records through the shared locked appender.
- FR-003: Ledger records date, run id, target, action, status landed or rejected, reason and evidence.
- FR-004: Session payload renders `Last promote <date>: landed N (targets); rejected M (target: reason, ...)` or `Last promote: none`.
- FR-005: Note loads come from recorded Read spans; guard refusals come from day events. Probation defaults to 10 working days and memory capacity to 60 notes.
- FR-006: Archive moves notes to `memory/archive/` and never deletes content.
- FR-007: Note creation and state writes refuse a symlinked `.wuwei` directory.

## Assumptions

- `wuwei promote` processes today's proposals in sorted filename order and uses one run id for the invocation.
- Target paths are workspace-relative `.wuwei/charters/<name>.md` or `.wuwei/memory/notes/<slug>.md`. New charter overrides may be added; note creation remains with `wuwei note add`.
- `text` is the complete replacement text for add and patch. A patch must name `old_text`, which is replaced once; `fold` names a `survivor` target. This makes contradictions explicit.
- A rule is a nonempty normalized line. An add that repeats one is a duplicate. The line cap is 200 lines per target, matching a compact charter or note.
- Working days are Monday through Friday. When a note lacks `created`, file modification date is the probation start.
- `wuwei consolidate` reports candidates and does not archive automatically. Archive is an explicit proposal.
- Malformed proposal files are rejected with a ledger line when their filename can be read. A ledger write failure is operational exit 2.

## Deferred

- Automatic contradiction discovery across natural language rules and full weekly fold/snapshot workflow belong to later consolidation work. Explicit `old_text` enforces rewrites here.
