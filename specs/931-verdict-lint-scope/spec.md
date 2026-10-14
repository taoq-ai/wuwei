# Feature Specification: Verdict lint scope

**Feature Branch**: `931-verdict-lint-scope`

**Created**: 2026-10-14

**Status**: Draft

**Input**: Issue #931, verdict lint scope and scenario wording

## User Scenarios & Testing

### User Story 1 - Findings are scoped (Priority: P1)

A sentinel can cite source lines in closure or evidence notes without those notes being treated as findings.

**Independent Test**: Lint a PASS verdict with cited prose outside a Findings section and an invalid cited bullet within it.

**Acceptance Scenarios**:

1. **Given** a verdict with a cited bullet outside a Findings section, **When** lint runs, **Then** that bullet is not parsed as a finding.
2. **Given** a malformed finding inside a Findings section, **When** lint runs, **Then** the verdict is refused with the missing field.
3. **Given** a FIX verdict with no blocking finding in Findings, **When** lint runs, **Then** the verdict is refused.

### User Story 2 - Scenario wording is flexible (Priority: P1)

A sentinel can describe a failure in natural language without memorizing a phrase list.

**Independent Test**: Lint a finding that says it fails open at admission when a required check is absent.

**Acceptance Scenarios**:

1. **Given** a finding with a concrete failure sentence using new wording, **When** lint runs, **Then** the finding passes scenario validation.
2. **Given** a finding with no failure description, **When** lint runs, **Then** the finding is refused.

### User Story 3 - Lint the written file (Priority: P1)

A sentinel's PostToolUse check evaluates the gate file its tool call wrote, without reading another seat's verdict.

**Independent Test**: Write one clean gate file while another gate file in the day directory is malformed.

**Acceptance Scenarios**:

1. **Given** a Bash write naming a gate file, **When** PostToolUse lint runs, **Then** only that gate file is checked.
2. **Given** a Bash call unrelated to a gate write, **When** PostToolUse lint runs, **Then** it returns clean.
3. **Given** SubagentStop for a registered sentinel, **When** lint runs, **Then** only that sentinel's gate file is checked.

### Edge Cases

- A Findings heading may identify blocking or non-blocking findings.
- Fenced examples and quoted text are ignored by the existing active-text filter.
- Unreadable targeted verdict files retain exit 2 with a reason.

## Requirements

### Functional Requirements

- **FR-001**: The lint MUST parse finding blocks only within a Findings section, including blocking and non-blocking Findings headings.
- **FR-002**: The lint MUST validate severity, citation, blocks decision, and a nonempty failure description for each parsed finding.
- **FR-003**: The lint MUST continue refusing a PASS with a blocking finding and a FIX without a blocking finding.
- **FR-004**: The lint MUST accept concrete failure descriptions regardless of their opening phrase.
- **FR-005**: PostToolUse MUST lint only gate paths identified as written by the current call; SubagentStop MUST retain the registered seat target.
- **FR-006**: Irrelevant calls outside a WUWEI workspace MUST return clean; unreadable targeted files MUST return exit 2.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Cited closure notes outside Findings cause zero finding-level refusals.
- **SC-002**: Findings inside Findings with missing required fields cause a refusal.
- **SC-003**: A valid finding using previously rejected scenario wording passes.
- **SC-004**: A PostToolUse write to one gate emits zero rejections for untouched gate files.

## Assumptions

- `## Findings`, `## Blocking findings`, `## Non-blocking findings`, and `## ZIRAN findings` delimit finding sections. Legacy `Findings:` and `**Findings**` labels also open sections. A later heading at the same or higher level ends the section; headings merely mentioning findings do not open one.
- PASS refuses active `blocks: yes` text even outside parsed findings. Non-PASS verdicts missing a Findings section get one finding diagnostic directing the seat to `## Findings`.
- Bash targets include output redirects and literal gate paths in non-reader arguments or argument values. On a shell parse error, lint literal gate paths found in the command; do not scan unrelated gates.
- A failure description is prose tied to the finding, either in a Scenario or Failure scenario field or after its citation; a bare placeholder does not describe a failure.
- Bash commands with an opaque interpreter write mentioning a gate file retain the existing refusal because the actual target cannot be verified safely.

## Deferred

- Issue #997 owns the broader review gate policy. This issue preserves its blocking checks.
