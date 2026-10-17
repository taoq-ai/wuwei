# Specification analysis: shell-doors

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| I1 | Inconsistency | MEDIUM | item promise 1 vs plan Design 1 | The promise refuses a punctuation-only word; the plan splits it | Resolved in Clarifications: refusing breaks the #1038 test and two everyday commands; splitting refuses every acceptance shape |
| A1 | Ambiguity | LOW | item promise 2 | Whether `$'` inside other quotes counts | Resolved: only a `$'` or `$"` that opens a quote span |
| A2 | Ambiguity | LOW | item promise 3 | Whether `dd of=` counts as a writer argument | Resolved: `=` before `.wuwei` matches |
| C1 | Coverage | LOW | spec How this fails 1, 2 | Bare `.wuwei` in DOOR_WORDS and LEDGER refuses a few read-only shapes | Accepted: 3 of 2,435 traced commands; migration in Breaking |
| B1 | Breaking | MEDIUM | spec Breaking | Commands that passed on main are refused | Declared with migration notes, `!` and a BREAKING CHANGE line |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 punctuation split, `\|&` | yes | T001, T002, T008 | |
| FR-002 `$'` and `$"` unreadable | yes | T003, T009, T011 | |
| FR-003 LEDGER spellings | yes | T004, T010 | |
| FR-004 DOOR_WORDS bare `.wuwei` | yes | T005, T010 | |
| FR-005 routes, docs, vendored copy | yes | T006, T012, T013, T014 | |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime under the 3,000 budget.
