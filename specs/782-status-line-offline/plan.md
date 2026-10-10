# Implementation Plan: the status line never waits on the network, and doctor names a slow probe

**Branch**: `782-status-line-offline` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

The status line and SessionStart already make no host call (spec, Root cause 1), and the
heartbeat already records a slow `status_line` probe with its milliseconds. The owner's
6.6 s was interpreter start-up on a busy host, slow for every probe at once (Root cause 2).
The defect is doctor's fix text: every failed guard probe row is told to reinstall.

Two changes:

1. A regression test that fails if `status --line` or the SessionStart lifecycle guard ever
   calls a network port. It passes on main; it is the pin the issue's first acceptance case
   asks for. No production code for it.
2. In `cli/wuwei/commands/doctor.py`, one helper `_probe_fix(name, probes)` replaces the
   inline conditional in `_guards`. For a timing failure it names the cause (busy host with
   the fastest slow peer, or the watch's cached line, or a rerun) and never says reinstall.
   Every other fix string stays as today.

Plus one bullet in `docs/site/reference.md`.

## Technical Context

Python 3.11+ stdlib only (constitution I). pytest dev-only. No new module, config key,
state key, event kind, probe, port operation or record. No guard or decision rule changes,
so no invariant row (constitution, Workflow).

## Constitution Check

- I stdlib: no import added.
- II exits: doctor's row statuses (`fail`, `unmeasured`) and its exit codes do not change;
  only the `fix` text of timing failures does.
- III one behaviour, one function: the fix choice for a guard probe row lives only in
  `_probe_fix`; `_guards` calls it.
- IV test first: each implementation task in `tasks.md` follows its failing test. The
  offline pin (T001) is a regression test that passes on main by design (spec, Root cause
  1); it is not followed by production code.
- V simplicity: the slow threshold reuses `heartbeat.STATUS_LINE_BUDGET_MS`; the compared
  probes are a module tuple beside the helper; no config, no new probe, no change to what
  the heartbeat records.
- VII security: fix texts are fixed words plus a probe name from a fixed tuple and an
  integer; nothing from probe stderr enters the fix.

## Design

### cli/wuwei/commands/doctor.py

Add, next to `PROBE` (line 573) or just above `_guards` (line 714):

```python
TIMED = ('refused', 'allowed', 'state_write', 'read_loop')  # the heartbeat probes that carry ms


def _probe_fix(name, probes):
    """A failed guard probe row's fix. #782: a probe over its time is a busy host or a
    missing cached line, never a reinstall; damaged files are the integrity row's."""
    value = probes[name]['value']
    if 'plugin integrity' in value:
        return 'fix the integrity row first'
    if value != 'timeout' and ' ms over ' not in value:
        return 'the hook no longer behaves as shipped; run wuwei integrity check and ' + REINSTALL
    budget = heartbeat.STATUS_LINE_BUDGET_MS
    peers = {other: probes[other] for other in TIMED if other != name}
    if all(row['value'] == 'timeout' or row.get('ms', 0) > budget for row in peers.values()):
        fastest = min(((row['ms'], other) for other, row in peers.items() if 'ms' in row), default=None)
        detail = f'fastest hook probe {fastest[1]} {fastest[0]} ms' if fastest else 'every hook probe timed out'
        return (f'every launcher call in this run was slow ({detail}): the host is busy, not the '
                'hook; rerun wuwei doctor when fewer seats run')
    if name == 'status_line':
        return ('only status --line was slow: it prints the line the watch heartbeat caches each '
                'tick, and a dead watch caches none; fix the watch row, then rerun wuwei doctor')
    return 'only this probe timed out in this run; rerun wuwei doctor'
```

In `_guards` (lines 716-718) the comprehension becomes:

```python
rows = [_row('guards', name, PROBE[probes[name]['result']], probes[name]['value'], _probe_fix(name, probes))
        for name in ('refused', 'allowed', 'state_write', 'read_loop', 'git_read', 'status_line')] if root is not None else []
```

Notes for the builder:

- `heartbeat` is already imported at module level (line 15); `REINSTALL` is line 29.
- The probe dict always holds all thirteen `heartbeat.PROBES` names (real `measure` and the
  `tests/test_doctor.py` fixture), so `probes[other]` cannot raise.
- `_row` rewrites `wuwei doctor` in a fix to the real launcher path (#362); tests compare
  with `in` on the distinctive part or build the expected text with the file's `W` helper.
- `ms` exists only on the four `TIMED` probes and only when the call did not time out
  (`heartbeat.measure`, `timed`). A peer whose value is neither `timeout` nor a measured
  `ms` over 200 (an adapter error, or the doctor fixture's probes with no `ms`) is not slow.
- Do not change the row status mapping, the value, or the `outside workspace` row.

### docs/site/reference.md (heartbeat section, after the `watch.status_line` bullet at line 220)

Add one bullet:

`- status --line and the SessionStart hook make no code-host, tracker or calendar call: the watch tick makes those calls and caches what they return. A slow status_line probe is interpreter start-up on a busy host, so doctor's fix for a probe over its time (N ms over 200 ms, or timeout) never says reinstall: when every other hook probe in the same run was also over 200 ms or timed out, it says the host is busy and names the fastest of them; when only status --line was slow, it points at the watch row, whose heartbeat writes the cached line; otherwise it asks for a rerun. Reinstall advice for changed files stays on the integrity row.`

(Use code formatting for `status --line`, `status_line`, `N ms over 200 ms` and `timeout`
as the neighbouring bullets do.)

## What must not change

- `cli/wuwei/heartbeat.py`: probe names, order, values, results, the `ms` set
  (`test_hook_probes_carry_ms` pins that `status_line` has no `ms`), `STATUS_LINE_BUDGET_MS`,
  `beat`, the page and drift rules.
- `cli/wuwei/commands/status.py`: `snapshot`, `_line_or_cache`, `LINE_BUDGET_MS`, the line
  text and the cache.
- `cli/wuwei/guards/lifecycle.py`, `adapters/watch_service.py`, telemetry's `PROBES`.
- Doctor's other rows, including the `heartbeat` day row and the `heartbeat page` row.

## Files

| File | Change |
| --- | --- |
| `cli/wuwei/commands/doctor.py` | `TIMED`, `_probe_fix`, `_guards` calls it |
| `docs/site/reference.md` | one bullet in the heartbeat section |
| `tests/test_heartbeat.py` | offline pin for `status --line` and SessionStart |
| `tests/test_doctor.py` | timing-fix cases for the guard probe rows |
