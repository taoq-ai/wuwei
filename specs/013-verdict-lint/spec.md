# Feature Specification: Verdict lint and retro-note capture

**Feature Branch**: `013-verdict-lint`
**Created**: 2026-09-28
**Status**: Implemented, review fixes verified
**Input**: Issue #13, amendment #75 and production verdict-lint source.

## User Scenarios & Testing

### User Story 1 - Return incomplete verdicts (Priority: P1)

A sentinel gets actionable refusals when its gate verdict lacks review evidence.

**Independent Test**: Check valid and invalid verdict files and replay write hooks.

**Acceptance Scenarios**:

1. Given a FIX verdict without file:line, when written under decisions/gate-*.md,
   then it is returned to the seat with the missing citation identified.
2. Given a complete verdict, when checked, then it is accepted.
3. Given a quality verdict missing Simplicity: or Design:, then lint refuses it.
4. Given an unreadable verdict or malformed applicable payload, then checking fails
   closed with exit 2 and a reason.

### User Story 2 - Retain every seat's retro (Priority: P1)

The steward can find captured blockers, gaps and proposed procedure changes.

**Independent Test**: Stop a chartered seat and inspect the day's events and retro records.

**Acceptance Scenarios**:

1. Given a seat that ends without a retro note, then an event records the gap and
   the seat receives a finding unless `stop_hook_active` is true, in which case
   capture returns 0 to avoid a stop loop.
2. Given Blocked:, Gap: and Change: lines, then their values are recorded.
3. Given a substantive Change:, then its text stays in the retro record for the
   steward; capture does not write proposals, charters or existing memory notes.
4. Given no WUWEI workspace or a non-charter agent, then capture returns 0 before
   parsing the note. Relevant malformed inputs or failed persistence exit 2.

### Edge Cases

- PASS with no findings; PASS with nonblocking findings; all other verdict values.
- Markdown emphasis, heading and list verdict forms accepted by the source script.
- Missing or blank retro lines, duplicate rows, quoted examples and fenced samples.
- Relative, absolute and symlink paths; Edit patches versus saved file contents.
- Multiple findings where only one has evidence; quality detected from role or filename.
- Hook retries, stop_hook_active, malformed inputs and invalid UTF-8.

## Requirements

### Functional Requirements

- FR-001: Preserve production refusal order: verdict, non-PASS citation, blocks,
  scenario, mutation/probe, class sweep, Blocked, Gap, Change. Report all failures.
- FR-002: Require severity and citation, blocks yes/no and failure scenario for
  each finding, including nonblocking findings on PASS verdicts.
- FR-003: Require exactly one nonempty Simplicity: and Design: row for quality.
- FR-004: Check saved gate verdicts on Write, Edit, MultiEdit, NotebookEdit and
  Bash. Match decisions/gate-*.md case-insensitively. For file tools, find the
  workspace from cwd or fall back to the gate-shaped target's parent. Inside a
  workspace, any Bash command containing `gate-` case-insensitively lints every
  gate-*.md in the day's decisions directory, with case-insensitive filenames.
  Never extract shell paths; keep opaque interpreter one-liner refusal.
  At SubagentStop, roles starting `sentinel-` after the last plugin prefix lint
  the same day files regardless of tool history. Record rejections on every pass;
  `stop_hook_active` returns 0 on the second pass to avoid a stop loop.
- FR-005: Use `wuwei verdict lint FILE [--role ROLE]` with exits 0/1/2. This is
  the lint path for seats on the Codex runtime, which has no Claude Code hooks.
  The runtime adapter (#26) calls it after a Codex seat writes its verdict,
  passing the role to derive quality and class-sweep requirements like the hooks.
- FR-006: Capture retro fields and missing-field names in an append-only event;
  retain available fields even if some are missing. Missing or blank lines are findings.
- FR-007: Retain Change values under days/<date>/retro/ for the steward. The
  steward writes real proposals once #81 fixes the proposal contract. Until then,
  Change lines stay in retro evidence for the steward; capture never writes proposals.
- FR-008: I/O, decoding, malformed payload and persistence failures return 2.
- FR-009: Reuse the shared hook dispatcher, atomic writer and event writer.
- FR-010: Require exactly one `Head: <7 to 40 hex>` row and a nonempty `Probe:`,
  `Probes:` or `Mutation:` row (`not run` is valid). Refuse a PASS carrying any
  finding with blocks: yes. Numbered (`1.` or `1)`) and bare `[F2]` finding
  markers and paragraph markers `F2 (`, `F2:` and `F2.` start independent
  findings, each requiring its own citation.
- FR-011: Require a class-sweep line only for arch, quality and security verdicts,
  identified by role or filename token.
- FR-012: Every file lint rejection within a workspace appends `verdict.rejected`
  with file and reasons, including unreadable files and opaque relevant commands.
  Failure to append the event returns 2.

### Key Entities

- Verdict: review result, findings, probe evidence, class sweep, retro and quality rows.
- Retro: seat identity, Blocked, Gap, Change and missing fields.
- Captured change: retro text and evidence awaiting the steward, not a proposal.

## Success Criteria

- Every source-script refusal has a regression case with preserved relative order.
- Both issue acceptance scenarios and both amendment requirements are tested.
- Both guards have clean, finding and could-not-run cases and a disabling mutation check.
- No retro capture modifies charters, notes or promotion history.

## Assumptions

- The source has no self-test cases. Its fixed verdict vocabulary and review class
  taxonomy are protocol constants, not engagement configuration.
- Keep the source's Lnn documentation citation alternative. Unreadable files use
  exit 2 under the binding three-state contract, overriding the source's exit 1.
- Quality is identified by a `quality` filename token or the role after the last
  plugin prefix being sentinel-quality.
  Direct lint accepts `--role` with the same plugin-prefix handling as hooks.
- Findings use severity-led rows/bullets/headings, numbered or finding-ID markers,
  or an explicit Severity: label;
  severities are P0-P3, critical, high, medium, low or info. Multiline findings end
  at the next finding or section. Probe coverage retains the source's document-level
  check; determining whether every natural-language claim has a probe is semantic.
- SubagentStop uses last_assistant_message, not the full transcript. Explicit
  `none` is valid. Duplicate fields are findings rather than silently choosing one.
- Retro capture applies only when agent_type after the last colon matches a
  charter stem under plugin charters/*.md. Other agents pass without note parsing.
  Retro capture needs cwd inside the workspace or WUWEI_WORKSPACE naming its root;
  it has no file target from which to discover a workspace.
- Retro names are content-derived for retry safety. Events remain append-only.

## Deferred

- Issue #81 owns proposal enrichment, promotion lint, landing, ledger and changelog.
- Semantic assessment of evidence, reviewed-head validation and general shell write mediation
  remain with their respective gate or guard features.
