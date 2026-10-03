# Data model: 422-telemetry

Definitions are design 5.13; this file fixes the shapes the code and tests share.

## Week file `.wuwei/metrics/<week>.json`

Written only by `telemetry.write_week` through `workspace.atomic_write`; protected by
`protect_state`. `<week>` is `YYYY-Www` from `date.fromisoformat(day).isocalendar()` of the
day directory names.

```json
{
  "schema": 1,
  "week": "2026-W40",
  "final": true,
  "versions": {"plugin": "0.12.0", "python": "3.12", "os": "darwin"},
  "config": {"posture": "guarded", "profile": "strict",
             "adapters": {"tracker": "none", "chat": "none", "code_host": "github", "...": "..."},
             "repositories": 2},
  "metrics": {"days": 5, "tool_calls": 120, "refusals": {"commit_push": 2},
              "unmeasured": {"config": 1}, "warnings": {"outward": 3},
              "refusal_rate": 0.02, "unmeasured_rate": 0.17,
              "hook_latency_ms": {"p50": 80, "p95": 140, "max": 210},
              "seat_minutes": {"p50": 12.5, "p90": 31.0},
              "escaped_by_tier": {"standard": {"merged": 6, "escaped": 2}},
              "...": "every key of the 5.13 table"},
  "evidence": {"verdict_items": 6, "external_wait_hours": [3.0, 5.5, 7.0]},
  "proposals": [{"rule": "wait-hours", "evidence": "3 external waits, p90 7.0 h under 12 h",
                 "command": "bin/wuwei config set decisions.wait_hours 11"}],
  "shared": "anonymous",
  "ready": true,
  "presented": true
}
```

- `final` false: the current week, refreshed each run; no `proposals`.
- `evidence`: inputs the proposal rules need that are not 5.13 metrics; never in a payload.
- `shared` (`anonymous` or `attributed`), `ready` (attributed nudge recorded), `presented`
  (widgets printed): absent until they happen.
- `first_hour_refusals` is present only in the week holding the earliest retained day.
- Every value that cannot be computed is the string `"unmeasured"`. Numbers that are not
  counts are rounded to two decimals when written.

## Payload

`telemetry.payload(week_file, *, token=None)`: exactly
`{"schema", "week", "versions", "config", "metrics"}` plus `"token"` when a token is given
(anonymous). Never `final`, `evidence`, `proposals`, `shared`, `ready` or `presented`.

`telemetry.validate(payload)` raises `ValueError(<rule>)` unless:

- top-level keys are exactly the set above (with or without `token`);
- `metrics` keys are 5.13 metric keys; keys inside a metric are a guard module name,
  `config`, a phase, a tier, a 5.8.1 class, a posture area, `p50`, `p75`, `p90`, `p95`,
  `max`, `merged`, `escaped`, `owner`, `seat` or `cruise`;
- `versions` keys are `plugin`, `python`, `os`; `config` keys are `posture`, `profile`,
  `adapters`, `repositories`; `adapters` keys are port names and each value an adapter
  shipped for that port;
- every leaf is a non-negative integer, a non-negative number with at most two decimals,
  `"unmeasured"`, a version (`^\d+\.\d+(\.\d+)?$`), a week (`^\d{4}-W\d{2}$`), a token
  (`^[0-9a-f]{32}$`), a posture name, a profile name, an OS family, or one of the names above
  where a name is expected;
- the serialised payload (`json.dumps(..., sort_keys=True)`) is at most 16384 bytes.

The vocabularies are literals in `cli/wuwei/telemetry.py` so `validate` imports without the
`wuwei` package (the worker bundles the file); a test pins them to `guards.MODULES`,
`guards.AREAS` values, `state.PHASES`, the gate floor tiers in `workspace.SCHEMA`,
`decision.CLASSES`, `workspace.POSTURES`, `workspace.AREAS` and `registry.known(port)`.

## Attributed issue

`telemetry.issue(payload)` returns `(title, body)`: title `telemetry: <week>`; body a
two-column Markdown table `| key | value |` with one row per leaf, dotted keys
(`metrics.refusals.commit_push`), sorted, rendered from a payload built without the token.

## Token `.wuwei/metrics/token`

`secrets.token_hex(16)` plus a newline, mode 0600, created by `telemetry.token(root)` on first
use (preview or anonymous send); read back and checked against `^[0-9a-f]{32}$`.

## Watch state (day `state.json`, `watch` record)

- `telemetry_at`: ISO time of the last step attempt.
- `telemetry`: `{"week": "<week>"}` after a full run, or `{"week": ..., "skipped": "<reason>"}`
  after a skip. The board reads it.
- `otlp_at`: `{"day": "YYYY-MM-DD", "offset": <bytes>}`, the end of the last exported record
  of `events.jsonl`. It carries over days through `watch.previous(root)`.

## Events (all CLI-only)

| Kind | Payload | Tier |
|---|---|---|
| `telemetry.skipped` | `week`, `reason` (`size` or `time`) | silent |
| `telemetry.unsent` | `week` (absent for otlp traces), `mode` (`anonymous` or `otlp`), `reason` (the validate rule, `no endpoint`, an exception class or `HTTP <n>`) | silent |
| `telemetry.shared` | `week`, `mode` | silent |
| `telemetry.ready` | `week` | nudge |
| `telemetry.presented` | `week`, `count` | silent |
| `telemetry.off` | `{}` | silent |

## Added record fields

- `hook.refusal` `refusals[]`: `{"guard", "reason", "exit"}`.
- `guard.would_refuse`: adds `"exit"`.
- `heartbeat: clock` `probes.refused|allowed|state_write|read_loop`: adds `"ms"` (int) when the
  call returned an exit code.

## OTLP shapes (owner's platform only)

- Traces body: `{"resourceSpans": [{"resource": {"attributes": [service.name = "wuwei"]},
  "scopeSpans": [{"scope": {"name": "wuwei"}, "spans": [...]}]}]}`. `traceId` is the first 32
  hex of `sha256(<root path> + "/" + <day>)`; `spanId` the first 16 hex of
  `sha256(<day> + ":" + <byte offset of the record>)`.
- Hook-call span per `hook.refusal` row and per `guard.would_refuse`: name
  `wuwei.hook`, start and end the record's time, attributes `wuwei.event` (`PreToolUse` for
  refusals, the record's kind otherwise), `wuwei.guard`, `wuwei.outcome` (`refuse` for exit 1,
  `unmeasured` for exit 2, `warn` for `guard.would_refuse`), `wuwei.reason_code`
  (`<guard>.<exit>`), `wuwei.posture`, `wuwei.item` when present.
- Seat span per `seat stopped` whose `seat launched` (same name, same day) is known: name
  `wuwei.seat`, from launch to stop, `wuwei.item` when the launch names one.
- One `wuwei.day` span per batch carrying span events for `decision.routed`,
  `decision.decided`, `decision.reversed`, `negotiation.loop`, `gate.received` and the owner
  interaction kinds, each event named by its kind with `wuwei.item` when present.
- Metrics body: `{"resourceMetrics": [...]}`: integer metrics and per-key counts as `sum`
  data points (`wuwei.key` attribute for the inner key), percentiles and rates as `gauge`
  data points; `"unmeasured"` values are omitted.
