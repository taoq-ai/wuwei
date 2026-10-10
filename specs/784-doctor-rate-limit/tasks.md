# Tasks: a 403 rate-limit reply is reported as a rate limit, never as missing gh auth

Test first: each test task runs and fails for the expected reason before its implementation
task. No test sleeps, reaches the network or runs a real `gh`: use `install_replay`,
`install_clock`, `limits`, `SECONDARY`, `NOW` and `hms` from `tests/fakes/replay.py`, and
`wait_cap` and `RATE_LIMIT` from `tests/test_code_host.py`. Run only the touched test files
after each pair, then the full suite (`python -m pytest -q`).

Fixture text: `AUTH_FAILED` = gh's `auth status` failure output, `github.com\n  X Failed to
log in to github.com account octocat (keyring)\n  - Active account: true\n  - The token in
keyring is invalid.\n` (put it on stdout; gh 2.93 writes there).
`AUTH = ['auth', 'status', '--hostname', 'github.com']`,
`USER = ['api', 'user', '--hostname', 'github.com']`.

## Phase 1: the adapter tells a rate limit from missing auth (FR-001, FR-002, US1, US2)

- [X] T001 Test in `tests/test_code_host.py`: `test_auth_status_rate_limit_is_not_missing`,
  parametrized over `rate_limit` stdout `limits(5000, 5000, NOW + 3600)` (secondary: reset
  `NOW + 60`, `(5000 of 5000 core calls left)`) and `limits(0, 5000, NOW + 900)` (primary:
  reset `NOW + 900`, `(0 of 5000 core calls left)`). `wait_cap(tmp_path, monkeypatch, 0)`,
  `install_clock`, replay `[{'argv': AUTH, 'exit': 1, 'stdout': AUTH_FAILED}, {'argv': USER,
  'exit': 1, 'stderr': SECONDARY}, {'argv': RATE_LIMIT, 'stdout': <limits>}]`. Assert
  `adapter().auth_status()` is `exit == 2`, `reason == f'GitHub rate limit until {hms(reset)}
  UTC {left}; retry after it'`, no sleep recorded and three calls. Run it: fails (exit 1,
  `gh auth: missing`, one call; the replay also asserts no extra step).
- [X] T002 Test in `tests/test_code_host.py`: `test_auth_status_missing_and_ok`, parametrized:
  probe `{'argv': USER, 'exit': 1, 'stderr': 'gh: Bad credentials (HTTP 401)'}` gives
  `(1, 'gh auth: missing')`; probe `{'argv': USER, 'exit': 4, 'stderr': 'To get started with
  GitHub CLI, please run:  gh auth login'}` gives `(1, 'gh auth: missing')`; probe
  `{'argv': USER, 'stdout': '{"login": "octocat"}'}` gives `(0, None)`; and `gh auth status`
  exiting 0 with no probe step gives `(0, None)` after one call. Assert `(exit, reason)` and
  the call count. Run it: the probe-success case fails (exit 1) and the missing cases fail on
  the replay (no probe made, one step unused: assert `len(calls) == 2`).
- [X] T003 Update in `tests/test_env_credentials.py` `test_github_auth_through_adapter`
  (lines 369-383): for outcome `1` expect the two calls `['gh', 'auth', 'status',
  '--hostname', 'github.com']` and `['gh', 'api', 'user', '--hostname', 'github.com']`; other
  outcomes keep one call; `KEY not in output` stays. Run it: fails (one call).
- [X] T004 Implement in `adapters/code_host/github.py` `auth_status`: the `code == 1` branch
  from `plan.md` (probe `_run(['api', 'user'])`; `Result(0)` on success; `Result(2,
  reason=str(exc))` when the text starts `GitHub rate limit until `; else `Result(1,
  reason='gh auth: missing')`). T001 to T003 pass; `tests/test_code_host.py`,
  `tests/test_env_credentials.py`, `tests/test_setup.py` and `tests/test_adapters.py` pass.

## Phase 2: doctor shows `waiting` (FR-003, FR-004, US1, US3)

- [X] T005 Test in `tests/test_doctor.py`: `test_gh_row_on_a_rate_limit`: set
  `ws.code_host.results['auth_status'] = Result(2, reason='GitHub rate limit until 14:05:00
  UTC (5000 of 5000 core calls left); retry after it')`; `found = row(doctor.diagnose(),
  'gh')`; assert status `waiting`, value `rate limited until 14:05:00 UTC (5000 of 5000 core
  calls left); retry after it`, `'wait until the reset' in found['fix']`, and no row in
  `diagnose()` has `'gh auth: missing'` in its value or `'gh auth login'` in its fix. Also
  assert `main(['doctor'])` exits 2 and its last line ends `1 waiting`. Run it: fails
  (status `unmeasured`).
- [X] T006 Test in `tests/test_doctor.py`: update `test_tracker_row_on_a_rate_limit`
  (around line 1263) to status `waiting` and value `rate limited until 14:05:00 UTC (0 of
  5000 graphql calls left); retry after it`, fix still `wait until the reset`. Add to the
  outcome assertions (lines 178-181) `doctor.outcome([ok, waiting]) == 2` and
  `doctor.outcome([waiting, warn]) == 1`, and assert `doctor.CODES['waiting'] == 2`. Run it:
  fails (`unmeasured`, `KeyError`).
- [X] T007 Implement in `cli/wuwei/commands/doctor.py`: `'waiting': 2` in `CODES`;
  `outcome` counts `waiting` with `unmeasured`; `render` counts `waiting`; `LIMITED` and
  `_limited` as in `plan.md`; `_host` gh row `_limited('host', 'gh', result.reason) or
  <today's row>`; `_tracker` uses `_limited('day', 'tracker', reason)` in place of the #738
  inline block. T005 and T006 pass; `tests/test_doctor.py`, `tests/test_setup.py` and
  `tests/test_docs.py` pass.

## Phase 3: docs (FR-005)

- [X] T008 Docs: append the sentence from `plan.md` to the `code_host.github` row of
  `docs/site/adapters.md` (line 65) and change the sample summary line in
  `docs/site/daily.md` (line 177) to `doctor: 1 fail, 1 warn, 0 unmeasured, 0 waiting`.
  `tests/test_docs.py` passes.

## Phase 4: finish

- [X] T009 Run the full suite (`python -m pytest -q`); all green. Check every changed file for
  em-dashes, emojis and absolute local paths.
