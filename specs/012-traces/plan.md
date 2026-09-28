# Implementation Plan: Tool-call traces

**Branch**: `012-traces` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

## Summary

Register a PostToolUse guard for all tools. Build one OTLP resourceSpans envelope per
call, redact inputs, and append using the state writer's shared locking and write logic.
Handle recorder errors locally with stderr and an event while returning (0, "").
Preserve the shared dispatcher refusal behavior for every other guard.

## Technical Context

Python 3.11+, stdlib runtime; pytest dev only. Local JSONL files on existing POSIX storage.
No external commands, network calls, config additions or new dependencies. Existing
hook latency benchmark remains applicable. Tests run in process with temporary workspaces.

## Constitution Check

Pass before and after design: stdlib only, test first, one guard module, shared state
writer and workspace discovery, no subprocess in core. Generic fail-closed behavior
has the explicit design 4.1 trace recorder exception: telemetry fails closed by writing no
unsafe record, reports failure, and does not block the tool. No commits or GitHub calls.

## Project Structure

- cli/wuwei/guards/traces.py: validation, span construction and GUARDS registration.
- cli/wuwei/redact.py: recursive built-in redaction for trace metadata and arguments.
- cli/wuwei/state.py: extract existing low-level append into a reusable JSONL helper.
- cli/wuwei/commands/hook.py: retain fail-closed dispatch and safe input diagnostics.
- tests/test_traces.py: format, ordering, redaction, storage and failure contracts.
- tests/test_hooks.py: update registry expectation and PostToolUse result tables.
- specs/012-traces/contracts/otel.md: external format and redaction contract.

## Design Decisions

Inspected ZIRAN's ziran/infrastructure/trace_ingestors/otel_ingestor.py and
its tests/fixtures/sample_otel_traces.jsonl. It requires resourceSpans -> scopeSpans ->
spans, camelCase IDs/timestamps, and attributes as key/value.stringValue entries.
It groups on traceId and sorts by start time; gen_ai.tool.arguments must be JSON text.
A flat span would be silently ignored. Put agent identity in service.name as well as
on the span since the current ingestor reads service.name for agent_name.

Use SHA-256(session_id) truncated to 32 hex digits, random UUID span IDs truncated to
16 hex digits, empty parentSpanId, shared-clock Unix nanoseconds as
strings. Do not invent a parent chain for unrelated calls or retain session state.

Extract the current locked append mechanism without changing event semantics. Both
traces and events use state.lock, O_APPEND, and short-write detection with rollback
of incomplete bytes under the lock. Both remain mode 0444 outside the writer;
existing files temporarily become 0600 to open the writable descriptor, then return
to 0444 even on failure. Create days and the day directory only under an existing
.wuwei directory, without recursive workspace creation.
Recorder failure events store only safe diagnostics. Unexpected exceptions
report their class and operation, never arbitrary exception contents.

Redaction replaces sensitive fields or an entire matched string with [REDACTED].
Bound every regex quantifier and truncate strings over 2048 characters before regex
matching to a redacted 512-character prefix plus length/SHA-256 marker. Replace shell
message bodies with BODY length/SHA-256 markers. Sensitive file paths redact content
and edit strings whole. Pattern redaction is best effort; the durable path is M5.
Preserve nonmatching JSON data types.

## Validation Strategy

For each task pair, write tests, run to expected failure, then implement and rerun.
Check emitted envelope against the inspected ZIRAN traversal without importing ZIRAN.
Exercise unknown tool names, Bash wrappers as opaque recorded data, secret variants,
invalid metadata, concurrent append, short writes, unavailable storage, recorder-local failures, other
PostToolUse guard results 0/1/2 and unchanged pre-tool refusal. Both PreToolUse and
PostToolUse fixtures must meet the existing 50 ms p95 CPU benchmark; 5 MB Write and
100 KB hex arguments must each record in under 50 ms CPU. Run full pytest using the supplied
interpreter and scan all changed/new files for machine paths, em dashes and emojis.

## Deferred

See spec.md. No scanner adapter or M5 redactor framework is introduced.
