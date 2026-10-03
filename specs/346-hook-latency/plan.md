# Implementation Plan: Hook, status line and heartbeat under their latency budgets

**Branch**: `346-hook-latency` | **Spec**: `specs/346-hook-latency/spec.md` |
**Research**: `specs/346-hook-latency/research.md`

## Summary

Stop importing and compiling what a call does not use, at the shared spots every call
routes through: a hook fast path in `__main__`, function-level imports and first-use regex
compilation in eight modules, a direct command import instead of listing the commands
package, `namedtuple` records instead of `dataclass` and `typing.NamedTuple`, and a
raw-line prefilter in `status.scan`. The heartbeat gets faster through its children; its code does not change.
Three new tests. No existing test, budget, job or launcher line changes.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. Files changed:
`cli/wuwei/__main__.py`, `cli/wuwei/env.py`, `cli/wuwei/redact.py`,
`cli/wuwei/workspace.py`, `cli/wuwei/registry.py`, `cli/wuwei/guards/__init__.py`,
`cli/wuwei/guards/agent_launch.py`, `cli/wuwei/outward.py`, `cli/wuwei/security.py`,
`cli/wuwei/verdict.py`, `cli/wuwei/commands/status.py`,
`adapters/redactor/builtin.py`, `tests/test_hooks.py` and `tests/test_signal_status.py`
(new test functions only).

Must not change: `bin/wuwei`, `.github/workflows/tests.yml`, `hooks/hooks.json`, any
existing test function, `assert_latency_budget`, `startup_floor`, run counts, the
50/100/200 ms budgets, `heartbeat.py`, `adapters/watch_service.py`, the order inside
`commands/hook.run` (#323 scope first, then config, then discovery), every guard's checks
and messages, `signal.SILENT`.

## Constitution Check

- I Stdlib only: `collections.namedtuple`, `types.SimpleNamespace`, module
  `__getattr__` (PEP 562).
- II Fail closed: the fast path keeps `_main`'s status validation and exception-to-exit-2
  wrapper; an unknown event or extra argument takes the argparse path; a torn or
  hand-edited event line is decoded as today; a missing config or guard error answers as
  today.
- III One behaviour, one function: the run-and-validate step becomes one `_call` used by
  both paths; guard listing stays in `discover()`; the skip set lives next to `scan`.
- IV Test first: each new test is run red before its change (tasks.md).
- V Ponytail: no new module, no cache file, no daemon, no new abstraction; every change
  is an import moved, a constant made lazy, or a listing call replaced.

## Changes

### 1. Hook fast path (`cli/wuwei/__main__.py`)

Module imports shrink to what `main` needs on every path:

```python
from contextlib import redirect_stdout, redirect_stderr
import sys

from wuwei import env, redact
from wuwei.exits import CLEAN, FINDINGS, UNRUN
```

At the top of `_main`, after `argv` is resolved:

```python
    if len(argv) == 2 and argv[0] == 'hook':
        from types import SimpleNamespace
        from wuwei.commands import hook
        if argv[1] in hook.EVENTS:
            return _call(hook.run, SimpleNamespace(command='hook', event=argv[1]))
    import argparse
    from importlib import import_module
    import json
    from pathlib import Path
    from wuwei import commands, workspace
```

Wrap the `from wuwei.commands import hook` in the same `try`/`except Exception` shape the
slow path uses around registration, so an import error in `commands.hook` or
`wuwei.guards` prints `wuwei: <reason>` and returns `UNRUN` as today.

The tail of `_main` (status validation and the `except BaseException` that prints
`wuwei {args.command}: ...`) moves unchanged into `_call(func, args)`; the slow path ends
with `return _call(args.func, args)`.

Slow-path command dispatch: replace the unconditional listing (lines 41-51) with a direct
import when the named module file exists, and keep `pkgutil` for the fallback only:

```python
        name = argv[0].replace("-", "_") if argv else ""
        if (name.isidentifier() and not name.startswith("_")
                and (Path(commands.__file__).parent / f"{name}.py").is_file()):
            import_module(f"{commands.__name__}.{name}").register(subparsers)
        if not argv or (argv[0] != "--version" and argv[0] not in subparsers.choices):
            import pkgutil
            for module in pkgutil.iter_modules(commands.__path__, commands.__name__ + "."):
                short = module.name.rsplit(".", 1)[-1]
                if not short.startswith("_") and short != name:
                    import_module(module.name).register(subparsers)
```

The `env.load` branch for non-hook commands and the version read stay where they are.

### 2. `cli/wuwei/env.py`

Line 9 becomes `from wuwei import redact`; `initialize` starts with
`from wuwei import workspace`.

### 3. `cli/wuwei/redact.py`

- Module imports: `import re` only.
- `known_values`: the string branch runs only when `VALUES` is non-empty and imports
  `json` and `from urllib.parse import quote, quote_plus` there.
- `body_marker` and `redact` import `hashlib` (and `redact` `unquote`) locally.
- `SENSITIVE_KEY`, `SECRET`, `PHONE`, `BODY`, `HEREDOC` stay as module names but hold
  pattern strings (drop `re.compile(` and the `re.I` argument; keep `SENSITIVE_FIELD`).
  Call sites use the `re` module functions with the flags, which compile once per process
  through `re`'s own cache: `re.search(SENSITIVE_KEY, key, re.I)`,
  `re.search(SECRET, decoded, re.I)`, `re.finditer(PHONE, decoded)`,
  `re.sub(HEREDOC, ..., value)`, `re.sub(BODY, ..., value)`.

### 4. `adapters/redactor/builtin.py:12,14`

`patterns.SECRET.pattern` becomes `patterns.SECRET`, `patterns.PHONE.pattern` becomes
`patterns.PHONE`. Nothing else.

### 5. `cli/wuwei/workspace.py`

- Drop `from copy import deepcopy`, `from datetime import date, datetime`,
  `import tempfile`, `import tomllib` from the module imports.
- `atomic_write`: `import tempfile` locally.
- `now`: `from datetime import datetime` locally.
- `_default`: `from copy import deepcopy` locally.
- `load_config`: `from copy import deepcopy`, `from datetime import date` and
  `import tomllib` at the top of the function (its `except` clause names
  `tomllib.TOMLDecodeError`).
- `tests/test_workspace.py:798-799` monkeypatches `workspace.tomllib.loads`, so the name
  must keep resolving. Add, near the module constants:

```python
def __getattr__(name):
    # tomllib loads on first use, off the hook path; workspace.tomllib stays addressable.
    if name == 'tomllib':
        import tomllib
        return tomllib
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
```

  The test patches the `tomllib` module object itself, so `load_config`'s local import
  sees the patch.
- `load_config` line 484: move `from wuwei.decision import CLASSES` inside the
  `for name, value in config['decisions']['cruise']['levels'].items():` loop body.
- `scope` lines 256-257: move `from wuwei import registry` and
  `from wuwei.registry import data` into the `if any((parent / '.git').exists() ...)`
  branch, the only place that uses them.

Grep the module for any other bare use of `date`, `datetime`, `deepcopy`, `tempfile` or
`tomllib` before deleting the module imports; the research found only these.

### 6. `cli/wuwei/registry.py`

```python
from collections import namedtuple
...
Result = namedtuple('Result', 'exit data reason', defaults=(None, ''))
```

replacing `from dataclasses import dataclass` and the `@dataclass(frozen=True)` class.

### 7. `cli/wuwei/guards/__init__.py`

- `from typing import Callable, NamedTuple` becomes `from collections import namedtuple`;
  `class Guard(NamedTuple)` becomes
  `Guard = namedtuple('Guard', 'event matcher check profile_relaxable', defaults=(False,))`.
- Remove the module-level `import pkgutil` (importing it pulls `typing` through its
  `singledispatch` registration). `discover()` starts with `import pkgutil` and is
  otherwise unchanged: it still calls `pkgutil.iter_modules(__path__, __name__ + '.')`,
  because `tests/test_profiles.py:92` monkeypatches `guards.pkgutil.iter_modules` and
  expects discovery to go through it. Keep that name resolving with the same four-line
  module `__getattr__` as `workspace` (for `'pkgutil'`). Do not switch the listing to
  `os.listdir`: it would save about 3 ms (`pkgutil.iter_modules` imports `inspect`) but
  breaks that test.

### 8. `cli/wuwei/guards/agent_launch.py`

Remove `from datetime import date, datetime` at line 3; import it in the functions that
use `date` or `datetime` (lines 153 and 211 per the research; grep the file for others).

### 9. `cli/wuwei/outward.py`

`TELLS` holds `(name, pattern)` strings (drop `re.compile(pattern, re.IGNORECASE)`);
`tells()` tests `re.search(pattern, text, re.IGNORECASE)`.

### 10. `cli/wuwei/security.py`

Remove `import secrets` from the module imports; `initialize` imports it.

### 11. `cli/wuwei/verdict.py`

Remove `import hashlib` from the module imports; the function at line 160 imports it.

### 12. `status.scan` prefilter (`cli/wuwei/commands/status.py`)

Import `SILENT` already comes from `wuwei.signal`. Add below the imports:

```python
# Silent kinds scan drops with no action; the rest of SILENT is read (clocks, replies,
# draft and decision closures, wake, steward and acknowledgements).
SKIP = frozenset(SILENT) - {
    'watch: clock', 'listen: clock', 'heartbeat: clock', 'decision.replied',
    'decision.decided', 'draft.sending', 'draft.sent', 'draft.dropped',
    'session: wake-seen', 'steward.run', 'remote.acknowledged'}
```

In the loop, right after the blank-line check:

```python
                # Producer lines (state._append_jsonl) start with the kind; skip silent ones
                # undecoded. Anything else, torn lines included, is decoded as before.
                if (line.startswith('{"kind": "') and line.rstrip().endswith('}')
                        and line[10:line.find('"', 10)] in SKIP):
                    continue
```

`number` still counts every line (it comes from `enumerate`), so row keys are unchanged.

### 13. Heartbeat

No change. It gains from changes 1 to 12 in each of its four launcher children.

## Tests (new functions only)

1. `tests/test_hooks.py::test_hook_imports_no_unused_stdlib` parametrized
   `('outside', DENY)` and `('workspace', {'argparse', 'dataclasses', 'subprocess'})`
   with `DENY = {'tomllib', 'hashlib', 'argparse', 'dataclasses',
   'inspect', 'typing', 'datetime', 'subprocess'}`. Reuse the fresh-interpreter pattern of
   `test_hook_imports_only_needed_guards` (script calls `wuwei.__main__.main(['hook',
   'PreToolUse'])` and writes `sorted(sys.modules)` to a JSON file in `tmp_path`), payload
   `tests/payloads/PreToolUse/bash.json` with `cwd` replaced. Outside: cwd is a fresh
   directory under `tmp_path` with no `.wuwei`, env is `os.environ` without `WUWEI_*` and
   `GIT_*` keys; assert exit 0, empty stdout. Workspace: `tmp_path/.wuwei/config.toml`
   empty, `seed(tmp_path)` from `fakes.integrity`, `WUWEI_WORKSPACE=tmp_path`, cwd
   `tmp_path`; assert exit 0. Both assert `DENY_CASE & set(modules) == set()`. Name
   avoids "latency" so the `latency` job still selects exactly its 17 tests.
2. `tests/test_hooks.py::test_guard_modules_defer_heavy_imports`: for each
   `cli/wuwei/guards/*.py`, parse with `ast` and collect the root names of `Import` and
   `ImportFrom` nodes in `tree.body` (module level only); assert none is in
   `{'tomllib', 'datetime', 'subprocess', 'hashlib'}`. Reuse the style of
   `test_no_hook_path_imports_heartbeat`.
3. `tests/test_signal_status.py::test_scan_skips_silent_lines_undecoded`: a day (the
   file's `day()` helper) with 50 `state.write` events, one `watch: clock` and one
   non-silent event (`hook.warning` with a reason), all with `'ts': NOW` and a payload;
   `monkeypatch.setattr(status, 'json', SimpleNamespace(loads=spy, dumps=json.dumps))`
   where `spy` records each line and calls the real `json.loads`; call
   `status.scan(directory)` with `WUWEI_NOW=NOW` and `WUWEI_WORKSPACE` set; assert the spy
   saw exactly the two non-skipped lines (none containing `"state.write"`) and the result
   carries the `hook.warning` nudge and `watch` health as computed today.

## Measuring (for the PR body)

Before the first change and after the last, in the same session:
`WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py -k latency -s` twice, keeping the
report lines. The PR body pastes those and the PR's own `latency` job lines. Measurements
and scratch scripts stay outside the repository.

## Complexity Tracking

Two module `__getattr__` hooks exist only so that names existing tests address keep
resolving; they are the smallest way to defer the import without editing a test.
Rejected: `os.listdir` in `discover()` (breaks `tests/test_profiles.py:92`), in-process
heartbeat probes (breaks five heartbeat tests and the
installed-files proof), reordering the force-push refusal in `commit_push` (changes a
guard's answer), `-S` or a `dirname`-free launcher (pinned by `tests/test_cli.py`),
skipping `tomllib` for an empty config (games the benchmark; real workspaces have a
config), a day summary maintained by producers for the status line (a new writer and a
new trust question for a 10 ms read the prefilter already removes).
