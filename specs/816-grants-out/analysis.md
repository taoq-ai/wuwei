# Specification Analysis Report: 816-grants-out

Artifacts read:

- spec.md, plan.md, tasks.md;
- `.specify/memory/constitution.md` (1.5.0);
- the #789 pass plan and its "Process control kept" table;
- the code and tests at ac5403f, with parts 9 and 10's plans applied.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| P1 | Process control | CRITICAL | FR-001 to FR-003 | A grant cleared merges the policy refused: by_grant skipped auto, breaker, cap, quiet hours, item evidence, never-auto paths, size and soak. Without a replacement, those merges would stall with no owner decision. | Resolved. Each skipped condition is now either a wait the policy clears later (quiet hours, daily cap, soak) or `merge.Owner` (the rest). `merge.policy_blocked.owner` records which. `next` returns one park row for an owner block (T001 to T003, SC-003). |
| C1 | Constitution | CRITICAL | constitution VII | VII says a guard under observe and guarded is never a wall except for records, and that an owner-only action runs on the owner's recorded answer. Refusing deploys from the session in every posture contradicts both. | Resolved. VII is amended in this part (plan, Constitution Check): owner-only publishing becomes a second floor, and a merge the policy does not clear is the owner's decision. This follows the pass plan's edge list. T007 adds the dated amendment. |
| L1 | Test | HIGH | `test_reason_corpus_has_no_wall` | The new deploy reason contains "host terminal", which the kept wall lint flags. | Resolved. One EXEMPT row cites the amended floor (T007), and the grants.py rows go. This is not a loosening: the floor is now in the constitution. |
| D1 | Constitution | HIGH | design spec edits | The design spec is amended only by its owner. | Resolved: the edits are part of the owner-approved #789 pass (Assumption 9). |
| B1 | Behaviour change | HIGH | `merge.default_tier = "today"` | Workspaces that merged under the today auto-grant now need `repos.<n>.merge.auto`. | Accepted and documented in spec Edge Cases, plan Risks and the T016 PR body. The safe direction is an owner block, never an unpoliced merge. |
| E1 | Edge case | MEDIUM | `next` park row | A stale owner block from earlier in the day could park an item whose PR changed since. | Mitigated: only the latest merge event per PR counts, and a later `merge.intent` clears it. Documented in spec Edge Cases. |
| E2 | Edge case | MEDIUM | open grant cards | Cards asked before the upgrade stay pending decision routes. | Accepted: `next` asks them as plain decisions, and the answer records the option only (Assumption 8). |
| B2 | Budget | LOW | `next._seen` (#346) | More event lines are parsed. | Accepted: only lines containing `"merge.` are parsed, behind the existing substring prefilter. |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 Owner vs wait in merge.check | yes | T001, T003 |
| FR-002 execute writes owner, no grant path | yes | T001, T003 |
| FR-003 next owner row | yes | T002, T003 |
| FR-004 deploy refuses in every posture | yes | T005, T006 |
| FR-005 evidence under publish level, no card | yes | T005, T006 |
| FR-006 plan lines, understood moved | yes | T008, T009 |
| FR-007 modules, keys, events, sections gone | yes | T010 to T012 |
| FR-008 _record moved | yes | T009 |
| FR-009 docs and charters | yes | T013 to T015 |

**Constitution Alignment**:

- C1 and D1 are resolved as above.
- I holds.
- II holds: no exit-0 grant path remains.
- III holds: there is one merge decision function.
- IV holds: red tests come first (T001, T002, T005, T008, T010).
- V holds: net deletion.

**Unmapped Tasks**: none.

**Metrics**:

- 9 requirements and 16 tasks, coverage 100%.
- 2 critical and 4 high findings, all resolved or documented.

**Next Actions**: no CRITICAL or HIGH finding is open. Proceed to the checklist and
implement.
