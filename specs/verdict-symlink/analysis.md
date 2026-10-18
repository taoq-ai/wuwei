# Specification analysis: verdict-symlink

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | LOW | spec.md | The promise names `copy.resolve()` under verdicts and no link between; the check reads links only | Resolved: the copy is built under the resolved root from a resolved path, so no link implies it resolves under verdicts (spec, promise in my words) |
| A2 | Coverage | LOW | spec.md Clarifications | The promise does not name a link at `verdicts/` itself | Resolved: covered, since `verdicts.resolve()` would hide it; tested |
| A3 | Inconsistency | LOW | plan.md | The promise lists hook.py, tests and the vendored copy; ws.py changes three lines | Recorded as an assumption: the promise's temporary-file write reuses the existing helper, and its exclusive create covers every caller |
| A4 | Coverage | LOW | spec.md How this fails 1 | A link planted at a parent after the check is not covered | Recorded as residual risk; the planner holds it as a follow-up item (dir-fd walk) |
| A5 | Coverage | HIGH (closed) | ws.py atomic_write | Gate round 1: the predictable temporary name was opened with write_bytes and followed a link | Resolved: unlink, then O_CREAT, O_EXCL and O_NOFOLLOW; tests T013 and T014 |
| A6 | Inconsistency | LOW | spec.md How this fails 3 | The loop claim overstated: a loop at verdicts itself raises on 3.11 and 3.12 | Resolved: claim corrected; the fail-open is on main too and is a follow-up item |
| C1 | Coverage | LOW | tasks.md | Acceptance 3 has no new test | Held by the existing worktree copy test, and by T015 for a symlinked workspace path |

No open finding above LOW. A5 was HIGH and is closed in this round.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 refuse a link at any component | yes | T001, T002, T005 | |
| FR-002 write by temporary file and os.replace | yes | T003, T006 | |
| FR-003 atomic_write takes bytes, creates exclusively | yes | T007, T013, T014, T017 | |
| FR-004 runtime budget | yes | T008 | tests/test_setup.py size test |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
