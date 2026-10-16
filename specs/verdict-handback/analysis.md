# Specification analysis: verdict-handback

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | LOW | spec.md | The promise's line numbers predate #1081 | Resolved: located by name (pre_tool, subagent_stop, post_tool, transcript) |
| A2 | Ambiguity | LOW | spec.md Assumptions | agent_type on a subagent's PreToolUse is assumed | Recorded with its fallback: the stop path records the problem |
| A3 | Coverage | LOW | spec.md Clarifications | The #1039 fallback for an unreadable transcript moves from post_tool to the hand-back | Accepted: the hand-back message arrives in the tool input; the promise frees those lines |
| A4 | Ambiguity | LOW | spec.md Assumptions | "the sentinel charters" read as the shared charters/_gate.md | Recorded as an assumption |
| C1 | Coverage | LOW | tasks.md | Acceptance 5 (3,000 lines) has no new test | Held by tests/test_setup.py::test_the_runtime_holds_its_size_budget |

No open finding above LOW.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 deny at the hand-back | yes | T001, T003, T009 | |
| FR-002 one attest | yes | T002, T009 | |
| FR-003 verdict.missing on an ended run | yes | T004, T008, T010 | |
| FR-004 notes need no place | yes | T005, T012, T014 | |
| FR-005 re-read removed, budget | yes | T006, T011, T013 | |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
