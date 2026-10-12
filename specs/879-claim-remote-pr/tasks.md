# Tasks: pr claim on a remote-only PR creates its worktree

**Input**: [spec.md](spec.md), [plan.md](plan.md)

## Phase 1: tests first (red)

- [x] T001 [US1] `tests/test_worktree_command.py`: `test_claim_fetches_a_remote_only_branch`
  (FR-001, FR-002, SC-001); run it, see no worktree recorded.
- [x] T002 [US1] `tests/test_shepherd.py`: `test_claim_refuses_a_fork_head` and
  `test_claim_adds_a_worktree_when_none_is_on_the_branch` (FR-001, FR-003); run, see them fail.
- [x] T003 [US2] `tests/test_worktree_command.py`: `test_next_launches_a_builder_for_a_claimed_conflict`
  (FR-004, FR-005, SC-002); run it, see a `run` entry, not a builder launch.
- [x] T004 [US2] `tests/test_derive.py`: claimed PR offers (conflict and due activity are `fix`
  steps, a ready build is `build next`, a WUWEI-raised PR unchanged); run, see them fail.

## Phase 2: implementation (green)

- [x] T005 [US1] vcs `worktree_checkout` fetch and its signature (FR-002).
- [x] T006 [US1] code host `head_repo`; `claim_pr` creates or refuses (FR-001, FR-003).
- [x] T007 [US2] `pr_actions.act` conflict fix round and `pr_actions.launch` (FR-005).
- [x] T008 [US2] `derive.offers`, `derive.seated`, `launch_set`, `resolve_offer`,
  `next.resolve` (FR-004).

## Phase 3: verification

- [x] T009 Every test file importing a changed module under 3.12; worktree, pr, next and
  dispatch files under 3.11.

## Phase 4: review fix round

- [x] T010 F1: `tests/test_worktree_command.py` `test_next_never_merges_posts_or_readies_a_claimed_pr`
  (red: `merge.execute` reached from `launch_set`); `pr_actions.launch` opens only the fix round
  for conflicted, ci_red, changes_requested and threads_unanswered, through `_fix_round`, which
  returns the action instead of printing it.
- [x] T011 F2: `test_a_claimed_pr_fix_round_pushes_and_never_reaches_delta` (red: no push line,
  round 2 moved to phase fix); `tests/test_edges.py` `test_a_claimed_pr_fix_push_passes_every_edge`.
  A claimed round's brief ends with `git push <brief.remote> HEAD:refs/heads/<pr branch>` (never
  force); each round is a fresh adopted-fix brief up to `gates.max_rounds`, so the item stays raised.
- [x] T012 F3, F4, F5: `tests/test_shepherd.py` fork message read-only, host base repository name,
  a failed worktree step names the rerun and keeps exit 0.

## Phase 5: second review fix round

- [x] T013 G1: `tests/test_e2e_day.py` `test_a_claimed_pr_fix_round_is_gated_before_its_push` (red:
  the round stayed raised); the first claimed round opens in implement, `raise_action` returns
  `wuwei pr act <ref> --push` for a claimed PR, and `--push` reuses the `_rebase` push block after
  `derive._gate` says every gate passed. The push line and the `<item>-adopted-fix-n` loop are gone.
- [x] T014 G3, G4: activity is a `pr` step; `test_a_claimed_pr_at_the_round_cap_parks_once`;
  `test_claim_refuses_a_worktree_on_the_default_branch`.

## Phase 6: third review fix round

- [x] T015 H1: `test_a_gated_push_never_overwrites_a_teammate_commit` (local bare remote; red: the
  push was attempted) and `test_a_moved_claimed_pr_opens_a_merge_round_instead_of_a_push`; `--push`
  fetches the PR head and pushes only when the worktree contains it, else opens a merge fix round.
- [x] T016 H3: `test_a_commit_after_the_gate_check_is_not_pushed`; the gated head is passed to `_push`.
- [x] T017 H2: `test_a_seat_push_to_a_claimed_pr_branch_is_refused`; edges refuses a push from a
  claimed PR's worktree (state read only for git push).

## Phase 7: fourth review fix round

- [x] T018 J1: `test_a_moved_claimed_pr_at_the_round_cap_parks_for_the_owner` (red: exit 2, no park);
  `_gated_push` parks with a "round cap" reason before `open_fix` when no round is left.
- [x] T019 J2: `pr claim` records the PR head branch on the item; edges refuses a push whose
  destination is that branch from any checkout, and a push located in the worktree by -C,
  --git-dir, --work-tree, GIT_DIR or GIT_WORK_TREE (`test_a_seat_push_to_a_claimed_pr_branch_is_refused`).

## Phase 8: fifth review fix round

- [x] T020 K1: the J1 test resumes the parked item; `--push` then opens the merge round with `granted` (red: it parked again).
- [x] T021 K2: edges refuses an exported `GIT_DIR` push, `heads/<b>`, `--all`, `--branches`, glob refspecs and a relative `--git-dir` after `-C` (rows in `test_a_seat_push_to_a_claimed_pr_branch_is_refused`).
