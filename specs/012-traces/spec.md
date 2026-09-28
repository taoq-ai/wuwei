# Feature Specification: Tool-call traces

**Feature Branch**: `012-traces`
**Created**: 2026-09-28
**Status**: Implemented
**Input**: Issue #12, record every tool call to traces.jsonl in OTel JSONL.

## User Scenarios & Testing

### User Story 1 - Inspect a session's calls (Priority: P1)

The security sweep can reconstruct tool calls in a session from the day's trace file.

**Why this priority**: S2 sequence analysis needs a complete ordered record.
**Independent Test**: Replay Read then WebFetch through the hook in process.

**Acceptance Scenarios**:

1. **Given** a session with Read then WebFetch, **when** PostToolUse runs for each,
   **then** two spans appear in order with the same session identifier.
2. **Given** another session or an unfamiliar tool, **when** a call completes,
   **then** it is recorded with its own session identity and original tool name.
3. **Given** concurrent calls, **when** records append, **then** each complete record
   survives without overwriting existing records or interleaving lines.

### User Story 2 - Keep secrets out of traces (Priority: P1)

The operator can inspect traces without exposing credentials or personal message data.

**Why this priority**: Persisted credentials violate the security boundary.
**Independent Test**: Replay nested arguments containing sensitive keys and secret patterns.

**Acceptance Scenarios**:

1. **Given** arguments matching secret patterns, **when** recorded, **then** matches
   are redacted before any write and ordinary arguments remain useful.
2. **Given** nested objects, arrays, command strings, or URL credentials, **when**
   recorded, **then** the same protection applies without changing the input payload.
3. **Given** message bodies or phone fields, **when** recorded, **then** personal data
   is replaced by a redaction marker; tool responses are never persisted.

### User Story 3 - Report recording failures (Priority: P2)

The operator sees missing telemetry without the completed tool call being refused.

**Why this priority**: The trace recorder is observational and must never block; other PostToolUse guards retain their exits.
**Independent Test**: Make traces.jsonl unwritable and inspect stderr, exit, and events.

**Acceptance Scenarios**:

1. **Given** a write or validation failure, **when** the recorder runs, **then** it
   exits 0, reports a safe reason, and logs an error event when storage is available.
2. **Given** unavailable event storage too, **when** recording fails, **then** stderr
   reports both failures and exit remains 0 without leaking payload or exception data.

### Edge Cases

Missing/invalid session, tool, arguments, duration or role; malformed JSON; unknown tools;
missing workspace; absent duration/role; day rollover; concurrent writers; short writes.
No partially validated or unredacted span may be written on error.

## Requirements

### Functional Requirements

- **FR-001**: Append one OTel-compatible JSON object per completed call to the day's
  traces.jsonl, including trace/span/parent identity, name, start/end time, session,
  original tool name, redacted arguments, and agent role.
- **FR-002**: Preserve sequential arrival order and group calls from the same session.
- **FR-003**: Redact credential keys recursively and recognizable secrets in strings,
  phone numbers and message bodies before serialization; omit tool responses.
- **FR-004**: Reuse workspace discovery, day clock, and shared locked append storage.
- **FR-005**: The trace recorder never refuses; its validation and storage failures are
  reported and logged without raw payloads or raw exception text. The shared dispatcher
  retains exit 2 for malformed hook input and other PostToolUse guard failures.
- **FR-006**: All other guards and hook events retain their existing exit behavior.

### Key Entities

- **Tool span**: One completed tool invocation associated with a session and agent.
- **Recording error event**: A safe diagnostic marking missing telemetry.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Read then WebFetch yields exactly two ordered, related calls consumable
  by the inspected ZIRAN OTel format.
- **SC-002**: None of the secret or personal-data values in the redaction test table
  appears in persisted records; benign arguments remain unchanged.
- **SC-003**: Every exercised trace recorder failure returns 0 and reports the failure;
  every failure with writable event storage produces an event.

## Assumptions

- Traces are CLI-owned, so traces.jsonl stays mode 0444 like events.jsonl outside
  the locked writer. Writes require an existing .wuwei directory.
- Check workspace scope before parsing trace metadata. All completed tools are relevant.
  No discovered workspace returns 0 quietly. External repos and worktrees require
  WUWEI_WORKSPACE until a shared scope helper resolves configured repos and worktrees.
  An invalid explicit override reports a configuration failure. Do not read transcripts.
- Completion time is the shared clock; start is completion minus optional nonnegative
  duration_ms, default zero. These are observed hook times, not instrumented tool timings.
- Stable session-derived trace IDs group invocations; span IDs are fresh per invocation.
  The parent is empty until runtime instrumentation supplies a supported parent chain.
- agent_type supplies the role; absent role becomes unknown. Ignore agent_role and parent_span_id.
- Built-in redaction patterns are fixed and documented in contracts/otel.md. No redactor
  port exists yet. Sensitive strings are replaced whole, accepting lost argument detail.
- The recorder catches its own failures, logs hook.post_tool_use_error and returns (0, "").
  Policy guard findings/errors and dispatcher failures still reach the seat as exit 2.
- Strings longer than 2048 characters are reduced before regex matching to a redacted
  512-character prefix plus original length and SHA-256. Patterns have bounded quantifiers.
  Sensitive file contents, additional credential prefixes, national phone numbers and
  shell message bodies are covered by the review regression tables.

## Deferred

Scanner execution and parking belong to S2 sweeps. The pluggable redactor belongs to M5.
Pre-tool timing and parent propagation require runtime instrumentation outside this issue.
