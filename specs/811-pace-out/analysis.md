# Specification Analysis Report: 811-pace-out

Artifacts read: spec.md, plan.md, tasks.md, `.specify/memory/constitution.md` (1.5.0), the
#789 pass plan, and the code and tests at 221f1f2.

| ID | Category | Severity | Location(s) | Summary | Resolution |
|----|----------|----------|-------------|---------|------------|
| D1 | Constitution | HIGH | plan.md, Files to edit, docs | The constitution says the design spec is amended only by its owner; the plan edits 5.2, 5.6 and 9.2. | Resolved: the edits are part of the owner-approved #789 pass (pass plan PR 1 edits 9.2 the same way); recorded as spec Assumption 7 and in the plan's Constitution Check. |
| D2 | Constitution | HIGH | Workflow, invariant rule | A guard change (the planner allowance for `plan set pace=<p>` in `protect_state`) normally adds a 9.2 row; here rows I15 to I17 go. | Resolved: the rule they guard is deleted; the two (b) parts (a pending required check is never green; an untiered or gate-read item runs standard) are named with the existing tests that keep them (plan.md, Constitution Check and the process-control table). |
| F1 | Inconsistency | HIGH | tasks.md T009 vs phase order | T009 (Phase 2) deletes `pace.py` while `fast_checks.py` and `brief.py` still import it until T014 (Phase 3). | Resolved: T009 now says "after T014" and Dependencies gives the run order T001-T006, T011-T015, T007-T010, T016-T026. |
| C1 | Underspecification | MEDIUM | spec Edge Cases, plan Risks | A strict workspace whose config still holds `[pace]` or `repos.tests` fails to load until #799 or pass part 2 lands. The template never wrote either key, so only hand-set configs are hit. | Documented: plan.md "RETIRED at rebase" and Risks; the PR body names the keys. |
| C2 | Coverage | MEDIUM | FR-007 | The narrowed `protect_state` allowance has no test of its own. | Accepted: `plan set pace=fast` now fails in argparse before any guard matters (T007); `tests/test_protect_state.py` runs in T010 for the remaining `_planner_ticket` path. |
| C3 | Coverage | LOW | FR-009 | The `pace` field of `metrics.cycles` rows and the status `snapshot` field have no direct assertion. | Accepted: nothing reads either; the SC-002 grep (T024) catches a leftover. |
| A1 | Ambiguity | LOW | spec SC-002 | "nothing names pace" could include tests. | Resolved: SC-002 excludes `tests/`, which may write a stale day key to prove it is ignored. |
| E1 | Edge case | LOW | spec Assumption 5 | Old `pace.set` rows classify as a nudge on the upgrade day. | Accepted: one day, and nudges go in pass part 4. |

**Coverage Summary**

| Requirement | Has task? | Task IDs | Notes |
|-------------|-----------|----------|-------|
| FR-001 tier without pace, no `depth` | yes | T001, T004 | |
| FR-002 depth ignores `gates.depth` | yes | T002, T004 | |
| FR-003 launch_set CAP as derived, no hold | yes | T003, T004 | |
| FR-004 calibrate.host without load and costs | yes | T005, T004 | budget bound kept |
| FR-005 one approve option, no `--pace` | yes | T007, T008 | |
| FR-006 propose writes no pace | yes | T007, T008 | |
| FR-007 `plan set` item form only | yes | T007, T008 | C2 |
| FR-008 checks are `fast_checks` | yes | T011-T014 | push evidence guard kept |
| FR-009 modules, keys, events, metric, sections gone | yes | T009, T016-T019 | C3 |
| FR-010 docs, charters, design spec | yes | T020-T022, T024 | |
| FR-011 retired keys listed | yes | plan.md, T026 | no `workspace.RETIRED` at base |

**Constitution Alignment**: D1 and D2 resolved as above. I (stdlib), II (exits), III (one
function per behaviour), IV (each behaviour change has a red test first) and V (net
deletion; `fast_checks.commands` folded into the config list) hold.

**Unmapped Tasks**: none (T024 to T026 close SC-001, SC-002 and FR-011).

**Metrics**: 11 requirements, 26 tasks, coverage 100%, ambiguity 1, duplication 0, critical
0, high 3 (all resolved).

**Next Actions**: no CRITICAL or HIGH finding is open; proceed to the checklist and implement.
