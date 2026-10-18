# Specification analysis: goal-met

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | LOW | spec.md Clarifications | "offers it again only after its date moves" has no ledger meaning in the promise | Resolved: a no holds the goal while its day is on or after the goal's date; tested both ways |
| A2 | Scope | LOW | spec.md FR-004 | The run skill and design gain a sentence the promise does not name | Accepted: the planner needs to know what the pass line asks; docs only |
| A3 | Coverage | LOW | spec.md How this fails 1, 2 | A misleading question or a free-text answer records the wrong state | Accepted: the ruling keeps the question and answer; the note names what was recorded |
| A4 | Coverage | LOW | spec.md How this fails 3 | A non-ISO goal date is never offered | Accepted: the template and every goal here use ISO dates; recorded as residual risk |
| C1 | Coverage | LOW | tasks.md | No task changes the guard | Accepted: goal: takes any wording; the probe shows the guard refuses none of 20,736 questions |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 pass offers due goals | yes | T001, T002, T006, T007, T014 | |
| FR-002 hook records goal.met | yes | T003, T004, T008, T015 | |
| FR-003 report lists met goals | yes | T003, T009 | |
| FR-004 lead charter and skill | yes | T010 | |
| FR-005 goals.md untouched | yes | T006 to T009 | no write in the diff |
| FR-006 no route moves | yes | T012 | |
| FR-007 budget and copies | yes | T010, T011 | |

## Constitution alignment

No conflict: stdlib only, an auditor that records and never edits the owner's goals, test first,
runtime budget held.
