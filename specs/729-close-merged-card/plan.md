# Implementation Plan: a merged PR closes its merge card

**Branch**: `729-close-merged-card` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

One new function, `grants.close_merged`, called from the one place both PR producers turn a
fresh read into state, `pr_actions.observe`, when the PR is merged. It writes the owner
outcome row that every open-card reader already checks through `decision.answered`, marks the
card's grant row `merged`, and records one `decision.closed` event with the merge sha and the
merger's login. The GitHub adapter's `pr` read adds `merged_by`. No reader of open cards
changes.

## Technical Context

Stdlib-only Python 3.11+, pytest for tests. No new module, no new state key, one new event
kind (`decision.closed`), one new adapter field (`merged_by`). The status line path is
untouched (it reads state it already reads).

## Constitution Check

- I stdlib only: yes.
- II exits: a close failure raises inside `observe`; the watch reports that PR unreadable
  (exit 2) and `pr state` returns exit 2 for it, as for any `observe` failure. Nothing reports
  clean when the write did not happen.
- III one behaviour, one function: the subject match and the close live only in
  `grants.close_merged`; the trigger lives only in `observe`.
- IV test first: tasks put each test before its code.
- V ponytail: one function at the shared spot, the existing `answered` predicate reused by
  writing the row it reads; the record file is not rewritten; deploy and release deferred.
- VII security: the merge fact is the adapter's read, not a seat-writable record; a closed card
  grants nothing (`grants.active` ignores `answered: merged`), so I5 holds. The event kind is
  reserved through `EVENT_PRODUCERS` like every non-free kind.

## Changes, by file

### `adapters/code_host/github.py`

- `pr` (line 207): add `'merged_by': _login(value.get('merged_by')),` next to
  `'merge_commit'`. `_login` (line 195) already returns `None` for `None`. `.get` because the
  recordings and some hand-built bodies have no `merged_by`.

### `tests/fixtures/code_host/recordings.json`

- The recorded `pr` case's expected `data` (around line 44) gains `"merged_by": null`, so the
  replay test of the adapter and the recording fake (`tests/test_adapters.py`
  `test_recording_fake`) agree with the new field. The recorded `stdout` is unchanged.

### `cli/wuwei/grants.py`

Add after `ask` (line 90):

```python
MERGED = 'merged by the owner'  # #729: the outcome of a merge card whose PR merged


def close_merged(root, ref, pr):
    """#729: close each open merge card about ref (a pr: target, or a wuwei merge rule naming
    it) now that the code host reads it merged; returns the closed ids."""
    from wuwei import decision, state, workspace
    from wuwei.exits import RACE
    evidence = {'pr': ref, 'sha': pr.get('merge_commit'), 'by': pr.get('merged_by')}
    data = state.read_state(root)
    found = [key for key, row in data.get('grants', {}).items()
             if row['action'] == 'merge' and row['answered'] is None
             and decision.answered(data, key) is None
             and (row['target'] == f'pr:{ref}' or str(row.get('rule')).startswith(f'merge: {ref} at '))]
    for key in found:
        def close(current, key=key):
            if current['grants'][key]['answered'] is not None or decision.answered(current, key) is not None:
                raise ValueError(f'grants: {key} changed; {RACE}')
            current['grants'][key]['answered'] = 'merged'
            current.setdefault('decision_outcomes', {})[key] = {
                'option': 'merged', 'outcome': MERGED, 'decided_by': 'owner', **evidence,
                'at': workspace.now().isoformat()}
        state._write_state(close, root, reserved=False, kind='decision.closed',
                           payload={'id': key, 'outcome': MERGED, **evidence})
    return found
```

Notes for the builder:

- The `startswith(f'merge: {ref} at ')` form is what keeps `acme/widget#7` from matching a
  rule for `acme/widget#70`. The rule shape comes from `merge.by_grant`
  (`cli/wuwei/merge.py:477`, `f'merge: {ref} at {head}'`); do not change it.
- `str(row.get('rule'))`: a planned row's rule is `planned` and a runtime row always has one;
  `str` keeps a `None` from raising.
- Do not add `reversibility`, `class`, `cisr` or `recommendation` to the outcome row (spec,
  Clarifications): report class counts fall back to the route's `cisr`, and the report's
  one-way list and agreement counts must not count a close.
- Reuse `state._write_state(..., reserved=False, kind=..., payload=...)` exactly as `ask`
  does; one write per card so each event carries its own id.

### `cli/wuwei/pr_actions.py`

- `observe` (line 151), after the existing `shutil.rmtree` loop at the end (before
  `return row`):

```python
    if current == 'merged':  # #729: a merge card about this PR is now moot
        from wuwei import grants
        grants.close_merged(root, ref, measured['pr'])
```

  Local import, as the module does for `shutil`. `observe` is reached by `watch.poll`
  (`cli/wuwei/watch.py:482`) and `pr_actions.evaluate` (`wuwei pr state`, `pr act`,
  `wuwei close` through `closing`, the shepherd and the stop check), so every producer that
  sees the merge closes the card; no call is added anywhere else. `closing` calls `evaluate`
  before it reads the open cards (`cli/wuwei/closing.py:262`), so a dead card no longer holds
  the day close.

### `cli/wuwei/signal.py`

- `SILENT`: add `'decision.closed'` next to `'decision.decided'` (line 15). Without it the
  unknown kind classifies as a nudge.

### `cli/wuwei/commands/event.py`

- `EVENT_PRODUCERS`: add `'decision.closed': 'wuwei watch or wuwei pr state (a merged PR closes its merge card)'`.

### `cli/wuwei/state.py`

- `STATE_PRODUCERS['decision_outcomes']` (line 253): append
  ` or wuwei watch and wuwei pr state (a merged PR closes its merge card)`; keep the existing
  text, `wuwei listen` included (`tests/test_remote.py:412` checks it).
- `STATE_PRODUCERS['grants']` (line 277): append ` or wuwei watch and wuwei pr state (a merged
  PR closes its merge card)`.

### `docs/site/concepts.md`

- The merge paragraph under `## Grants` (line 195): one sentence after the card description:
  "When the pull request merges while its card is still open (you merged it yourself), the
  watch or `bin/wuwei pr state` closes the card as merged by you, with a
  `decision.closed` event naming the merge commit and who merged it; `wuwei next`, the status
  line and the board stop asking it, and the next merge on that repository asks a new card."

## What must not change

- `decision.answered` and every reader of open cards (`next`, `status`, `control_plane`,
  `dashboard`, `closing`, `sessions`, `memory`, `metrics`): they drop the card because of the
  row the close writes.
- `grants.active`, `grants.gate`, `grants.gate_widgets`: they already skip a row whose
  `answered` is not `None`, `today`, `once` or `keep`.
- `watch.poll` and `pr_actions.evaluate`: no new call there; `observe` is the shared spot.
- The `D-n.md` record file and the item move to `merged` in `observe`.
- `merge.by_grant`'s rule text and `grants.plan`'s targets.
- Owner answers: `commands/decision.owner_outcome` still refuses a second answer to a decided
  card (`already answered`), which now covers a closed one.

## Tests (in-process, existing fixtures)

- `tests/test_merge_ports.py`: adapter `merged_by` (beside
  `test_pr_carries_actual_merge_commit`).
- `tests/test_pr_actions.py`: the acceptance through `watch.poll` and `wuwei pr state`
  (parametrized), the subject filter, idempotence, the answered card, the closed-unmerged PR,
  and `signal.classify` silent for `decision.closed`. Use `linked(case)` and `grants.ask` with
  `grants._record` to write cards, `host.results['pr'].data.update(state='closed',
  merged=True, merge_commit=..., merged_by=...)`.
- `tests/test_next.py`: `next.step` drops the decision row once `grants.close_merged` closed
  the card (the `approved` helper with `decision_routes` and `grants`).
- `tests/test_grants.py`: a closed runtime card grants nothing and the next merge on the
  repository writes and names a new card (`grants.gate` called as `merge.by_grant` calls it).

## Deferred

- Deploy and release cards (spec, Deferred).
