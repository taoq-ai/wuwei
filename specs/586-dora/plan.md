# Implementation Plan: The DORA four keys read from what WUWEI already records

**Branch**: `586-dora` | **Spec**: `specs/586-dora/spec.md` | **Issue**: #586

## Summary

One function, `metrics.dora(root, config, since, until)`, reads the four keys from what
already exists: `metrics.cycles` (#567) for lead time to merge, `metrics._escaped` (5.6) for
change failure rate, and one new code host read, `deployments(repo, since)`, for deployment
frequency and lead time to deploy. Time to restore is a fixed unmeasured row until #415.
One renderer, `report.dora_lines(rows)`, prints the table for `wuwei dora`, the report, the
retro and the week digest. Telemetry adds five flat keys filled by the same function. No
second cycle time, no second escaped-defect measure, no config key, no event kind, no
refusal.

## Technical Context

Python 3.11 stdlib (`datetime`, `statistics.median`), pytest for tests. Touched modules:
`cli/wuwei/metrics.py`, `cli/wuwei/report.py`, `cli/wuwei/retro.py`, `cli/wuwei/digest.py`,
`cli/wuwei/telemetry.py`, `cli/wuwei/registry.py`, `cli/wuwei/commands/dora.py` (new),
`cli/wuwei/commands/__init__.py`, `cli/wuwei/__main__.py`, `adapters/code_host/github.py`,
`adapters/code_host/none.py`, `tests/fakes/code_host.py`, `README.md`, docs and the design
spec.
Tests: `tests/conftest.py`, `tests/test_dora.py` (new), `tests/test_code_host.py`, `tests/test_adapters.py`,
`tests/test_report_retro.py`, `tests/test_digest.py`, `tests/test_telemetry.py`,
`tests/test_cli_known_command.py`, `tests/test_docs.py`. Run only these.

## Constitution Check

- I stdlib only: yes. The core never spawns `gh`; the read goes through the code host port.
- II three-state exits: `wuwei dora` exits 0, or 2 with the reason when nothing could be
  read or a row failed because the code host could not run. A key without evidence prints
  `unmeasured` with its reason, never zero. The adapter fails closed on error bodies,
  missing fields and timestamps without a timezone (`_operation`, `_errors`, `_field`).
- III one behaviour, one function: `metrics.dora` computes, `report.dora_lines` renders;
  every surface calls them.
- IV test first: every task pair below is test then implementation.
- V ponytail: reuse `cycles`, `_escaped`, `_pages`, `record_none`, `install_replay`, the
  fake code host. Deployment statuses and environments are not read (`ponytail:` comment).
- VII security: read-only API calls already inside `_run`'s allowlist (`repos/<repo>/...`
  with `--paginate --slurp`); no allowlist change. No new refusal under any posture (#530).
- Telemetry constraint: nothing runs in a hook; the aggregate stays in the watch sweep.
- #551: `wuwei dora` is a read-only owner and planner report, not a step in the loop; it
  returns no action and changes no action the planner walks.

## Design

### Code host port: `deployments(repo, since)`

- `cli/wuwei/registry.py` `PARAMETERS['code_host']`: add `'deployments': ('repo', 'since')`.
- `adapters/code_host/none.py`: `def deployments(repo, since, root=None): return
  record_none('code_host', 'deployments', root, measurement=True)`.
- `adapters/code_host/github.py`: one `@_operation def deployments(repo, since, root=None)`.
  `repo = _repo(repo)`; `start` = `datetime.fromisoformat(since)`, `ValueError('since needs
  a timezone')` when naive. Read `_pages(f'repos/{repo}/deployments')` and take each
  `_field(v, 'created_at', str)`; source `deployments` when the list is not empty. Else read
  `_pages(f'repos/{repo}/releases')`, skip rows where `_field(v, 'draft', bool)` is true or
  `_field(v, 'published_at', str, nullable=True)` is None; source `releases` when any
  remain, else `None`. Return `{'source': source, 'at': sorted(at for at in times if
  parsed(at) >= start)}`, where each timestamp parses with a timezone or raises. A
  `ponytail:` comment: every environment counts at creation; filter on
  `production_environment` or read statuses when previews inflate the count.
- `tests/fakes/code_host.py`: `def deployments(self, repo, since, root=None): return
  self._call('deployments', (repo, since), root)`.
- `tests/test_adapters.py` `CALLS`: `('code_host', 'deployments', ('repo', 'since'), True)`.

### `metrics.dora`

In `cli/wuwei/metrics.py`, after `by_pace`:

```python
DORA = (('lead_time_merge_hours', 'Lead time to merge', '{:.1f} hours'),
        ('lead_time_deploy_hours', 'Lead time to deploy', '{:.1f} hours'),
        ('deploys_per_week', 'Deployment frequency', '{:.1f} per week'),
        ('change_failure_rate', 'Change failure rate', '{:.2f}'),
        ('time_to_restore_hours', 'Time to restore', '{:.1f} hours'))
DORA_WINDOW = 28  # #586: days, the default window of wuwei dora, the report and the retro
```

`week_window(config, monday)`: `(since, since + 7 days)` with `since =
datetime.combine(monday, time.min, tzinfo=workspace.zone(config) or
workspace.now().tzinfo)`; the digest and telemetry call it.

`dora(root, config, since, until, host=True)` returns `{key: row}` in `DORA` order, where a row is
`{'value': number, 'source': text}` or `{'value': UNMEASURED, 'reason': text}` plus
`'failed': True` when the code host could not run:

1. `rows = [row for row in cycles(root) if since <= row['merged_at'] < until]`.
2. Lead time to merge: `median(cycle_minutes) / 60`, source `cycle_minutes of <n> merged
   items (#567)`; none: reason `no item merged in the window`.
3. Change failure rate: `_, escaped = _escaped(root)`; `k = sum(row['item'] in escaped)`;
   value `k / n`, source `<k> of <n> merged items named by a later fix brief (5.6)`; none:
   the same reason as 2.
4. Deploys, in one helper `_deploys(root, config, since)` returning `(deploys, reason,
   failed)`, called only when `host` is true (else reason `read when the week is final`):
   `code_host == 'none'` gives reason `code host adapter is none` (the adapter is
   not called, so no `adapter: none` event); no `config['repos']` gives `no repository
   configured`. Else `host = registry.load('code_host', config)` and, per repository,
   `host.deployments(repo['name'], since.isoformat(), root=root)`; an exit other than 0 is
   `failed` with reason `code host could not run: <result.reason>` for both deploy rows.
   `deploys` is `{name: (source, [datetime])}` for repositories whose source is not None;
   none left gives reason `the code host reports no deployments or releases`.
5. Deployment frequency: `count` of deploys in `[since, until)` over all repositories;
   value `count * 7 / window_days` (`window_days = (until - since).total_seconds() /
   86400`), source `<count> <deployments|releases|deployments and releases> in <days:g>
   days`. Zero in the window with a known source is a measured 0.
6. Lead time to deploy: the items' pull requests from day state (`watch.days`, `_state`,
   `items[name]["pr"]`, newest day first, the first one found). For each row of 1 whose pull request starts with a
   deploy repository name plus `#`, the first deploy at or after `merged_at`; lead =
   `cycle_minutes / 60 + (deploy - merged_at) hours`. Median, source `<n> merged items
   reached a deploy`; none: reason `no merged item reached a deploy yet` (or the deploy
   reason of 4 when 4 has no deploys).
7. Time to restore: reason `no on-call incident signal yet (#415)`.

Damaged day records raise `ValueError` as `cycles` and `_escaped` already do; the adapter
failure never raises out of `dora`.

### Rendering and surfaces

- `cli/wuwei/report.py`: `dora_lines(rows)` returns `['| Key | Value | Source |', '| --- |
  --- | --- |', ...]` with one line per `metrics.DORA` entry: the label, the formatted value
  or `unmeasured`, the source or the reason (`|` replaced by `/`). `dora_section(root,
  config, days=metrics.DORA_WINDOW)` returns `[f'## DORA (last {days} days)',
  *dora_lines(metrics.dora(root, config, now - days, now))]`.
- `report.build`: after the `## Pace` lines, `lines += ['', *dora_section(root, config)]`
  (before the brief return, so every verbosity shows it).
- `retro.compile`: after the `## Pace` block, `lines += ['', *report.dora_section(root,
  workspace.load_config(root))]`.
- `cli/wuwei/digest.py`: `build(root, title, dates, config, dora=())` appends `dora` to
  `sections['Metrics']`; `write` passes `report.dora_lines(metrics.dora(root, config,
  *metrics.week_window(config, dates[0])))` when `kind == 'week'`. Month digests unchanged.
  A damaged day record (the keys need valid state, the digest reads loose records) gives one
  line `- DORA unmeasured: a day record failed its check; run bin/wuwei doctor` instead of the
  table, so the week digest is still written.
- `cli/wuwei/commands/dora.py` (new): `register` adds `dora` with `--window` (int, default
  `metrics.DORA_WINDOW`). `run`: `--window < 1` prints `wuwei dora: --window must be a
  positive number of days` and returns 2; otherwise find the workspace, load config,
  `until = workspace.now()`, `since = until - window days`, `rows = metrics.dora(...)`;
  `(OSError, UnicodeError, ValueError, TypeError, KeyError)` print `wuwei dora: <reason>`
  to stderr and return 2. Print `DORA, last <n> days (<since date> to <until date>)` and
  `report.dora_lines(rows)`; print each distinct failed reason to stderr and return 2 when
  any row failed, else 0.
- `cli/wuwei/commands/__init__.py`: `'dora'` in `READ_ONLY`.
- `cli/wuwei/__main__.py`: `dora` in the Owner help group, after `telemetry`. (Changed in
  implementation: the Daily group feeds the agent guide, whose page is capped at 100 lines and
  sat at 100; the guide still names `dora` in its read-only list.)

### Telemetry

- `cli/wuwei/telemetry.py` `METRICS`: add the five `DORA` keys before `aggregation_ms`.
- `aggregate`: `since, until = day_metrics.week_window(config,
  date.fromisocalendar(year, week, 1))` from the `week` string; `found.update({key:
  row['value'] for key, row in day_metrics.dora(root, config, since, until,
  host=week < current_week(root)).items()})`. The code host is read only when a week is
  finalised (once per week), never on the daily refresh of the current week, so the 10
  second budget of 5.13 is spent on it at most once a week; the current week's deploy keys
  stay `unmeasured` until it is final.
  `_round` already rounds floats to two decimals; `validate` already accepts a number or
  `unmeasured` at the top level, so `INNER` and `SCHEMA` do not change.

### Docs and design

- Design 5.6: a bullet `DORA keys (owner, 2026-10-08, #586)` naming the five rows, their
  sources, the window and `wuwei dora`.
- Design 5.13 metrics table: five rows, noting the deploy rows read the code host once per
  computed week.
- `docs/site/concepts.md`: a `## DORA keys` section after `## Measured reversibility` (not
  in the glossary: `test_concepts_opens_with_the_glossary` pins the glossary terms).
- `docs/site/reference.md`: a `bin/wuwei dora` row after `bin/wuwei docs ...`.
- `README.md:42`: the line `Landing next: [#586](...)` goes, since this feature directory
  now exists and `test_readme_landing_marks_follow_main` (#561) forbids a landing mark on a
  shipped issue. The feature list gains one bullet after the register bullet: `- The DORA
  four keys: bin/wuwei dora prints lead time, deployment frequency, change failure rate and
  time to restore, each with its source or why it is unmeasured ([DORA
  keys](docs/site/concepts.md#dora-keys)).` That leaves no landing sentence, so the test's
  `assert sentences` becomes conditional: with no landing sentence there is nothing to
  check (the rest of the test is unchanged).

## What must not change

- `cycles`, `cycle_by_tier`, `by_pace`, `_escaped`, `_escaped_defects`, `lead_time` and
  every existing `collect` key keep their values and shapes.
- The adapter's `_run` allowlist, the merge policy, every guard and every refusal.
- `telemetry.SCHEMA`, `INNER`, `validate`, the share modes and the payload's top-level keys.
- The digest's five section names and its month form.
- No event kind, state key or config key is added.

### Tests never reach `gh`

About forty existing test files build a report, a retro, a digest or a close with the
default `code_host = "github"` and repositories configured; each would now spawn `gh` for
deployments. `tests/conftest.py` gains one autouse fixture, `unread_deploys`, in the shape
of `rehearsed_undo`: it replaces `metrics._deploys` with `lambda root, config, since: ({},
'code host not read in tests', False)` and returns the real helper, which `tests/test_dora.py`
and the deploy cases of `tests/test_telemetry.py` restore. Nothing else changes in those
files.

## Risks

- `test_aggregate_every_metric`'s `EXPECTED` gains the five keys (`lead_time_merge_hours`
  33, `change_failure_rate` 0, the rest `unmeasured`).
- A busy repository's deployments read paginates all history: bounded by the 30 second
  `gh` timeout per call; a timeout is a failed row, never a crash.
