# Implementation Plan: Import only the guards an event needs

**Branch**: `240-guard-import-map` | **Spec**: `specs/240-guard-import-map/spec.md` |
**Research**: `specs/240-guard-import-map/research.md`

## Summary

Two small changes at the shared spots every hook routes through: `discover()` in
`cli/wuwei/guards/__init__.py` consults an explicit module-to-events map before each
import while the hook's selection is set, and `workspace.scope` stops importing the commit
guard for a registry-result check that moves to `wuwei.registry`. Three new tests, one
docs section. No existing test changes.

## Technical Context

Python 3.11+ stdlib only (`contextvars`, `re`, `pkgutil`, `importlib`); pytest for tests.
Files changed: `cli/wuwei/guards/__init__.py`, `cli/wuwei/commands/hook.py`,
`cli/wuwei/registry.py`, `cli/wuwei/guards/commit_push.py`, `cli/wuwei/workspace.py`,
`tests/test_hooks.py` (new functions only), `docs/site/reference.md`.

## Constitution Check

- I Stdlib only: `contextvars.ContextVar` and `re.fullmatch`.
- II Fail closed: import errors and invalid `GUARDS` keep failing the hook with the same
  message; a non-string `tool_name` imports every module for the event so the per-guard
  matcher still fails closed; an unmapped module is imported, never skipped.
- III One behaviour, one function: selection lives in `discover()` only; the registry
  result check lives in `registry.data` only (commit_push re-exports it).
- IV Test first: each test below is run red before its change.
- V Ponytail: one literal map, one context variable, one moved function. No new file, no
  cache, no daemon, no change to guard modules' `GUARDS`.

## Changes

### 1. Registry result check moves to `wuwei.registry` (`cli/wuwei/registry.py`)

Add, right after `class Result` (line 104), the body of `commit_push.data` unchanged
except that it no longer imports `registry`:

```python
def data(result):
    if not isinstance(result, Result) or type(result.exit) is not int or result.exit != 0:
        raise ValueError(getattr(result, 'reason', '') or 'VCS operation unavailable')
    if not isinstance(result.data, dict):
        raise ValueError('malformed VCS data')
    return result.data
```

### 2. `commit_push` re-exports it (`cli/wuwei/guards/commit_push.py:45-52`)

Delete `def data(result)` and add `from wuwei.registry import data` to the module
imports. `pr.py:13`, `fast_checks.py:7` and `commands/build.py`, which import `data` or
`context` from `commit_push`, stay as they are.

### 3. `workspace` imports it from the registry (`cli/wuwei/workspace.py:215` and `:436`)

Replace `from wuwei.guards.commit_push import data` with
`from wuwei.registry import data` in `scope` and in `create_worktree`. Nothing else in
`workspace.py` changes. After this, `guard_scope` loads no guard module.

### 4. The import map and selection (`cli/wuwei/guards/__init__.py`)

Add `from contextvars import ContextVar` and, below `EVENTS`:

```python
# Each built-in guard module's events and, per event, the tools its matchers select
# (None: any tool). discover() skips a module the hook's event and tool cannot run;
# a module missing here is imported for every event. tests/test_hooks.py pins this
# to the modules' GUARDS.
MODULES = {
    'agent_launch': {'PreToolUse': 'Agent', 'SubagentStop': None},
    'commit_push': {'PreToolUse': 'Bash'},
    'decision': {'PostToolUse': 'Write|Edit|MultiEdit|NotebookEdit|Bash',
                 'PreToolUse': 'AskUserQuestion'},
    'deploy': {'PreToolUse': 'Bash'},
    'integrity': {'PreToolUse': None, 'SessionStart': None},
    'lifecycle': {'SessionStart': None, 'PreCompact': None, 'Stop': None},
    'outward': {'PreToolUse': None},
    'pr': {'PreToolUse': 'Bash'},
    'protect_state': {'PreToolUse': 'Write|Edit|MultiEdit|NotebookEdit|Bash'},
    'stop': {'Stop': None},
    'traces': {'PostToolUse': None},
    'verdict': {'PostToolUse': 'Write|Edit|MultiEdit|NotebookEdit|Bash', 'SubagentStop': None},
}
# ponytail: the hook's (event, tool_name) travels in context, not as discover()
# arguments, because tests replace hook.discover with zero-argument stubs; make it a
# parameter when those stubs take arguments.
SELECTION = ContextVar('SELECTION', default=None)
```

In `discover()`, read `selection = SELECTION.get()` once, and in the loop skip a module
when its short name starts with `_` (as today) or when all of these hold: `selection` is
not `None`, the short name is in `MODULES`, and either the event is not in
`MODULES[name]`, or the pattern is not `None`, the tool is a `str`, and
`re.fullmatch(pattern, tool)` is `None`. Everything after the skip (import, `GUARDS`
validation, `guards.extend`) is unchanged. Keep using the module-level `import_module`
and `pkgutil.iter_modules` and `module.name`: existing tests patch exactly those.

### 5. The hook sets the selection around discovery (`cli/wuwei/commands/hook.py:41`)

Import `SELECTION` with the other names from `wuwei.guards` (line 9) and replace
`guards = discover()` with:

```python
        token = SELECTION.set((args.event, payload.get('tool_name', '')))
        try:
            guards = discover()
        finally:
            SELECTION.reset(token)
```

It stays inside the existing `try` at lines 30-45, so a failure keeps the same refusal.
The tool value is the same expression the guard loop uses at line 51. The guard loop,
matcher check, result validation, profile handling and refusal output do not change.

### 6. Operator reference (`docs/site/reference.md`)

After the 2-CPU table of the "Hook latency budget" section and before "### The latency CI
job", add "### Where hook time goes": one table per event on M-series hardware
(startup floor, guard imports, p95 CPU and wall) before and after, from the measurements
in tasks T001 and T010, and two sentences: each hook imports only the guard modules its
event and tool can run (`MODULES` in `cli/wuwei/guards/__init__.py`); a guard module
missing from that map is imported for every event. Keep every phrase that
`tests/test_docs.py::test_reference_states_hook_latency_budget` checks.

## Tests (all new functions in `tests/test_hooks.py`)

1. `test_import_map_matches_guard_tables` (FR-005): iterate the real guard package with
   `pkgutil.iter_modules(wuwei.guards.__path__, 'wuwei.guards.')`, skip `_` modules, and
   build `{name: {event: None if any matcher is None else '|'.join(matchers in GUARDS order)}}`;
   assert it equals `wuwei.guards.MODULES`. Red before change 4: no `MODULES`.
2. `test_selected_guards_match_full_discovery` (FR-001, FR-002, FR-003), parametrized over
   every event in `EVENTS` and tools `''`, `'Bash'`, `'Write'`, `'Edit'`, `'Agent'`,
   `'AskUserQuestion'`, `'mcp__example__operation'` and `5`: with `SELECTION` set to
   `(event, tool)` (token reset in `finally`), the guards the hook loop would run
   (`g.event == event` and, for a string tool, `g.matcher is None or re.fullmatch(g.matcher, tool)`)
   equal, in order, the same filter over `discover()` with no selection; for the
   non-string tool compare all guards of the event. Red before change 4: no `SELECTION`.
3. `test_hook_imports_only_needed_guards` (FR-006), parametrized:
   `('Stop', {commit_push, deploy, pr, protect_state})`,
   `('PostToolUse', same four)`, `('PreToolUse', {commit_push, deploy, pr})` with the
   Write payload. Set up `tmp_path/.wuwei/config.toml` (empty) and `fakes.integrity.seed(tmp_path)`;
   payload is `fixture(event)` (for PreToolUse the `write.json` payload) with
   `cwd=str(tmp_path)` and, for Stop, `stop_hook_active=False`. Run a fresh interpreter,
   because loaded modules are process state and other tests import every guard:
   `subprocess.run([sys.executable, '-I', '-P', '-c', script, str(ROOT / 'cli'), str(ROOT), event, str(out)], input=..., text=True, capture_output=True, cwd=tmp_path, env={**os.environ, 'WUWEI_WORKSPACE': str(tmp_path)})`
   where `script` puts the two paths first on `sys.path`, calls
   `wuwei.__main__.main(['hook', event])`, and writes the sorted `wuwei.guards.*` names in
   `sys.modules` as JSON to `out`. Assert exit 0 and that the expected set is disjoint from
   the loaded names. Red on main: every module is loaded. Still red for `commit_push` after
   change 4 alone (through `workspace.scope`); green after changes 1 to 3.

## Must not change

- Any existing test function, fixture, payload or expected message.
- Any guard module's `GUARDS`, checks or messages; `hooks/hooks.json`; `bin/wuwei`.
- `discover()` with no selection: same guards, same order, same validation errors.
- Refusal format, exit codes, `hook.refusal` and `hook.warning` events.
- Authorisation is decided per call; nothing is cached across hook invocations.

## Verification

- `python -m pytest -q` from the repository root: all pass, `git diff tests/` shows only
  added functions in `tests/test_hooks.py`.
- Before and after measurements per `research.md` "Measuring after the change", in the PR
  body: benchmark lines for PreToolUse (`npm test` and `commit in a workspace`),
  PostToolUse and Stop in a workspace, the per-event guard import cost, and the audit
  counts for `ls -la`.
