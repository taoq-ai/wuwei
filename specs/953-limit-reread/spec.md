# Feature Specification: Re-read GitHub quota after a zero-header refusal

**Feature Branch**: `953-limit-reread`
**Created**: 2026-10-13
**Status**: Ready
**Input**: GitHub issue #953.

## User Scenarios & Testing

### User Story 1 - Resume after a false empty bucket (Priority: P1)

**Independent Test**: Replay a primary-worded 403 with core remaining 0 in its headers and core 5000/5000 in `gh api rate_limit` using the same environment.

1. **Given** the two readings disagree, **when** a PR read is refused, **then** the reason names both readings and the short hold uses `Retry-After` or 60 seconds.
2. **Given** the short hold is within the configured cap, **when** it expires, **then** the refused call runs once more.

### User Story 2 - Preserve true exhaustion (Priority: P2)

**Independent Test**: Replay zero in both readings, and a failed quota read, separately.

1. **Given** both readings say zero, **when** the call is refused, **then** the hold uses the refused reply's reset.
2. **Given** the quota read fails, **when** the call is refused, **then** the hold uses the refused reply's reset.

### User Story 3 - Identify the token source (Priority: P2)

**Independent Test**: Replay a refused call under each token environment and under gh login. The reason names `GH_TOKEN`, `GITHUB_TOKEN`, or `gh keyring`, without a token value.

## Edge Cases

- Explicit secondary wording or numeric `Retry-After` retains the short hold behavior without a quota read.
- Compare only the same named resource. A full core bucket does not override an empty search or GraphQL bucket.
- A malformed, missing, or failed quota read preserves the refused reply's header-based decision.
- With both token variables set, gh uses `GH_TOKEN` first.

## Requirements

- **FR-001**: For a refusal with valid zero-remaining headers and no secondary evidence, read `gh api rate_limit` once using the refused call's environment.
- **FR-002**: If the same resource has calls left, use numeric `Retry-After` or 60 seconds, then permit one retry within the existing wait cap. Name both readings.
- **FR-003**: If the same resource is empty or the read fails, use the refused reply's reset.
- **FR-004**: Name the token source, never its value, in rate-limit reasons.
- **FR-005**: Preserve existing secondary-limit and no-header behavior and avoid a repeat probe of the refused endpoint.

## Success Criteria

- **SC-001**: Recorded false-empty response causes exactly one quota read, a 60-second hold, and one retry when the cap permits.
- **SC-002**: True exhaustion and failed quota read retain the header reset.
- **SC-003**: Every new reason includes a source label and no secret value.

## Assumptions

- The refused reply's resource identifies the quota bucket to compare. If the quota response lacks that bucket, the header decision stands.
- The environment passed to `gh_limit` is the effective child environment; when absent, `os.environ` is the effective environment.
- `GH_TOKEN` takes precedence over `GITHUB_TOKEN`, matching gh's environment priority; otherwise the source is the gh keyring.
- The existing retry cap governs whether WUWEI sleeps or reports the hold.
- A `token_scopes` probe may pass the measured `GITHUB_TOKEN` as `GH_TOKEN` to its child; the reason names the original measured variable.
- The design spec is owner-only and requires no wording change for this issue.
