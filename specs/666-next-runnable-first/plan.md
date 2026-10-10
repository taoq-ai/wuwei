# Implementation Plan: a PR waiting on people never hides work that can run now, and build next and dispatch next give one answer

**Branch**: `666-next-runnable-first` | **Date**: 2026-10-10 | **Spec**: `specs/666-next-runnable-first/spec.md`

## Summary

Two small changes at the two shared spots the root cause names:

1. `next.step` (`cli/wuwei/commands/next.py`) stops returning from inside the item loop. It
   collects runnable item rows and `pr` rows, returns the first runnable row, and only falls
   back to the first `pr` row after the steward rows. More than one item row adds `rows`.
2. The `build next` command (`cli/wuwei/commands/build.py`, `run`) asks
   `dispatch.next_step` when `next_action` answers `done` for an item at `gate` or `delta`,
   so both commands read one decision function.

No new module, helper or config key.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime
**Testing**: pytest (dev only), in-process via `wuwei.__main__.main` and `next_command.step`
**Constraints**: `next.step` runs on hook paths (SessionStart orientation, `guards/lifecycle.py:52`):
it only reads and must not import modules hook paths refuse (it already imports `docs`
lazily for gate items; that stays lazy)

## Constitution Check

- I. Stdlib only: no new import.
- II. Exits: `build next` keeps 0 for an action, 1 for a finding (escalate, refusal, as
  `dispatch next`), 2 when it could not run.
- III. One behaviour, one function: the gate decision stays in `dispatch.next_step`;
  `build next` calls it instead of answering from its cache. The ranking stays in
  `next.step`.
- IV. Test first: every task below has its failing test first.
- V. Ponytail: no new abstraction; `rows` is one list comprehension, the build change is
  one branch in `run`.

## Design

### 1. `next.step` ranks runnable rows first (`cli/wuwei/commands/next.py`)

In the item loop (lines 243 to 272), replace each `return _row(...)` with an append:

- `build`, `docs`, `verdicts` rows go to `found` (runnable), in queue order.
- The `dispatch` launch-set row goes to `found` once (the first planned item that can start
  adds it; later planned items do not add a second one). The `waiting` label keeps its
  current meaning: the first planned item when no build slot is free.
- The `pr` row goes to `prs`.

After the loop:

```python
rows = [{'state': row['state'], 'item': row.get('item', ''), 'command': row['command']}
        for row in found + prs]
queue = {'rows': rows} if len(rows) > 1 else {}
if found:
    return {**found[0], **queue}
```

Then the steward block (unchanged), then:

```python
if prs:
    return {**prs[0], **queue}
```

Then the wait rows and everything after them, unchanged. Update the `step` docstring's
ponytail line: one action, the first runnable item wins, `rows` names the rest.

### 2. `rows` survives `resolve` (`next.run`)

`resolve` builds new dicts for `build`, `verdicts`, `dispatch` and launch rows, which drop
`rows`. In `run`, after the resolve loop and its `except` branches (the `except` branches
already spread `row`), carry it once:

```python
if 'rows' in row:
    action = {**action, 'rows': row['rows']}
```

`named(action)` and `_record` stay as they are: the `rows` commands are not evidence that a
command ran.

### 3. Text mode names the queue (`next.text`)

Append one line when `rows` is present:
`Queue: build A, verdicts B, pr P` (state, then item when there is one; the `dispatch` row
has no item). The orientation block reuses `text`, so SessionStart shows the same line.

### 4. `build next` reads `dispatch.next_step` past the build (`cli/wuwei/commands/build.py`)

In `run`, the `next` branch (line 40) becomes:

```python
action = next_action(item, *paths, root=root)
if action['action'] == 'done' and state.read_state(root)['items'][item]['phase'] in ('gate', 'delta'):
    from wuwei import dispatch  # #666: one decision for build next and dispatch next
    try:
        action = dispatch.next_step(item, root)
    except dispatch.Refused as exc:
        print(f'build: {exc}', file=sys.stderr)
        return 1
    if action['action'] == 'fix':  # the round just opened: its builder action, read live
        action = state.read_state(root)['builds'][item]['action']
print(json.dumps(action))
return 1 if action['action'] == 'escalate' else 0
```

`dispatch.Refused` subclasses `ValueError`, so it must be caught before the existing
`except (OSError, ValueError, RuntimeError)` (which maps to exit 2); a local `try` around
the call does that. `PortExit` from `open_fix` keeps its existing handler.

Reading `builds[item]['action']` after `fix` is the shared record `open_fix` just wrote
(`continue` with `resume`, or `launch` on a new fix brief when there is no agent id). Do not
call `next_action` again here: when `open_fix` wrote a new brief, the brief and worktree
passed on the command line no longer match the record and `next_action` would refuse.

### What must not change

- `build.next_action` (its cached return feeds `run_loop`, `launch_set`, `open_fix` and the
  `next` `build` row, all of which only see build phases or need `done` to stop).
- `build.run_loop` (Codex): it still ends on `done`.
- `dispatch.next_step`, `dispatch.launch_set`, `next.resolve`, `next.named`, `next._record`.
- The shape of a one-row `next` answer (existing equality tests pin it).
- The `pr` row's command and `then` line.

## Docs

- `docs/site/reference.md` line 49 (`bin/wuwei next` row): after the `--json` shape add
  that a day with more than one item row adds `rows` (`{state, item, command}`, runnable
  first, open PRs last) and text mode prints a `Queue:` line; the one action is still the
  first runnable row.
- `docs/site/reference.md` line 304 (Automatic phases row): add that `build next` on an
  item at `gate` or `delta` whose build is done answers what `dispatch next` decides
  (opening the fix round the same way), so the two never disagree.
- `docs/specs/2026-09-24-wuwei-design.md`, Step loop amendment (line 587): one sentence:
  once the build is done and the item is at its gates, `build next` answers what
  `dispatch next` decides (#666).

## Project Structure

Files changed:

```text
cli/wuwei/commands/next.py      step (item loop and its tail), run (carry rows), text (Queue line)
cli/wuwei/commands/build.py     run, the next branch
tests/test_next.py              US1 tests
tests/test_dispatch.py          US2 tests (reuses built, gate_fix, record)
docs/site/reference.md          next row, Automatic phases row
docs/specs/2026-09-24-wuwei-design.md  Step loop amendment
```

No research.md, data-model.md, contracts/ or quickstart.md: the only contract change is the
optional `rows` key, documented in `reference.md`.
