# Specification analysis: models-table

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Reach | MEDIUM | cli/wuwei/hook.py session_start, charters/planner.md | The session context is over Claude Code's 10,000-character hook cap at main (12,522 without the CLI path line) and at the head (15,834), so the session sees a file path and a 2,000-character preview | Pre-existing at main and runtime; out of this item's 0-line scope. Carried by the session-context-cap item |
| A2 | Scope | MEDIUM | charters/planner.md rule 7, models.md | The Codex mapping was added mid-build at the planner's request, while the promise said the page marks Codex unmeasured | Kept unmeasured and named as a reading of the catalog; every fact re-read at openai/codex 8c07694; role-file rendering left to models-record |
| A3 | Forward reference | LOW | charters/planner.md rule 6 | The owner's `models` rows do not exist until models-record | Recorded under Assumptions |
| A4 | Interpretation | LOW | charters/planner.md rule 3 | "Terminal gate" read as any gate on risky, owner or contract paths | Stricter than the promise and testable; recorded in Clarifications |
| A6 | Vocabulary | MEDIUM | charters/planner.md, models.md | "Trust paths" clashed with the TRUST pattern in evidence.py (arch, 901cd72) | Fixed at the delta: renamed to "risky, owner or contract paths" everywhere in the PR |
| A7 | Test strength | MEDIUM | tests/test_charters.py | The diversity test grepped words; three clause mutants survived (quality, 901cd72) | Fixed at the delta: the test parses the table and computes rule 3 and the floor over every tier and path; 12 of 12 mutants killed |
| A5 | Drift | LOW | docs/site/concepts/models.md | The page restates the table's settings with reasons | The charter is the source; the page says so in its first paragraph |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 table rows | yes | T001, T008 | |
| FR-002 ladder, diversity, effort, precedence | yes | T002, T008 | |
| FR-003 models page | yes | T003, T009 | |
| FR-004 team, codex, design | yes | T004, T010 | |
| FR-005 steward and watch | yes | T005, T011 | |
| FR-006 Codex mapping | yes | T006, T012 | |
| FR-007 build and vendor | yes | T013, T014 | |

## Constitution alignment

No conflict: charter, skill, test and docs text; no door change; no config key; no runtime line;
test first; no emoji, no em dash.
