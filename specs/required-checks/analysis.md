# Specification analysis: required-checks

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | MEDIUM | spec.md Clarifications, brief | The brief named `protection/required_status_checks`; the spec reads `branches/{b}` | Resolved: the branch read carries the same contexts to read access and has no "no protection" 404 to tell from a refusal; the item's promise names no endpoint; recorded as an assumption |
| A2 | Coverage | LOW | spec.md How this fails 1 | A token that cannot read the branch or rules holds every merge in its repository | Accepted: fails closed by design; the gap names the error |
| A3 | Coverage | LOW | spec.md How this fails 3 | The gap shows for seconds after a push, before GitHub creates the runs | Accepted: it clears on the next read; the PR cache is written only once CI settled |
| A4 | Ambiguity | LOW | spec.md Clarifications | "a reason WUWEI can name" is not defined by the item | Resolved: any safety gap at that read; process gaps and duties do not count |
| A5 | Coverage | LOW | spec.md Assumptions | A rule the owner adds can take 15 minutes to hold | Accepted: PR_TTL, the board's own window; recorded as an assumption |
| A6 | Coverage | LOW | tests/replay | The recorded replay case gains two answers | Accepted: the answers say no protection and no rulesets, so its recorded gaps stand |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 required contexts from protection and rulesets | yes | T001, T003, T009 | |
| FR-002 every page of rules | yes | T003, T009 | the rules read asks per_page=100&page=1 |
| FR-003 mergeableState on the PR read | yes | T006, T009 | |
| FR-004 the not-run gap | yes | T002, T003, T004, T010 | |
| FR-005 unreadable fails closed, not cached | yes | T005, T007, T010 | |
| FR-006 the blocked gap | yes | T006, T010 | |
| FR-007 cached per repository and branch | yes | T007, T010 | |
| FR-008 budget, vendored copy, docs | yes | T012, T013, T014 | |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held at +10.
