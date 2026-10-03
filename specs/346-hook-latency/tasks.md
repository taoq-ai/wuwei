# Tasks: Hook, status line and heartbeat under their latency budgets

Each test task is written, run and seen failing for the stated reason before its
implementation task. Test command: `python -m pytest -q` from the repository root with the
interpreter the task names. Measurements go to a scratch directory outside the repository
and into the PR body; never write local paths into the repository. No existing test
function, budget, run count, `bin/wuwei` or `.github/workflows/tests.yml` changes.

## Phase 0: Baseline

- [X] T001 Before any code change: `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py
  -k latency -s` twice, keeping every report line (plan.md, Measuring). Also time the
  bash `PreToolUse` fixture through `bin/wuwei` 60 times inside a scratch workspace and 60
  times from a directory outside any workspace (no `WUWEI_*`), p95 CPU from
  `RUSAGE_CHILDREN`. No repository file changes.

## Phase 1: Hooks pay only for what they use [US1]

- [X] T002 [US1] Add `test_hook_imports_no_unused_stdlib` to tests/test_hooks.py (plan.md,
  Tests 1), parametrized `outside` and `workspace`. Run it. Expected failure: both cases
  list `argparse`, `dataclasses` (and, outside, `tomllib`, `hashlib`, `inspect`,
  `typing`, `datetime`) in `sys.modules`.
- [X] T003 [US1] cli/wuwei/__main__.py: module imports cut to `contextlib`, `sys`,
  `env`, `redact`, `exits`; the hook fast path; `_call(func, args)` shared by both paths;
  the slow path's imports moved under the fast-path check (plan.md, change 1, first two
  blocks). Run tests/test_cli.py and tests/test_hooks.py: they pass unchanged.
- [X] T004 [US1] cli/wuwei/env.py: import `workspace` inside `initialize` (plan.md,
  change 2).
- [X] T005 [US1] cli/wuwei/redact.py: local `hashlib`, `json`, `urllib.parse` imports;
  the five patterns as strings used through `re.search`, `re.finditer`, `re.sub` with
  their flags (plan.md, change 3). adapters/redactor/builtin.py: read `patterns.SECRET`
  and `patterns.PHONE` directly (plan.md, change 4). Run tests/test_traces.py,
  tests/test_env_credentials.py, tests/test_inbox.py, tests/test_why.py: pass.
- [X] T006 [US1] cli/wuwei/workspace.py: local imports in `atomic_write`, `now`,
  `_default`, `load_config`; `CLASSES` import inside the cruise-levels loop; `registry`
  imports inside the external-worktree branch of `scope`; module `__getattr__` for
  `tomllib` (plan.md, change 5). Grep the module for other uses of the removed names
  first. Run tests/test_workspace.py (including `test_config_parsed_once_per_text`): pass.
- [X] T007 [US1] cli/wuwei/registry.py: `Result` as `collections.namedtuple` (plan.md,
  change 6). Run tests/test_adapters.py, tests/test_listen.py, tests/test_remote.py,
  tests/test_vcs.py: pass.
- [X] T008 [US1] cli/wuwei/guards/__init__.py: `Guard` as `collections.namedtuple`;
  `import pkgutil` moved into `discover()`; module `__getattr__` for `pkgutil` (plan.md,
  change 7). Run tests/test_hooks.py and tests/test_profiles.py: pass.
- [X] T009 [US1] cli/wuwei/outward.py (lazy tells), cli/wuwei/security.py (`secrets` in
  `initialize`), cli/wuwei/verdict.py (`hashlib` in its function) (plan.md, changes 9 to
  11). Run tests/test_outward.py, tests/test_canary.py, tests/test_verdict.py: pass. T002 now passes in both cases; if a deny-list module is still present, find the
  importer with a `sys.meta_path` print (research.md, Method) and defer it the same way.

## Phase 2: Guard modules keep heavy imports out of module level [US4]

- [X] T010 [US4] Add `test_guard_modules_defer_heavy_imports` to tests/test_hooks.py
  (plan.md, Tests 2). Run it. Expected failure: `agent_launch.py` imports `datetime` at
  module level.
- [X] T011 [US4] cli/wuwei/guards/agent_launch.py: move `from datetime import date,
  datetime` into the functions that use them (plan.md, change 8). Run T010 and
  tests/test_agent_launch.py: pass.

## Phase 3: The status line reads only what it shows [US2]

- [X] T012 [US2] Add `test_scan_skips_silent_lines_undecoded` to
  tests/test_signal_status.py (plan.md, Tests 3). Run it. Expected failure: the spy sees
  every `state.write` line.
- [X] T013 [US2] cli/wuwei/commands/status.py: `SKIP` and the producer-line prefilter in
  `scan` (plan.md, change 12). Run T012 and the files that drive the scan:
  tests/test_signal_status.py, tests/test_heartbeat.py, tests/test_board_mcp.py,
  tests/test_listen.py, tests/test_mcp.py, tests/test_posture.py, tests/test_remote.py,
  tests/test_shadow.py: pass.

## Phase 4: Proof [US3, US4]

- [X] T014 [US3] [US4] Repeat the T001 measurements in the same session (host load
  printed in each report line; rerun if it differs from T001 by more than 2). Keep the
  report lines for the PR body. Check SC-002 against T001; if a figure regressed, profile
  it (research.md, Method) before going further.
- [X] T015 [US4] Full suite: `python -m pytest -q`. Everything passes; no existing test
  function was edited (`git diff --stat tests/` shows additions only in
  tests/test_hooks.py and tests/test_signal_status.py).
- [X] T016 Check every file you wrote for em-dashes, emojis and absolute local paths;
  remove any. Report files changed, the last pytest summary line, the before and after
  figures, and the follow-up levers from the spec's Assumptions if a runner target is at
  risk.

## Dependencies

T001 first. T002 before T003 to T009 (T002 goes green only after T009). T010 before T011.
T012 before T013. Phases 1 to 3 are independent of each other after T001. T014 to T016
last.
