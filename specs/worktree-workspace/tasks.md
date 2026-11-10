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
