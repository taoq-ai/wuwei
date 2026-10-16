# Specification analysis: gh-doors

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | LOW | item promise 2 | Whether `-f query=@file` reads a file | Resolved in Clarifications: real gh sends it literally, so it passes |
| A2 | Ambiguity | LOW | item promise 2 | How an `--input` file's query is found | Resolved: the whole file with `\u` escapes decoded, covering batches |
| I1 | Inconsistency | LOW | item promise 2 vs plan Design 3 | The plain-call rule also covers `-F query=@file` | Accepted: the same cwd gap; recorded in Clarifications, no extra line |
| C1 | Coverage | LOW | spec How this fails 2 | A future gh merge flag `_flags` does not know | Accepted: the pflag mirror check is the place to look |
| B1 | Breaking | MEDIUM | spec Breaking | Commands that passed on main are refused | Declared with migration notes, `!` and a BREAKING CHANGE line |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 merge flags through _flags | yes | T002, T003, T004, T010 | pflag mirror agrees on 18 argv |
| FR-002 unreadable graphql refused | yes | T001, T006, T011, T012 | |
| FR-003 input file query checked | yes | T005, T011 | |
| FR-004 repositories/ writes refused | yes | T001, T007, T012 | |
| FR-005 segments clause removed | yes | T012 | |
| FR-006 routes, docs, vendored copy | yes | T008, T014, T015, T016 | |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime at the 3,000 budget.
