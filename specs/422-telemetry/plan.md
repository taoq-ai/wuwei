# Implementation Plan: Telemetry (#422)

**Branch**: `422-telemetry` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md) |
**Shapes**: [data-model.md](data-model.md) | **Design**: 5.13 in
`docs/specs/2026-09-24-wuwei-design.md`

## Summary

Two fields on records the hook already writes (`exit` on refusals and warnings, `ms` on the
heartbeat's hook probes), then everything else off the hook path in one new module,
`cli/wuwei/telemetry.py`, called from one place, the watch sweep, plus one command module,
`cli/wuwei/commands/telemetry.py`. Two port operations (`watch_service.post`,
`code_host.issue`), small wiring edits, docs, and the project-side worker under `scripts/`.

## Technical Context

Python 3.11+ stdlib only at runtime (`json`, `hashlib`, `secrets`, `statistics`, `time`,
`datetime`, `re`, `urllib` inside the adapter). pytest for tests, in-process, fixture day
directories under `tmp_path`, `WUWEI_NOW` for the clock, a fake watch service (as
`tests/test_heartbeat.py` `Service`) and the code host fake in `tests/fakes/code_host.py`. No
network in any test.

## Constitution Check

- I stdlib: yes; HTTP only in `adapters/watch_service.py`, `gh` only in
  `adapters/code_host/github.py`.
- II exits: `metrics --week`, `telemetry *` exit 0, 1 or 2 with the reason; the sweep step
  never changes the sweep's exit (5.13) but prints `watch telemetry unmeasured: <reason>`.
- III one behaviour, one function: aggregation, proposals, payload, validation and export
  live once in `telemetry.py`; the collector imports the same `validate`.
- IV test first: every task pair below is test, then code.
- V ponytail: one module, one call site, no new event family beyond `telemetry.*`, reuse of
  `metrics._percentile`, `metrics._escaped_by_tier`, `watch.records`, `watch.days`,
  `decision.naming`, `decision.answered`, `decision.weekday_hours`, `verdict.rows`,
  `workspace.atomic_write`, `setup.set_value`, `decision.widget`, `integrity._host_confirm`,
  `security.outbound`, the GitHub adapter's `_api`.
- VII security: nothing leaves without `share`; the payload is an allowlist; attributed is an
  owner action with a host confirm and the canary check; `.wuwei/metrics/` is protected; a
  profile cannot carry `telemetry`; the OTLP header value is read from `.wuwei/env` only.
- Constraint "Telemetry adds no record and no step to a hook": pinned by T002 and T004.

## Files and functions

### Hook path (the only hook change)

`cli/wuwei/commands/hook.py`:

- `run` line 111: `refusals.append((guard.check, message, code))`.
- line 114: `enforced = [(module(check), message, '', code) for check, message, code in refusals]`;
  line 118 and line 130 unpack the fourth element; `refuse(..., refusals=[(guard, message,
  code), ...])`.
- `posture` (line 229): iterate `(check, reason, code)`; add `'exit': code` to the
  `guard.would_refuse` payload; append `(guard, reason, line, code)`; the `except` return at
  line 240 carries `code` too.
- `refuse` line 330: `{'guard': guard, 'reason': message, 'exit': code}`.
- Nothing else: no import, no append, no clock.

`cli/wuwei/heartbeat.py` `measure` (line 119): keep the third element of the four hook probe
results and return `{'result', 'value', 'ms'}` for `refused`, `allowed`, `state_write`,
`read_loop` when the code is not `None`. `_exit` unchanged.

Existing tests whose expected rows gain `exit` or `ms` (update the literals, nothing else):
`tests/test_hooks.py` around lines 1163, 1196, 1212 and 1222; `tests/test_heartbeat.py`
line 359; `tests/test_why.py` line 299 only if it compares a recorded row.

### `cli/wuwei/telemetry.py` (new)

Top-level imports stdlib only (`json`, `re`); every `wuwei` import is inside a function, so
`scripts/telemetry-worker/` can bundle the file and call `validate` alone.

- Constants: `SCHEMA = 1`, `BUDGET_SECONDS = 10`, `MAX_DAY_BYTES = 20_000_000`, `WEEKS = 4`,
  `MAX_PAYLOAD = 16_384`, `METRICS` (the 5.13 keys in table order), `GUARDS`, `PHASES`,
  `TIERS`, `CLASSES`, `AREAS`, `POSTURES`, `PROFILES`, `OS`, `ADAPTERS` (port to shipped
  names), `OWNER_KINDS` (`remote.acknowledged`, `state.recovered`, `integrity_confirmation`,
  `mcp.decided`, `draft.sending`, `draft.dropped`), `PROBES = ('refused', 'allowed',
  'state_write', 'read_loop')`.
- `week_of(day)`: ISO week string of a `YYYY-MM-DD` name.
- `read_days(root, start)`: `{day name: rows}` for `watch.days(root)` (ascending), each
  `events.jsonl` checked against `MAX_DAY_BYTES` with `stat` before `watch.records`, and
  `time.monotonic() - start` against `BUDGET_SECONDS` between days; raises
  `Skipped(reason, day)` (`size` or `time`). One read per run serves every week.
- `aggregate(root, config, week, days)`: returns the week file without `final`; per metric
  (5.13 table definitions; the event, field and helper each uses):
  - `days`: day names in the week. `tool_calls`: lines of each `traces.jsonl` in the week
    (counted, not parsed); `"unmeasured"` when no day has the file.
  - `refusals`, `unmeasured`: `hook.refusal` rows by `guard` and `exit` (missing `exit` is 1);
    a record without rows is `config`, exit 2. `warnings`: `guard.would_refuse` by `guard`.
  - `refusal_rate`, `unmeasured_rate`: as 5.13, `"unmeasured"` on a zero denominator or
    unmeasured `tool_calls`.
  - `first_hour_refusals`: refusal rows, unmeasured rows and warnings within one hour of the
    first event of the earliest retained day, only when that day is in the week.
  - `hook_latency_ms`: `metrics._percentile` p50, p95 and max of `probes[name]['ms']` in
    `heartbeat: clock` records for `PROBES`.
  - `seats_launched`: `seat launched` records; `seats_lost`: launches whose `name` has no
    `seat stopped` later the same day. `seat_minutes`: p50, p90 of `seat.usage`
    `usage.duration` seconds over 60, rows without a number skipped.
  - `phase_entries`: values of every record's `phase_changes`, by phase.
  - `plan_to_merge_hours`: first approval per item from `plan.approved` `items`,
    `state.import` `items` and `approved_items`, and `plan.added` `item` over all retained
    days; to the item's move to `merged` in the week; p50, p75.
  - `gate_rounds_per_item`: `gate.received` per item, for items with one in the week; p50,
    max. `fix_rounds_per_item`: moves into `fix` per item, same items; p50, max. The number
    of such items is `evidence.verdict_items`.
  - `gate_tiers`: `gate.tiered` by `computed`. `long_loops`: `negotiation.loop` records.
    `stuck_parks`: `build.parked` records. `reversals`: `decision.reversed` records.
  - `decisions`: distinct `id` of `decision.routed` and `decision.decided` in the week.
  - `decisions_by_class`: per decision id, the `Class:` line of
    `days/<day>/decisions/<id>.md` through `verdict.rows(verdict.active_text(text), 'Class')`
    (as `commands/why.py` line 211); a missing, symlinked or unknown class is `other`.
  - `decided_by`: `decision.decided` by `decided_by`, any `cruise ...` counted as `cruise`.
  - `owner_wait_hours`: `decision.routed` time to the owner's `decision.decided` or
    `decision.reversed` time for the same id, decided in the week; p50, p90. Routes whose
    payload names an `item` (an external wait, 5.8.2) also go, as
    `decision.weekday_hours(start, end, workspace.zone(config))`, into
    `evidence.external_wait_hours`.
  - `owner_asks_per_item`: per day in the week, `decision.naming(directory, items)` over the
    day state's `decision_routes`, as `metrics.collect` line 566; the mean count over items
    with at least one. `unnecessary_asks`: `decision.answered(data, id) ==
    route['recommendation']`, summed.
  - `owner_actions`: records whose kind starts with `remote.` or is in `OWNER_KINDS`.
  - `escaped_by_tier`: `metrics._escaped_by_tier(root)` unchanged.
  - `aggregation_ms`: the run's wall milliseconds so far.
  - `versions`: `integrity.version()`, `f'{major}.{minor}'`, `sys.platform` mapped to
    `darwin`, `linux` or `other`. `config`: `workspace.posture(config)[0]`,
    `config['profile']`, `config['adapters']`, `len(config['repos'])`.
- `proposals(week_file, config)`: the five 5.13 rules, each `{rule, evidence, command}`;
  `floor-raise` and `floor-lower` iterate `config['repos']` by index; `area-block` maps
  warned guards to areas with `wuwei.guards.AREAS` and checks `workspace.posture(config)[1]`
  for `warn`; `wait-hours` uses `evidence.external_wait_hours` (3 or more, p90 under half of
  `decisions.wait_hours`, command value `max(4, ceil(p90 * 1.5))`); `fast-checks` uses
  `evidence.verdict_items` and `fix_rounds_per_item.p50`.
- `week_file(root, config, week, days=None, *, write=True)`: compute (`final` when the week
  is before the current one, with `proposals`), round numbers, write with
  `workspace.atomic_write` to `.wuwei/metrics/<week>.json`, keeping `shared`, `ready` and
  `presented` from an existing file. Used by the step and by `metrics --week`.
- `load_week(root, week)`: read a week file (`None` when absent).
- `payload(week_file, *, token=None)`, `validate(payload)`, `issue(payload)`,
  `token(root)`: as data-model.md.
- `spans(root, mark)`: OTLP traces body for records after `mark` (`{day, offset}`) up to
  the end of today's `events.jsonl`, and the new mark; `otlp_metrics(week_file)`: OTLP
  metrics body. `# ponytail:` allowed calls are in traces.jsonl, not exported.
- `step(root, config)`: the sweep step, returns a short status string and never raises
  `watch.ERRORS`:
  1. `enabled` false: `'off'`. A `telemetry_at` within 86400 s: `'not due'`.
  2. `read_days`, then `week_file` for the current week and for each of the `WEEKS` earlier
     weeks with day directories and no final file. On `Skipped`:
     `watch.save(root, {'telemetry_at': now, 'telemetry': {'week', 'skipped'}},
     kind='telemetry.skipped', payload={'week', 'reason'})` and return `'skipped: <reason>'`
     (one event, the previous file kept).
  3. Share by `config['telemetry']['share']`: `anonymous`: for each of the four newest
     final weeks without `shared`: `payload` with `token(root)`, `validate`, then
     `registry.watch_service().post(endpoint, body)`; 2xx or 409 sets `shared` and appends
     `telemetry.shared`; anything else appends `telemetry.unsent`. Empty or non-`https://`
     endpoint is `telemetry.unsent` with reason `no endpoint`. `attributed`: each final week
     without `ready` gets `ready` and one `telemetry.ready`. `""` and `off`: nothing.
  4. OTLP when `telemetry.otlp.endpoint`: headers from `os.environ[headers_env]` after
     `env.load(root)` (split on `,` then the first `=`), `post` to `/v1/traces` with
     `spans`, then `/v1/metrics` for weeks finalised in this run; save `otlp_at` only on
     2xx; else `telemetry.unsent` with mode `otlp` and the exception class or status only.
  5. `watch.save(root, {'telemetry_at': now, 'telemetry': {'week': current}})`.

### Call site

`cli/wuwei/watch.py` `sweep`, after the steward block (line 301), before the `watch: sweep`
append: `counts['telemetry'] = telemetry.step(root, config)` inside `try/except ERRORS`
that sets `counts['telemetry'] = f'unmeasured: {exc}'` and prints it. Never touches
`owed`, `unreadable` or `exit`.

### Ports

- `adapters/watch_service.py`: `post(url, body, headers=None, timeout=5)` beside `ping`:
  `https://` only (`ValueError`), JSON body, `Content-Type: application/json` plus
  `headers`; returns the HTTP status; an `urllib.error.HTTPError` returns its `code`; other
  failures raise `OSError` or `ValueError`; reads at most 1024 bytes.
- `cli/wuwei/registry.py` `PARAMETERS['code_host']`: add `'issue': ('repo', 'title', 'body')`.
- `adapters/code_host/github.py`: `issue(repo, title, body, root=None)` under `_operation`
  (not `outward_operation`: 5.13 exempts the validated body from the outward lint), calling
  `_api(f'repos/{repo}/issues', payload={'title': title, 'body': body})`; the `_run`
  allowlist regex for POST endpoints (line 102) gains `issues`. Returns `{number, url}`.
- `adapters/code_host/none.py`: `issue` returns `record_none('code_host', 'issue', root,
  measurement=False)`.

### Commands

- `cli/wuwei/commands/metrics.py`: `--week [WEEK]` (`nargs='?'`, `const` the current week);
  with it, print `json.dumps(telemetry.load_week(...) or telemetry.week_file(...),
  sort_keys=True)`; a malformed week is exit 2 with the reason. Without it, unchanged.
- `cli/wuwei/commands/telemetry.py` (new; discovered by `__main__.main` like every command
  module; add `telemetry` to the Owner group of `cli/wuwei/__main__.py` `GROUPS`):
  - `preview [WEEK]`: the latest final week by default; prints `mode in force: <share or
    "not asked (off)">`, then for anonymous the endpoint (or `nothing is sent: no endpoint`)
    and the JSON payload with the token, for attributed `issue on <repository> from your gh
    account (shows your login)` with the title and body from `telemetry.issue`, and for off
    `nothing leaves this machine`. A payload failing `validate` prints the rule and exits 1.
    No final week: exit 1 `no final week yet`.
  - `off`: `setup.set_value(Namespace(key='telemetry.share', value='"off"'),
    confirm=lambda *args, **kwargs: True)`; on a change, append `telemetry.off`.
  - `send [WEEK]`: refuses (exit 1) unless `share == "attributed"`; refuses a week already
    `shared`; builds the payload without token, `validate`, `issue`; `security.outbound(
    {'title': title, 'body': body}, root)`; `integrity._host_confirm(sha256 of title and
    body, prompt=...)` as `drafts.approve` line 146; then `registry.load('code_host',
    config).issue(repository, title, body)`; on exit 0 sets `shared: attributed` and
    appends `telemetry.shared`.
  - `proposals [--widget]`: the latest final week; without `--widget` prints the proposals
    and writes nothing; with it prints a JSON list of `decision.widget(decision.gate(root) +
    f'Telemetry {week}: {evidence}. Apply it?', 'Telemetry', [('Yes', f'Recommended. Run
    {command} in a host terminal.'), ('Skip', 'Nothing changes.')], command)` when not yet
    `presented`, sets `presented` and appends `telemetry.presented`; else prints `[]`.
- `cli/wuwei/commands/__init__.py`: `telemetry preview`, `telemetry off`, `telemetry send`,
  `telemetry proposals` in `WRITES` (preview may create the token).
- `cli/wuwei/guards/protect_state.py`: `_OWNER_ACTIONS[('telemetry', 'send')] =
  'Telemetry sends are an owner action on the host, outside agent tools.'`;
  `_protected_name` adds `tail[:1] == ('metrics',)` to the first-level protected list
  (line 218).

### Wiring

- `cli/wuwei/workspace.py` `SCHEMA` adds `"telemetry": {"enabled": (bool, True), "share":
  (str, "", ("", "off", "anonymous", "attributed")), "endpoint": (str, ""), "repository":
  (str, "taoq-ai/wuwei"), "otlp": {"endpoint": (str, ""), "headers_env": (str, "")}}`;
  `CONFIG_CACHE_VERSION = 2`.
- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: the six `telemetry.*` kinds,
  `'wuwei telemetry or wuwei sweep'`.
- `cli/wuwei/signal.py` `SILENT`: `telemetry.skipped`, `telemetry.unsent`,
  `telemetry.shared`, `telemetry.presented`, `telemetry.off`. `telemetry.ready` stays a nudge
  (the default for an unlisted kind).
- `cli/wuwei/profiles.py` `DENIED`: `('telemetry.*', lambda new, old: True)` (not `PRIVATE`:
  its values would become literals searched in exported text).
- `cli/wuwei/interview.py` `QUESTIONS`: after `posture`, `{'id': 'telemetry', 'scope':
  'workspace', 'header': 'Telemetry', 'question': 'Share weekly usage counts with the WUWEI
  project?', 'choices': (('Anonymous', <5.13 text>, {'telemetry.share': 'anonymous'}),
  ('Attributed', <5.13 text>, {'telemetry.share': 'attributed'}), ('Off', <5.13 text>,
  {'telemetry.share': 'off'})), 'free': None}`.
- `cli/wuwei/commands/doctor.py` `_calibration` (line 303): when `telemetry.enabled` and
  `share == ""`, `_row('workspace', 'telemetry', 'warn', 'sharing not chosen yet (pending
  interview question)', 'bin/wuwei calibrate --interview telemetry')`; otherwise an `ok` row
  naming the mode. Fix any doctor test whose expected output changes by setting `share`.
- `cli/wuwei/commands/board.py` `read` (line 117): one `_table('Telemetry', ('Metric',
  'Value'), rows)` after Attention: rows are `('unmeasured', reason)` when
  `data['watch']['telemetry']` has `skipped`, else one row per metric of the current week's
  file (`json.dumps` of the value), else `('unmeasured', 'no aggregate yet')`.
- `templates/workspace/config.toml`: a commented `# [telemetry]` block with the four keys and
  a commented `# [telemetry.otlp]` block with its two.
- `skills/wuwei-plan/SKILL.md`: line 12 lists `wuwei telemetry proposals --widget` among the
  widget commands; step 4 ends with one sentence: after the gate, run it, skip on `[]`,
  otherwise ask and record as any widget. Keep every phrase `test_one_gate_question` pins.

### Docs

- `docs/site/configuration.md`: `[telemetry]` and `[telemetry.otlp]` in Sections and a
  Telemetry section with each key (`telemetry.enabled`, `telemetry.share`,
  `telemetry.endpoint`, `telemetry.repository`, `telemetry.otlp.endpoint`,
  `telemetry.otlp.headers_env`) and one OpenTelemetry paragraph (day as trace, spans,
  attributes, span events, counters and histograms, never the project).
- `docs/site/reference.md`: Commands row `bin/wuwei telemetry`; `metrics --week`; the
  Heartbeat section names `ms`; `telemetry send` in Host terminal actions.
- `docs/site/concepts.md`: `telemetry send` in Host terminal actions.
- `docs/site/security.md`: one paragraph: what leaves in each mode, what never does, the
  collector sees the IP address and does not store it, attributed shows the owner's login,
  `wuwei telemetry off`.

### Project side

- `scripts/telemetry-worker/worker.py`: `accept(body, *, today, seen, ip_count, writes)`
  returns `(status, path)`: 400 on JSON or `validate` failure, 400 without a token, 422 for a
  week outside the four ISO weeks before `today`'s week, 409 when `(token, week)` is in
  `seen`, 429 when `ip_count >= 10` or `writes >= 1000`, else `(201,
  f'data/{week}/{token}.json')`. `validate` comes from `telemetry.py` bundled beside it
  (`import telemetry`). A thin `on_fetch` platform entry keeps the per-IP counts in memory
  and writes through the dataset repository's contents API with the bot token from the
  worker's environment; not unit-tested.
- `scripts/telemetry-worker/summary.py`: `summarise(directory)` per week: workspaces (files)
  and the sum of each integer metric; `__main__` prints it as JSON.
- `scripts/telemetry-worker/README.md`: deploy note (bundle `cli/wuwei/telemetry.py`, the
  dataset repository, the bot token as a worker secret, then the default `endpoint` in
  `workspace.py`).
- `.github/workflows/telemetry-label.yml`: on `issues: opened`, when the title starts with
  `telemetry: `, add the `telemetry` label with the workflow's token.

## What must not change

- The 10.6 latency budget and its tests; `hook.py` beyond carrying `code`; no hook imports
  `wuwei.telemetry`, `secrets` or `urllib.request`.
- `metrics.collect` output and the bare `wuwei metrics` command.
- The 4.9 tiers and the outward lint (attributed bodies skip the lint by design, not by a
  lint change).
- The sweep's `exit`, `owed` and `unreadable` arithmetic.
- `docs/specs/` and `.specify/memory/constitution.md` (5.13 is merged; raise a conflict
  rather than edit).

## Verification

```sh
python -m pytest -q tests/test_telemetry.py tests/test_hooks.py tests/test_heartbeat.py tests/test_watch.py
python -m pytest -q
```

## Changes made while building

- The profile tests (T012) live in `tests/test_calibrate.py`, where the calibration profile
  deny table and export tests already are; `tests/test_profiles.py` covers guard profiles.
- The board's Telemetry table sits before Attention, not after: an existing board test counts
  the table rows after the Attention heading.
- `spans(root, config, mark)` takes the config for `wuwei.posture` on refusal spans (refusal
  records carry no posture). A refusal span's id hashes `<day>:<offset>:<row>`, since one
  record can hold several rows.
- `area-block` never proposes an area no guard module maps to (`mcp` applies its own posture,
  so it never records `guard.would_refuse`); a `ponytail:` comment names it.
- The doctor's ok row reads `share <mode>`, or `disabled` when `telemetry.enabled` is false.
- `first_hour_refusals` is one integer: refusal rows, unmeasured rows and warnings together.
