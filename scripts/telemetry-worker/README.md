# Telemetry collector

The collector behind `telemetry.endpoint` (design 5.13). It is project infrastructure; the
plugin never runs it.

- `worker.py`: `accept` checks one posted payload with the plugin's own `telemetry.validate`,
  takes only a week among the four ISO weeks before the week of receipt, answers 409 for a
  repeat token and week, and 429 past 10 payloads a day per IP address or 1000 writes a day.
  `on_fetch` is the Python worker entry: it keeps the per-IP counts in memory only and writes
  each accepted payload to the dataset repository as `data/<week>/<token>.json`.
- `summary.py`: `python3 summary.py <dataset checkout>/data` prints workspaces and integer sums
  per week.

## Deploy (owner steps)

1. Create the public dataset repository and a bot token that can write its contents, and a
   `telemetry` label in this repository.
2. Bundle `worker.py` with `cli/wuwei/telemetry.py` copied beside it, so `import telemetry`
   resolves, and deploy it as a Python worker.
3. Set the worker variables `DATASET` (`owner/repository`) and the secret `BOT_TOKEN`. The
   token lives only in the worker.
4. Set the default `telemetry.endpoint` in `cli/wuwei/workspace.py` to the worker's `https://`
   URL and release.

Attributed weeks arrive as issues titled `telemetry: <week>`;
`.github/workflows/telemetry-label.yml` labels them `telemetry`.
