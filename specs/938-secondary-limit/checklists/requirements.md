# Requirements Quality Checklist: Secondary GitHub Limits

**Purpose**: Review the clarity and completeness of issue #938 requirements.
**Created**: 2026-10-13
**Owner**: Requirements reviewer. An `[x]` marker means the requirement wording was reviewed, not that code was implemented.

## Classification

- [ ] CHK001 Is the precedence between secondary evidence and a zero-remaining header explicit? [Clarity, FR-001]
- [ ] CHK002 Is the fallback for missing `Retry-After` specified? [Completeness, Edge Cases]

## Scope and outcome

- [ ] CHK003 Is the endpoint scope expressed as observable behavior without assuming storage that does not exist? [Clarity, FR-003]
- [ ] CHK004 Are reason wording and retry timing objectively testable? [Measurability, FR-002, SC-002]
- [ ] CHK005 Is primary exhaustion preserved explicitly? [Coverage, FR-004]

## Notes

The checklist stays reviewer-owned and unchecked; implementation tasks have separate markers.
