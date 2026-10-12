# Tasks: repo, goal, parent item, scope and title carry through admission

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: tests first (red)

- [x] T001 [US1] `tests/test_admit_context.py`: a seat finding in A under G-2 keeps goal,
  repository and parent through `plan add` and `_start`; an unknown `--item`; a finding with no
  item asks for `--goal`, then `--repo` (FR-001, FR-002).
- [x] T002 [US2] an owner item admitted by title (FR-004); `test_main_broken.py` fix item
  records its repository (FR-003).
- [x] T003 [US3] an adopted worktree outside `worktrees/ITEM` (FR-005).
- [x] T004 [US4] `test_plan.py` three repositories with one PR number and one file;
  `test_shepherd.py` claim in three repositories (FR-006).
- [x] T005 run them, see each fail for the stated reason.

## Phase 2: implementation (green)

- [x] T006 `plan.adopted_id`; `_owner_prs` and `claim_pr` use it; `claim_pr` passes `repo`.
- [x] T007 `plan.add`: finding inheritance, one refusal per missing selection, `title`,
  `parent`, `evidence`, the repository check for every source (FR-002, FR-004, FR-007).
- [x] T008 `seat note --item` (FR-001); a finding in an item approved from the proposal takes
  the proposal's repository.
- [x] T009 `build._admit(repo)` (FR-003).
- [x] T010 `_start` reads the recorded worktree and promise (FR-005).
- [x] T011 builder charter, `bin/wuwei agents build`, reference and daily (FR-008).

## Phase 3: review fix round

- [x] T013 red: a PR linked to yesterday's `PR-widget-12` claimed as `PR-acme_widget-12`
  (`test_a_linked_pr_admits_no_second_item`), then FR-009 in `claim_pr`.
- [x] T014 red: `test_a_finding_launch_names_the_selection_it_needs`, then FR-010 in `next`.
- [x] T015 F2 recorded under Assumptions.

## Phase 4: verification

- [x] T012 whole suite under 3.12; the changed areas plus charters, docs, invariants under 3.11.
