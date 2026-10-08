# Tasks: The DORA four keys read from what WUWEI already records

Test first: each test task runs and fails for the expected reason before its implementation
task. Fixtures are neutral (items `A` to `D`, repository `acme/widget`, pull requests
`acme/widget#1` to `#4`). Set `WUWEI_NOW` and `owner.timezone = "UTC"`; build day
directories with the `write_day` pattern of `tests/test_telemetry.py` (events, state with
`items[name]['pr']` and `gates`, a `brief written` builder event whose brief file names an
earlier item for an escaped defect). Fake the code host with `tests/fakes/code_host.py`
(monkeypatch `registry.load`) and replay `gh` with `fakes.replay.install_replay`; never
reach the network. After T005 the autouse `unread_deploys` fixture keeps every other test
from spawning `gh`; tests of the deploy rows restore the real `metrics._deploys` from it.
Run only the touched test files.

## Phase 1: the code host port (FR-003, US2)

- [X] T001 Test in `tests/test_adapters.py`: add `('code_host', 'deployments', ('repo',
  'since'), True)` to `CALLS`, so `test_module_contracts` fails until the port, both
  adapters and the signature exist. Test in `tests/test_code_host.py`:
  `deployments('acme/widget', '2026-09-10T00:00:00+00:00')` with replayed pages returns
  `{'source': 'deployments', 'at': [...]}` holding only timestamps at or after `since`,
  sorted; with an empty deployments page and releases (one draft, one with
  `published_at` null, two published) returns `source: 'releases'` and the published ones;
  with both empty returns `{'source': None, 'at': []}`; an error body, `gh` exit 1, a
  missing `created_at` and a naive `since` each return exit 2 with no data; the `gh`
  arguments are `api repos/acme/widget/deployments?per_page=100 -H Cache-Control: no-cache
  --paginate --slurp --hostname github.com` (inside the existing allowlist).
- [X] T002 Implement `PARAMETERS['code_host']['deployments']` in `cli/wuwei/registry.py`,
  `deployments` in `adapters/code_host/github.py` (with the `ponytail:` comment on
  environments and statuses) and `adapters/code_host/none.py`, and the fake method in
  `tests/fakes/code_host.py`.

## Phase 2: the keys (FR-001, FR-002, FR-004, FR-005, US1, US2)

- [X] T003 Test in `tests/test_dora.py` (new): with `code_host = "none"`, items A, B, C
  merged in the window (cycle 60, 120 and 300 minutes) and a later builder brief naming B,
  `metrics.dora` returns, in `DORA` order, lead time to merge `2.0` with source
  `cycle_minutes of 3 merged items (#567)`, change failure rate `1/3` with source `1 of 3
  merged items named by a later fix brief (5.6)`, both deploy rows `unmeasured` with reason
  `code host adapter is none`, time to restore `unmeasured` with reason `no on-call
  incident signal yet (#415)`; and no `adapter: none` event is appended. An item merged
  before `since` is not counted. No item in the window gives both local rows `unmeasured`
  with reason `no item merged in the window`.
- [X] T004 Test in `tests/test_dora.py`: with `code_host = "github"`, one repository
  `acme/widget` and the fake returning deployments 2 hours after A's merge and 1 hour after
  C's merge plus one before `since`: deployment frequency is the in-window count times 7
  over 28 with source `<n> deployments in 28 days`; lead time to deploy is the median of
  `cycle_minutes / 60` plus the merge-to-deploy hours over A and C (B has no pull request
  and is skipped) with source `2 merged items reached a deploy`. The fake returning
  `source: 'releases'` names releases. `source: None` gives reason `the code host reports no
  deployments or releases`. A failed result (exit 2, reason `offline`) gives both deploy
  rows `unmeasured`, `failed: True`, reason `code host could not run: offline`, and the
  local rows are still measured. No repositories configured gives `no repository
  configured`. `host=False` never calls the fake and gives reason `read when the week is
  final`.
- [X] T005 Implement `DORA`, `DORA_WINDOW`, `week_window`, `_deploys` and `dora` in
  `cli/wuwei/metrics.py`, reusing `cycles` and `_escaped`. Add the autouse fixture
  `unread_deploys` to `tests/conftest.py` (replaces `metrics._deploys`, returns the real
  one); `tests/test_dora.py` restores it with `monkeypatch.setattr(metrics, '_deploys',
  unread_deploys)` for T003 and T004.

## Phase 3: the table and `wuwei dora` (FR-006, FR-007, US1)

- [X] T006 Test in `tests/test_dora.py`: `report.dora_lines(rows)` returns the header, the
  separator and five rows labelled as in `DORA`, values formatted (`2.0 hours`, `0.33`,
  `unmeasured`), the source or reason in the third column. `main(['dora'])` in the T003
  workspace prints `DORA, last 28 days (<date> to <date>)` and that table and returns 0;
  `main(['dora', '--window', '7'])` counts only the last 7 days; `--window 0` returns 2 with
  `--window must be a positive number of days`; the T004 failed fake returns 2 after
  printing the table, with `code host could not run: offline` on stderr; no workspace
  returns 2 with the reason and no table. Test in `tests/test_cli_known_command.py`
  (existing sets check): `dora` is registered and in `READ_ONLY`.
- [X] T007 Implement `dora_lines` and `dora_section` in `cli/wuwei/report.py`,
  `cli/wuwei/commands/dora.py`, `'dora'` in `READ_ONLY` in `cli/wuwei/commands/__init__.py`
  and in the Owner help group of `cli/wuwei/__main__.py` (the Daily group feeds the 100-line agent guide).

## Phase 4: report, retro, digest (US3)

- [X] T008 Test in `tests/test_report_retro.py`: the retro (existing retro fixture,
  `code_host = "none"`) has `## DORA (last 28 days)` after the `## Pace` lines and before
  `## Gate verdicts`, with the `dora_lines` table; the day report has the same section after
  `## Pace` at `brief` and `full` verbosity. Test in `tests/test_digest.py`: a week digest
  `## Metrics` section ends with the DORA table over that ISO week; a month digest has no
  DORA row.
- [X] T009 Implement the section in `report.build`, `retro.compile`, and the `dora`
  argument of `digest.build` filled by `digest.write` for weeks.

## Phase 5: telemetry (FR-008, US4)

- [X] T010 Test in `tests/test_telemetry.py`: `EXPECTED` gains `lead_time_merge_hours: 33`,
  `change_failure_rate: 0`, `lead_time_deploy_hours`, `deploys_per_week` and
  `time_to_restore_hours` `'unmeasured'`; `set(telemetry.METRICS)` matches; a final week
  carrying the five keys passes `telemetry.validate` and `payload`; with the real
  `metrics._deploys` restored, a faked failing code host and one repository, the deploy
  keys are `'unmeasured'` and the week is still written (no `telemetry.skipped`); the
  current (non-final) week never calls the fake code host and a final week calls it once
  per repository.
- [X] T011 Implement the five keys in `telemetry.METRICS` and their fill in
  `telemetry.aggregate` through `metrics.week_window` and `metrics.dora`.

## Phase 6: docs (FR-009)

- [X] T012 Test in `tests/test_docs.py`: `docs/site/reference.md` has a `bin/wuwei dora`
  row; `docs/site/concepts.md` has a `## DORA keys` section naming the five rows and
  `unmeasured`; design 5.6 names `wuwei dora` and 5.13's table has the five keys (each key
  in `telemetry.METRICS` appears in the 5.13 table); the README feature list has the DORA
  bullet linking `concepts.md#dora-keys`. `test_readme_landing_marks_follow_main` already
  fails on the base once `specs/586-dora/` exists (README still marks #586 landing): run it
  and see it fail.
- [X] T013 Write the design 5.6 bullet, the 5.13 rows, the concepts section and the
  reference row; in `README.md` replace the `Landing next: #586` line with the DORA bullet;
  in `tests/test_docs.py` `test_readme_landing_marks_follow_main`, make `assert sentences`
  apply only when a landing sentence exists (keep every other check).

## Phase 7: finish

- [X] T014 Run `python -m pytest -q tests/test_dora.py tests/test_pace.py
  tests/test_metrics.py tests/test_code_host.py tests/test_adapters.py tests/test_report_retro.py tests/test_digest.py
  tests/test_telemetry.py tests/test_cli_known_command.py tests/test_docs.py`; all green.
  Check the touched files for em-dashes, emojis and absolute local paths.
