# Research: where the hook, status line and heartbeat spend their time

All figures: owner's machine class (M-series, 10 CPUs), Python 3.12 venv, host load 4.5
to 7 from other sessions, so absolute values drift by 10 to 20 percent between runs; only
same-session comparisons count. Scratch scripts lived outside the repository.

## Method

- Budgets as the job runs them: `WUWEI_BENCH=1 python -m pytest -q tests/test_hooks.py
  -k latency -s` (prints every report line).
- Imports: the launcher's own line with `-X importtime` added,
  `python3 -X importtime -I -P -c 'import runpy, sys; sys.path[:0] = sys.argv[1:3]; del
  sys.argv[1:3]; runpy.run_module("wuwei", run_name="__main__", alter_sys=True)' <cli>
  <root> hook PreToolUse`, payload `tests/payloads/PreToolUse/bash.json`, once with
  `WUWEI_WORKSPACE` at a scratch workspace with an empty `config.toml` (what
  `test_hook_latency` measures) and once from a directory outside any workspace with no
  `WUWEI_*` variables (every tool call in a non-WUWEI repository).
- Who imports a module: a `sys.meta_path` finder that prints the stack the first time a
  watched name is imported.
- Functions: the same line under `cProfile`.
- Heartbeat stages: temporary timing around `during()` and per launcher child in a scratch
  copy, under the unchanged `test_heartbeat_latency`.

## Baseline (main at 9568967)

| test | CPU p95 | wall p95 |
|---|---|---|
| `PreToolUse` | 43.9 ms | 50.3 ms |
| `PostToolUse` | 38.3 ms | 43.2 ms |
| `status --line` (10,000 events) | 51.2 ms (fails) | 59.5 ms |
| `push in a workspace` | 209.5 ms | 93.3 ms |
| `heartbeat tick` | 286 ms | 106 ms |
| `python3 -I -c pass` floor | 11.8 ms | 13.4 ms |

Floors no code change here can move: `bin/wuwei`'s shell prefix (`sh`, `$(...)`,
`dirname`) costs 3.8 ms CPU p50; `python3 -I` 9.9 ms; `import pathlib` another 3 ms
(it imports `urllib.parse` and `ipaddress`). `-S` would save 2.8 ms and a `dirname`-free
root 1.3 ms, but `tests/test_cli.py::test_shim_requires_python_311` pins
`exec python3 -I -P -c` and `test_shim_missing_dependency[dirname]` pins the `dirname`
dependency.

## Hook, outside a workspace

146 modules imported before the fix. The hook returns 0 after `reaches_workspace`, yet
it imported `tomllib`, `hashlib`, `urllib.parse`, `argparse`, `dataclasses`, `inspect`,
`typing`, `datetime`, `tempfile`, `copy`, `gettext`, `pkgutil`. Sources, by cumulative
import time: `wuwei.env` 9.9 ms (pulls `wuwei.workspace` and `wuwei.redact`),
`argparse` 3.2 ms, `wuwei.redact` 2.8 ms (3.4 ms of it is `re.compile` of five patterns),
`pkgutil` 1.8 ms, `tomllib` 1.7 ms, `inspect` 2.5 ms (via `dataclasses` in
`wuwei.registry`, loaded by `workspace.scope`), `typing` 0.9 ms (via `guards/__init__.py`
and `pkgutil`).

After the prototype: 82 modules, none of the deny list except `urllib.parse` (from
`pathlib`).

## Hook, inside a workspace (the benchmark)

cProfile total 51 ms before, 27 ms after. Before: `re.compile` 77 patterns, 12 ms under
the profiler (redact 3.4, outward tells 2.1, protect_state 1.6, tomllib 0.9, shell 0.6);
`workspace.guard_scope` 9 ms of which `load_config` 7 ms (imports `tomllib`,
`wuwei.decision`, `wuwei.registry`); `pkgutil.iter_modules` in `discover()` 5 ms (it
imports `inspect` at `pkgutil.py:135` and `typing` through `functools.singledispatch`
registration). After: remaining cost is `tomllib` (needed: the config is parsed),
`pathlib`, and the guard modules the event selects (their own regexes are used by the
checks on every Bash call).

## status --line

cProfile 75 ms before: `scan` 39 ms (`json.loads` 10,002 calls 18 ms, the loop 11 ms),
imports 35 ms (`env` 9, `redact` 5, `pkgutil.iter_modules` over `commands` 5). With the
prefilter the loop is 6 ms under the profiler and decodes none of the 10,000 silent lines.
Back-to-back CPU p95, same load: 62 to 68 ms before, 43 to 47 ms after.

Silent kinds the scan acts on before its `SILENT` check (so they must still be decoded):
`watch: clock`, `listen: clock`, `heartbeat: clock`, `decision.replied`,
`decision.decided`, `draft.sending`, `draft.sent`, `draft.dropped`, `session: wake-seen`,
`steward.run`, `remote.acknowledged`. `state.transition` is silent and skipped by its own
`continue`, so it is safe to skip.

## Heartbeat tick

Per-child wall medians in the seeded workspace: `status --line` 50 ms, `refused`
(`git push --force origin main`) 95 ms, `allowed` 45 ms, `state_write` 43 ms;
`during()` 12 ms median, 17 ms p95. Tick wall equals the slowest child. `refused` is slow
because `commit_push.check` calls `context()` (Git subprocess through the VCS adapter)
before it returns `force-push is refused`. CPU per tick 290 to 330 ms here; the runner
reports 370 to 590 ms on 4 CPUs, so contention, not the in-process probes, sets the wall.

Moving three probes in-process would cut about 140 ms of child CPU but breaks five
heartbeat tests and the mutation proof (`test_allow_all_guard_fails_the_refused_probe`
asserts `state_write` fails when the copied plugin's hook allows everything; an in-process
probe runs the importing process's guards, not the installed copy's). Not done; see the
spec's Assumptions.

## Prototype after all fixes (same session)

| test | before | after |
|---|---|---|
| `PreToolUse` CPU p95 | 43.9 ms | 30.6 ms |
| `PostToolUse` CPU p95 | 38.3 ms | 32.9 ms |
| `status --line` CPU p95 | 51.2 ms | 40.9 ms |
| hook outside a workspace CPU p95 | 44 to 60 ms | 20 to 30 ms |
| `heartbeat tick` wall p95 | 135.5 ms | 122.5 ms (load 7) |

With `discover()` kept on `pkgutil.iter_modules` (required, below), alternating runs at
load 9 (another suite running): hook in a workspace `PreToolUse` 67/68 to 57/58 ms,
`PostToolUse` 66/64 to 52/56 ms; outside a workspace `PreToolUse` 57/60 to 32/38 ms,
`PostToolUse` 55/55 to 31/35 ms. Under that load the absolute figures are inflated; the
ratios are what carries over.

## Compatibility checks found while prototyping

- `adapters/redactor/builtin.py:12,14` reads `redact.SECRET.pattern` and
  `redact.PHONE.pattern`; with pattern strings it must read `redact.SECRET` and
  `redact.PHONE`. Missing this breaks collection of `tests/test_inbox.py`.
- `tests/test_cli.py::test_dispatch_falls_back_to_discovery[True]` has `scan_probe.py`
  register `other` while `probe.py` registers `scan-probe`: the direct import must still
  fall back to the full listing (minus the module already imported) when the name is not
  registered after it.
- `tests/test_workspace.py:798-799` monkeypatches `workspace.tomllib.loads`: deleting
  the module-level import raises `AttributeError` there. A module `__getattr__` that
  imports `tomllib` on access keeps the name and keeps it off the hook path.
- `tests/test_profiles.py:92` monkeypatches `guards.pkgutil.iter_modules` and expects
  `discover()` to list through it: `os.listdir` fails the test three times. `discover()`
  keeps `pkgutil.iter_modules`; only the module-level import moves (same `__getattr__`).
- `tests/test_outward.py:567` reads `row[0]` of `outward.TELLS`: `(name, pattern)` string
  pairs keep that.
- `Result` equality is used by tests (`tests/test_listen.py:76`,
  `tests/test_remote.py:136`); `namedtuple` keeps `==` between records. No code checks
  `isinstance(..., tuple)` on a `Result` (the hook's guard-result check wants length 2).
