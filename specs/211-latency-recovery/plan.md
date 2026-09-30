# Implementation Plan: Hook latency budget and corrupt state recovery

**Branch**: `211-latency-recovery` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md) |
**Research**: [research.md](research.md)

## Summary

The slow hooks wait on subprocesses: Stop and a builder's SubagentStop call the code host
inside the hook, and commit and push start up to 16 git processes one after another. Move
the two network paths onto the watch, which already polls the same evidence, run
independent git reads concurrently in the git adapter, and parse config once per process.
For recovery, the state writer keeps a snapshot of what it last wrote and an owner-only
`wuwei state recover` restores it; every state read failure names that command.

## Technical Context

Python 3.11+ stdlib runtime (`concurrent.futures`, `hashlib`, `json`), pytest for tests.
Reuse: `state._write_state`, `state.lock_ex`, `state._append_event`,
`workspace.atomic_write`, `workspace.now`, `watch.records`, `watch.ERRORS`,
`obligations._time`, `references.pull_request`, `integrity._host_confirm`,
`protect_state._names_wuwei` and `shell.mentions`, the test helpers
`subprocess_plugin`, `subprocess_replay` and `assert_latency_budget` in
`tests/test_hooks.py`. No new dependency, adapter operation, git command, config key or
state key outside the watch's own record.

## Constitution Check

Stdlib only; exits stay 0/1/2 and every new failure is exit 2 with its reason; the watch
record is producer-owned (`watch` is reserved to `wuwei watch`); the new event kind is
reserved; no guard refuses less (the fast path only answers "clean" when the watch proves
it, anything else takes today's live path); test first. Passes before and after design.

## Design

### 1. Stop per planner turn: trust a fresh, clean watch record (`cli/wuwei/pr_actions.py`)

Add `_watched(root)` and call it first in `check`:

```python
def check(root, *, closing=False, rows=None):
    if rows is None and not closing and _watched(root):
        return 0, ''
    ...  # unchanged
```

`_watched` returns True only when all hold, and False on any `watch.ERRORS`:

- today's state has at least one owned PR (`raised_prs + claimed_prs`, normalised with
  `pull_request`);
- `state['watch']['measured_at']` parses with `obligations._time` and its age is between
  0 and `2 * config['pr']['poll_seconds']` seconds;
- every owned ref is a key of `state['watch']['prs']`;
- no owned ref has an episode in `state['watch']['actions']` whose `deadline` is before
  `workspace.now()`.

Anything else falls through to `evaluate` exactly as today, which also handles parked,
completed and merged PRs. `closing.check` passes `rows`, so day close never takes the fast
path.

### 2. Watch records a complete measurement (`cli/wuwei/watch.py`, `poll`)

Capture `started = workspace.now()` at the top of `poll`. In the final save (line 366) add
`'measured_at': started.isoformat()` only when `unreadable` is False. A failed read leaves
the old `measured_at`, which ages out.

### 3. Seat-free discovery runs in the watch

- `cli/wuwei/dispatch.py`, `discovery`: keep the queue check and the
  `discovery.requested` event; run `discovery_module.intake` only when
  `trigger == 'sweep'`. The seat-free trigger (hook and `wuwei dispatch discovery
  seat-free`) now only records the request. The return value is unchanged.
- `cli/wuwei/watch.py`, `tick`: at the end, if the last of today's events with kind
  `discovery.requested`, `discovery.intake` or `discovery.unmeasured` is a
  `discovery.requested` with `payload.trigger == 'seat-free'`, run
  `discovery.intake(root, trigger='seat-free')`; on `(*ERRORS, RuntimeError)` append
  `discovery.unmeasured` with the reason and return 2. Read events with `watch.records`.
- `cli/wuwei/guards/agent_launch.py` does not change: it still calls
  `dispatch.discovery('seat-free', root)` and still reports a failure of that call.

### 4. Concurrent independent git reads (`adapters/vcs/git.py`)

One helper next to `_run`:

```python
def _together(*calls):
    """Run independent reads concurrently; results and the first error keep call order."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(len(calls)) as pool:
        futures = [pool.submit(call) for call in calls]
    return [future.result() for future in futures]
```

Use it in:

- `commit_context`: the two `rev-parse` reads and the two `var` reads in one call, then the
  existing validation in the existing order.
- `push_context`: after the argument checks, `head(repo)`, `symbolic-ref`, and, when the
  remote name passes the existing pattern, the `push.followtags`, `remote.<r>.mirror` and
  `remote.<r>.push` reads; then the existing checks in the existing order (an invalid
  remote still raises `use a named push remote` after the HEAD and branch checks).
  `check-ref-format` per refspec and `push_commits` stay sequential (they depend on
  earlier results).
- `workspace_changes`: `status(repo)` and the history `log` together.

The `_run` allowlist does not change. Every single-failure error message is unchanged;
when several reads fail at once, the first failing read in call order is reported.

### 5. One config parse per process (`cli/wuwei/workspace.py`, `load_config`)

Keep a module dict `_CONFIGS = {path: (raw, config)}`. After reading `raw`, return
`deepcopy(config)` when the cached raw text is identical; otherwise parse and validate as
today, store, and return a deepcopy. Errors are never cached. Mark with
`# ponytail: per-process memo keyed on the config text; adapter and path checks rerun only
when the text changes`.

### 6. State snapshot and recovery (`cli/wuwei/state.py`)

- `_load(text)`: the three lines `read_state` already runs (`json.loads`,
  `json.dumps(..., allow_nan=False)`, `_validate`); `read_state` uses it.
- `read_state` failure message: `f'{path}: {exc}; run wuwei state recover in a host
  terminal'` (line 120). Every hook and command inherits it.
- `_write_state`: after writing `state.json` (line 211), also
  `workspace.atomic_write(directory / SNAPSHOT, encoded, mode=0o444)` with
  `SNAPSHOT = 'state.snapshot.json'`, inside the same lock.
- `recover(root=None, *, confirm)`:
  1. `measure()`: if `state.json` exists and reads, raise `StateError('state.json is
     readable; nothing to recover')`; keep the read error (or `state.json missing`) as the
     reason. Read the snapshot text (missing file raises `OSError`), `_load` it and turn
     any `ValueError`/`TypeError` into a plain `ValueError(f'unusable state snapshot:
     {exc}')` so it exits 2, not 1. Digest is `sha256(text)`.
  2. Outside the lock, `confirm(digest[:12])`; False raises `StateError('state recovery
     declined')`; an `OSError` from the terminal propagates (exit 2).
  3. Under `state.lock` (`lock_ex`), run `measure()` again and require the same digest,
     else `ValueError('state changed during confirmation; retry')`. Then
     `workspace.atomic_write(state.json, text, mode=0o444)` and
     `_append_event('state.recovered', {'snapshot': digest, 'reason': reason}, directory)`.
  4. Return the digest.

### 7. Command and guards

- `cli/wuwei/commands/state.py`: add the `recover` action. It calls `state.recover(confirm=
  lambda token: _host_confirm(token, prompt="Restore today's state from its snapshot. To
  confirm, type:"))` with `_host_confirm` from `wuwei.integrity`, prints `state recovered
  from snapshot <digest[:12]>`, and returns 0. `StateError` already maps to exit 1; other
  errors reach `__main__` as exit 2 with the reason.
- `cli/wuwei/guards/protect_state.py`:
  - `_protected_name` (line 80): add `state.snapshot.json` to the protected day files.
  - `check_bash`: next to the `integrity reconfirm` clause (line 279), refuse when the raw
    text names wuwei (`_names_wuwei(owner_action_text)`), `mentions(script, ('state',))`
    and contains the word `recover`, and `guard_scope(payload)` is not None:
    `return 1, 'State recovery is an owner action on the host, outside agent tools.'`.
- `cli/wuwei/commands/event.py`: add `'state.recovered': 'owner host wuwei state recover'`
  to `EVENT_PRODUCERS`.

### 8. Benchmark (`tests/test_hooks.py`)

- `assert_latency_budget` gains `wall_budget=None`: when set, assert `wall_ms <
  wall_budget` instead of `cpu_ms < 50`; the skip rule and the printed report are
  unchanged.
- A fixture builds, once per test, a workspace next to the `subprocess_plugin` copy (also
  copy `keys/` so SessionStart runs the full integrity measurement; the unsigned copy's
  finding is context, SessionStart never refuses): a git repo under `repos/` with
  a bare `origin` holding `main`, repo-local identity matching `config.toml`, a worktree
  `worktrees/ITEM-1` on branch `item-1` with one commit, today's day (fixed `WUWEI_NOW`)
  with approved item `ITEM-1` (worktree, claimed PR), `planner_session_id`, a running
  builder seat with its brief and transcript, fast-check evidence for the worktree HEAD,
  a watch record (`clock_at`, `measured_at`, `prs`, no overdue episode), and about 1000
  events including `plan.session` and a `watch: clock` line. PATH carries a `gh` stub that
  appends to a marker file and exits 1.
- `test_workspace_hook_latency[path]` for the five paths replays through `bin/wuwei`
  (`subprocess_replay`), restores the seeded day directory before every run outside the
  timed region, asserts exit 0 each run, then asserts the gh marker file does not exist
  and calls `assert_latency_budget(..., wall_budget=100)`. Runs: 60 with `WUWEI_BENCH=1`,
  otherwise 20.

## Must not change

- The Stop day-close path, `closing.check`, and `evaluate`/`observe` behaviour.
- The git `_run` allowlist, every adapter operation's signature and result shape, and the
  single-failure error texts.
- The existing CPU 50 ms assertions for the bare PreToolUse and PostToolUse benchmarks.
- `agent_launch.stop` and its tests; `dispatch.discovery` return values.
- Which state keys and event kinds are reserved, apart from adding `state.recovered`.

## Docs

- `docs/site/reference.md`: a short "State recovery" section (message, snapshot, owner-only
  command in a host terminal, exits).
- `docs/site/configuration.md` line 201: seat-free discovery is run by the watch on its
  next tick.

## Validation

For each behaviour: write the failing test, run it and see it fail for the expected
reason, implement the minimum, rerun. Run the benchmark with `WUWEI_BENCH=1` before and
after the latency changes and keep both reports for the final output. Then run the full
suite with `python -m pytest -q` using the interpreter the task names, and scan authored
files for em-dashes, emojis and machine-specific paths.

## Changes made during implementation

- Order-based test fakes: running reads concurrently made the replay fakes in
  `tests/fakes/replay.py` pick steps by arrival order, which is nondeterministic. The fake is
  now thread-safe and a step may carry `when` tokens that bind it to the call naming them;
  steps without `when` keep arrival order. The context, push and pushed-range step helpers
  in `tests/test_vcs_guard.py`, the installed-hook steps in `tests/test_git_hook.py` and the
  workspace-history stub in `tests/test_integrity.py` name their reads. Assertions are
  unchanged except where they relied on the first call's position.
- Two more rounds of git reads were cut after the first benchmark, still with no new git
  command or adapter operation:
  - `commit_push.context` skips the second `commit_context` read when the configured
    checkout's own `.git` directory is the common directory Git just measured for the
    command's repository (the read would return that same directory).
  - `push_context` validates explicit refspec destinations alongside the other reads; each
    result, or its error, is used exactly where the sequential check used it
    (`_later`/`_used`). `push_commits` reads the tracking ref and the default-branch base
    together; the base's error is raised only when it is needed.
- `read_state` also fails, naming the command, when `state.json` is missing and a snapshot
  exists, so no write can replace the snapshot before the owner recovers it. The Bash
  state-mention pattern names the snapshot too.
- The benchmark fixture runs `integrity.initialize` and signs the plugin copy with a
  throwaway key when `ssh-keygen` exists, so SessionStart pays the full signed measurement.
- `test_atomic_replace_and_cleanup` and `test_state_syncs_file_before_replace_and_directory_after`
  now expect the snapshot write after the state write (FR-011 exception).
