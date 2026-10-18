# Specification analysis: pr-draft-text

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Scope | LOW | charters/_pr.md:22 | The delta sentence is kept though the promise lists four points | Kept as true and consistent with `_common.md` Done; recorded under Assumptions |
| A2 | Reach | LOW | cli/wuwei/guards.py:252-256 | A non-draft create at a gated head shows the same note, which describes the draft route | Advice once per session, not a refusal; recorded under Assumptions and How this fails 2 |
| A3 | Test brittleness | LOW | tests/test_guards.py | The test holds whole sentences, so a rewording fails it | Intended: a rewording of the rule should be a deliberate test change; the failure prints the sentence |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 draft route paragraph | yes | T001, T003 | |
| FR-002 no reviewer instruction, no "before it opened" | yes | T001, T003 | |
| FR-003 vendored copy, agents unchanged | yes | T004, T007 | |
| FR-004 test holds against negation and clause removal | yes | T001, T006 | |

## Constitution alignment

No conflict: charter, test and spec text; no door change; no config key; no runtime line; test
first; no emoji, no em dash.
