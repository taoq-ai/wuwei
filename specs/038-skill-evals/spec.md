# Feature Specification: Skill triggering evals

**Feature Branch**: `038-skill-evals`
**Created**: 2026-09-29
**Status**: Ready
**Input**: GitHub issue #38

## User Scenarios & Testing

### User Story 1 - Verify skill routing (Priority: P1)

A maintainer runs plugin evals to measure whether each shipped skill triggers on intended requests and stays quiet on adjacent requests.

**Independent Test**: Run `claude plugin eval . --trust-plugin --ablation none --threshold 0.9 --json <file>` with API access.

**Acceptance Scenarios**:

1. **Given** a request for a shipped skill, **when** the runner evaluates it, **then** the Skill tool is called with that skill.
2. **Given** an adjacent request for a different skill or no skill, **when** the runner evaluates it, **then** the named skill is not called.
3. **Given** the full suite, **when** every case scores at least 0.9, **then** the runner exits 0; if any case scores below 0.9, it exits 1. With the default three runs per case, each case must pass every run.

### User Story 2 - Catch missing coverage offline (Priority: P1)

A contributor runs pytest without network access and gets a failure if a shipped skill lacks coverage or a grader names an absent skill.

**Independent Test**: Run the structure test in the default pytest suite.

**Acceptance Scenarios**:

1. **Given** a new skill without cases, **when** pytest runs, **then** it fails.
2. **Given** a grader naming an unknown skill, **when** pytest runs, **then** it fails.
3. **Given** five positive and five near-miss cases per skill, **when** pytest runs, **then** it passes without API access.

### User Story 3 - Run hosted eval with credentials (Priority: P2)

CI runs the live evaluation when the owner configures an API key and gives a clear skip message otherwise.

**Independent Test**: Inspect CI conditions and run its command locally with a key.

**Acceptance Scenarios**:

1. **Given** an API key, **when** CI runs, **then** it invokes the eval runner at threshold 0.9.
2. **Given** no API key, **when** CI runs, **then** the eval job prints a skip message and succeeds.

### Edge Cases

- A missing or malformed prompt or grader fails offline validation.
- Every shipped skill means every `skills/*/SKILL.md`, including future additions.
- A runner exit 2 is an incomplete run, not a pass.

## Requirements

### Functional Requirements

- **FR-001**: Every shipped skill MUST have at least five should-trigger and five near-miss should-not-trigger cases.
- **FR-002**: Each case MUST use `evals/<case-name>/prompt.md` with `name` and `tags` frontmatter and a user query body.
- **FR-003**: Each case MUST include a `tool_used` grader for `Skill` with an `input_match` naming an existing skill and the required min/max bounds.
- **FR-004**: Offline pytest MUST validate coverage, case shape, grader shape and references without network or Claude.
- **FR-005**: CI MUST invoke the live runner only when `ANTHROPIC_API_KEY` is present and clearly skip otherwise.
- **FR-006**: Documentation MUST give the local command and credential setup.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every live case scores at least 0.9 when the owner runs the authenticated suite.
- **SC-002**: Offline validation fails when any skill has fewer than five cases of either kind.
- **SC-003**: The default pytest suite passes without credentials or network.

## Assumptions

- The agreed success threshold is 0.9, since section 10 gives no other rate.
- The shipped skills are currently `wuwei-plan`, `wuwei-report` and `wuwei-retro`; discovery stays dynamic for future skills.
- The runner understands the issue's prompt and grader format.

## Deferred

- The owner must add `ANTHROPIC_API_KEY` as a repository secret. Live rate verification needs that secret and network access.
