# Specification analysis

## Cross-artifact consistency

| Check | Result |
|---|---|
| FR-001 to FR-003 quota comparison and fallback | Covered by T001 to T003 |
| FR-004 token source | Covered by T004 |
| FR-005 caller and retry behavior | Covered by T005 and T006 |
| Constitution: stdlib, test first, no secret value | Covered by plan gates and T001, T004 |

No CRITICAL or HIGH findings. The field replay failed on the old header reset before the shared fix. The implementation keeps the existing `retry` path, makes one quota read for a primary zero-header refusal, and names only the token source. The explicit importing-file test run and diff review found no remaining issue.

## Review follow-up

The review found that secondary refusals with zero headers made an unused quota read. The secondary replay failed before the fix, then passed with no quota read. A scope probe for `GITHUB_TOKEN` also failed because its child used `GH_TOKEN`; the reason now carries the measured variable name. Both findings are resolved. The direct HTTP tracker quota path remains outside this gh-specific issue.
