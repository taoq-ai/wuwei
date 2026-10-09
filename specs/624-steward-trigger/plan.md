# Implementation Plan: steward trigger

**Branch**: `624-steward-trigger` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

## Summary

One default (50 to 250), one shared predicate `state.mid_round(data)` read at the three places
a steward review starts (`steward.run`, the steward rows of `next.step`, the watch sweep), and
one report section counting today's `steward.run` events per trigger. No size trigger and no
`steward.ignore` (spec, corrected premise).

## Technical Context

Python 3.11+ stdlib only (constitution I). pytest dev-only. No new module, no new config key,
no new event kind, no new port operation, no change on the trace hook path.

## Constitution Check

- I stdlib: no new import.
- II exits: a waiting `steward run` is exit 0 with one printed line (nothing ran, nothing is
  owed: the due nudge stays pending). An unreadable state in the watch stays inside the
  existing `try` and counts as `unreadable` (exit 2), as today.
- III one behaviour one function: "mid-round" lives only in `state.mid_round`; `steward.run`,
  `next.step` and `watch.sweep` call it, none re-derives the phases.
- IV test first: each change starts with a failing test (tasks.md).
- V simplicity: no wait event, no retry timer: a pending due and an unsaved `steward_at` are the
  retry. No `steward.ignore` for a trigger that does not exist.
- VII security: no guard, refusal or trust surface changes; no 9.2 row.

## Design

### cli/wuwei/workspace.py

- `SCHEMA['steward']['every_tool_calls']`: `(int, 50, 1)` becomes `(int, 250, 1)`. Nothing
  else reads the number; `maybe_run_for_tool_calls` already reads the config.

### cli/wuwei/state.py

Add next to `BUILD_PHASES` / `in_flight`:

```python
def mid_round(data):
    """Items between a FIX verdict and its delta verdict (#624): no steward review starts."""
    return sorted(name for name, item in data['items'].items() if item['phase'] in ('fix', 'delta'))
```

`state.py` is already imported by `next.py` (hook path), `watch.py` and `steward.py`, so the
predicate adds no import to the hook path. Do not import `wuwei.steward` from `next.py`.

### cli/wuwei/steward.py `run`

After the trigger validation and the close de-duplication, before `review(root)`:

```python
if trigger != 'close' and (waiting := state.mid_round(state.read_state(root))):
    print(f"steward: waits for {', '.join(waiting)} to finish the fix round")
    return 0
```

No brief, no `steward.run`, no `registry.load`. `close` is untouched.

### cli/wuwei/commands/next.py `step`

The steward block at line 271: extend its condition so neither row (due review, brief launch)
is offered mid-round:

```python
if not state.mid_round(data) and not any(seat['role'] == 'steward' and ... ):
```

Update the `#617` comment to name #624. The due flag is not touched, so the row returns once
the round ends.

### cli/wuwei/watch.py `sweep`

Inside the existing steward `try` (line 295): run the steward and save `steward_at` only when
`state.mid_round(state.read_state(root))` is empty. A skipped sweep leaves `steward_at`
unsaved, so the next sweep after the round runs the steward.

### cli/wuwei/report.py `build`

After the `## Grants` block and before the `if level == 'brief'` return (so brief and full
both show it), reusing `watch.records(day / 'events.jsonl')` and `Counter` already imported:

```
## Steward runs
- close: 1
- sweep: 2
- tool-calls: 1
Settings: steward.every_tool_calls = 250, watch.sweep_seconds = 7200
```

`none` replaces the trigger lines when today has no `steward.run`. Config via
`workspace.load_config(root)` (already called in `build`). Same read pattern as the
`grant.used` block; do not refactor the existing reads.

### Docs

- `docs/site/configuration.md` row `steward.every_tool_calls`: default `250`, and "no review
  starts while an item is in `fix` or `delta`; it waits for the round to end".
- `docs/site/reference.md` `steward run` paragraph: `--trigger sweep|tool-calls` while an item
  is in `fix` or `delta` prints `steward: waits for <items> to finish the fix round`, writes no
  brief and exits 0; `--trigger close` runs as before.
- `docs/site/daily.md`, next to the `## Cycle time` sentence: the report's `## Steward runs`
  section counts today's steward reviews per trigger beside `steward.every_tool_calls` and
  `watch.sweep_seconds`.
- Design spec 5.5 is not edited (owner-only); the pull request carries the proposed text from
  the spec's "Design spec conflict" section.

## What must not change

- `maybe_run_for_tool_calls` and the trace guard (`cli/wuwei/guards/traces.py`): the count,
  the checkpoint logic and the "never a hook refusal" catch stay as they are.
- The close review, its once-a-day rule, `steward.review`, `negotiation`, `decision_queue`.
- The `#617` rules in `next.step`: one steward at a time, newest brief only, due waits while a
  steward seat runs.
- `repos.merge.size_exclude` and the merge size rule (#615).
- Event kinds and `RESERVED`: no new kind.

## Tests

- `tests/test_workspace.py`: the defaults table expects `every_tool_calls: 250`.
- `tests/test_steward.py`: 250 calls on the default config give one due; `every_tool_calls =
  100` gives two; `run` waits for `fix` and `delta` on `sweep` and `tool-calls` (no brief, no
  event, `registry.load` not called); `close` runs mid-round; the report section with counts,
  with `none`, and under brief verbosity.
- `tests/test_next.py`: due and unlaunched-brief rows are held while an item is mid-round and
  its seat runs; the due row returns after the item merges.
- `tests/test_quiet_sweeps.py`: the sweep skips the steward and leaves `steward_at` unset while
  an item is in `fix`; the next sweep after the item leaves `fix` runs it.
- `tests/test_docs.py`: the three docs phrases.
