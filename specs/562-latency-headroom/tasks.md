# Tasks: Latency headroom and a regression report

Test first: each test task runs and fails for the expected reason before its implementation
task. Fixtures are neutral. Run only the touched test files (never the full suite):
`python -m pytest -q tests/test_hooks.py tests/test_signal_status.py tests/test_outward.py
tests/test_invariants.py tests/test_latency_report.py tests/test_sessions.py tests/test_watch.py`.

## Phase 0: baseline

- [ ] T001 Baseline, no code: on the unchanged worktree run
  `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k latency -s` and
  `python -m pytest -q tests/test_invariants.py -k invariants_hold --durations=1`; keep the
  printed CPU, wall and floor of every probe and the walk time for the PR body. Profile
  `status --line`, PreToolUse bash, SessionStart and push (`-X importtime`, cProfile over
  60 runs, in-process because the launcher leaves through `os._exit`).

## Phase 1: status line (FR-001)

- [X] T002 Test in `tests/test_hooks.py`: extend `test_status_line_skips_parser_and_hashlib`
  (or add a sibling) with a config that sets a calendar adapter and a `cruise.json`; assert
  the line is unchanged and `{'wuwei.cruise', 'wuwei.sessions'}` are not
  in `sys.modules`. Fails today (cruise imported). Builder: `wuwei.registry` stays out of
  the deny set because a config parse (no cache yet) validates adapters through it; T005
  pins the integrity import instead.
- [X] T003 Test in `tests/test_signal_status.py`: `status --json` and `status` on the same
  day still carry `cruise`, `plugin`, `template`, `next_meeting`, `next_reply_due`,
  `sessions` (passes today; guards the change).
- [X] T004 Implement `snapshot(directory, line=False)` and `scan(..., config=None)` in
  `cli/wuwei/commands/status.py`; `run` passes `line=args.line`. T002 and T003 green.

## Phase 2: integrity import (FR-002)

- [X] T005 Test in `tests/test_hooks.py`: a fresh `sys.executable -I` subprocess with the
  plugin paths runs `import wuwei.integrity` and reports `'wuwei.registry' in sys.modules`
  as false. Fails today (module-level import). T002 goes green only after T004 and T006.
- [X] T006 Implement: move the `registry` imports into the functions of
  `cli/wuwei/integrity.py` that use them.

## Phase 3: outward topics (FR-003)

- [X] T007 Test in `tests/test_outward.py`: `_topics` on a table of texts (keyword alone,
  inside a longer word, with underscores, with accents removed by `_normalize`, two
  keywords, empty keyword list) returns the same dict as the per-word reference
  (`any(re.search(r'(?<!\w)' + re.escape(_normalize(w)) + r'(?!\w)', ...))`) written in the
  test; and a second call with the same keyword tuple builds no new pattern
  (`_keyword_pattern.cache_info().misses` unchanged). Fails: no `_keyword_pattern`.
- [X] T008 Implement `_keyword_pattern` with `functools.lru_cache` and use it in `_topics`
  in `cli/wuwei/outward.py`.

## Phase 4: SessionStart (FR-004)

- [X] T009 Test in `tests/test_sessions.py` (or the file holding `session_start` tests):
  wrap `state.read_state` and `watch._day_rows` (monkeypatch counting wrappers) and run
  `lifecycle.session_start` on a neutral workspace with watch and listen clock lines;
  assert the session guard's own reads are one state read and one events read beyond
  `next.step`'s, and the returned text equals the text before the change (captured on the
  base in the test as the expected literal lines). Fails today (two state reads, two
  events reads).
- [X] T010 Test: a broken `events.jsonl` still yields the same `watch.health` message and
  exit as today (passes today; guards the fallback).
- [X] T011 Implement the single reads in `session_start` in `cli/wuwei/guards/lifecycle.py`.
- [ ] T012 Profile SessionStart again; for each further cut found, first a test pinning the
  removed work (module deny set or read count), then the cut. Record figures for the PR.

## Phase 5: PreToolUse and push (FR-005)

- [ ] T013 Profile PreToolUse bash and the `push` probe after Phases 2 and 3; for each cut,
  first a test pinning it (extend the deny sets of the launcher module tests in
  `tests/test_hooks.py`), then the cut in the module profiling names. No guard dropped or
  reordered.

## Phase 6: latency artifact and report (FR-006, FR-007)

- [X] T014 Test in `tests/test_hooks.py`: with `WUWEI_LATENCY_OUT` set to a `tmp_path`
  file and `WUWEI_BENCH=1`, `assert_latency_budget('hook', 51.0, 60.0, capsys)` raises its
  `AssertionError` and the file holds one JSON line with `probe 'hook'`, `cpu_ms 51.0`,
  `wall_ms 60.0`, `budget_ms 50`, `measure 'cpu'`, the floor and load keys; with
  `wall_budget=100` the row has `budget_ms 100`, `measure 'wall'`; unset, no file. (Use the
  `startup_floor` monkeypatch of `test_latency_budget_decision`.) Fails today.
- [X] T015 Implement the row write in `assert_latency_budget`.
- [X] T016 Test file `tests/test_latency_report.py` (in-process `main(argv)` with capsys,
  one subprocess smoke run with `sys.executable`): (a) table rows for every probe with now,
  last green, change and margin; (b) status line 30 to 45 ms CPU, PreToolUse +20 percent,
  heartbeat wall 120 to 144: names `status --line`; (c) a CPU probe at 42 of 50 prints
  `margin short` and exits 1, a wall probe at 85 of 100 likewise; (d) all margins held exits
  0; (e) no previous file: `-` column, no `moved most`, margin still checked; (f) malformed
  previous: one note, treated as absent; (g) malformed or missing current: exit 2 with the
  reason on stderr; (h) a probe new in the current run shows `-` and is not named. Fails:
  no script.
- [X] T017 Implement `scripts/latency_report.py`.

## Phase 7: job (FR-008)

- [X] T018 Test in `tests/test_latency_report.py`: the `latency` job in
  `.github/workflows/tests.yml` sets `WUWEI_LATENCY_OUT`, keeps `continue-on-error: true`
  and `WUWEI_BENCH: "1"`, has `actions: read`, uploads an artifact named `latency`, and
  runs `scripts/latency_report.py` with `if: always()` (text checks on the job block, no
  YAML library). Fails today.
- [X] T019 Implement the job steps (plan item 8).

## Phase 8: invariant walk (FR-009)

- [X] T020 Test in `tests/test_invariants.py`: `test_undeclared_read_raises` sets
  `READS['I4']` to omit `kind` (monkeypatch) and asserts `walk` raises an `AssertionError`
  naming `I4`; `test_invariants_hold` asserts `len(cases) == CASES` and `CASES >= 18000`
  and `elapsed < 1.0`. Fails: no `READS`, no `UNREAD`, the 1.0 bound fails on this host
  with the current walk.
- [X] T021 Implement: module-level imports of `test_grants.run`,
  `test_decision.draft_question` and `wuwei.__main__.main`; `CASES`, `READS`, `UNREAD` and
  the projected walk; restore `elapsed < 1.0`; drop the 3.0 ponytail comment. Run the
  whole file: `test_broken_rule_is_caught` still prints full tuples, the walk is under
  0.5 s CPU here (SC-003).
- [X] T021a Review fix: `walk` returns before the per-case expansion when no check failed,
  and I1 runs as two parts (`PARTS`): its outward half on the outward projection and its
  grant half on (posture, grant), both reporting as I1. Walk measured 0.31 to 0.35 s CPU
  here, so `elapsed < 1.0` keeps about 2x headroom on the runner.

## Phase 9: docs and close

- [X] T022 Update `docs/site/reference.md#hook-latency-budget` (plan item 10); run
  `tests/test_docs.py` if it covers the page.
- [ ] T023 Re-measure every probe with T001's command at the same load; check SC-002 (each
  changed path's above-floor CPU p95 down). Report the before and
  after figures (status line at least 25 percent, the others at least 10 percent).
  Check every written file for em-dashes and emojis and for absolute local
  paths.
