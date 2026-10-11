# Specification Analysis Report: 834-decision-cards-out

Artifacts read:

- spec.md, plan.md, tasks.md;
- `.specify/memory/constitution.md` (2.1.0);
- the #789 pass plan (owner constraints, "Process control kept", outward duties, #831 handoff);
- the code and tests at 9639dd8, with the plans of parts 12 and 13 applied.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| P1 | Process control | CRITICAL | FR-001 to FR-003 | Deleting records removes the only paths that brought a PARK or ESCALATE verdict, a cap park and a parked item's resume to the owner. | Resolved. Each has an Owner step card on a real command (`dispatch next`, `plan resume`), with tests per row (T003, T005, SC-001). |
| P2 | Owner constraint | CRITICAL | #831 handoff | The Owner step branch of `record_gate` and the `wuwei hook` refusal must survive the guard's deletion. | Resolved. `record_gate` moves to `guards/answers.py` first (Phase 1), and its cases move with it. The refusal in `protect_state` is untouched and tested (US5). |
| P3 | Dead end | HIGH | owner cards | A card that only reads Yes would ask again after No, forever. | Resolved. `sessions.owner_answer` reads No, and the code applies the safe choice: park for a verdict, defer for a scope thread, stay parked for `plan resume` (FR-005). |
| P4 | Budget | HIGH | round cap | Letting the owner resume past the cap must not open a fix round past the budget. | Resolved. Resume returns the item to its phase, and the cap check parks it again, as the old `keep` answer did (Assumption 2). |
| S1 | Scope | HIGH | parts 16 and 18 | The learning cards and the MCP decisions still use records; deleting all of `decision.py` would break them before their parts. | Resolved. `decision.py` keeps a named record library, `decide` goes, and the learning card gets `outbound answer`. The Handoff names what 16 and 18 delete, and one LEFT row is relabelled to 18. |
| B1 | Behaviour change | HIGH | observe, guarded | PARK and ESCALATE no longer auto-resolve under the mandate. | Accepted and documented (Assumption 1, Risks): the pass plan names them owner decisions. The waiting item blocks only itself. |
| T1 | Test | MEDIUM | day-walk tests | `test_path_day` and `test_e2e_day` encode the mandate path. | Resolved in tasks: rewrite them to answer the cards with `tests/fakes/owner.py`, and assert no `D-*.md` (T011). |
| F1 | Format | MEDIUM | traces digest, PR markers | The digest file and the disposition marker change shape. | Mitigated: the digest reader accepts the old shape; an old marker needs a fresh one (spec Edge Cases). |
| D1 | Constitution | LOW | design spec edits | The design spec is amended only by its owner. | Resolved: part of the owner-approved #789 pass. |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 verdict card | yes | T003, T005 |
| FR-002 cap park | yes | T003, T005 |
| FR-003 plan resume | yes | T003, T005 |
| FR-004 no record producers | yes | T005, T011 |
| FR-005 owner_answer | yes | T003, T004 |
| FR-006 deletions | yes | T006, T008 |
| FR-007 answers guard | yes | T001, T002 |
| FR-008 outbound answer | yes | T006 |
| FR-009 readers | yes | T009 |
| FR-010 config, texts, LEFT rows | yes | T010, T012, T013 |

**Constitution Alignment**: I, II, III and V hold. IV holds (red tests T001, T003, T006 to T008,
T010). VII holds: the records floor and the merge policy stay; no publishing edge changes.

**Unmapped Tasks**: none.

**Metrics**: 10 requirements, 15 tasks, coverage 100%. 2 critical and 4 high findings, all
resolved or documented.

**Next Actions**: no CRITICAL or HIGH finding is open. Proceed to implement.
