# Specification analysis: verdict-closed

Artifacts read: spec.md, plan.md, tasks.md, checklists/requirements.md, against the item's promise
and acceptance and the constitution.

## Findings

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| A1 | Inconsistency | LOW | plan.md Lines | The item budgets 0 runtime lines (budget 1); the free-name helper costs 2 | Resolved: the replaced-verdict message folds from 3 lines to 2, net +1, inside the budget |
| A2 | Coverage | MEDIUM | spec.md How this fails 1 | The promise names only `<stem>-2.md`; a taken or linked -2 would send the seat into a second refusal | Resolved: the free name skips listed names, links included; tests for -2, -3, -4 and links, and an end-to-end write and attest |
| A3 | Scope | LOW | spec.md Assumptions | The copy-in and replaced-verdict refusals change too, outside the promise's literal text | Recorded as an assumption, backed by the lead's brief; the revert is two expressions |
| A4 | Scope | LOW | cli/wuwei/verdict.py | The FORMAT note is not named in the promise | Recorded as an assumption: the refusal prints FORMAT, the parser is unchanged |
| A5 | Coverage | LOW | spec.md How this fails 4 | Two seats told the same free number at once | Residual: the second meets the copy-in refusal, which names the next number; no write is lost |
| C1 | Constitution | LOW | charters/_gate.md | `agents/sentinel-arch.md` sits at the 2,250 word ceiling, with no headroom | Recorded in the PR as residual risk; the next _gate.md change pays for its words |

No open finding above LOW. A2 was MEDIUM and is resolved in this change.

## Coverage

| Requirement Key | Has Task? | Task IDs | Notes |
|-----------------|-----------|----------|-------|
| FR-001 rule 6 | yes | T006, T010 | |
| FR-002 verdict block | yes | T006, T010 | the test reads the block's Findings line |
| FR-003 shape refusal names the free file | yes | T002, T003, T004, T008 | |
| FR-004 other refusals | yes | T005, T008 | |
| FR-005 agents and vendor | yes | T011 | tests/test_setup.py and bin/wuwei agents check |
| FR-006 runtime budget | yes | T012 | tests/test_setup.py size test |

## Constitution alignment

No conflict: stdlib only, no new door, no config key, test first, runtime budget held.
