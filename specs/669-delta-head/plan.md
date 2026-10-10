# Implementation Plan: the delta round refreshes the reviewer's recorded head

**Branch**: `669-delta-head` | **Date**: 2026-10-10 | **Spec**: `specs/669-delta-head/spec.md`

## Summary

`dispatch next` records the live worktree head on the reviewer's seat as `delta_head` when
it builds the delta `continue` action, and names that head in the delta feedback.
`receive` in a delta round checks the verdict's `Head:` against `delta_head` (else the
seat's `head`) instead of the stale brief text, refusing with both heads named. Three small
edits in `cli/wuwei/dispatch.py`, one line each in `commands/event.py` and `signal.py`, one
sentence of docs.

## Technical Context

Python 3.11+, stdlib only at runtime; pytest for tests. No new dependency, no new module,
no new config key, no new port method (the VCS port's `head` already exists and `receive`
already calls it the same way).

## Constitution Check

- I. Stdlib only: yes, no imports added beyond the module's existing ones (`brief`,
  `registry`, `state`, `workspace` are already imported at the top of `dispatch.py`).
- II. Fail closed: an unreadable live head raises through `brief.read` (`ValueError`), which
  `dispatch next` already maps to exit 2; nothing is recorded on failure.
- III. One behaviour, one function: the delta head is written in `_seats` only and read in
  `receive` only.
- IV. Test first: every behaviour below has its failing test first (tasks.md).
- V. Ponytail: one seat field, no helper, no abstraction; the existing head check is
  narrowed by round, not duplicated.
- VII. Security: the seat record is producer-owned (`state._generic_allowed` never allows a
  seat path), the new event kind is reserved in `EVENT_PRODUCERS`, and the live worktree
  check in `receive` stays, so a forged `delta_head` cannot admit a head that is not the
  item's live head.

## Design

### 1. `_seats`, delta branch (`cli/wuwei/dispatch.py:547` to `561`)

After the existing `if not delta_due(data, item, role, name): continue`, before building the
feedback:

```python
head = brief.read(registry.load('vcs', workspace.load_config(root)).head,
                  str((root / worktree).resolve()), root=root)['sha']
if seat.get('delta_head') != head:  # #669: the head the delta verdict must carry
    state._write_state(lambda fresh: fresh['seats'][name].update(delta_head=head), root,
                       reserved=False, kind='gate.delta_head',
                       payload={'item': item, 'seat': name, 'head': head})
feedback = _delta_feedback(first, depth(data['items'][item], gate=True) == 'light', head)
```

`worktree` is the local already bound at the top of `_seats` (the item's recorded
worktree); `(root / worktree).resolve()` is the same form `_changes` uses
(`cli/wuwei/dispatch.py:160`). The read and write happen only for a seat that is due its
delta continue, so the initial round and the second-opinion branch (which `continue`s
earlier) never read the VCS here. No event when the head is unchanged keeps
`dispatch next` idempotent, the same rule the `gate.tiered` write follows.

### 2. `_delta_feedback` (`cli/wuwei/dispatch.py:598` to `606`)

Add a third parameter `head='HEAD'` and use it in both texts:

- light: `Re-read: the fix round changed {first}..{head}. Re-read the diff for your
  blocking findings and rewrite only the Verdict: and Head: lines of {file} (Head: {head});
  mark each finding the fix closed blocks: no.`
- delta review: `Delta review: the fix round changed {first}..{head}. Re-check your
  findings at {head} and rewrite {file} with Head: {head}. A new finding on lines ...`
  (the #623 sentence unchanged).

Prefixes `Re-read:` and `Delta review:` and the #623 sentence stay byte-identical (tests in
`test_process_depth.py`, `test_pace.py`, `test_path_day.py` and `test_dispatch.py:1365`
assert them). `opinion` keeps calling `_delta_feedback(first)`; the default `'HEAD'` reads
as today's text.

### 3. `receive`, the brief head check (`cli/wuwei/dispatch.py:661` to `663`)

Split the existing check by round; the initial branch is the existing condition and
message, unchanged. Amended during implementation: a fresh delta seat under a new name with
no recorded head (no `delta_head`, no `head`) keeps the brief check, since it was briefed
for the current head; refusing it broke the fresh-seat delta path
(`test_fix_pass_then_only_quality_delta` and its siblings):

```python
expected = str(seat.get('delta_head') or seat.get('head') or '') if round_name == 'delta' else ''
if expected:  # #669: the delta head, never the initial brief's head
    if not expected.lower().startswith(head.lower()):
        raise Refused(f'verdict Head {head} is not the delta head {expected}; ...')
elif (f'HEAD: {head}' not in brief_text and ...):   # unchanged
    raise Refused('verdict HEAD differs from dispatched brief; ...')   # unchanged
```

`brief_text` is still read (the `Worktree:` line below needs it). The live worktree check,
the sibling check, the scanner merge and the record are untouched.

### 4. Event kind (`cli/wuwei/commands/event.py`, `cli/wuwei/signal.py`)

- `EVENT_PRODUCERS['gate.delta_head'] = 'wuwei dispatch next'`, next to `gate.tiered`.
- Add `'gate.delta_head'` to `signal.SILENT` beside `'gate.tiered'`.

### 5. Docs (`docs/site/daily.md`, step 5 Delta)

One sentence: `dispatch next` records the delta head on the seat and the `continue`
feedback names it; the planner may continue the same seat in its session or launch it as a
fresh Agent, and the delta verdict's `Head:` is that delta head.

## Files

| File | Change |
|---|---|
| `cli/wuwei/dispatch.py` | `_seats` delta branch records `delta_head`; `_delta_feedback` takes `head`; `receive` delta-round head check |
| `cli/wuwei/commands/event.py` | `gate.delta_head` producer |
| `cli/wuwei/signal.py` | `gate.delta_head` in `SILENT` |
| `docs/site/daily.md` | step 5 sentence |
| `tests/test_dispatch.py` | new acceptance tests; VCS fake in the existing delta-continue test; updated match in `test_continued_sentinel_delta_head_matches_seat_head` |
| `tests/test_process_depth.py`, `tests/test_pace.py` | VCS fake for the delta-continue tests that now read the live head |

## Reuse

- `brief.read(vcs.head, tree, root=root)['sha']`: the live-head read `receive`
  (`dispatch.py:670`) and `_changes` (`dispatch.py:162`) already use.
- `state._write_state(..., reserved=False, kind=..., payload=...)`: the same producer write
  `next_step` uses for `gate.tiered`.
- `delta_due`: unchanged; it still decides which seat gets the continue (and so the record).

## Must not change

- `delta_due` and the seat's `head` field (the launch guard and `delta_due` rely on `head`
  equal to the initial head while the continue is due).
- `cli/wuwei/guards/agent_launch.py`: the relaunch path keeps rewriting the seat with the
  live head; `receive` falls back to that `head`.
- The initial-round head check and its message, the live worktree check, the sibling-head
  check, the scanner path, `opinion`.
- The gate brief files (hash-bound to their `brief written` events).
- The `continue` action's shape (`action`, `resume`, `feedback`, `prompt`, `receive`).

## Test notes

- The VCS fake must answer only `kind == 'vcs'` and delegate other kinds to the real
  `registry.load`, because `next_step` runs other ports (steward, tracker check):
  `real = registry.load; monkeypatch.setattr(registry, 'load', lambda kind, config: VCS() if kind == 'vcs' else real(kind, config))`.
- The acceptance seat brief carries `Worktree: <root>` so `receive`'s live check runs,
  as in `test_receive_rechecks_current_worktree_head`.
