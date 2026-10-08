# Tasks: SessionStart under 75 ms wall on the runner

Test first: each test task runs and fails for the expected reason before its implementation
task. Run only the touched test files (never the full suite):
`python -m pytest -q tests/test_hooks.py tests/test_sessions.py tests/test_integrity.py
tests/test_memory.py tests/test_next.py tests/test_promotion.py tests/test_digest.py`.

## Phase 0: baseline

- [X] T001 Baseline, no code: on the unchanged worktree run
  `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k "workspace_hook_latency and
  SessionStart" -s` and keep CPU, wall, floor and load; profile SessionStart with
  `python3 -X importtime` and cProfile over 60 runs; set up the interleaved A/B scratch test
  of plan "Method" step 2 outside the repository and record the A/A noise.

## Phase 1: imports the session block does not need (FR-001, FR-002, FR-003, FR-006)

- [X] T002 Test in `tests/test_hooks.py`: give `run_launcher` a `printed=False` keyword
  that skips its empty-stdout assert; add `test_session_start_loads_only_what_it_prints`
  (two `SessionStart` runs on `seeded_workspace`, the second checked) asserting none of
  `shutil`, `tempfile`, `bz2`, `lzma`, `random`, `uuid`, `calendar`, `wuwei.decision`,
  `wuwei.cruise`, `wuwei.novelty` is loaded. Run it: fails on the first nine names.
- [X] T003 Implement FR-001 in `cli/wuwei/promotion.py` (`shutil`, `uuid4` inside
  `_cruise_write`, `_snapshot`, `promote`) and `cli/wuwei/digest.py` (`monthrange` inside
  `period`). Run `tests/test_promotion.py tests/test_digest.py tests/test_memory.py`: green.
  T002 still fails (decision, ssh adapter).
- [X] T004 Implement FR-002 in `cli/wuwei/commands/next.py` (`answered` imported in `step`
  before `pending`) and `cli/wuwei/memory.py` `constraints` (import only with routes). Run
  `tests/test_next.py tests/test_memory.py tests/test_sessions.py`: green, the open
  decision lines included. T002 still fails on the ssh adapter's modules.
- [X] T005 Test in `tests/test_integrity.py`: change the three
  `monkeypatch.setattr(adapter.shutil, 'which', ...)` to `adapter._installed` with the same
  truth values; add `test_verify_leaves_no_signers_file` (`TMPDIR` set to an empty
  directory; stubbed `subprocess.run` returns 0, then 1, then raises `TimeoutExpired`;
  exits 0, 1, 2; the stub saw a `-f` path inside `TMPDIR`; `TMPDIR` empty after each). Run:
  fails (`_installed` missing).
- [X] T006 Implement FR-003 in `adapters/integrity/ssh.py`: `_installed()` on
  `os.get_exec_path()`, the private 0700 directory under `TMPDIR` or `/tmp` with an
  exclusive-create file, removed in `finally`; no `shutil`, no `tempfile`. Run
  `tests/test_integrity.py` (the real `ssh-keygen` roundtrip too) and T002: green.
- [X] T007 Measure: interleaved A/B of T003 to T006 together against the baseline copy;
  keep the figures for the PR body.

## Phase 2: one day state read fewer (FR-004)

- [X] T008 Test in `tests/test_sessions.py`: `test_session_start_reads_the_day_state_twice`
  wraps `state.read_state` and counts the calls whose `directory` argument, or
  `workspace.day_dir(root)` of their `root` argument, is today's day directory, during the
  SessionStart hook (the file's `hook` helper on the `root` day): expects 2 (`next.step`
  and the registry write). Run: fails with 3.
- [X] T009 Implement FR-004 in `cli/wuwei/guards/lifecycle.py` `session_start`: `day` from
  `_seen(...)`, read only when `None`. Run `tests/test_sessions.py tests/test_next.py
  tests/test_memory.py`: green; `test_session_start_without_day_state_creates_none` still
  green.

## Phase 3: SessionStart guards in turn (FR-005)

- [X] T010 Test in `tests/test_hooks.py`: rename
  `test_session_start_guards_run_together_in_guard_order` to
  `test_session_start_guards_run_in_guard_order`; drop the barrier; each guard appends
  `(name, threading.current_thread() is threading.main_thread())` to a module list; assert
  `[('first', True), ('second', True)]` and the unchanged
  `'first\nValueError: second failed'`. Run: fails (second runs on a worker thread).
- [X] T011 Implement FR-005 in `cli/wuwei/commands/hook.py`: delete the SessionStart
  `together` branch (lines 84-90) and its comment; one-line comment on why. Run
  `tests/test_hooks.py -k "session_start or SessionStart"` and `tests/test_next.py`
  (`test_orientation_precedes_integrity_line`): green.
- [X] T012 Measure: interleaved A/B of T011 on top of Phase 1 and 2 against Phase 1 and 2
  alone. Keep T011 only if the CPU median drops and the wall p95 does not rise; otherwise
  revert T010 and T011 and say so in the PR body and under Assumptions in `spec.md`.
  Result: wall p95 rose (94.7 to 107.0 ms) with CPU within the noise; T010 and T011 reverted.

## Phase 4: docs, figures, close

- [X] T013 `docs/site/reference.md` line 451: the SessionStart sentence per plan item 6.
  No budget or job text changes.
- [X] T014 Run the touched test files listed at the top, then
  `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k "workspace_hook_latency and
  SessionStart" -s` for the after line beside T001's. Check that the diff changes no budget
  or margin constant (`tests/test_hooks.py`, `scripts/latency_report.py`,
  `.github/workflows/tests.yml` untouched) and that no written file holds an em-dash, an
  emoji or an absolute local path. Write the PR body figures (T001, T007, T012, T014, and
  the latency job artifacts of the last green main run and of the pull request).
