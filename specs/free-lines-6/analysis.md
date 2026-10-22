# Specification analysis: free-lines-6

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | promise "no line golf" | Dropping eleven trailing `return 0` lines could read as golf | Resolved in Clarifications: repeated boilerplate carried by one `or 0` in the dispatcher, no line made denser; the Assumptions name the fallback (12 lines) if the owner prefers explicit codes |
| I1 | Inconsistency | MEDIUM | promise "no behaviour change", tests/test_plan.py | Removing `plan.restore` changes its unit test | Resolved in Clarifications: the test moves to `wuwei plan restore`, the surface the function served, and pins more than before; it is green on main and on the head |
| C1 | Coverage | LOW | acceptance 1 | "Each rewritten function's inputs" is not enumerated | Plan names the probe's 73 CLI calls, 72 cache_get, 4 cache_prune and 33 find cases, and seven mutants that show the probe sees each rewrite |
| I2 | Inconsistency | LOW | promise, plan | The promise asks for 16 or more lines; the head frees 23 | Within the floor; the extra lines are headroom for the five waiting items (15 to 25 lines; 27 free at the head) |

No open CRITICAL or HIGH finding.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 runtime at 3,380 or less | yes | T003-T005, T010 | budget test and wc |
| FR-002 four modules unchanged | yes | T010 | git diff --stat |
| FR-003 probe outputs identical | yes | T002, T008, T009 | mutants show the probe sees each rewrite |
| FR-004 no order-of-growth change | yes | T005 | each rewrite keeps its loop shape |
| FR-005 vendored copy | yes | T006 | vendored-copy test |
| FR-006 no long or joined line | yes | T010 | awk over the diff |

## Constitution alignment

No conflict: stdlib only, no door changed, no config key, runtime budget held. Principle V (test
first) is met by the CLI restore test written before the removal and by the differential probe
and its mutants, since the refactor adds no behaviour.
