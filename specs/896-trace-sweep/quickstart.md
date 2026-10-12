# Quickstart: 896-trace-sweep

Live checks with ZIRAN 0.40.0 on PATH, offline, in a scratch workspace (never an owner one).

## Trace sweep on a busy day

A day of 3000 spans in the audit's tracescale shape (40 sessions, tools picked at random from
Read, Edit, Bash, Write, Grep, Glob, WebFetch), then 100 more, swept as `dispatch receive` and
`close` do (`scanner.trace_sweep(root, workspace.load_config(root))`):

| Sweep | Before (main) | After |
| --- | --- | --- |
| 1: 3000 spans | 60.26 s, unmeasured (TimeoutExpired) | 24.26 s, measured |
| 2: 100 new spans | 60.32 s, unmeasured | 1.23 s, measured |
| 3: no new span | 60.23 s, unmeasured | 0.00 s, measured |

Window size, same day, first sweep, with the per-tool carry (review F1): 5 per session 20.23 s,
10 per session 18.21 s, 15 per session 21.06 s, 20 per session 24.26 s. Before the carry fix:
40 per session 34.12 s, 20 per session 7.26 s.

Review F1 probe (`split.py`, real ZIRAN): pad, busy and twosweeps each report `Read -> WebFetch`
for the session, as main does.

```
cat .wuwei/days/<date>/trace-sweep.json   # {"offset": <bytes measured>}, plus "unmeasured" after a failure
bin/wuwei doctor                          # an unmeasured "trace sweep" row while the last sweep failed
```

## Discovery candidates

The audit's `agent-svc` repo, real `ziran audit`:

- Before: ids such as `audit/agent-svc:scanner:SA001:<absolute checkout path>/src/agent_svc/tools.py:5`.
- After: `audit/agent-svc:scanner:SA001:src/agent_svc/tools.py:5`, critical rows first;
  `measured: 14`.
- With `discovery_threshold = "high"` and `discovery_rows = 3`:
  `measured: 3; audit/agent-svc: 11 more past scanner.discovery_rows`.
