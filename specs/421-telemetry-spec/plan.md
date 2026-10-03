# Implementation Plan: Telemetry: signals at no hook cost, weekly aggregation with proposals, anonymous sharing

**Branch**: `421-telemetry-spec` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

A spec-only change. The amendment is already in the working tree, written by the spec
author: a new `### 5.13 Telemetry (owner, 2026-10-03, #421)` in
`docs/specs/2026-09-24-wuwei-design.md`, four one-line pointers elsewhere in that file, and
one constitution constraint. The builder shows the phrase check red on main and green
here, reviews the text for consistency, and runs the suite. No runtime code, no test
changes. The "Hand-off to #422" section below is the build map for the implementation.

## Technical Context

Markdown only. The check below is a throwaway stdlib script run from a scratch directory,
never committed. `tests/test_docs.py` reads the design spec only in
`test_guard_boundaries_are_stated_once` (4.5, 9.1, section 10) and the constitution for
"design reconsideration recorded in its spec" and "#222"; none of those is touched, and
`tests/test_docs.py` passes on the worktree (58 passed).

## Constitution Check

- I (stdlib), II (three-state exits), III (one behaviour, one function): no runtime code.
  The amendment keeps them for #422: sending uses stdlib `urllib` in an adapter, every
  failure is recorded and never blocks, aggregation is one module.
- IV (test first): the phrase check runs red against a `git archive main` export, then
  green on the worktree. Red is never produced by stashing or reverting the worktree.
- V (ponytail): one aggregation point instead of five, two fields instead of a new event
  family, no sample rate, no share cadence setting, no auto-send for attributed issues, one
  validator shared by the plugin and the collector, proposals as existing owner commands.
- VII (security): nothing leaves without the owner's choice; the payload is an allowlist
  of keys and numeric values; attributed sending stays an owner yes (4.9 floor); a profile
  cannot turn sharing on; `.wuwei/metrics/` is a protected record.
- Constraints: the constitution now scopes "no hosted service" to the plugin and names the
  collector as the project's; version 1.2.0.
- Governance: the design spec is amended only by its owner; the owner's request and the
  addition are in the issue, and the owner merges. The constitution amendment needs a
  dated line in the commit message (the orchestrator commits).

## What was changed (spec author, already in the working tree)

`docs/specs/2026-09-24-wuwei-design.md`:

1. Section 1 Non-goals, hosted service: the optional telemetry collector (5.13) is the
   project's, outside the plugin.
2. 3.3 Workspace layout: `metrics/` line.
3. 5.9 nudge list: "a telemetry week ready to send (5.13)".
4. New `### 5.13 Telemetry (owner, 2026-10-03, #421)` before `## 6. Memory`: config keys,
   Signals, Aggregation, Metrics table, Proposals table, Sharing (anonymisation rules and
   the three modes), preview and off, Interview, Project side, Residual risk.
5. Section 8 `code_host` row: `issue(repo, title, body)` (5.13).

`.specify/memory/constitution.md`: the "No hosted service" constraint scoped to the plugin,
a new telemetry constraint (no record and no step in a hook; proposals only), version
1.2.0, last amended 2026-10-03.

## Design decisions the builder must check against the issue

- Signals are the events that already exist. Only two fields are added: `exit` on each
  `hook.refusal` refusal row and on `guard.would_refuse` (today `hook.py` drops the guard's
  code), and `ms` on the heartbeat's four hook probe rows (today `heartbeat._exit` drops
  it). The vocabulary version is `schema` in the aggregate and payload, not on each event.
- Hook latency is the heartbeat's measured wall time per probe call, every clock tick;
  no clock and no append in the hook. `sample_rate` is not built.
- One aggregation point: a step in `watch.sweep`, at most once per 24 hours, with a 10 s
  budget and a 20 MB per-file cap, recording `telemetry.skipped` past either. It never
  changes the sweep's exit.
- Weeks are ISO weeks of the day directory dates; at most the last four are finalised or
  retried. Final weeks carry proposals.
- Five proposal rules with fixed thresholds, each one `bin/wuwei config set ...` or
  `bin/wuwei calibrate --measure`; presented once per final week at the morning gate;
  nothing applied on its own.
- Sharing: `share` unset behaves as off. Anonymous posts JSON with a random token over
  HTTPS from the sweep, never blocking, retried by the next run. Attributed is an owner
  command with a yes or no that opens a GitHub issue without the token. `share_auto` is not
  built (4.9 approve tier is a 9.1 floor).
- Anonymisation is an allowlist enforced by `telemetry.validate` in the plugin and by the
  collector, which imports the same function.

## Consistency review (builder)

Read these against 5.13 and edit only the design spec or constitution, only for a real
conflict, keeping the phrases the check pins:

- G5 (works with `git`, `gh`, `python3`): anonymous sending is stdlib `urllib`.
- 3.5 (only adapters talk HTTP or run `gh`): the POST is in `adapters/watch_service.py`,
  the issue in `adapters/code_host/github.py`.
- 4.1 and 10.6 (hook table and latency budget): no hook gains a step.
- 4.2 (sweeps): the telemetry step is inside the sweep.
- 4.3, 4.8, 4.9 (outward lint, voice, approval tiers): attributed issues are an owner yes;
  the lint is not applied to the generated body; canary and honeytoken checks are.
- 5.6 (outcome metrics, "unmeasured, never zero"), 5.8 and 5.8.1 (classes, `decided_by`,
  cruise promotions stay the steward's), 5.8.2 (`negotiation.loop`, `decisions.wait_hours`),
  5.9 (signal tiers).
- 6.8 (propose then promote): telemetry proposals are owner commands, not promote
  proposals; no charter or note target.
- 7.1 (canary, honeytoken), 9.1 (threat model, floors, guard scope; `.wuwei/metrics/` is a
  record).
- Constitution I, III, V, VII and Constraints.
- A grep of the design spec for `sample_rate`, `share_auto` and `share_every` finds
  nothing.

## What must not change

- Runtime and shipped text: `cli/`, `adapters/`, `hooks/`, `bin/`, `agents/`, `charters/`,
  `skills/`, `templates/`, `scripts/`, `.github/`, `docs/site/`, `README.md`, `SECURITY.md`.
- `tests/`: no file changes.
- Design 4.5, 9.1 and section 10: untouched, so `test_guard_boundaries_are_stated_once`
  keeps passing.
- The constitution phrases "design reconsideration recorded in its spec" and "#222".

## Verification commands

Run from the repository root. `<scratch>` is any directory outside the repository.

```sh
mkdir -p <scratch>/main && git archive main docs/specs .specify/memory | tar -x -C <scratch>/main
python3 <scratch>/check_421.py <scratch>/main   # must fail: AssertionError: section 5.13
python3 <scratch>/check_421.py .                # must print: OK: telemetry stated in 5.13
git diff --stat main -- cli adapters hooks bin agents charters skills templates scripts .github docs/site tests README.md SECURITY.md   # must be empty
python -m pytest -q
```

`<scratch>/check_421.py`:

```python
import re, sys
from pathlib import Path
base = Path(sys.argv[1])
spec = (base / 'docs/specs/2026-09-24-wuwei-design.md').read_text()
constitution = ' '.join((base / '.specify/memory/constitution.md').read_text().split())
flat = lambda text: ' '.join(text.split())
part = lambda pattern: flat((re.search(pattern, spec, re.S | re.M) or [''])[0])
tele = part(r'^### 5\.13 Telemetry \(owner, 2026-10-03, #421\).*?(?=^## )')
assert tele, 'section 5.13'
for phrase in (
        # config keys and defaults
        '`enabled` (default true)', '`share` (default `""`, not asked yet, which behaves as `"off"`)',
        '`"anonymous"`, `"attributed"` or `"off"`', 'never carries a `telemetry` key',
        '`endpoint` (default: the project\'s collector URL, empty until the project deploys it)',
        '`repository` (default `"taoq-ai/wuwei"`)', 'The cadence is a week and is not configurable',
        # signals and recording rule
        'no record and no step to any hook', 'gains `exit` (1 refused, 2 could not run)',
        'counts as guard `config`, exit 2', 'Heartbeat probe calls record nothing',
        '(`refused`, `allowed`, `state_write`, `read_loop`)', 'gains `ms`',
        'The vocabulary\'s version is `schema` in every aggregate and payload, starting at 1',
        # aggregation point and budget
        'One step of the watch sweep (4.2), at most once per 24 hours', '`telemetry_at` mark',
        'never in a hook and never in a seat', '`.wuwei/metrics/<week>.json`',
        'that `protect_state` guards like `state.json`', 'finalises each earlier week, of the last four',
        '10 seconds of wall time per run and 20 MB per `events.jsonl`', '`telemetry.skipped`',
        'never changes the sweep\'s exit', '`wuwei metrics --week [<week>]`',
        # metrics
        'is `"unmeasured"`, never zero', '| `refusal_rate` | refusals over tool calls plus refusals |',
        '| `unmeasured_rate` |', '| `first_hour_refusals` |', '| `hook_latency_ms` |',
        '| `seats_launched`, `seats_lost` |', '| `plan_to_merge_hours` |', '| `long_loops` |',
        '| `decisions_by_class` |', '| `owner_wait_hours` |', '| `escaped_by_tier` |',
        # proposals
        'a new rule amends this section', 'Nothing is applied on its own, as with calibration (#278)',
        '| `floor-raise` |', '| `floor-lower` |', '| `area-block` |', '| `wait-hours` |', '| `fast-checks` |',
        'Cruise promotions stay the steward\'s (5.8.1)', '`wuwei telemetry proposals --widget`',
        '`telemetry.presented`',
        # sharing and anonymisation
        'never the proposals or anything else in the file', '`telemetry.validate` before every send',
        'repositories appear only as a count', 'at most 16 KB', '`telemetry.unsent`',
        '32 hex characters generated once per workspace with `secrets`', '`.wuwei/metrics/token`',
        'No login and no secret in the plugin', 'sees the sender\'s IP address and does not store it',
        'the four newest weeks at most', '`telemetry.shared`', '`telemetry.ready` once per final week',
        '`bin/wuwei telemetry send`, an owner action on the host', 'shows the owner\'s login',
        'Title `telemetry: <week>`', 'without the token', 'the outward-text lint does not',
        '`wuwei telemetry preview [<week>]` prints exactly what each mode would send',
        '`wuwei telemetry off` sets `share = "off"` without a confirmation', '`telemetry.off`',
        'Every `telemetry.*` event is written only by the CLI',
        # interview
        '"Share weekly usage counts with the WUWEI project?"',
        'Anonymous: "Counts only, sent over HTTPS with a random workspace id',
        'Attributed: "The same counts as a GitHub issue opened from your gh account, so it shows your login."',
        'Off: "Nothing leaves this machine; the counts stay local."',
        # project side and risk
        '`scripts/telemetry-worker/`', 'one payload per token and week', '`data/<week>/<token>.json`',
        'bot token that lives only in the worker', '`scripts/telemetry-worker/summary.py`',
        'title starts with `telemetry: `', 'Residual risk',
        # OpenTelemetry export (owner addition, 2026-10-03)
        'a day is a trace', 'each hook call and each seat run is a span',
        '`wuwei.event`, `wuwei.guard`, `wuwei.outcome`', '`wuwei.reason_code`',
        '`wuwei.posture` and `wuwei.item`', 'are span events', 'counters and histograms',
        '`[telemetry.otlp]`', '`headers_env` (default `""`)', '`<endpoint>/v1/traces`',
        '`<endpoint>/v1/metrics`', 'no SDK', '`otlp_at` mark', 'mode `otlp`',
        'never goes to the project', '`events.jsonl` stays the source of truth',
        # payload shape and collector limits (review F1 to F3)
        'exactly these top-level keys', '`versions` (`plugin`, `python`, `os`)',
        '`config` (`posture`, `profile`, `adapters`, `repositories`)', 'a port name',
        'a week (`^\\d{4}-W\\d{2}$`)', 'a token (`^[0-9a-f]{32}$`)',
        'a posture name (`observe`, `guarded`, `strict`)', 'a profile name (`strict`, `standard`)',
        'an OS family (`darwin`, `linux`, `other`)', 'A 409 answer counts as sent',
        'among the four ISO weeks before the week of receipt', 'per IP address kept in memory only',
        'at most 1000 writes a day', 'answers 429', 'Its limits bound how many arrive'):
    assert phrase in tele, phrase
assert tele.index('Anonymous: "') < tele.index('Attributed: "') < tele.index('Off: "'), 'interview order'
whole = flat(spec)
assert 'The optional telemetry collector (5.13) is the project\'s, outside the plugin' in whole
assert 'metrics/ weekly telemetry aggregates and the workspace token (5.13)' in whole
assert 'a telemetry week ready to send (5.13)' in part(r'^### 5\.9 .*?(?=^### )')
assert '`issue(repo, title, body)` (5.13)' in part(r'^## 8\. .*?(?=^## )')
for once in ('telemetry_at', '.wuwei/metrics/token', '10 seconds of wall time'):
    assert whole.count(once) == 1, once
assert 'sample_rate' not in whole and 'share_auto' not in whole and 'share_every' not in whole
assert 'Telemetry adds no record and no step to a hook' in constitution
assert 'telemetry collector (design 5.13) runs outside the plugin' in constitution
assert '**Version**: 1.2.0' in constitution and '**Last Amended**: 2026-10-03' in constitution
assert 'design reconsideration recorded in its spec' in constitution and '#222' in constitution
for text in (spec, constitution):
    assert '\N{EM DASH}' not in text
print('OK: telemetry stated in 5.13')
```

## Hand-off to #422 (build map, not built here)

Files and functions, in test-first order. Reuse what is named; add nothing else.

Recording (the only hook-path change):

- `cli/wuwei/commands/hook.py` `run`: keep the guard's `code` with each refusal
  (`(guard.check, message, code)`); `posture` writes `'exit': code` into
  `guard.would_refuse`; `refuse` writes `'exit'` into each `refusals` row. No new append,
  no new import. Tests in `tests/test_hooks.py`: the rows carry `exit` 1 and 2; one refused
  call still appends exactly one event; `test_hook_imports_only_needed_guards`,
  `test_hook_imports_no_unused_stdlib` and `test_no_hook_path_imports_heartbeat` pass
  unchanged.
- `cli/wuwei/heartbeat.py` `measure`: the `refused`, `allowed`, `state_write` and
  `read_loop` rows gain `ms` (the third element `probe` already returns). Test in
  `tests/test_heartbeat.py`.

Aggregation, proposals and sharing, one new module `cli/wuwei/telemetry.py`, top-level
imports stdlib only (the collector imports `validate` from this file):

- constants `SCHEMA = 1`, `BUDGET_SECONDS = 10`, `MAX_DAY_BYTES = 20_000_000`, `WEEKS = 4`,
  `MAX_PAYLOAD = 16_384`, and the vocabulary tables (metric keys, inner keys, adapter
  names) as literals, so the collector can import `validate` without the package; one test
  pins them to `wuwei.guards.MODULES`, `wuwei.guards.AREAS`, `wuwei.state.PHASES`, the
  gate tiers, the 5.8.1 classes and `registry.known(port)` for every port.
- `aggregate(root, week)`: reads `watch.days(root)` in the week with `watch.records`, counts
  `traces.jsonl` lines without parsing them, reuses `metrics._percentile`,
  `metrics._escaped_by_tier`, `decision.naming` and `decision.answered` (as in
  `metrics.collect`), the decision record parser for `Class:`, `workspace.zone`,
  `workspace.posture`; never calls an adapter or reads transcripts.
- `proposals(aggregate, config)`: the five rules of 5.13 with their thresholds and
  commands.
- `payload(aggregate, config, *, token=None)`, `validate(payload)` (raises with the rule),
  `issue(payload)` (title and Markdown table, no token), `token(root)` (`secrets.token_hex(16)`
  in `.wuwei/metrics/token`, created on first anonymous send).
- `step(root, config)`: the sweep step: refresh, finalise, share by mode; writes with
  `workspace.atomic_write`; events through `state.append_event`.
- Tests in a new `tests/test_telemetry.py` with fixture day directories (`tmp_path`), a
  fake watch service and a fake code host; no network.

Call sites and ports:

- `cli/wuwei/watch.py` `sweep`: after the steward block, the telemetry step under a
  `telemetry_at` mark (`saved`/`save`, 86400 s), its outcome in `counts['telemetry']`,
  never in `owed`, `unreadable` or `exit`. Test in `tests/test_watch.py`.
- `adapters/watch_service.py`: `post(url, payload, headers=None, timeout=5)` beside `ping`:
  `https://` only, JSON body, optional extra headers (the OTLP auth), raise `OSError` or `ValueError` on any failure, read at most 1024 bytes.
- `cli/wuwei/registry.py` `PARAMETERS['code_host']`: `'issue': ('repo', 'title', 'body')`;
  `adapters/code_host/github.py` `issue` runs `gh issue create --repo <repo> --title <title>
  --body-file -` with the body on stdin, inside its closed allowlist;
  `adapters/code_host/none.py` returns exit 2. The port contract test covers both.
- `cli/wuwei/commands/telemetry.py` (new, and in the known-command list in
  `cli/wuwei/commands/__init__.py`): `preview [week]`, `off`, `send [week]`,
  `proposals [--widget]` (widgets through `decision.widget`, as `close --widget`).
  `send` confirms with `integrity._host_confirm` and checks with `security.outbound`, as
  `drafts.approve` does.
- `cli/wuwei/commands/metrics.py`: `--week [WEEK]`.
- `cli/wuwei/guards/protect_state.py`: `_protected_name` adds `.wuwei/metrics/`;
  `_OWNER_ACTIONS` adds `('telemetry', 'send')`.
- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS` and `cli/wuwei/state.py` reserved
  producers: every `telemetry.*` kind is `wuwei telemetry`.
- `cli/wuwei/signal.py`: `telemetry.ready` is a nudge; the other `telemetry.*` kinds are
  `SILENT`.
- `cli/wuwei/workspace.py` schema: `"telemetry": {"enabled": (bool, True), "share": (str,
  "", ("", "off", "anonymous", "attributed")), "endpoint": (str, ""), "repository": (str,
  "taoq-ai/wuwei"), "otlp": {"endpoint": (str, ""), "headers_env": (str, "")}}`.
- OpenTelemetry export: in `cli/wuwei/telemetry.py`, `spans(root, mark)` builds OTLP/HTTP
  JSON (`resourceSpans`) from the records after the `otlp_at` mark and returns the new
  mark; `otlp_metrics(aggregate)` builds `resourceMetrics` (counts as sums, percentiles as
  gauges); `step` posts both through `watch_service.post` to `<endpoint>/v1/traces` and
  `/v1/metrics` with the headers read by `env.load` from `headers_env`, saves the mark only
  on success, and records `telemetry.unsent` with mode `otlp` on failure. Tests: a fixture
  day maps to the pinned attributes; no command text or reason reaches the body; a failed
  post keeps the mark; the header value never appears in events or output.
- `cli/wuwei/profiles.py` `DENIED`: `('telemetry.*', lambda new, old: True)`.
- `cli/wuwei/interview.py` `QUESTIONS`: the `telemetry` row after `posture`, choices and
  texts exactly as in 5.13, effects `{'telemetry.share': ...}`.
- `templates/workspace/config.toml`: a commented `[telemetry]` block.
- `skills/wuwei-plan/SKILL.md`: the morning gate runs `wuwei telemetry proposals --widget`
  and lists it among the widget commands.
- Docs: `docs/site/configuration.md` `[telemetry]` rows, `docs/site/security.md` one
  paragraph (what leaves, what never does, the IP address, the attributed login),
  `docs/site/reference.md` (`telemetry`, `metrics --week`, the heartbeat `ms`), glossary
  entries in `docs/site/concepts.md` (telemetry, anonymous, attributed).
- Project side: `scripts/telemetry-worker/worker.py` (a pure `accept(body, exists)` that
  returns status and the `data/<week>/<token>.json` path, plus the platform entry with the
  week window, the in-memory per-IP limit and the daily cap, each answering 429),
  `scripts/telemetry-worker/summary.py`, `scripts/telemetry-worker/README.md` (deploy
  note: the worker, the dataset repository, the bot token as a worker secret, the default
  endpoint in `workspace.py`), `.github/workflows/telemetry-label.yml`.

Must not change in #422: the 10.6 budget and its tests; the hook dispatcher beyond the
`exit` field; `metrics.collect`'s output; the 4.9 tiers; the outward lint.
