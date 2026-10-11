# Specification Analysis Report: 798-invariant-walk-out

Artifacts: `spec.md`, `plan.md`, `tasks.md`, checked against `.specify/memory/constitution.md`
(1.5.0), design 4.6, 4.7 and 9.2, issue #798, the pass plan #789 and the code on main at
bfbf6a3.

## Findings

| ID | Category | Severity | Location | Summary | Resolution |
|----|----------|----------|----------|---------|------------|
| A1 | Constitution | CRITICAL | constitution Workflow, last bullet; spec FR-009 | The change removes the rule that every guard change adds a 9.2 row and a walk check; a feature may not silently drop a constitution rule. | Resolved: the removal is an explicit, owner-ordered constitution amendment in this feature (pass plan #789, issue acceptance), versioned 2.0.0 under the speckit-constitution MAJOR rule and dated 2026-10-11 in the footer and the commit message (T014, T020). No guard changes here, so the old rule is not broken in the meantime. |
| A2 | Governance | HIGH | constitution Governance; spec FR-010 | The design spec is amended only by its owner. | Resolved: the owner ordered the 9.2 replacement in the pass plan; recorded under Assumptions. The new text is given verbatim in plan.md so the builder adds nothing of their own. |
| A3 | Test first | HIGH | constitution IV; tasks T002 to T005 | Moved tests pass on arrival, so red-before-green is not shown by default. | Resolved: T003 and T005 break the guarded rule with a temporary monkeypatch (`guards.pr.gate_check`, `merge.owner_hold`), see the test fail, and revert. |
| A4 | Coverage | HIGH | spec FR-003, plan removed-units table | Deleting the walk could drop the only test of a kept process rule. | Resolved: every (b) row names a passing test outside the walk, checked by grep on main (I3, I6, I17, I20, I25, I26, I27, I34, I35, I37, I38, I39, I40, I42, I43, I44, I72 and the trust-surface case). The two rows with no other test of the exact path (moved head under the auto policy, `owner_merge` on all five paths) move. |
| A5 | Scope | MEDIUM | issue scope; spec Clarifications | The issue names `tests/test_dispatch.py` as a destination; the plan adds nothing there. | Resolved: dispatch has no merge step and never reads `owner_merge`; all three cases need the merge fixture. Recorded with the evidence. |
| A6 | Ambiguity | MEDIUM | issue "one case each" | `owner_merge` keeps five parametrized paths. | Resolved: one test per invariant, keeping only the process-error axis; the five paths are the point of that invariant. |
| A7 | Consistency | MEDIUM | plan items 3 and 4 vs pass plan detail | The keep lists add `test_hero_files_match_their_generator`, `test_charter_sentences_have_one_home` and two lint self-tests to the pass plan's lists. | Resolved: they pin no prose (the issue keeps structural tests); recorded under Clarifications. |
| A8 | Regression | MEDIUM | README, NOTICE, constitution edits | `tests/test_tone.py` (docs class) and `tests/test_calibrate.py` read README and the constitution. | Resolved: each edited sentence stays under 35 words and plain; T017 runs both files; no budget is touched. |
| A9 | Constitution | LOW | Constraints: "a test reads them" | Deleting `test_never_blocking_rule_is_written_down` could look like dropping the never-blocked test. | Accepted: the test that reads skills and charters is `test_no_blocking_instruction_in_skills_or_charters`, which stays. |
| A10 | Drift | LOW | comments citing 9.2 ids | `pace.py`, `commands/init.py`, `guards/__init__.py` and some test comments cite rows that leave 9.2. | Accepted: each unit is deleted by a later PR of the pass; listed under Clarifications. |
| A11 | Invariants | LOW | design 9.2 | No guard or decision rule changes. | No new row; the edge rows restate guards that exist. |

No open CRITICAL or HIGH finding.

## Coverage

| Requirement | Tasks |
|-------------|-------|
| FR-001 | T007, T009 |
| FR-002 | T010 |
| FR-003 | T002, T003, T004, T005 |
| FR-004 | T006 |
| FR-005 | T011, T013 |
| FR-006 | T012, T013 |
| FR-007 | T008, T009 |
| FR-008 | T010 |
| FR-009 | T014, T020 |
| FR-010 | T015 |
| FR-011 | T016, T017 |

Requirements with at least one task: 11 of 11. Unmapped tasks: T001 (baseline), T018 and
T019 (close).
