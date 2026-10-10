# Tasks: the gate depth reads the item's flags

Test first: each test task runs and fails for the expected reason before its implementation
task. No test reaches the network or a real `git`: the brief tests use the `day` fixture and
fake vcs of `tests/test_brief.py`, the tier test uses `tiered` from `tests/test_dispatch.py`.
Run only the touched test files after each pair, then the full suite (`python -m pytest -q`).

## Phase 1: step zero reads the flags (FR-001, FR-002, FR-003, US1)

- [X] T001 Test in `tests/test_process_depth.py`: give `depth_day` a `flags=None` parameter
  that updates `items.X.flags` through `state._write_state(..., reserved=False)`. Add
  `test_gate_brief_runs_step_zero_for_a_flagged_item`, parametrized over (diff, flags,
  expected) with recorded tier `standard` and a `security` gate brief
  (`brief(monkeypatch, 'Review it.', 'security', 'X', 'g', '--gate', '--worktree', 'tree')`):
  - `['cli/wuwei/mask.py']`, `{'trust_surface': True}`:
    `Depth: standard; step zero: run (trust_surface)`;
  - `['cli/wuwei/mask.py']`, `{'boundary_relevant': True}`:
    `Depth: standard; step zero: run (boundary_relevant)`;
  - `['cli/wuwei/guards/x.py']`, both true:
    `Depth: standard; step zero: run (trust_surface, boundary_relevant)`;
  - `['cli/wuwei/mask.py']`, `{'agent_surface': True}`:
    `Depth: standard; step zero: skip (no guard code or trust path in the diff); write Mutation: skipped (depth standard)`.
  Add one case at recorded tier `full` with `trust_surface` true: `Depth: full; step zero: run`.
  Run it: the first three cases fail with the skip line (the reproduced bug).
- [X] T002 Implement in `cli/wuwei/dispatch.py`: `step_zero(value, paths, trust_paths,
  flags=None)` returns `(True, ', '.join(named))` after the light and full checks when
  `trust_surface` or `boundary_relevant` is true in `flags` (in that order); docstring names
  #663.
- [X] T003 Implement in `cli/wuwei/brief.py`: `depth_line(..., flags=None)` passes `flags` to
  `dispatch.step_zero`; the brief writer's call (lines 450-452) passes `current.get('flags')`.
  T001 passes; `test_gate_brief_says_when_step_zero_runs` still passes unchanged.

## Phase 2: the security reviewer is pinned (FR-004, US2)

- [X] T004 Test in `tests/test_process_depth.py`: `test_flagged_item_gets_the_security_reviewer`:
  `tiered(root, monkeypatch, [('cli/wuwei/mask.py', 3, 1)], flags=['trust_surface'])`, then
  `dispatch.tier(root, workspace.load_config(root), state.read_state(root)['items']['A'])`
  has tier `standard`, `'security' in record['roles']` and `'lead flag trust_surface'` in
  `record['reasons']`. Expected to pass on main (no implementation task); if it fails, stop
  and report: the US2 premise in the spec is wrong.

## Phase 3: invariant I43 (FR-005)

- [X] T005 Test in `tests/test_invariants.py`: add `i43` as `plan.md` describes, register
  `'I43': i43` in `INVARIANTS` and `'I43': ()` in `READS`. Run
  `python -m pytest -q tests/test_invariants.py`: `test_table_matches_the_checks` fails
  (no I43 row in design 9.2).
- [X] T006 Docs in `docs/specs/2026-09-24-wuwei-design.md`: the I43 row after I37 in 9.2 (text
  in `plan.md`), and the 5.3 table's step-zero standard cell names the flags. T005 passes.
  If another item has taken I43 on main, use the next free number in T005 and T006.

## Phase 4: docs (FR-005)

- [X] T007 Docs in `docs/site/concepts.md` (step zero row, standard column) and
  `docs/site/daily.md` (the depth paragraph): name the `trust_surface` and
  `boundary_relevant` flags as a reason step zero runs.

## Phase 5: finish

- [X] T008 Run `python -m pytest -q` from the repository root: all green. Check every file
  touched for em-dashes and emojis.
