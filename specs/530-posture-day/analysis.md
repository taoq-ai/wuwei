# Specification Analysis Report: 530-posture-day

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
(1.5.0) and main at 705250f. No extension hooks were run.

| ID | Category | Severity | Location(s) | Summary | Recommendation |
|----|----------|----------|-------------|---------|----------------|
| E1 | Environment | HIGH | spec.md Build base; plan.md Step 0; tasks.md T001 | The worktree branch was cut at 327dd57, before part B (#555), part C (#596), #524 (#575) and #551 (#564). `tests/test_invariants.py`, `tests/test_path_day.py`, `specs/524-merge-grant` and the `autonomy` question are missing on it. | Resolved in the artifacts: T001 checks the base and stops with a report. The orchestrator brings the worktree to main before the build (no commits on the branch, so it fast-forwards). |
| F1 | Inconsistency | HIGH | plan.md test_posture_day assertions; spec.md US1.3, FR-003 | The first draft counted cards "after setup", but `wuwei next` returns the `gate` row before the `calibrate` row (`cli/wuwei/commands/next.py:193-204`), so the gate card would have been excluded. | Resolved: the count excludes the setup card by row, not by time; the answered rows are `gate` and `calibrate` only, and `calibrate` holds the autonomy widget only. |
| F2 | Inconsistency | HIGH | spec.md (previous draft) US1.1, US1.4 | The earlier draft ran a deploy under autonomous and expected it to pass on today's grant. Part C made the autonomous default cover merges on configured repositories only, and I18 keeps every publish target on a card. | Resolved: the autonomous day has no deploy; the supervised day adds one to prove it asks (Edge Cases). |
| F3 | Inconsistency | HIGH | spec.md (previous draft) US3 | The earlier draft named the new rows I11 to I13; main took I11 to I18 (#558, #559, #560, #579, #530 C). | Resolved: the new rows are I19 (#526), I20 (#528), I21 (#533). |
| C1 | Underspecification | MEDIUM | plan.md i21 | A client or public chat is held by the default tiers with or without the word, so "held as a draft" would hold trivially. | Resolved: i21 adds owner rows that send to `C0CLIENT` and `C0PUB`, so the hold comes from the word, and its reason names the word. |
| C2 | Underspecification | MEDIUM | plan.md i20 | The I20 grid assumed 1024 MiB per seat; `calibrate.host` uses a measured seat cost when the day log has one. | Resolved: free values are built from the floor and the `seat_mib` the first call returns. |
| C3 | Underspecification | MEDIUM | plan.md card handler | "The recommended option" of a decision widget was not tied to anything the widget carries. | Resolved: the option the widget marks as the recommendation, else its first. |
| A1 | Ambiguity | MEDIUM | plan.md after handler b; spec.md Edge Cases | The review ping may not be a `wuwei next` action, and under supervised it may be held. | Kept as a stated risk: the driver runs the commands `test_scripted_day` runs and answers a held ping's draft card; a path gap goes to Deferred, not built. |
| D1 | Constitution | MEDIUM | spec.md Assumptions; plan.md tests/test_invariants.py | Moving the merge family from `OWNED` to `EXEMPT` could read as excusing walls. | Kept with its reason: constitution VII says a merge happens only through the merge policy, never by approval or override, and #524 US5 coaches a session merge to `bin/wuwei merge`. No guard text, `MERGE` or `hook.posture` changes. |
| D2 | Constitution | LOW | tasks.md | The constitution's Workflow lists `clarify` and `checklist`; this pass ran specify, plan, tasks and analyze only, as the pipeline asked. | The pipeline runs the remaining steps; no artifact change. |
| G1 | Coverage | LOW | spec.md SC-004; tasks.md T019 | The walk's 1.0 s CPU budget is covered by T019 with a fallback (narrow I21 first). | None. |
| R1 | Coverage | HIGH | spec.md Root cause 6; tasks.md T018a, T018b | Review 530e F2: #557, #556 and #552 pinned their invariants in their own tests because `tests/test_invariants.py` was not on their base, and #567 added no row; design 9.2 had no row for measured undo, novelty or the register. | Resolved: rows I22 (#557), I23 (#556), I24 (#552) and the #567 depth clause of I15, each with a walk check and a mutation entry. |
| G2 | Coverage | LOW | spec.md Deferred | The stale orientation text (`next.py:13-19`, "merges and approvals stay owner-only") is real but not exposed by the days. | Recorded under Deferred as a follow-up; not built. |

## Coverage Summary

| Requirement | Has task | Task IDs | Notes |
|-------------|----------|----------|-------|
| FR-001 shared walk, no new harness | Yes | T002 | |
| FR-002 setup answer on its card | Yes | T003 | ask before record |
| FR-003 card count | Yes | T003, T005 | |
| FR-004 WUWEI merges | Yes | T003, T005 | |
| FR-005 report lines | Yes | T003 | |
| FR-006 every refusal names a card | Yes | T003, T005 | |
| FR-007 table rows | Yes | T008, T010, T012, T014, T016, T018 | |
| FR-008 invariant checks | Yes | T009, T011, T013, T015, T017, T019 | |
| FR-009 stale marks test | Yes | T007 | |
| FR-010 small fixes or Deferred | Yes | T004, T006, T021 | |
| FR-011 no new refusal | Yes | plan What must not change | asserted by FR-006 and the walk |
| SC-001 to SC-004 | Yes | T019, T020 | |

## Constitution Alignment Issues

None open. IV (test first): every behaviour task is a test task ordered before its table or
fix task. V (ponytail): one extracted walk, no new harness, reuse of `Rules`, `READS` and the
`tests/test_merge.py` fixtures. VII: no new refusal, no rule change.

## Unmapped Tasks

None. T001 is the base check; T020 and T021 are finish tasks.

## Metrics

- Total requirements: 11 functional, 4 success criteria
- Total tasks: 21
- Coverage: 100 percent of requirements with at least one task
- Ambiguity count: 1 (A1, kept as a stated risk)
- Duplication count: 0
- Critical issues: 0; High issues: 4, all resolved in the artifacts (E1 by T001 and the
  report to the orchestrator)

## Next Actions

No CRITICAL or HIGH finding is open. Before `speckit-implement`, the worktree must be on main
at or after 705250f (E1); otherwise T001 stops the build.
