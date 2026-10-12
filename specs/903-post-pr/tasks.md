# Tasks: raised and claimed PRs share one post-PR path

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: tests first (red)

- [x] T001 [US1, US2] `tests/test_post_pr.py`: the issue's scenario, all PASS and arch FIX
  first (FR-001 to FR-004).
- [x] T002 [US3] red checks at gate and at delta raise a fix; red on an older PR head leaves the
  gates (FR-006, FR-007).
- [x] T003 [US4] `--complete` after a teammate's push pushes nothing (FR-008).
- [x] T004 [US2] `tests/test_edges.py`: a seat push from a raised PR's worktree is refused
  (FR-005).
- [x] T005 run them, see each fail for the stated reason.

## Phase 2: implementation (green)

- [x] T006 `rechecks` and `post_pr_gate`; `open_fix` rotates from raised; `rotate` free key.
- [x] T007 `raise_action` and `_gated_push` for any linked PR.
- [x] T008 `offers` red branch; `_fix_round` delta at the held head.
- [x] T009 `_rebase` run head lease.
- [x] T010 push guard `_owned`.
- [x] T011 docs reference paragraph.

## Phase 3: polish

- [x] T012 update the existing tests whose expectations encoded the old behaviour; full runs.

## Phase 4: review fix round

- [x] T013 tests first: base_red at gate, red with the build at its checks, a late initial not
  reviewed twice, a raised PR's seated fix launch, the --complete reset message (FR-009 to FR-012).
- [x] T014 offers takes decide first; observe records base_red; rechecks skips a late initial;
  the refusal names the reset; seated and launch cover raised PRs.
