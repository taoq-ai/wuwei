# Tasks: Import only the guards an event needs

Each test task is written, run and seen failing for the stated reason before its
implementation task. Test command: `python -m pytest -q` from the repository root with the
interpreter the task names. Measurements go to a scratch directory outside the repository
and into the PR body; never write local paths into the repository.

## Phase 0: Baseline

- [X] T001 Before any code change, record the baseline per `research.md` "Measuring after
  the change": `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k latency` twice
  (keep the report lines for PreToolUse, PostToolUse, `Stop in a workspace` and
  `commit in a workspace`), the per-event guard import cost (time `discover()` after
  importing `wuwei.commands.hook`, `wuwei.env`, `wuwei.workspace`), and the audit-hook
  `open` and `subprocess.Popen` counts after discovery for PreToolUse `ls -la` in a
  workspace. No repository file changes.

## Phase 1: The import map [US2]

- [X] T002 [US2] Add `test_import_map_matches_guard_tables` to tests/test_hooks.py
  (plan.md, Tests 1). Run it. Expected failure: `AttributeError` or `ImportError`, no
  `MODULES` in `wuwei.guards`.
- [X] T003 [US2] Add `test_selected_guards_match_full_discovery` to tests/test_hooks.py
  (plan.md, Tests 2), parametrized over `EVENTS` and the tools `''`, `'Bash'`, `'Write'`,
  `'Edit'`, `'Agent'`, `'AskUserQuestion'`, `'mcp__example__operation'`, `5`. Run it.
  Expected failure: `ImportError`, no `SELECTION` in `wuwei.guards`.
- [X] T004 [US2] In cli/wuwei/guards/__init__.py add `from contextvars import ContextVar`,
  the `MODULES` literal and the `SELECTION` context variable with its `ponytail:` comment,
  and the skip condition in `discover()` (plan.md, change 4). Keep `import_module`,
  `pkgutil.iter_modules`, `module.name` and all record validation as they are. T002 and
  T003 pass; `python -m pytest -q tests/test_hooks.py tests/test_profiles.py` passes.

## Phase 2: Stop and PostToolUse never load the Bash guards [US1]

- [X] T005 [US1] Add `test_hook_imports_only_needed_guards` to tests/test_hooks.py
  (plan.md, Tests 3), parametrized over Stop, PostToolUse and PreToolUse Write, running
  the hook in a fresh `sys.executable -I -P` interpreter and reading the loaded
  `wuwei.guards.*` names from a JSON file in `tmp_path`. Run it. Expected failure: every
  case lists `commit_push`, `deploy`, `pr` (and `protect_state` for Stop and PostToolUse),
  because the hook does not set a selection yet.
- [X] T006 [US1] In cli/wuwei/commands/hook.py import `SELECTION` from `wuwei.guards` and
  set it around `guards = discover()` with a token reset in `finally` (plan.md, change 5).
  Run T005. Expected: still failing, now only because `wuwei.guards.commit_push` is loaded
  (through `workspace.guard_scope` into `workspace.scope`); confirm that is the only name
  left.
- [X] T007 [US1] Move the registry result check: add `data(result)` after `class Result`
  in cli/wuwei/registry.py; in cli/wuwei/guards/commit_push.py delete `def data` and add
  `from wuwei.registry import data` to the imports; in cli/wuwei/workspace.py replace
  `from wuwei.guards.commit_push import data` with `from wuwei.registry import data` in
  `scope` and `create_worktree` (plan.md, changes 1 to 3). T005 passes.

## Phase 3: Verify and document

- [X] T008 Run `python -m pytest -q` from the repository root; everything passes. Run
  `git diff --stat tests/` and `git diff tests/`: only tests/test_hooks.py changes, and only
  by added functions.
- [X] T009 Confirm with `grep -n "guards" cli/wuwei/workspace.py` that `workspace.py` no
  longer imports a guard module, and that `hooks/hooks.json`, `bin/wuwei` and every
  module's `GUARDS` are untouched (`git diff --stat`).
- [X] T010 Repeat the T001 measurements on the same host, back to back if possible.
  PreToolUse (`npm test` and `commit in a workspace`), PostToolUse and Stop p95 CPU and
  wall must be lower; the `ls -la` audit counts must match or drop. If a path is not
  lower, rerun on a quieter host before concluding; report both runs.
- [X] T011 Add "### Where hook time goes" to docs/site/reference.md after the 2-CPU table
  and before "### The latency CI job" (plan.md, change 6), with the M-series before and
  after figures from T001 and T010. Run `python -m pytest -q tests/test_docs.py`; it
  passes.
- [X] T012 Check every changed or added file for em-dashes, emojis and absolute local
  paths, and write the PR body notes: before and after numbers, and that the 2-CPU runner
  figures come from the CI `latency` job on the PR.
