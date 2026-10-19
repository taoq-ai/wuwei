# Specification analysis: verdict-dirfd

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | MEDIUM (closed) | plan.md Lines | The promise budgets +10 runtime lines; the change adds 16 | Resolved as an assumption in spec.md: the walk needs a mkdir per folder, and the free() fix (+4) came from the #1144 gate through the caller; the planner may split it out |
| A2 | Coverage | LOW | spec.md How this fails 3 | The read-back after the copy-in still follows a swapped parent | Recorded as residual risk: no write follows the link, and a read of the wrong file fails the shape or holds bytes the seat could write itself |
| A3 | Inconsistency | LOW | spec.md How this fails 1 | sync.pull now raises OSError at a planted link and stops that pull | Recorded as an assumption; the SessionStart wrapper catches it and prints it |
| A4 | Coverage | LOW | plan.md Guard testing | The working-directory wrapper probes (cd, env -C, sudo -D) do not apply | No command is parsed by this change; the route corpus differential shows 0 moved routes |
| C1 | Coverage | LOW | tasks.md | Acceptance 2 holds on 3.13 by the lstat check, not by the RuntimeError catch | T003 raises RuntimeError on any version, and the suite runs on 3.11 and 3.12 |

No open CRITICAL or HIGH finding.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 walk by directory descriptor | yes | T001, T008, T016, T017 | |
| FR-002 temporary name and exclusive create kept | yes | T012, T017 | the four temp-name tests pin get_ident |
| FR-003 no root behaves as before | yes | T013 | full suite |
| FR-004 the copy-in and sync.pull pass a root | yes | T006, T009 | |
| FR-005 RuntimeError refused | yes | T002, T003, T010 | |
| FR-006 free() never raises, lists once | yes | T004, T005, T011 | |

## Constitution alignment

No conflict: stdlib only in the runtime, no new door, no config key, test first. The runtime stays
under the 3,400 cap; the item budget overrun is A1.
