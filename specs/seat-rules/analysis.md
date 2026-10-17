# Specification analysis: seat-rules

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Terminology | LOW | charters/_gate.md, charters/builder.md | "door program" is a WUWEI term in charters every workspace reads | Glossed in place as the guarded program the stub stands for |
| A2 | Renumbering | LOW | charters/_gate.md | Rules 4 to 6 become 5 to 7 | grep found no citation by number |
| A3 | Dependency | LOW | spec.md | free-lines-4 runs beside this item | No shared file per the promise |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 together-forward | yes | T005 | |
| FR-002 door-word-free probe | yes | T003 | |
| FR-003 generated probe | yes | T003, T004 | |
| FR-004 differential probe | yes | T003 | |
| FR-005 lesson placement | yes | T006 | |
| FR-006 fixtures by code | yes | T003, T004 | |
| FR-007 build, vendor | yes | T007, T008 | |

## Constitution alignment

No conflict: charter text only, no door change, no config key, no runtime line.
