# Tasks: worktree-workspace

## Phase 1: Tests first

- [x] T001 [US1, US2] `test_a_linked_worktree_resolves_to_its_main_checkouts_workspace`
- [x] T002 [US3] `test_a_worktree_with_no_workspace_above_its_main_checkout_and_a_plain_folder_are_no_workspace`
- [x] T003 Run at origin/main 8fc0d49b: 2 failed

## Phase 2: Implementation

- [x] T004 `ws.find` follows a linked worktree's `.git` file and `commondir` to the main checkout
- [x] T005 Vendored copy `.claude/wuwei/cli/wuwei/ws.py`
- [x] T006 SECURITY.md Hooks line

## Phase 3: Evidence

- [x] T007 `tests/test_ledger.py tests/test_setup.py`: 84 passed, 1 skipped; runtime 3,955 lines
- [x] T008 Probe: worktree of another repository, worktree with no workspace above its main, plain stray folder,
  forged loop, and the machine's real worktrees

## Phase 4: Gate round 1 at c62fdce (arch, quality, security, goal FIX)

- [x] T009 Tests red first at c62fdce (5 failed): a stray in a worktree subfolder; a redirect to a main checkout
  with no workspace (a `.git` planted in `cli/`, another repository's worktree inside the workspace); a forged
  commondir loop (RecursionError); FIFO `.git` and FIFO `commondir` (hang)
- [x] T010 `find` in one pass with no recursion, regular files only, falling back above the worktree; runtime
  3,955 lines (+6)
- [x] T011 Mutants on both copies, one at a time, `tests/test_ledger.py`. Killed: drop the `.git` name check,
  drop the fallback, drop `is_file`, drop the `break` (killed by `test_the_nearest_worktree_names_the_workspace`).
  Survives: scan from `common` as well as its parents. That one is equivalent, since nothing makes `.wuwei/` inside
  a `.git` folder. The `is_dir()` check is gone, so its mutant no longer applies.
- [x] T012 The security gate's 23-layout probe, main against the head. The six regressions it found (C, F, G, H,
  M, S) resolve to W. The intended moves (A, A2, Q, I, J, K, K2) hold. D and E (forged to a seat-made or other
  workspace) move, as main's stray could

## Phase 5: Gate round 2 at 11029df (arch and goal PASS; security and quality FIX)

- [x] T013 Tests red first at 11029df (9 failed): a `.git` file or a lone `commondir` planted above a git or a
  set-up workspace, aimed at an empty `.git` or a seat-made workspace (8 cases), and a git workspace cloned inside
  another repository's worktree
- [x] T014 The look-ahead ends at the nearest folder holding a `.git` entry or `.wuwei/config.toml`; runtime 3,955
  lines (+6). SECURITY.md names the fallback above the worktree and the boundary
- [x] T015 Mutants on both copies, one at a time: drop the name check, the fallback (to None or to path),
  `is_file`, the `break`, the `.git` boundary, the config boundary: all killed. Scan from `common` itself still
  survives, as equivalent
- [x] T016 The security gate's 29-layout probe (probe2fix2) at main and head: T, T2, T3 resolve to W; V (a stray
  without config in another repository's worktree) is None. Quality's probe2: A and B give the workspace; C keeps
  the folder; D (a `.wuwei/` with no `config.toml` below a forged `.git`) is None

## Phase 6: Gate round 3 at 37cf2af (security and quality FIX)

- [x] T017 Tests red first at 37cf2af (14 failed). `test_a_redirect_planted_above_or_at_a_workspace_never_moves_it`
  now takes the gates' layouts as parameters: T, T2, T3, E (a lone `commondir` at the root), F (a forged `.git`
  file at a set-up root), Z1 (a non-UTF-8 root `commondir`) and Z2 (a NUL one). Each runs for a git and a set-up
  workspace, aimed at an empty `.git` or a seat-made workspace
- [x] T018 The boundary moved out of the `suppress` block. A redirect needs `.git` read as a file and no
  `config.toml` at that folder. Runtime 3,955 lines (+6)
- [x] T019 Mutants on both copies, one at a time: 10 of 11 killed. The new ones were drop `text and`, drop the
  config check before the redirect, and the boundary back inside `suppress`. That last one is killed by an
  undecodable root `.git`. The name-check mutant is killed by
  `test_a_worktree_whose_common_dir_is_not_named_git_keeps_the_old_search`. Scan from `common` itself survives,
  as equivalent
- [x] T020 Probes rerun at the head. Security probe3b: Z0 to Z3 give W, and R keeps `rsib/src`. Quality probe3 E
  and probe4 F give the workspace. The 29-layout probe2fix2 moves the same 10 rows as round 3

## Phase 7: Gate round 4 at 69a1ea4 (quality PASS; security FIX, low)

- [x] T021 Test red first under Python 3.11 at 69a1ea4:
  `test_a_cwd_past_path_max_or_below_an_unreadable_workspace_folder_never_raises` (ENAMETOOLONG)
- [x] T022 The `config.toml` checks are `os.path.isfile`, and the `.wuwei/` scans are `os.path.isdir`. On 3.11 the
  final scan raised for the deep cwd as well, at main too. Runtime 3,955 lines (+6)
- [x] T023 Mutants under 3.11, one at a time on both copies: restoring `Path.is_file` on the boundary or
  `Path.is_dir` on the final scan is killed. The earlier mutants stay killed. 3.11: test_ledger, test_setup,
  test_charters 311 passed, 1 skipped. The 29-layout probe moves the same 10 rows
