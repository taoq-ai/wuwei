# Tasks: one broken main is one fix item

Test first: each test task runs and fails for the expected reason before its implementation
task. No test reaches git, the network or a real linter: check results are
`registry.Result(1, {'test_ids': [], 'error': ...})` with a ruff-style line such as
`cli/untouched.py:3:1: F401 'os' imported but unused`, and the item's diff is faked with
`monkeypatch.setattr(dispatch, '_changes', ...)` per worktree, plus the fixture's `vcs.status`.
Neutral fixtures only. All tests live in `tests/test_main_broken.py` unless named otherwise.

## Phase 1: build on main

- [x] T001 Fast-forward the branch onto `main`. Owner directive: build now, without #646 or
  #637. Open the fix item with the existing `plan.add`; record the hold on the held item's
  build record and in the dispatch reason, not in `depends_on`.

## Phase 2: the rule (FR-001)

- [x] T002 Tests: `fast_checks.unchanged` holds a lint location on an unchanged file (ruff,
  ruff's ` --> ` form, mypy's `./` form) and gives `[]` for a changed file, a missing file, a
  `..` path, no location, test ids, a pytest `FAILED`/`ERROR` line, one held failure beside
  one own failure, and a non-dict result.
- [x] T003 Implement `LOCATION`, `SUMMARY` and `unchanged` in `cli/wuwei/fast_checks.py`.

## Phase 3: the hold (FR-002, FR-003, FR-004; US1.1, US3)

- [x] T004 Tests: acceptance 1 (`A` and `B` fail on `cli/untouched.py`: one `main_broken`
  entry naming the check, path and both items; one fix item admitted; both actions `wait`
  naming it; no `fix_rounds`; one `build.held` per item); an item's own failure (changed,
  uncommitted, mixed, unreadable diff, test failure) gets today's `continue`; a merged fix
  gets a `-2` successor; a fix item never holds itself; no hold when `plan.add` refuses.
- [x] T005 Implement `state.held` and the `main_broken` producer (`cli/wuwei/state.py`), and
  `_save(also=)`, `_continue`, `_fix_id`, `_main_broken`, `_admit`, `_hold` and the hold in
  `complete_checks` (`cli/wuwei/commands/build.py`).

## Phase 4: the release (FR-007; US2)

- [x] T006 Tests: acceptance 2 (while the fix is open, `next_action` repeats `wait` with no
  event; once it merges, `A` and `B` each get one `continue` naming the fix and telling the
  builder to rebase and change nothing else, one `build.released` each, then a passing check
  moves `A` to `gate`); a parked fix releases, and the same failure then goes back to the
  builder.
- [x] T007 Implement `_release` and the release branch in `next_action`.

## Phase 5: next and dispatch (FR-005, FR-006, FR-008; US1.2, US1.3)

- [x] T008 Tests: `next` gives the dispatch row while `A` and `B` are held with CAP 2, the
  build row once the fix merged, and a wait row naming the item and the fix when nothing else
  is due; `launch_set` counts a held item as not building, carries its wait reason, and fills
  CAP with planned items; `candidate` and `_start` read the fix item's `main_broken` row.
- [x] T009 Implement in `cli/wuwei/commands/next.py` and `cli/wuwei/dispatch.py`.

## Phase 6: Codex loop, producers, charter (FR-009, FR-010, FR-011)

- [x] T010 Tests: `run_loop` exits 1 naming the wait reason and calls no runtime;
  `build.held` and `build.released` are reserved for `wuwei build` and silent; the builder
  charter and `agents/builder.md` carry the broken-main sentence.
- [x] T011 Implement the `wait` branch in `run_loop`, both events in `EVENT_PRODUCERS` and
  `SILENT`, the step 9 sentence in `charters/builder.md`, then `bin/wuwei agents build`.

## Phase 7: invariant and design (FR-012)

- [x] T012 Add the I57 row and the 5.3 amendment bullet to
  `docs/specs/2026-09-24-wuwei-design.md`, and `i57` to `tests/test_invariants.py`.

## Phase 8: verify

- [x] T013 Run `python -m pytest -q` from the repository root; everything passes. Check the
  changed files for em-dashes, emojis and absolute local paths.
