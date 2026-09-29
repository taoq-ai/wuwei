# Implementation Plan: ZIRAN live traces

## Technical Context

Python 3.11+ standard library runtime, pytest development tests. Extend the existing
scanner adapter, trace recorder, watch sweep and decision records. No new dependency.

## Constitution Check

Pass: external processes stay inside adapters; failures use 0/1/2; shared atomic and
locked state writers remain the only producers. Tests precede each implementation.
No approval or outbound messaging is introduced. Work stays in this worktree.

## Design

1. Require the released version before audit or trace execution. Audit requests severity
   low and uses the exact released JSON fields, validating exit against finding presence.
   The gate port evaluates the configured threshold against validated audit findings
   locally; no second external command or report conversion.
2. Validate trace report counts, metadata, chains and session evidence. Read reports from
   an adapter-owned temporary output directory and discard commands after validation.
3. Preserve the recorder's OTLP structure. Use a deterministic digest when session
   redaction would collapse identities. Subagents use session_id:agent_id and their own
   transcript for best-effort reservation binding, storing trace session ids under
   already protected seats.
4. Extend scanner core with sweep handling: skip missing/empty input; otherwise call
   traces, emit minimal finding events, park mapped active items using the state writer,
   and atomically write valid D-numbered owner decisions. Reserve decision deduplication
   state for the scanner producer. Use existing queue readers and page classification.
5. Replace the watch placeholder block with the core helper, preserving aggregate exit
   precedence. Document minimum version, released commands and empty-day behavior.

## Validation

Offline tests with recorded JSON and one PATH executable stub for the external boundary.
Test audit threshold/version/error paths; OTLP required types and redaction/grouping;
critical fixture through sweep, mapping, missing mapping, repeated sweep, empty day,
malformed reports, missing tool, timeout, reserved producers and exit precedence.
Run the full pytest suite with the interpreter supplied by the task.

## Structure and Dependencies

Adapter changes precede sweep integration. Recorder identity and reservation binding
precede mapped acceptance. No independent research is needed: binding CLI contracts are
provided in the issue. No additional model or quickstart files are needed.
