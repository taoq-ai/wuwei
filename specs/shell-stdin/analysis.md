# Specification analysis: shell-stdin

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | LOW | item promise 1 | Whether a shell with flags but no `-c` counts | Resolved in Clarifications: any shell segment without a readable `-c` body |
| A2 | Ambiguity | LOW | item promise 2 | Which `{name}` spellings are redirects | Resolved: bash's rule, `[A-Za-z_]\w*` in braces glued before `<` or `>` |
| C1 | Coverage | MEDIUM | spec How this fails 3 | A shell fed an infra write or a leaking command still passes | Accepted: unchanged from main, outside the promise; recorded as a candidate |
| B1 | Breaking | MEDIUM | spec Breaking | Commands that passed on main are refused | Declared with migration notes, `!` and a BREAKING CHANGE line |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 shell without `-c` leaves UNREAD | yes | T003, T006, T009 | |
| FR-002 `{name}` before a redirect dropped | yes | T002, T005, T008 | |
| FR-003 routes, docs, vendored copy | yes | T011, T012, T015 | |
| FR-004 line budget | yes | T013 | +0 lines |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime under the 3,000 budget.
