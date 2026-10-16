# Spec: the doctor's hooks row says ok only when a hook fired in the last two minutes (hooks-live)

## In my words

The #1065 check says `ok hooks` when `.wuwei/executable` exists or when this clone's ledger holds
any hook row since init. A session whose hooks are down still reads ok, because the evidence can
be days old. After this change every PreToolUse call stamps the time into the cache key
`hook-seen`. The doctor reads that key: `ok hooks (fired Ns ago)` when the stamp is under 120
seconds old, else a warning. The doctor runs from a Bash call, and that call fires PreToolUse, so
a live session always has a fresh stamp. The ledger scan and the `.wuwei/executable` shortcut go.

PostToolUse trace rows also carry the seat's role, read from the harness's `agent_type` with its
plugin prefix cut (`wuwei:sentinel-quality` gives `sentinel-quality`; the main session gives `''`).

Outside: detecting an outage without a doctor run; the Stop hook.

## Acceptance scenarios

1. PreToolUse ran 5 seconds ago: the doctor's hooks row is `ok` and reads `fired 5s ago`.
2. Hook rows in the ledger from earlier today and no PreToolUse in the last 2 minutes: the row
   warns `no hook fired in the last 2 minutes: inside a session, the doors and attestations are off`.
3. A PostToolUse payload with `agent_type` `wuwei:sentinel-quality` and telemetry on: the trace
   row has `role` `sentinel-quality`.
4. The runtime stays at 3,000 lines or fewer.

## Requirements

- FR-1: `hook.pre_tool` writes `ws.now().timestamp()` to cache key `hook-seen` on every call,
  before any guard runs.
- FR-2: the doctor's hooks row is ok only when `hook-seen` was written within 120 seconds and
  holds a number; the detail names the age in whole seconds.
- FR-3: `hook.post_tool` adds `role` to each trace row.

## Assumptions

- The `.wuwei/executable` shortcut and the since-init ledger scan are removed, not kept beside the
  new check: the promise names the cache key as the one source, and both old signals are what made
  the row say ok while hooks were down. Overturned if the owner wants a cold doctor run outside a
  session to read ok.
- A failed `hook-seen` write raises inside `pre_tool`, so `hook.handle` fails open for ordinary
  calls and refuses a door call, as for any other PreToolUse failure. The same disk failure would
  break the ledger write anyway.
- `docs/site/concepts/cloud.md` still quotes the old warning; it is outside the files the promise
  names and is left as a candidate.
