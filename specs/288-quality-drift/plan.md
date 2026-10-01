# Implementation Plan: quality by hour and by session age, and planned planner-session rotation

**Branch**: `288-quality-drift` | **Date**: 2026-10-01 | **Spec**: `specs/288-quality-drift/spec.md`

## Summary

Three small additions at the spots every caller already routes through. (1) The session
registry counts turns and compactions per row with one shared rule
(`sessions.count`), and the metrics replay the same rule over the `session.seen` events
that already exist, so `metrics.collect` can split the quality counters by hour band and
by the planner's session-age band; `report` and `retro` print the tables and the retro
names the worst band over seven days. (2) `lifecycle.stop`, after the wake check, asks
`sessions.rotation` whether `sessions.rotate_after` is due at a clean boundary and, if so,
blocks once with the existing `plan session --take-over` instruction and records
`session.rotated`. (3) `memory.session_payload` opens with an `Active constraints:` block
(goal text, plan, open decisions, current briefs), so every SessionStart, compaction and
rotation included, restates them.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime (`zoneinfo`, `datetime`,
`collections`).
**Testing**: pytest (dev only), `python -m pytest -q` from the repository root with the
interpreter the task names. Fixtures build workspaces in `tmp_path`, pin the clock with
`WUWEI_NOW` and, for any hour-band assertion, set `[owner] timezone = "UTC"` so the
machine's zone never decides a band.
**Constraints**: exits 0/1/2; `unmeasured`, never zero, for missing evidence; event kinds
producer-only; Stop never blocks on its own error (existing `planner wake unmeasured`
path); hook latency budget (design 10.6); no absolute local paths, emojis or em-dashes.

## Constitution Check

- I Stdlib only: yes (`zoneinfo` is stdlib, imported lazily so the hook path pays nothing
  when `owner.timezone` is empty).
- II Fail closed: a missing transcript source makes `interventions` `unmeasured`; missing
  `events.jsonl` makes `quality_by_band` `unmeasured`; a bad zone or clock text raises
  `ValueError`, which `metrics` maps to exit 2 and Stop reports without blocking (as its
  other errors today).
- III One behaviour, one function: turn and compaction counting in `sessions.count`;
  rotation in `sessions.rotation`; owner zone in `workspace.zone`; bands in
  `metrics._bands`; worst band in `metrics.worst`; table text in `metrics.band_lines`
  (used by report and retro); constraints in `memory.constraints`.
- IV Test first: every task pair below is test then implementation.
- V Ponytail: no new state key (rows of the existing `sessions` key), no new hook, no
  PreCompact write (compactions are the `SessionStart:compact` rows `_seen` already
  records), no new command, fixed band constants, transcripts read once, the retro reuses
  its own proposal shape.
- VII Security: `session.rotated` reserved to `wuwei hook Stop`; the payload block holds
  goal fields, ids and paths only, no message or brief bodies.

## Design

### 1. `cli/wuwei/workspace.py`

`SCHEMA` gains:

```python
"owner": {"name": (str, ""), "pronouns": (str, ""), "handles": [(str, None)],
          "timezone": (str, "")},
"metrics": {"transcripts": (str, "~/.claude/projects"), "band_margin": (float, 0.2)},
"sessions": {"stale_seconds": (int, 3600, 1),
             "rotate_after": {"turns": (int, 0, 0), "compactions": (int, 0, 0),
                              "clock": (str, "")}},
```

New helper beside `now()`:

```python
def zone(config):
    """The owner's time zone, or None for the machine's local zone (astimezone(None))."""
    name = config['owner']['timezone']
    if not name:
        return None
    from zoneinfo import ZoneInfo  # Local: off the hook path when unset.
    try:
        return ZoneInfo(name)
    except (KeyError, ValueError):
        raise ValueError(f'owner.timezone: unknown zone {name!r}') from None
```

`ZoneInfoNotFoundError` is a `KeyError`. Every caller converts with
`at.astimezone(zone)`, which with `None` is the machine's local zone, so one call covers
both cases.

### 2. `cli/wuwei/sessions.py`

```python
COUNTED = {'Stop': 'turns', 'SessionStart:compact': 'compactions'}


def count(row, hook):
    """One counting rule for the registry write and the metrics replay."""
    if hook in COUNTED:
        row[COUNTED[hook]] = row.get(COUNTED[hook], 0) + 1
```

- `record`: call `count(row, hook)` after `row.update(...)`. Lifecycle hooks already pass
  `Stop` and `SessionStart:<source>`; `plan session`, claims and remote hooks are not
  counted.
- `rows`: add `'turns': row.get('turns', 0), 'compactions': row.get('compactions', 0)`
  and extend the optional-key tuple `('thread', 'stopped')` with `'rotated'`.
- New:

```python
def rotation(root, config, data, session_id):
    """Block once with the take-over instruction when rotate_after is due at a clean boundary."""
    row = data.get('sessions', {}).get(session_id)
    if row is None or 'rotated' in row:
        return ''
    reason = _due(row, config['sessions']['rotate_after'], workspace.zone(config))
    from wuwei.decision import answered
    if (reason is None
            or any(seat.get('status') == 'running' for seat in data['seats'].values())
            or any(answered(data, ident) is None for ident in data.get('decision_routes', {}))):
        return ''
    payload = {'session_id': session_id, 'reason': reason,
               'turns': row.get('turns', 0), 'compactions': row.get('compactions', 0)}
    state._write_state(lambda fresh: fresh['sessions'][session_id].update(
        rotated=workspace.now().isoformat()), root, reserved=False, kind='session.rotated',
        payload=payload)
    return (f'planner rotation due ({reason}): finish this turn and end this session. Start a '
            'fresh Claude Code session in this workspace and run there: '
            'wuwei plan session "$WUWEI_SESSION_ID" --take-over. Goals, plan, decisions and '
            'briefs live in .wuwei/ and load at its SessionStart.')
```

`_due(row, limits, zone)` returns a reason string or `None`: `turns N >= limit` when
`limits['turns']` and the row's turns reach it; `compactions N >= limit` likewise;
`clock HH:MM` when `limits['clock']`, parsed with `time.fromisoformat` (bad text raises
`ValueError`), and the owner-zone `workspace.now()` is at or past it while the row's
`started` (same zone) was before it on that date. All zero or empty: `None`.

The clean boundary reads only the state the Stop hook already holds; seats are read
inline, not through `brief.seats`, to keep `brief` off the Stop import path. `decision`
is already imported on the SessionStart path (`commands.status`) and is a light module.

### 3. `cli/wuwei/guards/lifecycle.py` `stop` (lines 92 to 106)

```python
root, config = context
data = _seen(root, payload, 'Stop') or state.read_state(root)
...
message = (watch.wake(root, consume=True)
           or sessions.rotation(root, config, data, payload['session_id']))
return int(bool(message)), message
```

The wake marker wins (a pending wake is not a clean boundary). A blocking Stop already
reaches the model as `{"decision": "block", "reason": ...}` through `commands/hook.py`
`refuse`, exactly like the wake today. Errors stay in the existing `except watch.ERRORS`
branch (`0, 'planner wake unmeasured: ...'`). `session_start` and `pre_compact` do not
change.

### 4. `cli/wuwei/memory.py`

New `constraints(root, data)` returns the block text; `session_payload` puts it first:

```text
Active constraints:
Goals: G-1 Ship checkout v2 (target 3 by 2026-10-30)
Plan: .wuwei/days/2026-10-01/plan.md (approved: ITEM-1)
Open decisions: D-1
Current briefs: ITEM-1 builder-1 .wuwei/days/2026-10-01/briefs/builder-1.md
```

- Goals: for each id in `data['goals']`, `goals.parse` of `.wuwei/memory/goals.md`
  (`outcome`, `target`, `date`); an id missing from the file prints the id alone. `none`
  with no ids (the file is not read). `OSError`/`ValueError` while reading or parsing
  prints `Goals: unmeasured: <reason>` and does not fail the payload.
- Plan: when `data['gate_approved']`, the day's `plan.md` path relative to the root and
  `approved: <ids>` from `approved_items` (`none` when empty); otherwise `not approved`.
- Open decisions: ids in `decision_routes` with `decision.answered(data, id) is None`,
  sorted, comma separated; `none`.
- Current briefs: `<item> <seat> <brief>` for each seat with status `running`, `; `
  separated; `none`.

`content = constraints + '\n' + <existing content>`; size and token estimate are computed
over the whole text as today, so `wuwei payload` and SessionStart print the true size.

### 5. `cli/wuwei/metrics.py`

Constants and helpers:

```python
HOURS = ((5, 'morning'), (11, 'midday'), (14, 'afternoon'), (18, 'evening'))
AGES = ('0-49 turns', '50-199 turns', '200+ turns', 'compacted', 'no planner')
COUNTERS = ('gates', 'fix_verdicts', 'fix_rounds', 'lint_rejections', 'interventions')
```

- `_hour_band(at)`: the last `HOURS` entry whose start is at or below `at.hour`, else
  `evening` (00:00 to 04:59).
- `_age_band(row)`: `no planner` for `None`; `compacted` when `row.get('compactions')`;
  otherwise by `row.get('turns', 0)`: below 50, below 200, else `200+ turns`.
- `_bands(days, turns, zone)`: `days` is a list of `(day name, events)` pairs. Start with
  every hour band and every age band at zero. For each day separately (the registry is
  day state, so ages restart per day): take its events plus one synthetic
  `{'kind': 'owner.turn', 'ts': ...}` per transcript turn whose owner-zone date is that
  day, sort by `datetime.fromisoformat(row['ts'])` (stable, so equal stamps keep file
  order), and replay: `plan.session` sets the current planner from `payload.session_id`;
  `session.seen` calls `sessions.count(ages.setdefault(sid, {}), hook)`; then the row's
  hits are `gates` and `fix_verdicts` (`gate.received`, verdict `FIX`), `fix_rounds`
  (values equal to `fix` in `payload.phase_changes`, as the existing `fix` counter),
  `lint_rejections` (`verdict.rejected`, first sight of `(str(file), sha256)` across the
  whole window, as the existing dedupe) and `interventions` (`owner.turn`). Hits add to
  `hour[_hour_band(at.astimezone(zone))]` and `session_age[_age_band(ages.get(planner))]`.
  Finally `fix_rate = fix_verdicts / gates` or `UNMEASURED`, and `interventions =
  UNMEASURED` in every cell when `turns` is empty.
- `bands(root, days)` (public, for retro): `_bands([(day.name, _events(day) or []) for
  day in days], _human_times(root, config), workspace.zone(config))`.
- `worst(table, margin)`: bands with `gates > 0`; fewer than two returns `None`; the
  highest `fix_rate` band is returned as `(band, rate, highest other rate)` only when it
  exceeds every other measured band by at least `margin`.
- `band_lines(title, table)`: a markdown table `| <title> | Gates | FIX rate | Fix rounds |
  Lint rejections | Interventions |` with one row per band in constant order, rates as
  `0.50`; `[f'{title}: unmeasured']` when the table is `UNMEASURED`.

`collect` changes:

```python
turns = _human_times(root, config)
event_metrics['owner_intervention'] = _owner_intervention(turns, now)   # was (root, config, now)
event_metrics['quality_by_band'] = (UNMEASURED if events is None else
                                    _bands([(directory.name, events)], turns, workspace.zone(config)))
```

`_owner_intervention(turns, now)` drops its own `_human_times` call (transcripts read once,
FR-004); its body is otherwise unchanged.

### 6. `cli/wuwei/report.py` `build`

After `## Carry`, before `## Process metrics`:

```python
quality = measured['quality_by_band']
lines += ['', '## Quality by band', *(metrics.band_lines('Hour', quality['hour'])
          + [''] + metrics.band_lines('Session age', quality['session_age'])
          if quality != metrics.UNMEASURED else ['unmeasured'])]
```

### 7. `cli/wuwei/retro.py` `compile`

Before `pending = sorted(proposals.glob('*.json'))` (so a new proposal is listed under
`## Proposed`):

```python
window = watch.days(root)[:7]
quality = metrics.bands(root, window)
margin = workspace.load_config(root)['metrics']['band_margin']
lines += ['', '## Quality by band (last 7 days)']
for key, title in (('hour', 'Hour'), ('session_age', 'Session age')):
    lines += metrics.band_lines(title, quality[key])
    found = metrics.worst(quality[key], margin)
    lines.append(f'Worst {title.lower()} band: ' + (
        f'{found[0]} (FIX rate {found[1]:.2f}; others at most {found[2]:.2f})' if found else 'none'))
    if found: write the proposal (below)
```

Proposal: name `quality-<key>-<slug>` with `slug = re.sub(r'[^a-z0-9]+', '-',
band).strip('-')`; skip when any `day / 'proposals' / f'{name}.{json,landed,rejected}'`
exists for a day in `window`; otherwise `workspace.atomic_write(proposals / f'{name}.json',
...)` with `{'target': '.wuwei/charters/planner.md', 'action': 'add', 'text': f'- Gate FIX
rate is highest in the {band} {title.lower()} band over the last 7 days ({rate:.2f}, others
at most {rest:.2f}): set sessions.rotate_after so the planner session rotates before it.',
'reason': 'quality by band', 'evidence': <retro path relative to root, as POSIX>}`. The
retro file is written at the end of the same `compile`, so the evidence exists before
`promote` reads it. Add a `ponytail:` comment: the dedupe looks back seven days only; a
band that stays worst re-proposes weekly.

### 8. Reserved kind and signal

- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS['session.rotated'] = 'wuwei hook Stop'`.
- `cli/wuwei/signal.py` `SILENT` gains `'session.rotated'` (the Stop reason is the
  channel; an unkeyed nudge would never clear).

### 9. Config template and docs

- `templates/workspace/config.toml`: `[owner]` gains `# timezone = "Europe/Amsterdam" #
  IANA zone for hour bands and rotate_after.clock; empty is this machine's zone`;
  `[metrics]` gains `band_margin = 0.2`; `[sessions]` gains
  `# rotate_after = { turns = 200 } # or compactions = 1, or clock = "13:00"; off by
  default`.
- `docs/site/configuration.md`: rows for `owner.timezone`, `metrics.band_margin`,
  `sessions.rotate_after` (with its three fields).
- `docs/site/daily.md`: a `## Long sessions` section before `## 6. Close`: what is measured
  (the two tables in `report`, the worst band in `retro`), what rotation does (the Stop
  instruction at a clean boundary, `wuwei plan session "$WUWEI_SESSION_ID" --take-over` in
  the fresh session, `session.rotated` in `wuwei sessions`, nothing lost because state
  lives in `.wuwei/`), the `Active constraints` block after a compaction, and the three
  keys the owner can set.

## What must not change

- Stop with `stop_hook_active`, Stop for a non-planner session, and Stop outside a
  workspace: unchanged early returns, no rotation write.
- `guards/stop.py` (PR anchor and close) is untouched; its block and the rotation reason
  may both appear, joined by `commands/hook.py` as for any two Stop guards.
- `session_start` keeps every existing line and code; only the payload text gains the
  block at its head. `pre_compact` is untouched.
- Existing `metrics` keys and values are unchanged (`owner_intervention` only stops
  reading transcripts twice); `report`'s `## Process metrics` line stays the metrics JSON.
- Rotation never kills a session, never changes `planner_session_id` and never creates
  today's state; take-over stays `wuwei plan session ... --take-over` (#260).
- Existing tests that pin an exact registry row (`tests/test_sessions.py::
  test_record_inserts_then_moves_only_last_seen`) and the full defaults dict
  (`tests/test_workspace.py::test_config_defaults_and_independence`) are updated for the
  new `turns` field and config keys, not weakened.

## Project Structure

Files changed: `cli/wuwei/workspace.py`, `cli/wuwei/sessions.py`,
`cli/wuwei/guards/lifecycle.py`, `cli/wuwei/memory.py`, `cli/wuwei/metrics.py`,
`cli/wuwei/report.py`, `cli/wuwei/retro.py`, `cli/wuwei/commands/event.py`,
`cli/wuwei/signal.py`, `templates/workspace/config.toml`, `docs/site/configuration.md`,
`docs/site/daily.md`. Tests: `tests/test_workspace.py`, `tests/test_sessions.py`,
`tests/test_metrics.py`, `tests/test_report_retro.py`, `tests/test_memory.py`,
`tests/test_hooks.py`, `tests/test_state_allowlist.py`, `tests/test_signal_status.py`,
`tests/test_docs.py`. No new modules.
