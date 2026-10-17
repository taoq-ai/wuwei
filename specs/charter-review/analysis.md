# Specification analysis: charter-review

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Decision reversal | MEDIUM | charters/_gate.md, AGENTS.md | seat-rules (merged this week) put the parser-probe rules in the generic charters; this item moves them out | Two-way: the text moves, a revert restores it; recorded under Assumptions and in the PR body |
| A2 | Test brittleness | LOW | tests/test_charters.py | The 35-word test reads sentences with a splitter | The failure prints the sentence; code spans count as one word; semicolons split; the spec says the test, not the rule, is wrong when no honest split exists |
| A3 | Reach | LOW | .wuwei/standards.md | The standards lines are workspace state, not in the PR | AGENTS.md is the committed home; `wuwei sync` carries the standards to `wuwei/state` |
| A4 | Size | LOW | the diff | 65 files against main (`git diff --stat origin/main`), 30 of them hand-written (charters, skills, tests, AGENTS.md, docs, spec); the rest is `agents/` and `.claude/` rebuilt | `Size:` line in the PR body; one coherent rewrite, since splitting it would keep the rules stated twice between PRs |
| A5 | Gate selection | MEDIUM | charters/sentinel-arch.md | A contract file off a risky path runs arch without security (`evidence.needed`), so the arch gate cannot defer a trust defect | Fixed at the delta: a trust defect the arch gate sees blocks under gate rule 5 |
| A6 | Evidence | MEDIUM | spec.md, tasks.md, PR body | Red-first and size counts at 7021905 were from an earlier test version and did not reproduce | Fixed at the delta: every count re-derived from a run and named with its command |

No open finding at CRITICAL or HIGH.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 Decisions and Done once | yes | T005, T009 | |
| FR-002 repository lessons out, AGENTS.md in | yes | T003, T004, T010 | |
| FR-003 architect's gate | yes | T006, T011 | |
| FR-004 frameworks, scanner, supply chain, test quality, capacity | yes | T006, T012 | |
| FR-005 negative triggers and trigger set | yes | T007, T013 | |
| FR-006 fitness tests | yes | T001, T002, T003, T014 | |
| FR-007 build, vendor, runtime unchanged | yes | T016, T018 | |
| FR-008 docs | yes | T017 | |

## Constitution alignment

No conflict: charter, skill, test and docs text; no door change; no config key; no runtime line;
test first; no emoji, no em dash.
