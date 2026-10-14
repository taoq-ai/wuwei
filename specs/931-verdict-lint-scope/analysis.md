# Cross-artifact analysis: Issue #931

## Coverage

| Requirement | Plan | Task pair | Status |
| --- | --- | --- | --- |
| FR-001, FR-003 Findings scope and blocking verdicts | Findings parser | T001, T002 | Covered |
| FR-002, FR-004 Failure description | Scenario prose validation | T003, T004 | Covered |
| FR-005 Written file and registered seat | Bash target selection; existing stop lookup | T005, T006 | Covered |
| FR-006 Scope and unreadable input | Existing workspace and lint helpers | T005, T006, T007 | Covered |

## Findings

No CRITICAL or HIGH inconsistencies. The issue has no separate Acceptance section, so the three Expected outcomes and defect reports supply the acceptance scenarios. Bash commands without a literal target cannot identify a written file and retain the existing opaque interpreter refusal where relevant.

## Review fix round

The fresh review identified an FR-003 fail-open path: PASS could contain active blocking text outside Findings. T009 adds a whole-active-text refusal while keeping finding extraction scoped. T010 restores legacy section forms and checks downstream stored-verdict readers. T011 restricts section names, and T012 restores literal Bash target coverage without scanning untouched gates. `protect_state._write_targets` filters state-specific protected paths and applies copy semantics, so it is not reused for the gate-path predicate. No runtime dependency or new state is introduced. F5 is explicitly outside this fix round.
