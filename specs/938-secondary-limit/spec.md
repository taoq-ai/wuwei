# Feature Specification: Scope secondary GitHub rate limits to the refused endpoint

**Feature Branch**: `938-secondary-limit`

**Created**: 2026-10-13

**Status**: Draft

**Input**: GitHub issue #938, a secondary 403 on Actions jobs delayed seat briefs and named an empty core bucket while `gh api rate_limit` showed a full core bucket.

## User Scenarios & Testing

### User Story 1 - Continue unrelated code-host reads (Priority: P1)

**Independent Test**: Replay a secondary 403 from `repos/acme/widget/actions/jobs/123` with zero core remaining in that reply, a `Retry-After: 30` header, and a full core bucket. A subsequent pulls read succeeds without waiting or checking a shared block.

1. **Given** that Actions jobs reply, **when** a seat reads `repos/acme/widget/pulls/7`, **then** the pulls call runs immediately and succeeds.
2. **Given** the refusal, **when** its reason is shown, **then** it names a secondary limit on `repos/acme/widget/actions/jobs/123` and the retry time, without claiming zero core calls remain.

### User Story 2 - Preserve primary exhaustion behavior (Priority: P2)

**Independent Test**: Replay a primary 403 with zero remaining and no secondary evidence. Its reset and bucket remain in the reason.

1. **Given** a primary core exhaustion with no `Retry-After` or secondary wording, **when** the call fails, **then** the reason names the core bucket and its reset.

## Edge Cases

- Secondary wording without a numeric `Retry-After` uses the existing one-minute fallback, even when the reply says zero remaining.
- A numeric `Retry-After` signals a secondary hold even when the stderr uses primary wording.
- An endpoint with a query, such as search, keeps its current sanitized endpoint name.

## Requirements

- **FR-001**: A secondary-limit refusal, identified by wording or numeric `Retry-After`, MUST use its `Retry-After` duration when present and MUST never use a primary bucket reset for that refusal.
- **FR-002**: The reason MUST name the secondary limit and the refused endpoint, and MUST not report an empty primary bucket for that refusal.
- **FR-003**: A refused endpoint MUST NOT prevent a subsequent request to another endpoint family from being attempted.
- **FR-004**: Primary bucket exhaustion without secondary evidence MUST retain its existing reset behavior.

## Success Criteria

- **SC-001**: The Actions jobs 403 to pulls sequence makes both endpoint calls; the pulls result succeeds with no sleep.
- **SC-002**: The Actions reason names the secondary limit, endpoint and 30-second retry, with no `0 of 5000 core calls left` text.
- **SC-003**: Existing primary rate-limit regressions pass.

## Assumptions

- A numeric `Retry-After` on a 403 is authoritative secondary-limit evidence, including when `X-RateLimit-Remaining` reads zero. Secondary-limit wording is likewise authoritative when no `Retry-After` is supplied.
- The current adapter stores no rate-limit block across calls or commands. The field's 15-minute
  window is consistent with repeated independent refusals; the refused replies' stderr was not
  captured. This change applies when the reply carries secondary wording or `Retry-After`.
  A reply with only primary wording and zero remaining retains primary behavior.
- A secondary hold is scoped to the refused call. WUWEI does not preemptively block other endpoint families; GitHub may still refuse them independently.
- An Actions jobs read is represented by the GitHub adapter's existing allowlisted repository read path. No new endpoint operation is needed.
- The direct HTTP tracker path has no repository endpoint name in its error headers. Its
  secondary-limit reason names the rate-limit resource and `Retry-After`.
