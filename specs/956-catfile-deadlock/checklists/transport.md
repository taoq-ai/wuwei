# Transport Requirements Checklist: Cat-file batch deadlock

**Purpose**: Reviewer assessment of requirement quality.
**Created**: 2026-10-13
**Feature**: `spec.md`
**Review Ownership**: A checked item means a reviewer approved requirement quality, not implementation completion.

## Coverage

- [ ] CHK001 Does FR-001 specify the file-backed transport for large input without changing the command contract? [FR-001]
- [ ] CHK002 Do FR-002 and FR-003 define timeout, capture, error, and cleanup behavior? [FR-002, FR-003]
- [ ] CHK003 Does SC-001 require both sides of the batch to exceed 64 KiB and every blob to be checked? [SC-001]
- [ ] CHK004 Does SC-002 protect existing adapter behavior? [SC-002]

## Notes

Markers are reviewer-owned. The implementation proceeds under the user's explicit issue instruction.
