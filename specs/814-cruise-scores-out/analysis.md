# Specification Analysis Report: 814-cruise-scores-out

Artifacts read:

- spec.md, plan.md and tasks.md;
- `.specify/memory/constitution.md` (1.5.0);
- the #789 pass plan, and the code and tests at ac5403f.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| A1 | Inconsistency | CRITICAL | plan.md `undo.py`, `commands/decision.py::undo` | Measured reversibility needs the decision undo. `wuwei undo rehearse decision` calls `decision undo`, which refused without a cruise window. Deleting cruise as is would make the rehearsal fail forever, and every two-way park, defer and re-plan record would turn one-way. | Resolved: `decision undo` stays one part longer, without the window check (FR-006, spec Assumption 2). Part 10 deletes it together with measured reversibility. Covered by T003 and T009 (`test_undo.py`). |
| A2 | Coverage | HIGH | `brief.mandate` | The mandate text of every seat prompt reads cruise levels. Removing them changes the prompt unless something replaces them. | Resolved: FR-003 fixes the lists from `autonomy.mode`, with the same default output. T004 is red first, and `test_builder_prompt_carries_the_mandate` pins the default. |
| D1 | Constitution | HIGH | plan.md, docs | The design spec is amended only by its owner. | Resolved: the edits are part of the owner-approved #789 pass (spec Assumption 10, plan Constitution Check). |
| D2 | Constitution | HIGH | Workflow, invariant rule | A decision rule changes: rows I11 to I14 go and I16 changes. | Resolved: the rules those rows guard are deleted. I16 keeps its route part (`decision.route`). Skip this if #798 removed the table and the walk. |
| E1 | Edge case | MEDIUM | spec Edge Cases | A record written `Decided-by: cruise` before the upgrade could make `wuwei close` report it unmeasured. | Resolved: a stored cruise answer reads as `mandate` on every read path; lint and writes refuse it (plan.md Risks). |
| E2 | Edge case | MEDIUM | `guards.shadow_*` | Deleting `wuwei shadow report` while keeping `guards.shadow_since` and `shadow_days` could leave dangling text. | Resolved: the observe-trial texts (`SHADOW_NUDGE`, `next.py` POSTURES, docs) point to the day report's `## Shadow` section. The keys go with the posture in part 15 (Assumption 1). |
| C1 | Coverage | MEDIUM | FR-007 profiles | The profile refusal rows for `decisions.cruise.*` go without a test of their own. | Accepted: an unknown profile key fails closed (`profiles.py:265` validates with no unknown list). `test_calibrate.py` keeps the `guards.mode` refusal row. |
| C2 | Coverage | LOW | telemetry | `decided_by` loses its `cruise` bucket. | Covered by the T009 edit of `test_telemetry.py`. `telemetry.CLASSES` stays pinned to `decision.CLASSES`. |
| U1 | Underspecification | LOW | README principle 5 | The new principle text is a proposal. | Accepted: T012 pins its phrases and `test_tone.py` checks its tone. |

**Coverage Summary**

| Requirement | Has task? | Task IDs |
|-------------|-----------|----------|
| FR-001 routing from fields and mode | yes | T001, T003 |
| FR-002 cisr without ambiguous | yes | T001, T003 |
| FR-003 fixed mandate | yes | T004, T005 |
| FR-004 CLASSES tuple | yes | T002, T003 |
| FR-005 Decided-by values | yes | T002, T003 |
| FR-006 decision undo without window | yes | T003, T009 |
| FR-007 modules, keys, events, sections gone | yes | T006 to T009 |
| FR-008 guard shadow data kept | yes | T009 (`test_shadow.py`; `test_report_retro.py:344` kept) |
| FR-009 docs, charters, NOTICE | yes | T011 to T014 |
| FR-010 retired table listed | yes | plan.md, T015 |

**Constitution Alignment**

- D1 and D2 are resolved as above.
- I (stdlib) holds.
- II (exits) holds.
- III (one function per behaviour) holds.
- IV holds: every behaviour change has a red test first (T001, T002, T004, T006, T007).
- V holds: the change is a net deletion.

**Unmapped Tasks**: none.

**Metrics**

- 10 requirements, 15 tasks, coverage 100%.
- Critical 1 and high 3, all resolved.

**Next Actions**: no CRITICAL or HIGH finding is open. Proceed to the checklist and implement.
