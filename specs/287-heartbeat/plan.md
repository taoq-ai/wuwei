# Implementation Plan: Heartbeat: the watch proves the system is alive and behaving

**Branch**: `287-heartbeat` | **Date**: 2026-10-01 | **Spec**: `specs/287-heartbeat/spec.md`

## Summary

One new core module, `cli/wuwei/heartbeat.py`, holds the probe table and three functions:
`measure` (run every probe once), `health` (fold results) and `beat` (the watch's per-tick
step: drift, page text, ping, one record write). Everything else is a small edit at the
shared spot each consumer already routes through:

- process launches and the ping go into the existing fixed adapter
  `adapters/watch_service.py`, already loaded by `registry.watch_service()`;
- `watch.tick` calls `heartbeat.beat` once, right after the clock step;
- `status.scan` keeps the last `heartbeat: clock` payload in its existing single pass, and
  `status.line` prints `health <value>`; `nudges`, session start, the cockpit, SwiftBar and the
  phone status all read `scan`/`snapshot`/`line` already, so they get it for free;
- `integrity.fresh` adds the mtime freshness check next to `integrity.cached` (which stays
  untouched, it is on every PreToolUse);
- `commands/config.py` exposes its credential table so the config probe and `config check`
  share it;
- `commands/hook.py` skips the `hook.refusal` record for the heartbeat's own session id.

Measured on `main` on an M-series Mac (scratch workspace, seeded clean verdict, real
launcher): `git push --force origin main` refused in 111 to 118 ms, `ls -la` allowed in 54 to
67 ms, the `.wuwei` state Write refused in 51 to 59 ms, one at a time. Started together with
`status --line`, all four finish in 112 to 129 ms wall. `agent_launch.free_memory` takes 22 ms
including imports. So the heartbeat fits under 200 ms only when the launcher calls run
concurrently and the in-process probes run while they do; that is the one non-obvious design
choice below.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only
**Testing**: pytest; in-process tests with a faked `registry.watch_service()`; one real
launcher smoke test and one real mutation test; one latency benchmark in
`tests/test_hooks.py` (runs with `-k latency`)
**Constraints**: three-state exits, fail closed, no subprocess or `urllib.request` in the core
(`tests/test_adapters.py::test_core_does_not_access_process_launchers`), hook path unchanged
in cost, one new config key (`watch.ping_url`)

## Constitution Check

- Reuse: `watch.save` (shared writer, reserved `watch` key), `watch.records` and
  `watch.health` (clock rule of #210), `integrity.cached`, `agent_launch.free_memory`
  (host port and floor), `sessions.rows`/`sessions.stale_seconds`, `state.lock_ex`,
  `registry.watch_service()`, the page tier in `status.scan`. No new adapter kind, no new
  registry loader, no new state key.
- Ports: subprocess and urllib live only in `adapters/watch_service.py`, behind a closed
  argument allowlist and a fixed launcher path.
- Test first: every task in tasks.md has its failing test ordered first.
- Fail closed: an unmeasurable probe is `unmeasured`, never `ok`; health is never `ok` with an
  unmeasured probe; the ping is withheld unless health is `ok`.
- Ponytail: no probe class, no registry of probe functions, no config for the probe set, the
  timeouts or the status-line budget. The table is a tuple of names and descriptions.

## Changes

### `adapters/watch_service.py` (fixed adapter, extended)

Docstring becomes "Allowlisted local process and network calls for the watch: service
manager, heartbeat probes and the dead-man ping." Add:

```python
LAUNCHER = Path(__file__).resolve().parents[1] / 'bin/wuwei'
PROBE_ARGS = (('hook', 'PreToolUse'), ('status', '--line'))


def probe(calls, cwd, during=lambda: None, timeout=10):
    """Start allowlisted launcher calls together, run `during`, then collect each one.

    calls: [(argv tuple, stdin text)]. Returns ([(exit or None on timeout,
    first stderr line, wall ms)], during()).
    """


def ping(url, timeout=5):
    """GET an https check URL; raise OSError or ValueError on any failure."""
```

- `probe` raises `ValueError('unsupported probe command')` for any argv not in `PROBE_ARGS`,
  before starting anything. Each call is `subprocess.Popen([str(LAUNCHER), *argv], cwd=cwd,
  stdin=PIPE, stdout=DEVNULL, stderr=PIPE, text=True)`; write the stdin text and close stdin
  right after starting (otherwise a hook blocks reading stdin until its turn and the calls
  serialise). Gotcha: `Popen.communicate` flushes `stdin` and fails on a closed file, so set
  `process.stdin = None` after closing it (or read stderr and `wait` with the shared deadline).
  All calls share one deadline of `timeout` seconds from the first start; a call past it is
  killed and reported as `(None, 'timeout', ms)`. A `finally` kills anything still running.
  Wall ms is measured from each call's start to its collection; put `status --line` first in
  `calls` so its figure is not inflated by waiting on the others.
- `ping` refuses a URL not starting with `https://` (`ValueError('ping URL must be https')`),
  then `urllib.request.urlopen(url, timeout=timeout)` and reads at most 1 KiB. `HTTPError`
  and `URLError` are `OSError` subclasses.
- `call` (service manager) is unchanged.

### `cli/wuwei/heartbeat.py` (new)

```python
"""Synthetic probes: the watch proves the hooks still refuse, allow and answer in budget."""

PROBES = (  # data: order is the page order; docs/site/reference.md lists every row
    ('refused', 'hook PreToolUse refuses git push --force origin main (exit 2)'),
    ('allowed', 'hook PreToolUse allows ls -la (exit 0)'),
    ('state_write', "hook PreToolUse refuses a Write to today's state.json (exit 2)"),
    ('state', 'state.lock taken within 1 s and day state read'),
    ('integrity', 'cached integrity verdict clean and no plugin file newer than it'),
    ('config', 'config.toml loads and selected adapters have their credentials'),
    ('clocks', 'watch and listener clocks alive or off'),
    ('status_line', 'status --line exits 0 within 200 ms wall'),
    ('planner', 'planner session live, or no planner today'),
    ('memory', 'free memory at or above host.free_memory_mb'),
)
STATUS_LINE_BUDGET_MS = 200  # ponytail: one wall sample, the p95 lives in the latency benchmarks
CODES = {'ok': 0, 'degraded': 1, 'unmeasured': 2}
```

- `measure(root)` returns `{name: {'result': 'ok'|'failed'|'unmeasured', 'value': str}}` in
  `PROBES` order. It builds four calls: `status --line` with empty stdin, then three
  `hook PreToolUse` payloads, each `{'session_id': HEARTBEAT_SESSION, 'transcript_path':
  os.devnull, 'cwd': str(root / '.wuwei'), 'hook_event_name': 'PreToolUse', 'tool_name': ...,
  'tool_input': ...}` with Bash `git push --force origin main`, Bash `ls -la`, and Write
  `{'file_path': str(workspace.day_dir(root) / 'state.json'), 'content': ''}`. It calls
  `registry.watch_service().probe(calls, root / '.wuwei', during=<the in-process probes>)`.
  If the adapter raises (`OSError`, `ValueError`), the four launcher probes are `unmeasured`
  with the reason and the in-process probes run anyway. Each in-process probe is wrapped so
  that one exception in `ERRORS` (reuse `watch.ERRORS`) makes only that probe `unmeasured`.
- Launcher results: `refused` and `state_write` ok on exit 2, `allowed` ok on exit 0; value
  `exit N`, plus `: <first stderr line>` when not ok; `None` exit is `unmeasured` `timeout`.
  `status_line` ok on exit 0 and ms within `STATUS_LINE_BUDGET_MS` (value `<ms> ms`), failed on
  another exit or over budget (`<ms> ms over 200 ms`).
- `state`: `directory.mkdir(parents=True, exist_ok=True)` for today's day dir, open
  `state.lock` for append, `state.lock_ex(lock, 'state.lock', timeout=1)`, then
  `state.read_state(root)`; value is the wait in ms. `TimeoutError` (the stuck lock) and
  `ValueError` (unreadable state) are `failed` with the message; catch `TimeoutError` before
  the generic `OSError`, because it is one.
- `integrity`: `integrity.fresh(root)`; exit 0 is ok, anything else is `failed` with the reason
  (a cached exit 2 already makes every guard refuse, so the system is not behaving).
- `config`: `workspace.load_config(root)`; `ConfigError` is `failed` with its text; then
  `commands.config.missing(config)`; any name is `failed` with `missing <names>`; else ok
  `complete`.
- `clocks`: one `watch.records(workspace.day_dir(root) / 'events.jsonl')` read, then
  `watch.health(root, stamps, name=name)` for `watch` and `listen` with each one's stamps
  (passing the list skips a second read). Any code 1 is `failed` with the message, else any
  code 2 is `unmeasured`, else ok with e.g. `watch alive, listen off`.
- `planner`: `state.read_state(root).get('planner_session_id')`; none is ok `no planner`;
  otherwise the row from `sessions.rows(data, workspace.now(), sessions.stale_seconds(root))`:
  missing, stale or carrying `stopped` is `failed` (`planner <id> not registered` or
  `idle <n>s`), else ok `idle <n>s`.
- `memory`: when `config['adapters']['host'] == 'none'`, `unmeasured` `host adapter none`
  without calling the adapter (the none adapter appends an `adapter: none` nudge per call);
  else `agent_launch.free_memory(config, root) // 2**20` against `config['host']
  ['free_memory_mb']`, value `<n> MiB`.
- `health(probes)`: `degraded` if any `failed`, else `unmeasured` if any `unmeasured`, else `ok`.
- `beat(root)`: `probes = measure(root)`; `prior = watch.saved(root).get('heartbeat', {})
  .get('probes', {})`; `drift` = names `failed` now and `ok` in `prior`; `page` = '' or, for the
  first failed probe in table order, `heartbeat <name> failed: <value>` prefixed with
  `behaviour drift: ` when that probe drifted; `ping` from `_ping(root, status)`; then
  `watch.save(root, {'heartbeat': record}, kind='heartbeat: clock', payload=record)`. Print
  `heartbeat: behaviour drift: <name>` per drifted probe and the page text when there is one.
  Return `CODES[status]`. Wrap the whole body: `ERRORS` prints `heartbeat unmeasured: <exc>`
  and returns 2.
- `_ping(root, status)`: URL from `workspace.load_config(root)['watch']['ping_url']`
  (`withheld` when config cannot load); empty is `off`; `status != 'ok'` is `withheld`; else
  `registry.watch_service().ping(url)` is `sent`, and `OSError`/`ValueError` prints
  `heartbeat ping failed: <urlsplit(url).hostname or 'invalid URL'>: <type(exc).__name__>`
  and is `failed`. Never print or store the URL itself.

### `cli/wuwei/commands/heartbeat.py` (new command module, auto-discovered)

`register` adds `heartbeat` (help "Probe that hooks refuse, allow and answer in budget");
`run` calls `heartbeat.measure(workspace.find_workspace())`, prints
`<name>: <result> <value>` per probe and returns `heartbeat.CODES[heartbeat.health(probes)]`.
It never calls `beat`, so it writes no state, appends no event and sends no ping.

### `cli/wuwei/watch.py`

`tick`: right after the `clock_at` block (line 399), add

```python
    from wuwei import heartbeat
    result = max(result, heartbeat.beat(root))
```

Nothing else in `watch.py` changes.

### `cli/wuwei/commands/hook.py`

Add `HEARTBEAT_SESSION = 'wuwei-heartbeat'` (here, so the heartbeat imports it and the hook
never imports the heartbeat). `refuse` gains `record=True`; the `hook.refusal` append runs only
when `record` is true. The final `refuse` call in `run` passes
`record=payload.get('session_id') != HEARTBEAT_SESSION`. One string comparison on a refusal
path; nothing on the allow path changes.

### `cli/wuwei/commands/status.py`

- `scan`: add `beat = None` to the initial tuple; next to the clock capture (line 48) add
  `if kind == 'heartbeat: clock': beat = payload` (before the `SILENT` skip). After the
  watch/listen health block (line 129), compute `beat_health`: None without a line; the
  payload's `health` when `health['watch'] == 'alive'`, the payload is a dict, `health` is one
  of `ok`, `degraded`, `unmeasured` and `page` is a string; `unmeasured` otherwise. When it is
  `degraded` and `page` is non-empty, add `current[('heartbeat',)] = {'tier': 'page', 'source':
  'heartbeat', 'lane': 'Work', 'reason': beat['page']}`. Return a fourth value, `beat_health`.
  Still one pass.
- `attention` keeps `[0]`. `snapshot` unpacks four values into `result['health']`.
- `line`: after the listen part, `if data.get('health'): parts.append(f'health
  {data["health"]}')`.

### `cli/wuwei/signal.py`, `cli/wuwei/commands/event.py`

Add `'heartbeat: clock'` to `SILENT`; add `'heartbeat: clock': 'wuwei watch'` to
`EVENT_PRODUCERS` (every kind but `note` is already refused by `wuwei event`).

### `cli/wuwei/workspace.py`

`SCHEMA['watch']` gains `"ping_url": (str, "")`.

### `cli/wuwei/integrity.py`

```python
def fresh(root):
    """The cached verdict, also stale when an installed file changed after it (release installs)."""
```

Return `cached(root)` when it is not clean. Read `verdict.json` (via `_path`) once for its
`checkout` field and its `st_mtime`; when `checkout` is not None return the clean result (git
HEAD and the clean-tree check in `cached` already cover a checkout). Otherwise `os.walk(PLUGIN)`
skipping `.git` and `__pycache__` dirs and `.pyc` files, and return `Result(1, reason='page:
plugin integrity: <relative path> changed after the cached verdict; run wuwei integrity check
on the host')` for the first file whose `lstat().st_mtime` is newer. `OSError` and
`ValueError` give `Result(2, reason=...)`. `cached`, `check` and `measure` do not change.

### `cli/wuwei/commands/config.py`

Move the inline `requirements` dict (lines 33 to 41, including the `custom_app` tweak) into
`requirements(config)`, used by `run` unchanged in output. Add:

```python
def missing(config):
    """Offline findings of config check: credential variables, codex.command, owner pin."""
```

returning `' or '.join(alternatives)` for every unmet requirement of a selected adapter,
`codex.command` when the runtime is `codex` and the command is empty, and
`control_plane.owner` when inbound is not `none` and the pin does not match `remote.PIN`.
No code-host call.

### Docs and template

- `docs/site/reference.md`: new `## Heartbeat` section after `## Watch state`: the probe table
  (every name from `PROBES`), the `heartbeat: clock` record, `health ok | degraded |
  unmeasured` on the status line and when it is absent, the one page and when it clears,
  `behaviour drift`, the on-demand `bin/wuwei heartbeat` exit codes, and the dead-man ping
  (`watch.ping_url`, sent only when health is ok, hosted cron monitors such as Healthchecks.io
  or Cronitor alert the phone when pings stop, keep the URL private). Note that probe refusals
  are not recorded as `hook.refusal`.
- `docs/site/configuration.md`: `watch.ping_url` row in the settings table, and one sentence in
  "Running the watch" pointing at the reference section.
- `docs/site/remote.md` line 339: replace "and no external dead-man ping" with a pointer to
  the watch heartbeat ping; keep the rest of the sentence true (`listen dead` stays a host-side
  signal).
- `templates/workspace/config.toml` `[watch]`: `# ping_url = ""` with a one-line comment.

## What must not change

- The hook path: `integrity.cached`, every guard module, guard discovery, and the hook allow
  path. No hook or guard module imports `wuwei.heartbeat`. Hook latency benchmarks unchanged.
- `watch.health` semantics, the clock, poll, sweep and activity schedule in `tick`,
  `listen.tick`.
- `status.scan` stays one pass; existing status line parts keep their order and text; `watch`
  and `listen` fields keep their values.
- No new adapter kind in `registry.PARAMETERS`, no new registry loader, no new state key (the
  record lives under the already reserved `watch` key).
- `config check` output and exit codes.

## Test plumbing

- Every existing test that runs `watch.tick` would now start real launcher processes and see
  a degraded heartbeat. Add one autouse fixture in `tests/conftest.py` that replaces
  `wuwei.heartbeat.beat` with `lambda root: 0`. `tests/test_heartbeat.py` keeps a reference to
  the real function taken at import (`BEAT = heartbeat.beat`, collected before fixtures run) and
  restores it with `monkeypatch` where a test drives the tick.
- In-process tests fake `registry.watch_service` with an object whose `probe(calls, cwd,
  during, timeout=10)` records the calls, runs `during()` and returns configured results, and
  whose `ping(url)` records calls or raises. Integrity uses `fakes.integrity.seed` with
  `integrity.PLUGIN` monkeypatched to a temporary directory holding one file older than the
  verdict (`os.utime`). Memory uses `fakes.host.Fake` through `registry.load`, as
  `tests/test_agent_launch.py::test_memory_port_results` does.
- Real launcher tests copy `cli`, `bin`, `adapters` and `.claude-plugin` like the
  `subprocess_plugin` fixture in `tests/test_hooks.py`, and prepend a directory with a
  `python3` symlink to `sys.executable` to `PATH` with `monkeypatch.setenv` (the adapter
  inherits the environment). `registry.watch_service()` loads a fresh module on every call,
  so load it once, set that module's `LAUNCHER` to the copy's `bin/wuwei`, and monkeypatch
  `registry.watch_service` to return it. Set `integrity.PLUGIN` to the copy, seed the verdict
  after copying, set `host.free_memory_mb = 0` in the test config, and raise
  `heartbeat.STATUS_LINE_BUDGET_MS` so a slow CI runner does not fail the smoke run (the
  budget logic has its own in-process test). The mutation copy appends
  `discover = lambda: []` to its `cli/wuwei/commands/hook.py` (`run` resolves the global at
  call time), so no guard runs.

## Implementation notes

- T024: the real-launcher smoke, tamper and mutation tests passed against the code as planned;
  no fix was needed in `adapters/watch_service.py` or `cli/wuwei/heartbeat.py`.
- The adapter collects each launcher call on its own thread, so a call's wall figure is its
  own and not inflated by `during`. Stderr is decoded with `errors='replace'`.
- The conftest fixture returns the real `beat`; `tests/test_hooks.py::test_heartbeat_latency`
  requests it to restore the real step.
- T027 latency, measured 2026-10-01 on the M-series Mac with `WUWEI_BENCH=1` while other
  pipelines loaded the host (load 10.7 on 10 CPUs, interpreter startup floor 23 to 38 ms wall):
  heartbeat tick p95 over 60 runs wall 273 to 280 ms. The in-process probes take about 20 ms
  in total and run inside `during`; the rest is the slowest of the four concurrent launcher
  calls. At the same load the existing `push in a workspace` hook benchmark measured 349 ms
  wall against its 100 ms budget, so the host, not the heartbeat, was over budget. A rerun
  at load 8.35 passed: `heartbeat tick p95 over 60 runs: CPU 316.39 ms, wall 134.95 ms`
  (startup floor wall 20.61 ms). CPU is the sum over the four processes; the budget is wall.
