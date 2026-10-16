# Specification analysis: 1068 blunt multi-line rule

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against item 1068's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | LOW | spec.md Clarifications | The promise says no continuation parsing for the door rule; `segments` joins a backslash-newline | Accepted: the join feeds only the other doors, so a continued curl still reaches the leak door; the door rule reads raw text |
| A2 | Ambiguity | LOW | spec.md How this fails 3 | Newline splitting lets a heredoc body line meet the infra door | Accepted: an ask, not a refusal; noted as a pre-mortem item |
| C1 | Coverage | LOW | tasks.md | Acceptance 11 (3,000 lines) has no new task test | Held by tests/test_setup.py::test_the_runtime_holds_its_size_budget |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 raw-text rule | yes | T001, T002, T010 | |
| FR-002 hint text | yes | T001, T010 | |
| FR-003 newline splitting, None on unreadable | yes | T004, T005, T006, T009 | |
| FR-004 callers read None | yes | T007, T011 | |
| FR-005 one-line unchanged | yes | T003 | existing one-line door tests also hold |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
