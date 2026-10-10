# Implementation Plan: the fast-check timeout is per repository in config and the error names the limit

**Branch**: `724-check-timeout` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

One config key, one port parameter, one except branch. `repos.<n>.check_timeout_seconds`
(default 300) joins the `repos` schema; the checks port `run` takes `timeout`; its three
callers pass the repository's value; the local adapter catches `TimeoutExpired` before the
generic branch and returns the issue's message. Calibration records how long each measured run
took and, when the slowest reached 80 % of the limit, proposes twice the limit through the
existing additive `proposal`.

## Technical Context

Python 3.11+, stdlib only; pytest for tests. The check is a `/bin/sh -c` subprocess inside
`adapters/checks/local.py`; tests stub `subprocess.run` (no 600 s waits) and the calibrate
clock (`calibrate.monotonic`), as the existing tests do.

## Constitution Check

- I (stdlib): unchanged.
- II (exits, fail closed): a timeout stays exit 2 with a reason; a timed-out check is never
  evidence (the record keeps exit 2, the push guard refuses as today).
- III (one behaviour, one function): the limit is read in the callers that already hold the
  repository row; the message lives in the adapter only.
- IV (test first): every behaviour has its test task before its implementation task.
- V (ponytail): no new module, helper or port; 80 % and 2x are constants, not config. The
  adapter does not look up the repository (the callers already have it).
- VII (security): no new input reaches a shell; `timeout` is a validated config integer.

## Design

### 1. `cli/wuwei/workspace.py` (repos schema, line 72)

Add beside `"tests"`:

```python
"check_timeout_seconds": (int, 300, 1),  # #724: one check run's limit in this repository
```

### 2. `cli/wuwei/registry.py` (line 22)

```python
'checks': {'run': ('path', 'command', 'timeout')},
```

`tests/test_adapters.py` `CALLS` row for `('checks', 'run', ...)` changes the same way;
`test_module_contracts` then requires both adapters to take `(path, command, timeout, root)`.

### 3. `adapters/checks/local.py`

```python
def run(path, command, timeout=300, root=None):
    try:
        ...
        result = subprocess.run(['/bin/sh', '-c', command], cwd=path, timeout=timeout, ...)
        ...
    except subprocess.TimeoutExpired:
        return Result(2, reason=f'fast check `{command}` exceeded {timeout} s '
                                '(repos.<n>.check_timeout_seconds); raise it with '
                                'bin/wuwei config set or split the check')
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        ...  # unchanged
```

The `TimeoutExpired` branch must come before the generic one (it is a `SubprocessError`).
The default 300 is the schema default and keeps direct adapter calls in existing tests valid.

### 4. `adapters/checks/none.py`

`def run(path, command, timeout=300, root=None):` body unchanged.

### 5. Callers pass the repository's limit (keyword `timeout=`)

- `cli/wuwei/fast_checks.py:92`, `record`:
  `runner.run(str(path), run, timeout=repo['check_timeout_seconds'], root=root)`.
- `cli/wuwei/commands/worktree.py:63`, bootstrap:
  `.run(str(tree), bootstrap, timeout=repos[0]['check_timeout_seconds'], root=root)`.
- `cli/wuwei/calibrate.py`, `classify` and `survey` (section 6).

### 6. `cli/wuwei/calibrate.py`

```python
NEAR = 0.8  # #724: a measured run at 80 % of its limit proposes twice the limit
```

`classify(checkout, commands, runner, seconds, root=None, timeout=300, measured=None)`:
pass `timeout=timeout` to `runner.run`; after `took`, `if measured is not None:
measured[command] = took`; when `took >= NEAR * timeout` append
`, near the {timeout} s check timeout` to the note. Replace the `ponytail:` comment at line
165 (it names the 300 s cap) with one naming the per-repository limit. Return shape unchanged
(`{command: (fast, note)}`), so `proposed`, `ci_only`, `_label` and the existing classify
tests keep working.

`survey` (line 689):

```python
limit, measured = repo['check_timeout_seconds'], {}
result['checks'] = classify(checkout, result['facts']['fast_checks'], runner,
                            config['calibrate']['fast_check_seconds'], root, limit, measured)
result['check_timeout'] = 2 * limit if max(measured.values(), default=0) >= NEAR * limit else None
```

`proposed` (line 812): add `'check_timeout_seconds': result.get('check_timeout')` to the
returned facts (`.get`: tests and callers build results without it).

`proposal` (line 582): add `('check_timeout_seconds', facts.get('check_timeout_seconds'))` to
the per-repository tuple. The existing `if value:` skips `None`; an absent key is added, a
present different one becomes a hand edit, as for every other key. Nothing else changes in
`apply`, `settle` or `kept`.

### 7. `docs/site/configuration.md`

- New row after `repos.tests` (line 69): `repos.check_timeout_seconds` | `300` | seconds one
  run of one check command may take (fast checks, `repos.tests`, `checks.bootstrap`,
  `calibrate --measure`); past it the check is exit 2 with
  ``fast check `<cmd>` exceeded <n> s (repos.<n>.check_timeout_seconds)``.
- Calibration paragraph (line 356): "capped at 300 seconds" becomes "capped at
  `repos.check_timeout_seconds`, default 300"; add one sentence: a measured run at 80 % of
  that limit or more proposes `check_timeout_seconds` at twice the limit.

## What must not change

- The result shape of the checks port (`Result(exit, data, reason)`) and exits 0/1/2.
- Every other failure reason of the local adapter (`fast check could not run: <Name>`) and
  the `_environment` detection.
- `classify`'s return shape and the `calibrate.fast_check_seconds` fast/CI-only rule.
- `proposal`'s additive rule: an owner-set `check_timeout_seconds` is never rewritten.
- `fast_checks.record`'s record keys (`seconds` already exists, #579).
- No design spec change (it states no checks port signature and no 300 s figure).

## Test fakes to update

Fakes with a fixed `run(path, command, root=None)` signature receive `timeout=` after this
change and must accept it: `tests/test_fast_checks.py` (the `run` fakes near lines 43, 65 and
230, the last wrapping the real adapter: forward `timeout`), `tests/test_calibrate.py:329`,
`tests/test_worktree_command.py:532`, `tests/test_build.py:48`, `tests/fakes/day.py:218`, `tests/test_pace.py:210` (found while building).
Fakes written as `lambda *a, **k` need no change.

## Files

- `cli/wuwei/workspace.py`, `cli/wuwei/registry.py`, `adapters/checks/local.py`,
  `adapters/checks/none.py`, `cli/wuwei/fast_checks.py`, `cli/wuwei/commands/worktree.py`,
  `cli/wuwei/calibrate.py`, `docs/site/configuration.md`.
- Tests: `tests/test_fast_checks.py`, `tests/test_calibrate.py`, `tests/test_adapters.py`,
  `tests/test_worktree_command.py`, plus the fake signatures above.
