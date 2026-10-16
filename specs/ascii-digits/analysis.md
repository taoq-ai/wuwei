# Specification analysis: ascii-digits

Artifacts read: spec.md, plan.md, tasks.md, against the item's promise and acceptance and the
constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Ambiguity | MEDIUM | promise | `[0-9]` or `re.ASCII` | Resolved in Clarifications: `[0-9]`, since `re.ASCII` narrows `\w`, which the promise puts outside |
| A2 | Ambiguity | MEDIUM | hook `_answers` | The merged reader reads the class prefix; main's owner review pattern matched anywhere, case-sensitive | Resolved: recorded under Assumptions and How this fails; a question with text before the class records nothing (fails closed) |
| U1 | Underspecification | LOW | promise, line numbers | The plan's line numbers were taken at fe5bc0b | Resolved: re-found at 0104d00 and listed in Clarifications |
| C1 | Coverage | LOW | guards 341, 346 | Guard patterns change without a dedicated test | Covered by the scan test; a non-ASCII owner review question is now refused by the guard's shape check, consistent with the hook |
| S1 | Inconsistency | HIGH | hook `_answers` | The merged reader took the first REF anywhere, so a two-REF owner review approved the wrong PR (security at cda89f4) | Resolved: the REF must follow the class prefix, in the hook and in the guard; two-REF cases tested |
| I1 | Inconsistency | LOW | budget | Promise says about 2 lines freed; the change frees 4 | Within the promise (it must not add lines) |

No open finding above LOW: A1, A2 and S1 are resolved.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 `\d` to `[0-9]` | yes | T001, T003 | |
| FR-002 `_ref` isascii guard | yes | T004 | |
| FR-003 one ruling reader | yes | T005 | |
| FR-004 scan test | yes | T002, T006 | |
| FR-005 runtime not higher | yes | T006 | |
| FR-006 guard anchor | yes | T011, T012 | |

## Constitution alignment

Stdlib only, test first, no config key, no new evidence rule, runtime shrinks. No violation.

## Metrics

- Requirements: 6; tasks: 13; coverage 100 percent
- Critical issues: 0; high: 0 open
