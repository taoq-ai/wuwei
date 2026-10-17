# Specification analysis: free-lines-5

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | MEDIUM | acceptance 1, brief | The acceptance runs commands through guards.bash, while the brief bars edits to guards.py | Resolved in Clarifications: guards.bash reaches evidence.verdicts, which changes, so the probe runs with attested, edited, missing and imported verdicts on record |
| I2 | Inconsistency | LOW | promise, plan | The promise asks for 12 or more lines; the head frees 21 | Within the floor; the extra lines are headroom for the three waiting items |
| C1 | Coverage | LOW | acceptance 2 | "Worst shape" is not named per function | Plan names one or more shapes per rewritten function, including the unreadable-host path of board.compute and a 0.34 state of 1,000 imports |
| A1 | Ambiguity | LOW | promise "no complexity change" | Reusing `mine` in board.compute changes a generator into a list read twice | Same order of growth (the list already existed); timed at 125 KB and 500 KB |

No open CRITICAL or HIGH finding.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 runtime at 2,984 or less | yes | T003-T007, T013 | size test and wc |
| FR-002 guards.py unchanged | yes | T013 | git diff |
| FR-003 probe outputs identical | yes | T001, T010, T011 | mutants show the probe sees each rewrite |
| FR-004 timing within 20 percent | yes | T002, T012 | |
| FR-005 re-vendored copy | yes | T008 | drift test |
| FR-006 no long or joined line | yes | T013 | awk over the diff |

## Constitution alignment

No conflict: stdlib only, no door changed, no config key, runtime budget held. Principle V (test
first) is met by the differential probe and its mutants, since a refactor adds no behaviour.
