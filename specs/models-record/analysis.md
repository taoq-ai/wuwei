# Specification analysis: models-record

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | MEDIUM | spec.md Clarifications | The promise says the Agent hook input has no effort field; a session transcript shows the call's input holds `effort` when passed | Resolved: read the call's `effort`, else the brief's `Model:` line; fixture claude-agent-post-model-effort.json holds the shape |
| A2 | Constraint | MEDIUM | plan.md Lines | Runtime +60 against the item's budget of 40; constitution cap 3,400 holds (3,046) | Recorded for the planner with the per-file count; no safety gap |
| A3 | Coverage | LOW | spec.md How this fails 1 | The hook cannot see paths or a logic conflict at launch | Resolved: those settings count as fits, and the note names them |
| A4 | Ambiguity | LOW | spec.md Clarifications | `CLAUDE_CODE_SUBAGENT_MODEL` turns model advice off although the call's `model` wins over it | Recorded as an assumption, from the promise's words |
| A5 | Coverage | LOW | spec.md How this fails 3 | A foreground launch writes its attest before `seat.started`, so the attest copies `unrecorded` | Recorded: the report joins by agent id and still groups the seat |
| A6 | Coverage | LOW | plan.md Design | Escapes count gates that passed a reverted PR, not the builder that wrote it | Recorded: the promise names escapes traced to a passing gate |
| A7 | Ambiguity | LOW | spec.md How this fails 3 | `effort.level` at SubagentStop may be the firing session's level | Recorded on `seat.stopped` only; the report groups by the effort asked for |

No open finding above MEDIUM, and no CRITICAL or HIGH finding.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 TABLE and frontmatter | yes | T001, T002, T010, T017 | |
| FR-002 advice only, never a decision | yes | T003, T004, T011, T019, T021 | |
| FR-003 record fields | yes | T005, T006, T012 | |
| FR-004 the models key | yes | T007, T013, T016 | |
| FR-005 doctor rows | yes | T008, T014 | |
| FR-006 Learning lines | yes | T008, T015 | |
| FR-007 runtime cap | yes | T018 | tests/test_setup.py size test; item budget in A2 |

## Constitution alignment

No conflict: stdlib only, no new door or refusal, test first, the sixth key is the one VI names,
runtime under 3,400.
