# Feature Specification: Import only the guards an event needs

**Feature Branch**: `240-guard-import-map`
**Created**: 2026-09-30
**Status**: Ready for implementation
**Input**: Issue #240, perf(hooks): import only the guards an event needs, after profiling
on the owner's hardware. Design sections 9.1 (guard scope) and 10.6 (latency budget).
Depends on #231 (budget and report line). Evidence: whole-system review of 2026-09-30,
point B5.

## Root cause (reproduced read-only in this worktree)

Profiled on M-series hardware (10 CPUs, host load 5 to 7) through the same entry point as
`bin/wuwei hook <event>`, with a scratch workspace outside the repository. Numbers and
method are in `research.md`.

- Every hook process imports all twelve guard modules before it filters by event:
  `cli/wuwei/commands/hook.py:41` calls `discover()`, which imports every non-private
  module under `cli/wuwei/guards/` (`cli/wuwei/guards/__init__.py:33-35`). That costs 11 to
  13 ms per invocation, about a quarter of a hook's CPU. The events need far less: Stop
  needs `lifecycle` and `stop` (about 7 ms), PostToolUse needs `decision`, `traces` and
  `verdict` (about 1 ms), PreToolUse for Bash needs 6 modules (about 6 ms), PreToolUse for
  Write needs `integrity`, `outward` and `protect_state` (about 4.6 ms).
- A second path loads a Bash guard module even when discovery is filtered:
  `workspace.scope` (`cli/wuwei/workspace.py:215`) runs
  `from wuwei.guards.commit_push import data`, so every call of `workspace.guard_scope`
  (stop, traces, verdict, integrity, outward, lifecycle, and the hook itself at
  `cli/wuwei/commands/hook.py:38`) loads `wuwei.guards.commit_push`. Reproduced: with only
  the needed modules imported, Stop (`stop_hook_active` false), PostToolUse, SessionStart
  and PreCompact in a workspace still end with `wuwei.guards.commit_push` in
  `sys.modules`. `data` is a registry-result check (`cli/wuwei/guards/commit_push.py:45-52`)
  that lives in the Bash guard only by history.
- Config, scope and parse repeats are not where the time goes: `workspace.load_config`
  already caches parsed config per content per process (#211, `cli/wuwei/workspace.py:385`,
  0.055 ms per call), `workspace.scope` costs 0.1 ms and `shell.normalize` 0.02 to 0.1 ms.
  All repeats in one invocation add up to under 1 ms.

`python -X importtime` does not list the guard modules, because `importlib.import_module`
bypasses its logging; guard import cost has to be timed around `discover()`.

## User Scenarios & Testing

### User Story 1 - Hooks import only the guards their event needs (Priority: P1)

The owner's sessions pay for the guards a call can actually run and no more: a Stop or
PostToolUse hook never loads the Bash guards, and a PreToolUse hook for a non-Bash tool
loads only the guards that match that tool or any tool.

**Independent Test**: run the hook for Stop, PostToolUse and a PreToolUse Write inside a
workspace in a fresh interpreter and list the guard modules left in `sys.modules`.

**Acceptance Scenarios**:

1. Given a Stop hook (planner turn end, `stop_hook_active` false) inside a workspace, when
   it finishes, then none of `wuwei.guards.commit_push`, `wuwei.guards.deploy`,
   `wuwei.guards.pr`, `wuwei.guards.protect_state` is in `sys.modules`.
2. Given a PostToolUse hook for a Write inside a workspace, when it finishes, then none of
   those four modules is in `sys.modules`.
3. Given a PreToolUse hook for a Write inside a workspace, when it finishes, then
   `wuwei.guards.commit_push`, `wuwei.guards.deploy` and `wuwei.guards.pr` are not in
   `sys.modules` (`protect_state` holds the file guard and is loaded).
4. Given the same machine before and after, when the latency benchmarks and the stage
   profile run, then CPU and wall p95 for PreToolUse (a relevant command such as
   `git commit`, and an irrelevant one such as `ls -la`), PostToolUse and Stop are lower,
   with the numbers in the PR body.

### User Story 2 - Behaviour stays identical (Priority: P1)

The guards refuse, warn and pass exactly as before; only the imports change.

**Independent Test**: the existing suite, untouched, plus a table test that the import map
matches every guard module's own `GUARDS` list.

**Acceptance Scenarios**:

1. Given the existing guard, mutation and hook tests, when the suite runs, then they pass
   with no existing test function edited.
2. Given every built-in guard module, when its `GUARDS` records are read, then the import
   map names exactly the events it registers and, per event, exactly the tools its
   matchers select (`None` means any tool).
3. Given a PreToolUse payload whose `tool_name` is not a string, when guards are selected,
   then every PreToolUse module is imported and each matcher guard fails closed as today.
4. Given a guard module the map does not name (a new module, or a test module in a
   swapped package path), when any hook runs, then it is imported and run as today.

### Edge Cases

- A module in the map for an event whose pattern does not match the tool is not imported;
  its guards could not have matched either, because the pattern is the alternation of its
  matchers and `re.fullmatch` of an alternation matches exactly when one branch does.
- `tool_name` missing: the hook loop already uses `payload.get('tool_name', '')`; the
  selection uses the same value, so modules with a tool pattern are skipped and modules
  with `None` are imported.
- Private modules (`_name`) stay ignored.
- A module whose import raises, or whose `GUARDS` is invalid, still fails the hook closed
  with the same message whenever it is imported for the event.
- `discover()` called with no hook selection active (tests, any other caller) returns
  every guard, as today.
- Guard order stays the `pkgutil.iter_modules` order, so combined refusal messages keep
  their order.

## Requirements

- **FR-001**: The guard package holds one explicit map from each built-in guard module to
  the events it registers and, per event, the tool pattern its guards match (`None` for
  any tool). While the hook selects, a mapped module is imported only when the event is in
  its entry and the pattern is `None`, or the tool name is not a string, or the pattern
  full-matches the tool name.
- **FR-002**: A guard module found in the package path but absent from the map is imported
  for every event (a missing map entry costs time, never a skipped guard).
- **FR-003**: `discover()` with no active selection returns every guard exactly as today;
  its validation of `GUARDS` records is unchanged and applies to every imported module.
- **FR-004**: `workspace.scope` and `workspace.create_worktree` take the registry result
  check from `wuwei.registry`; `wuwei.guards.commit_push.data` stays importable with
  identical behaviour for its other callers.
- **FR-005**: A test fails when the map and the guard modules' `GUARDS` disagree.
- **FR-006**: A test fails when Stop or PostToolUse inside a workspace loads any Bash guard
  module, or a PreToolUse Write loads `commit_push`, `deploy` or `pr`.
- **FR-007**: No existing test changes. The audit-hook counts for PreToolUse `ls -la`
  (the #222 review's 6 opens and 0 subprocesses during the guard checks) do not rise.
- **FR-008**: The operator reference states where hook time goes per event on M-series
  hardware (interpreter start, imports, guard work), before and after, next to the budget.
- **FR-009**: No caching of any authorisation decision across calls; no daemon; stdlib
  only; no new runtime file.

### Key Entities

- Guard import map: module name to `{event: tool pattern or None}`, a literal in
  `cli/wuwei/guards/__init__.py`, written from each module's `GUARDS` and pinned by a
  table test.
- Hook selection: the `(event, tool name)` of the running hook invocation, visible to
  `discover()` only while the hook calls it.

## Success Criteria

- SC-001: Stop and PostToolUse in a workspace load none of the four Bash guard modules.
- SC-002: Same-machine p95 CPU and wall drop for PreToolUse (relevant and irrelevant),
  PostToolUse and Stop. Expected guard-import saving per call: about 5 ms (Stop), 10 ms
  (PostToolUse), 6 ms (PreToolUse Bash), 7 ms (PreToolUse Write).
- SC-003: The full suite passes with no existing test edited.

## Assumptions

- "Replace discovery with an explicit event-to-module map" is met by the map deciding
  every import while `pkgutil.iter_modules` still lists the package directory (0.07 ms):
  the hook tests install guard modules into a swapped package path and patch
  `guards.pkgutil.iter_modules` and `guards.import_module`, and must pass unchanged. The
  map is keyed module to events because the skip test is then one lookup and unmapped
  modules are recognisable; it carries the same information as event to modules.
- The hook passes its selection through a `contextvars.ContextVar` set around its
  `discover()` call, not as arguments: fourteen places in six existing test files
  (test_stop, test_traces, test_verdict, test_profiles, test_retro, test_env_credentials)
  replace `hook.discover` with zero-argument stubs, and the acceptance requires those
  tests unchanged.
- "Reuse config, scope and parse results within one invocation where safe" needs no new
  code: config is already cached per content per process (#211) and the remaining repeats
  cost under 1 ms in total, below the noise of the benchmark. An invocation-scoped cache
  would add state for no measurable gain; the measurement is in `research.md`.
- The "Bash guard modules" are `commit_push`, `deploy`, `pr` and `protect_state` (every
  module with a `Bash` matcher). `protect_state` also holds the file guard, so it is loaded
  for PreToolUse Write and Edit.
- The builder measures on the local M-series machine only. The 2-CPU runner numbers come
  from the CI `latency` job on the pull request; the orchestrator copies them into the PR
  and issue thread (the builder does not run `gh`). The existing 2-CPU table in the
  reference stays as #231 wrote it.
- No dry-run workspace is named for this issue; a scratch workspace outside the repository
  and the existing `seeded_workspace` benchmark fixture stand in for an installed one.
- Lazy imports of Bash guard modules inside action paths (`pr_actions._rebase`, `merge`,
  `shepherd`, the `security` honeytoken read check, `fast_checks`, `commands/build.py`,
  `commands/init.py`, `commands/git_hook.py`) stay: they run only when that action runs,
  not on the Stop or PostToolUse checks.

## Out of scope

- Base import cost outside the guards (`wuwei.env` pulls `redact`, `tempfile`, `shutil`,
  about 10 ms; `argparse` pulls `_colorize` on Python 3.14). A later issue may measure it.
- Runtime cost inside `traces.check` (it imports `steward` and `metrics`, about 7 ms,
  when it runs).
