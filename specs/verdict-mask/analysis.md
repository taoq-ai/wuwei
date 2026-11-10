# Specification analysis: verdict-mask

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Coverage | LOW | item domain | The item names two write sites; a gate's own write into the workspace verdicts folder is a third that syncs raw | Resolved: FR-002 masks it in place before its hash, test T002 |
| A2 | Coverage | LOW | spec.md How this fails 1 | Masking the copy breaks the repeat-stop compare against the raw worktree bytes | Resolved: FR-001 masks before the compare, T001 stops twice |
| A3 | Ambiguity | LOW | spec.md Assumptions | A secret or canary in a verdict's file name is left as written | Recorded as an assumption with what overturns it |
| C1 | Coverage | LOW | tasks.md | FR-005 (runtime budget) has no new test | Held by tests/test_setup.py::test_the_runtime_holds_its_size_budget |
| A4 | Coverage | LOW | gates on ed7f415 | A linked verdicts folder, the refused row and verdicts no stop reads were open | Resolved: FR-006 to FR-008, tests T014 to T016 |
| A5 | Inconsistency | LOW | spec.md How this fails 5 | A verdict attested raw before this change stops counting once masked | Accepted: fails closed |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 masked copy-in | yes | T001, T007 | |
| FR-002 masked direct write | yes | T002, T007 | |
| FR-003 masked verdict.missing | yes | T004, T005, T008 | |
| FR-004 exact bytes when clean | yes | T003 | |
| FR-005 runtime budget | yes | T010, T018 | |
| FR-006 masked refused row | yes | T015, T017 | |
| FR-007 masked push | yes | T016, T017 | |
| FR-008 no write out of the workspace | yes | T014, T017 | |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
