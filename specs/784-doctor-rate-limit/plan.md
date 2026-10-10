# Implementation Plan: a 403 rate-limit reply is reported as a rate limit, never as missing gh auth

**Branch**: `784-doctor-rate-limit` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

Two small edits at the two shared spots. In the code host adapter, `auth_status` probes
`gh api user` through `_run` when `gh auth status` exits 1, so #738's `gh_limit`, `retry` and
`RateLimited` decide whether it was a rate limit; the #738 reason comes back unchanged as
exit 2. In doctor, one helper turns any reason holding the #738 marker into a `waiting` row;
the `gh` row and the tracker row both call it. `waiting` joins `CODES`, `outcome` and the
summary count. One docs sentence.

## Technical Context

Python 3.11+ stdlib only. pytest dev-only. No new module, port operation, `Result` field,
config key, state key, event kind or gh command (`['api', 'user']` is already in `_run`'s
allowlist). No guard or decision rule changes, so no invariant row.

## Constitution Check

- I stdlib: no import added.
- II exits: a rate limit is exit 2 (could not measure), never 0 and never a finding; a real
  auth failure stays exit 1; probe timeouts fall into the existing exit 2 handler.
- III one behaviour one function: rate-limit detection stays in `_http.gh_limit`, the wait in
  `_http.retry`, the text in `_http.RateLimited`; doctor's reading of it lives only in the new
  `_limited` helper.
- IV test first: every implementation task in `tasks.md` follows its failing test.
- V simplicity: no status-code parsing of `gh auth status`, no new knob, no record; the probe
  runs only on the failing path.
- VII security: the probe's error text (which may hold stderr from gh) is discarded unless
  it is the #738 reason, which is built from numbers and fixed words only.

## Design

### adapters/code_host/github.py `auth_status` (lines 655-665)

Replace the `if code == 1:` branch:

```python
        if code == 1:
            # #784: gh auth status calls the API and says "token invalid" on any non-200, a
            # rate limit included; one gh api user read tells which (#738 names a limit).
            try:
                _run(['api', 'user'])
                return Result(0)
            except ValueError as exc:
                if str(exc).startswith('GitHub rate limit until '):
                    return Result(2, reason=str(exc))
            return Result(1, reason='gh auth: missing')
```

Everything else in `auth_status` is unchanged (exit 0, exit 2+, the outer `except`). `_run`
already: appends `--hostname github.com`, runs `gh_limit` on a nonzero exit, waits through
`retry`, and re-raises a `RateLimited` as `ValueError(str(limit))`; a non-limit failure raises
`ValueError('gh exited ...')`, which is discarded here. A JSON decode error of the probe is a
`ValueError` too and reads as missing.

### cli/wuwei/commands/doctor.py

- `CODES` (line 27): add `'waiting': 2`.
- `outcome` (line 65): `2 if statuses & {'unmeasured', 'waiting'} else 0` in place of
  `2 if 'unmeasured' in statuses else 0`.
- `render` (line 82): the counted statuses tuple becomes `('fail', 'warn', 'unmeasured',
  'waiting')`.
- New module constant and helper next to `_row`:

```python
LIMITED = 'GitHub rate limit until '  # adapters/_http.RateLimited's text (#738)


def _limited(section, name, reason):
    """#784: a GitHub rate limit is a wait, not a broken credential or tracker."""
    if LIMITED in (reason or ''):
        return _row(section, name, 'waiting', 'rate limited until ' + reason.split(LIMITED, 1)[1],
                    'wait until the reset it names (another job on the same GitHub account '
                    'shares the limit), then run doctor again')
```

- `_host` (lines 172-175): `rows.append(_limited('host', 'gh', result.reason) or _row(...))`
  with today's `_row(...)` call unchanged as the fallback.
- `_tracker` (lines 661-663): replace the #738 inline `if 'GitHub rate limit until' in reason:`
  block with `if found := _limited('day', 'tracker', reason): return found`.

Do not import `adapters._http` into doctor (core stays off adapter modules); the marker is
the one fixed string #738 already matched in doctor.

### docs/site/adapters.md (line 65, the `code_host.github` row)

Append: `When it fails, WUWEI reads gh api user once: a GitHub rate limit shows in doctor as
gh waiting, rate limited until <time>, never as missing auth.` (wrap the commands in
backticks as the row does).

### docs/site/daily.md (line 177)

Make the sample summary line `doctor: 1 fail, 1 warn, 0 unmeasured, 0 waiting` so the docs
match the output (`tests/test_docs.py` line 105 matches it as a substring and still passes).

## What must not change

- `adapters/_http.py` (`RateLimited`, `gh_limit`, `retry`, `cap`): reused as is.
- `_run`'s allowlist and its error text; every other code host operation.
- `auth_status` for exit 0 (one call, no probe) and exit 2 or more.
- `config check` and `setup discover` wording (they read exit 2 as `unmeasured`).
- Other doctor rows, statuses and fixes; `_row`'s fix rewriting.

## Test impact on existing tests

- `tests/test_env_credentials.py` `test_github_auth_through_adapter` (lines 369-383): the
  outcome `1` case now makes two calls; expect
  `[['gh', 'auth', 'status', '--hostname', 'github.com'], ['gh', 'api', 'user', '--hostname',
  'github.com']]` for it and keep the single call for `0`, `missing` and `timeout`. Its
  `KEY not in output` assertion must still hold (the probe's stderr is discarded).
- `tests/test_doctor.py` `test_tracker_row_on_a_rate_limit` (around line 1263): status
  `waiting`, value `rate limited until 14:05:00 UTC (0 of 5000 graphql calls left); retry
  after it`.
- `tests/test_doctor.py` outcome table (lines 178-181): add a `waiting` case.
