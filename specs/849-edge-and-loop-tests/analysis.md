# Specification Analysis Report: 849-edge-and-loop-tests

Artifacts read: spec.md, plan.md, tasks.md; the constitution (IV: guards get table tests for
exits 0, 1 and 2; tests never on model prose); the #789 pass plan (batch 8 care: the property
test first; owner constraint: never loosen a test or budget); `tests/` and
`.github/workflows/tests.yml` at 71d3f06b (7668 tests, 2964 functions).

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| N1 | Feasibility | CRITICAL | US4 | Parts 23 and 24 delete about 800 tests; the suite would still collect about 6850. Deleting tests to reach 3000 would drop coverage. | Resolved by B9 lead call (b): the limit counts test functions (`def test_`), 2643 after this part; nothing is collapsed and no row is dropped (FR-007 superseded). |
| N2 | Owner constraint | HIGH | FR-004 | Removing a latency budget could read as loosening a budget. | Resolved: the measurement moves to `scripts/hook_latency.py` in the informational latency job (as today, #805); the issue forbids timing assertions in tests. |
| N3 | Coverage | HIGH | FR-002 | Moving rows from eight files risks losing the context those files added (outside a workspace, enforce off, profiles). | Resolved: the tables carry the workspace and enforce columns; a row is dropped only as a named duplicate (Assumption 2); each table is shown red (T001). |
| N4 | Measurement | MEDIUM | US2 | The property test took 1.54 s setup plus 2.13 s for the state.json pair test at 71d3f06b. | Resolved: part 23 deletes the pair test and the cache writes; T005 measures and has a fallback that keeps the 300 worlds (Assumption 3). |
| N5 | CI | MEDIUM | FR-006 | `tests/test_dev_cycle.py` pins the timing group and the workflow text. | Resolved: T004 updates the pin and the workflow assertions together. |
| N6 | Regression guard | LOW | FR-008 | Without a check the count creeps back. | Resolved: a CI step counts test functions and fails at 3000. |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 edge tables | yes | T001 |
| FR-002 duplicates out | yes | T002 |
| FR-003 loop contract | yes | T005 |
| FR-004 no duration asserts | yes | T004 |
| FR-005 latency script | yes | T003 |
| FR-006 timing group | yes | T004 |
| FR-007 table collapse | yes | T006, T007 |
| FR-008 CI count | yes | T004 |

**Constitution alignment**: IV (table tests for guard exits stay and get one home), V (fewer
files), no runtime change.

**Metrics**: 8 functional requirements, 7 tasks, 100 percent covered. CRITICAL 0 open, HIGH 0
open.
