# Tasks: a GitHub rate limit is named, not redacted

Test first: each test task runs and fails for the expected reason before its implementation
task. No test sleeps, reaches the network or runs a real `gh`: patch `time.time` and
`time.sleep` with `monkeypatch` (record the sleep seconds in a list), fake `gh` with
`install_replay` (`tests/fakes/replay.py`) or a small argv-keyed `subprocess.run` fake, and
fake HTTP with the `replay` helper of `tests/test_tracker_adapters.py`. Use a fixed `NOW`
(for example `1_760_000_000`) so each `HH:MM:SS UTC` is exact. Run only the touched test
files after each pair, then the full suite (`python -m pytest -q`).

Fixture texts used below:

- `SECONDARY`: `gh: You have exceeded a secondary rate limit. Please wait a few minutes before
  you try again. If you reach out to GitHub Support for help, please include the request ID
  D5E6:3A0B:1F2C3D:2A3B4C:670800AA. (HTTP 403)`
- `SECONDARY_JSON`: `{"message":"You have exceeded a secondary rate limit. ...","documentation_url":"https://docs.github.com/rest/overview/rate-limits-for-the-rest-api"}`
- `LIMITS(core, graphql, reset)`: a `gh api rate_limit` stdout with `resources.core` and
  `resources.graphql` rows `{limit: 5000, remaining: <n>, reset: <reset>, used: ...}`.

## Phase 1: config key (FR-004)

- [X] T001 Test in `tests/test_workspace.py`: add `'rate_limit_wait_seconds': 120` to the
  `host` defaults at line 225, and a case that `rate_limit_wait_seconds = 0` loads and `-1` is
  refused (follow the neighbouring minimum-value tests). Run it: fails (unknown key, missing
  default).
- [X] T002 Implement in `cli/wuwei/workspace.py`: `"rate_limit_wait_seconds": (int, 120, 0)`
  in the `host` schema (line 126); add the line to `templates/workspace/config.toml` `[host]`
  and the row to `docs/site/configuration.md` (text in `plan.md`). T001 passes, and any
  template or docs consistency test still passes.

## Phase 2: the code host names a limit (FR-001, FR-003, US1)

- [X] T003 Test in `tests/test_code_host.py`: `test_rate_limit_is_named_not_redacted`,
  parametrized over stderr `SECONDARY` and `SECONDARY_JSON`, with `rate_limit` stdout
  `LIMITS(4990, 4800, NOW + 3600)` (secondary: reset NOW + 60) and the cap set to 0 (a
  `WUWEI_WORKSPACE` config, see `plan.md`) so no wait happens. Assert `adapter().pr('acme/app#7')`
  is exit 2 with reason exactly `github.pr: could not run: GitHub rate limit until <NOW+60 as
  HH:MM:SS> UTC (4800 of 5000 graphql calls left); retry after it`, that `[REDACTED]` is not in
  it, that no sleep was recorded, and that the replay calls were the failing call then
  `['gh', 'api', 'rate_limit', '--hostname', 'github.com']`. Add cases: `core` remaining 0 with
  reset R names R; a `rate_limit` step that exits 1 or prints `not json` gives NOW + 60 and no
  `calls left` part. Run it: fails (reason is `gh exited 1 ...` or `[REDACTED]`).
- [X] T004 Implement in `adapters/_http.py`: `WAIT`, `RateLimited`, `cap`, `gh_limit` as
  `plan.md` describes. `retry` waits for T006.
- [X] T005 Implement in `adapters/code_host/github.py` `_run`: the local `call()` around the
  `subprocess.run` that raises `gh_limit(result.stderr, env)` when it returns a limit,
  `result = call()`, and `except RateLimited as limit: raise ValueError(str(limit)) from None`.
  T003 passes; `test_stderr_line_and_auth_hint`, `test_stderr_line_search_has_no_email` and
  the replay tests still pass.

## Phase 3: a short limit is waited out (FR-003, US2)

- [X] T006 Test in `tests/test_code_host.py`: `test_rate_limit_within_the_cap_waits_and_retries`:
  steps (1) the pr call fails with `SECONDARY`, (2) `rate_limit` with `core` remaining 0 and
  reset NOW + 30, (3) the pr call succeeds with the recorded `pr` payload of
  `tests/fixtures/code_host/recordings.json` (and any further steps that operation makes).
  With the default cap (120, no workspace), assert exit 0, the expected data, and one sleep of
  30. Add: reset NOW + 121 with the default cap records no sleep and the reason names it; a
  reset in the past sleeps 0; the retried call limited again (steps fail, limits, fail,
  limits) makes exactly four gh calls, one sleep, and the reason names the second reset.
  Run it: fails (no retry).
- [X] T007 Implement `retry` in `adapters/_http.py` and make `_run` call `result =
  retry(call)`. T006 and T003 pass.

## Phase 4: the tracker names and waits out a limit (FR-001, FR-002, FR-003, US1, US2)

- [X] T008 Test in `tests/test_tracker_adapters.py`, gh path (`gh_root`):
  `test_github_gh_rate_limit_is_named_and_retried`. A fake `subprocess.run` answers
  `['gh', 'api', 'rate_limit', ...]` with `LIMITS(...)` and the graphql calls from a list.
  Cases: `(1, SECONDARY)` then the `created` answer, reset within the cap: exit 0, one sleep;
  reset beyond the cap (append `[host]\nrate_limit_wait_seconds = 0` to the config): exit 2,
  reason holds `GitHub rate limit until` and not `credential has no access`. Run it: fails
  (reason is `HTTP 403: credential has no access ...`).
- [X] T009 Implement in `adapters/tracker/github.py`: `_gh` raises `gh_limit(result.stderr)`
  first inside `if result.returncode:`; `_query` calls through `retry(..., root)`. T008
  passes; `test_github_gh_failure_names_the_cause_not_the_text` still passes.
- [X] T010 Test in `tests/test_tracker_adapters.py`, token path (`workspace_root('github')`):
  `test_github_token_rate_limit_reads_the_headers`, parametrized over an `HTTPError` on
  `https://api.github.com/graphql` with headers (403, `X-RateLimit-Remaining: 0`,
  `X-RateLimit-Limit: 5000`, `X-RateLimit-Resource: graphql`, `X-RateLimit-Reset: R`) giving
  `until <R> ... (0 of 5000 graphql calls left)`; (429, `Retry-After: 30`) giving NOW + 30;
  (429, no headers) giving NOW + 60; (403, no headers) keeping
  `HTTP 403: credential has no access`. With cap 0, assert the reason; with the default cap
  and the first case at R = NOW + 10, assert one sleep of 10 and exit 0 on the replayed second
  answer. Also: a 429 from a non-GitHub URL through `_http.request` still raises
  `HTTP 429: rate limited; retry later`. Run it: fails.
- [X] T011 Implement in `adapters/_http.py` `request`: the GitHub header branch in the
  `HTTPError` handler (`plan.md`). T010 passes; `tests/test_reference_adapters.py` (the
  status hint table at line 262 and the Slack 429 tests) still passes.

## Phase 5: a known API error reply is readable (FR-005, US3)

- [X] T012 Test in `tests/test_traces.py`: `test_reply_keeps_a_known_api_message`:
  `reply('{"message":"Resource not accessible by integration","documentation_url":"https://docs.github.com/rest"}')`
  is `Resource not accessible by integration`; with message `token ghp_` + 36 letters it is
  `[REDACTED]`; `{"message":"x: 1"}` (no `documentation_url`), `not json` and a plain
  `password=hunter2` line equal `redact(line)`. Run it: fails (`reply` missing).
- [X] T013 Implement `reply` in `cli/wuwei/redact.py`. T012 passes.
- [X] T014 Test in `tests/test_code_host.py`: `test_json_error_reply_shows_its_message`: stderr
  is the `Resource not accessible` JSON line; the reason ends
  `gh exited 1 (acme/app): Resource not accessible by integration`. Run it: fails
  (`[REDACTED]`).
- [X] T015 Implement in `adapters/code_host/github.py`: import `reply` in place of `redact`
  and use it at line 127. T014 passes.

## Phase 6: doctor names the limit (FR-006, US4)

- [X] T016 Test in `tests/test_doctor.py`: `test_tracker_row_on_a_rate_limit`, like
  `test_tracker_row` with a `Fake` tracker whose backlog returns `Result(2, reason='github.backlog:
  could not run: GitHub rate limit until 14:05:00 UTC (0 of 5000 graphql calls left); retry
  after it')`: the row is `unmeasured`, its value holds that reason, its fix holds
  `wait until the reset`. `test_tracker_row` and `test_github_tracker_row_names_the_auth_fix`
  stay unchanged. Run it: fails (status `fail`).
- [X] T017 Implement in `cli/wuwei/commands/doctor.py` `_tracker`: the rate-limit branch
  (`plan.md`). T016 passes.

## Phase 7: finish

- [X] T018 Run `python -m pytest -q` from the repository root: all green. Check every file
  touched for em-dashes, emojis and absolute local paths.
