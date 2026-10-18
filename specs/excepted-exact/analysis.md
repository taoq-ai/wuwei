# Specification analysis: excepted-exact

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Coverage | LOW | spec.md How this fails 1 | A gap the hook records with a trailing line no longer waives its gap | Accepted: fails closed; the exception-parser follow-up owns the hook's cut; recorded as an assumption |
| A2 | Coverage | LOW | spec.md How this fails 2 | A loose ruling recorded before this change stops waiving at open PRs | Accepted: fails closed; the owner answers a fresh question in the exact shape |
| A3 | Ambiguity | LOW | spec.md Clarifications | "names its gate exactly" could mean one gate inside a list | Resolved: the whole gate list, so a waiver never drops a gate it does not name |
| A4 | Coverage | LOW | spec.md Clarifications | "listed in the report as waived" names no report file | Resolved: the existing report line lists each approved exception; a test reads it |
| C1 | Coverage | LOW | tasks.md | The changed-pair list is not committed | Accepted: the probe regenerates it and prints its sha256 |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 waive only a named gap | yes | T002, T003, T004, T006 | |
| FR-002 a part waives nothing | yes | T001, T004, T006 | |
| FR-003 the report lists it | yes | T002 | report.day read in the test |
| FR-004 budget and vendored copy | yes | T007, T009 | |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
