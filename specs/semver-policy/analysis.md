# Specification analysis: semver-policy

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | evidence.md Breaking changes | A stricter reading of a PR body line is a format change seats write; it could read as a major | Resolved in round 1: a fix of behaviour that contradicted the documented API at the base is a patch, and an exit code or format is judged by its meaning and shape, not by which inputs reach it |
| A2 | Dependency | LOW | spec.md Assumptions | `Release-As:` works only if the squash commit carries it | The PR body asks the lead to carry it; acceptance 3 is read on the release PR |
| A3 | Scope | LOW | charters/sentinel-arch.md | The charters are generic; WUWEI's API list lives in its docs | Rule 7 reads the public API declared at the base commit of the repository under review |
| A4 | Coverage | LOW | agents/sentinel-arch.md | The bump has no verdict field of its own | `Breaking: no (minor)`; the parser reads any text after `no` as no |

| A5 | Inconsistency | HIGH | spec.md item text vs round 1 | The item says a stricter check is a minor; the lead's round-1 decision makes a fix of a documented rule a patch | Resolved: the spec records the decision under Clarifications and Assumptions, and builder rule 6 and the docs table agree with release-please's `fix:` patch bump |
| A6 | Coverage | MEDIUM | evidence.md public API list | Skills, plugin and marketplace names, role names and owner-written files were outside the list | Resolved: added to the list |

No open finding above LOW; A1, A5 and A6 are resolved in the docs and charter text.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 docs section | yes | T002, T004, T014 | |
| FR-002 rule 7 | yes | T003, T005, T012, T013 | |
| FR-003 builder rule 6 | yes | T006, T015 | |
| FR-004 pointers | yes | T007 | |
| FR-005 build, vendor, words | yes | T008, T009, T016 | |
| FR-006 Release-As | yes | T011 | |

## Constitution alignment

No conflict: no runtime change, no door change, no config key, the word ceiling not raised.
