# Specification Analysis Report: 938-secondary-limit

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| A1 | HIGH | `Retry-After` and secondary wording conflict with a zero-remaining header. | Resolved in FR-001 and Assumptions: explicit secondary evidence wins; the primary reset applies only without it. |
| A2 | HIGH | "Block only the endpoint family" could imply a new process-wide cache. | Resolved in FR-003 and Assumptions: the adapter has no shared or persisted block, so each other family is attempted independently. No cache is introduced. |
| A3 | MEDIUM | The Actions jobs path is not a named port operation. | Resolved in Assumptions: use the existing repository read path for the replay. |
| A4 | LOW | A secondary reply without `Retry-After` has no precise reset. | Resolved in Edge Cases: retain the existing one-minute fallback. |

Coverage: FR-001 to FR-004 map to T001 to T004. CRITICAL 0 open, HIGH 0 open.

## Implementation Review

The Actions jobs replay failed before the fix with a core-zero reason and a later reset. It passes
with a 30-second secondary reason and an immediate successful pulls read. Primary-limit fixtures
use primary wording; secondary wording with zero remaining uses the short fallback when no
`Retry-After` is available. The adapter stores no cross-call block, so a separate endpoint call
is attempted and GitHub decides its own response.

## Review Follow-up

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| F1 | HIGH | Doctor's primary-reset test fixture used secondary wording. | Resolved: the fixture uses primary wording and keeps its no-sleep and core-reset assertions. |
| F2 | MEDIUM | The field's refused reply stderr was not captured; the new classification requires secondary evidence. | Recorded in Assumptions. A primary-looking response remains primary. Capture stderr and headers on recurrence. |
| F3 | LOW | Direct HTTP 403 with `Retry-After` and zero remaining still printed a zero-core count. | Resolved: the direct HTTP path reports a secondary limit and `Retry-After`, covered by a failing-first test. |

The importing test files plus `tests/test_doctor.py` pass together, 657 tests. CRITICAL 0 open,
HIGH 0 open.
