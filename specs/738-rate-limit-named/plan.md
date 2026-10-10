# Implementation Plan: a GitHub rate limit is named, not redacted

**Branch**: `738-rate-limit-named` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

One shared helper set in `adapters/_http.py`, the module the HTTP adapters already share:
`RateLimited` (a `Failure` carrying the reset), `gh_limit` (is this gh stderr a rate limit,
and when does it reset), `retry` (wait within the cap, run the call once more) and `cap`
(the config value). Three call sites use it: the gh call in code host `_run`, the gh call in
tracker `_gh`, and the request in tracker `_query`; `request` itself raises `RateLimited`
from GitHub's headers. The redactor gains `reply`, which unwraps GitHub's JSON error reply
to its message before `redact` runs; the code host uses it for its stderr line. Doctor's
tracker row reads a rate-limit reason as `unmeasured` with a wait fix. One config key.

## Technical Context

Python 3.11+ stdlib only (constitution I): `json`, `re`, `subprocess`, `time`. pytest
dev-only. No new module, port function, `Result` field, state key or event kind. No guard or
decision rule changes, so no invariant row (constitution, Workflow).

## Constitution Check

- I stdlib: `subprocess` and `time` imported in `adapters/_http.py`, an adapter module; the
  core (`cli/wuwei/`) still runs no external tool. `redact.reply` uses `json`, already
  imported there.
- II exits: a limited call still ends exit 2 with a reason; the only new path that returns
  data is a successful retry. An unreadable `gh api rate_limit` reply is never parsed as
  data: it falls back to now + 60 s.
- III one behaviour one function: detection of a gh limit lives only in `gh_limit`, the
  wait only in `retry`, the reason text only in `RateLimited`. The three call sites call
  them and hold no rule.
- IV test first: every implementation task in `tasks.md` follows its failing test.
- V simplicity: no `Result` field (no caller needs one), the 60 s secondary wait is a module
  constant, `request` reads headers only for `https://api.github.com/` so no other adapter
  changes, doctor keeps no record.
- VII security: the rate-limit reason is built from integers and fixed words only, so it
  needs no redaction and carries no provider text. `reply` narrows nothing for traces:
  `SECRET` and `SENSITIVE_FIELD` are unchanged and the message still runs through `redact`.
  The new gh command is one literal argv (`gh api rate_limit --hostname github.com`), a
  closed allowlist of one, read only.

## Design

### adapters/_http.py (shared helpers)

Add imports `re`, `subprocess`, `time`.

- `WAIT = 60` with the comment `# GitHub: with no reset given, wait at least one minute (#738)`.
- `class RateLimited(Failure)`: `__init__(self, reset, remaining=None, limit=None,
  resource=None)` stores `self.reset = reset` and calls `Failure.__init__` with
  `f'GitHub rate limit until {time.strftime("%H:%M:%S", time.gmtime(reset))} UTC'`
  + (`f' ({remaining} of {limit} {resource} calls left)'` when all three are given)
  + `'; retry after it'`.
- `cap(root=None)`: `settings(root)['host']['rate_limit_wait_seconds']`; on `OSError`,
  `ValueError` or `KeyError` (no workspace, unreadable config) return `120`, the schema
  default.
- `gh_limit(stderr, env=None)`: `None` unless `re.search(r'rate limit', stderr or '', re.I)`.
  Then run `subprocess.run(['gh', 'api', 'rate_limit', '--hostname', 'github.com'],
  capture_output=True, text=True, timeout=30, env=env)`, read
  `json.loads(stdout)['resources']`, take the one of `core` and `graphql` with the fewest
  `remaining`, and require `returncode == 0` and `remaining`, `limit`, `reset` to be `int`.
  Return `RateLimited(row['reset'] if row['remaining'] == 0 else time.time() + WAIT,
  row['remaining'], row['limit'], name)`. On any `OSError`, `subprocess.SubprocessError`,
  `ValueError`, `TypeError`, `KeyError` or a failed check: `RateLimited(time.time() + WAIT)`.
- `retry(call, root=None)`: `return call()`; on `RateLimited as limit`, `wait = limit.reset
  - time.time()`; if `wait > cap(root)` re-raise; else `time.sleep(max(0, wait))` and
  `return call()` (a second `RateLimited` propagates: one retry only).
- `request` (the `except urllib.error.HTTPError as exc:` at line 77): before the existing
  `raise Failure(status(exc.code))`, when `url.startswith('https://api.github.com/')` and
  `exc.code in (403, 429)`, read `headers = exc.headers or {}`:
  - `Retry-After` all digits: raise `RateLimited(time.time() + int(value), ...)`;
  - `X-RateLimit-Remaining == '0'` and `X-RateLimit-Reset` all digits: raise
    `RateLimited(int(reset), ...)`;
  - `exc.code == 429`: raise `RateLimited(time.time() + WAIT)`;
  - otherwise fall through to today's `Failure(status(exc.code))`.
  The calls-left arguments come from `X-RateLimit-Remaining`, `X-RateLimit-Limit` and
  `X-RateLimit-Resource` when the first two are digits and the third is `[a-z_]+`; else none.
  Raise `from None` as today.

### adapters/code_host/github.py

- Import: `from .._http import RateLimited, gh_limit, retry`; line 13 becomes
  `from wuwei.redact import reply` (`redact` has no other use in this file).
- `_run`, the `subprocess.run` at lines 104-105: wrap it in a local `call()` that runs it and,
  when `result.returncode` and `gh_limit(result.stderr, env)` returns a limit, raises it. Then
  `result = retry(call)`; `except RateLimited as limit: raise ValueError(str(limit)) from None`
  (`_operation` prints the text of a plain `ValueError` only, line 41, and that check stays).
  Everything after (auth return code, 304, branch protection, the generic reason, JSON
  parsing) is unchanged.
- Line 127: `redact(line)[:200]` becomes `reply(line)[:200]`.
- The command allowlist (lines 60-101) does not change: the `rate_limit` read runs inside
  `gh_limit`, never through `_run`.

### adapters/tracker/github.py

- Add `gh_limit` and `retry` to the existing `from .._http import ...` line.
- `_query` (line 23): the two calls become `retry(lambda: request(URL,
  credential('GITHUB_TRACKER_TOKEN'), payload), root)` and `retry(lambda: _gh(payload),
  root)`. `RateLimited` is a `Failure`, so `operation` already prints its text.
- `_gh` (line 50): first thing inside `if result.returncode:`,
  `if limit := gh_limit(result.stderr): raise limit`. The HTTP-code hint, scope hint, error
  body and `gh auth status` branches below it are unchanged.

### cli/wuwei/redact.py

- `reply(line)` after `redact`: `json.loads(line)` inside `try` (on `ValueError` keep the
  line); when the value is a dict with a `str` `message` and a `documentation_url` key, use the
  message; return `redact(that)`. Docstring: `#738: GitHub's JSON error reply keeps its message
  when the message holds no credential shape; redact still runs on the message.`
- `SECRET`, `SENSITIVE_FIELD`, `PHONE`, `redact` and `known_values` do not change.

### cli/wuwei/commands/doctor.py

- `_tracker` (line 637): after `if not reason: return ...ok...`, add
  `if 'GitHub rate limit until' in reason: return _row('day', 'tracker', 'unmeasured', reason,
  'wait until the reset it names (another job on the same GitHub account shares the limit), '
  'then run doctor again')`. The rest is unchanged.

### cli/wuwei/workspace.py and the config docs

- Schema `host` (line 126): add `"rate_limit_wait_seconds": (int, 120, 0)`.
- `templates/workspace/config.toml` `[host]` (line 72): add
  `rate_limit_wait_seconds = 120 # Wait this long at most for a GitHub rate limit to reset, then retry once; 0 never waits.`
- `docs/site/configuration.md` after the `host.reservation_timeout_seconds` row (line 135):
  `| host.rate_limit_wait_seconds | 120 | Longest wait for a GitHub rate limit to reset before one retry; beyond it the reason names the reset time. 0 never waits. |`
  (code spans as in the neighbouring rows).

### Must not change

- `redact.SECRET`, `SENSITIVE_FIELD`, `redact()` and the trace recorder's redaction.
- `_http.status` and `HINTS`; `request` for any URL other than `https://api.github.com/`.
- The code host command allowlist, `_operation`'s `type(exc) is ValueError` check, the
  search rule that never shows stderr, `auth_status`, the 304 path.
- `Result` and the port interfaces in the registry; no caller of a port.
- `adapters/chat/slack.py` keeps its own 429 handling.

## Tests

No test sleeps or touches the network or a real `gh`. Patch `time.sleep` and `time.time`
(the `time` module `adapters._http` imports) with `monkeypatch`, and fake `gh` with the
existing helpers. A fixed `NOW` (for example `1_760_000_000`) makes every reset and the
`HH:MM:SS UTC` text exact.

- `tests/test_code_host.py`: uses `install_replay` (steps are taken in order, so a limited
  call is one step for the failing call and one for `rate_limit`, with `argv` checks). Code
  host calls run outside a workspace in these tests, so `cap()` returns 120; a test that needs
  another cap sets `WUWEI_WORKSPACE` to a `tmp_path` holding `.wuwei/config.toml` with
  `[host]\nrate_limit_wait_seconds = N`.
- `tests/test_tracker_adapters.py`: `gh_replay` asserts every call has JSON `input`, so the
  `rate_limit` call needs its own small fake there (a `subprocess.run` that answers by argv);
  the token path uses the existing `replay` with an `HTTPError` carrying headers. The cap
  comes from the `workspace_root` config (append `[host]` to it).
- `tests/test_traces.py` (where `redact` is tested directly today, line 17): `reply` cases.
- `tests/test_doctor.py`: next to `test_tracker_row`, with the `Fake` tracker.
- `tests/test_workspace.py` line 225 lists the full `host` defaults; it gains the new key.

## Project Structure

```text
adapters/_http.py                    RateLimited, WAIT, cap, gh_limit, retry; request reads GitHub headers
adapters/code_host/github.py         _run retries through retry(); stderr line through reply()
adapters/tracker/github.py           _query retries; _gh raises the limit
cli/wuwei/redact.py                  reply()
cli/wuwei/commands/doctor.py         _tracker: rate limit is unmeasured with a wait fix
cli/wuwei/workspace.py               host.rate_limit_wait_seconds
templates/workspace/config.toml      the key, commented
docs/site/configuration.md           the key's row
tests/test_code_host.py              limit named, waited, retried once; JSON reply readable
tests/test_tracker_adapters.py       gh and token paths limited and retried
tests/test_doctor.py                 tracker row on a limit
tests/test_workspace.py              host defaults
tests/test_traces.py                 reply()
```
