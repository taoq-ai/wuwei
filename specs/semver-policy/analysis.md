# Specification analysis: semver-policy

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | evidence.md Breaking changes | A stricter reading of a PR body line is a format change seats write; it could read as a major | Resolved: the section says a fix of a rule WUWEI already documents is a minor, and a newly required input is a major |
| A2 | Dependency | LOW | spec.md Assumptions | `Release-As:` works only if the squash commit carries it | The PR body asks the lead to carry it; acceptance 3 is read on the release PR |
| A3 | Scope | LOW | charters/sentinel-arch.md | The charters are generic; WUWEI's API list lives in its docs | Rule 7 reads "the declared or documented public API" of the repository under review |
| A4 | Coverage | LOW | agents/sentinel-arch.md | The bump has no verdict field of its own | `Breaking: no (minor)`; the parser reads any text after `no` as no |

No open finding above LOW; A1 is resolved in the docs text.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 docs section | yes | T002, T004 | |
| FR-002 rule 7 | yes | T003, T005 | |
| FR-003 builder rule 6 | yes | T006 | |
| FR-004 pointers | yes | T007 | |
| FR-005 build, vendor, words | yes | T008, T009 | |
| FR-006 Release-As | yes | T011 | |

## Constitution alignment

No conflict: no runtime change, no door change, no config key, the word ceiling not raised.
