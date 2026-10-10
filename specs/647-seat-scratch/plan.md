# Implementation Plan: a scratch directory per seat

**Branch**: `647-seat-scratch` | **Date**: 2026-10-10 | **Spec**: [spec.md](spec.md)

## Summary

One header line and one `mkdir` in `brief.write`, one PreToolUse check in `protect_state`
under the `seats` area, one `rmtree` where `pr_actions.observe` moves an item to `merged`.
The seat lookup reuses the subagent-transcript derivation `traces.check` already has, moved
into `brief` so both call one function.

## Technical Context

Python 3.11+ stdlib only. pytest dev-only. No new module, no new config key, no new event
kind, no new port operation, no state field.

## Constitution Check

- I stdlib: `shutil` and `pathlib` only.
- II exits: the check returns 0 (nothing, or a printed warning), 1 (a refusal at `block`),
  2 (malformed `agent_id`, unreadable state or config), and the hook levels 1 and 2 by the
  `seats` area like any guard.
- III one behaviour one function: the scratch base lives in `workspace.SCRATCH`; the
  subagent transcript derivation lives in `brief.subagent_transcript` (traces calls it).
- IV test first: tasks.md orders each test before its change.
- V simplicity: no event, no config key, no host-scratchpad discovery, no cleanup of the host
  scratchpad, no charter change.
- VII security: below strict a warning, never a wall (constitution VII, #530). Scope: inside
  a workspace or managed worktree only (`_workspace(cwd) or worktree_workspace(cwd)`, as
  `check_file`). The check only reads; the only new write is `mkdir` under `.wuwei/scratch`
  and its removal, neither of which is a protected record.

## Design

### cli/wuwei/workspace.py

Next to the other module constants:

```python
SCRATCH = '.wuwei/scratch'  # #647: <root>/.wuwei/scratch/<item>/<role>/, one per seat
```

### cli/wuwei/brief.py

1. `write`, line 367: after the `Seat policy:` entry append

   ```python
   scratch = root / workspace.SCRATCH / item / role
   header.append(f'Scratch: <your scratchpad>/{item}/{role}/, or {scratch}/ when your host names '
                 'no scratchpad; create it if missing and write every temporary file there, '
                 "never at the scratchpad root or in another item's directory")
   ```

   and before `return relative` (line 507), once the brief and its event are written:
   `scratch.mkdir(parents=True, exist_ok=True)`. `item` and `role` already passed
   `identifier`, so neither carries a separator. Every role gets the line (builder, gate
   seats, lead, steward, shepherd): every seat writes temporary files.

2. Two helpers next to `transcript_reference`:

   ```python
   def subagent_transcript(payload):
       """The subagent transcript of a hook call with agent_id (#473), else None."""
       agent_id = payload.get('agent_id')
       if agent_id is None:
           return None
       if not isinstance(agent_id, str) or not agent_id.strip():
           raise ValueError(f'invalid agent_id; {PAYLOAD}')
       if not payload.get('transcript_path'):
           return None
       return (Path(payload['transcript_path']).parent / payload['session_id']
               / 'subagents' / f'agent-{agent_id}.jsonl')


   def seat_of(payload, data):
       """#647: the seat record whose brief the calling subagent's transcript names, else None."""
       path = subagent_transcript(payload)
       if path is None:
           return None
       try:
           reference = transcript_reference(path)
       except OSError:
           return None
       return next((seat for seat in seats(data).values() if seat.get('brief') == reference), None)
   ```

### cli/wuwei/guards/traces.py

`check`, lines 104-112: replace the inline derivation with the helper, behaviour unchanged
(the existing `test_traces.py` subagent cases pin it):

```python
if 'agent_id' in payload:
    from wuwei import brief
    transcript_path = brief.subagent_transcript(payload)
    payload['session_id'] = payload['session_id'] + ':' + payload['agent_id']
```

The helper validates `agent_id` first and returns None for a falsy `transcript_path`, so the
old `if transcript_path:` branch is inside it. Keep the `ValueError` message
`invalid agent_id; ...` (now raised by the helper) so the existing except branch reports it
as before.

### cli/wuwei/guards/protect_state.py

A new function after `check_file`, and a third `GUARDS` entry with the same matcher:

```python
def check_scratch(payload):
    """#647: a seat's Write into another item's scratch directory: a warning below strict."""
    try:
        if 'agent_id' not in payload:
            return 0, ''
        cwd = _cwd(payload)
        root = _workspace(cwd) or worktree_workspace(cwd)
        if root is None:
            return 0, ''
        field = 'notebook_path' if payload.get('tool_name') == 'NotebookEdit' else 'file_path'
        parts = _path(_input(payload, field), cwd).resolve().parts
        found = next(((Path(*parts[:index + 1]), parts[index + 1]) for index in range(len(parts) - 2)
                      if parts[index] == 'scratchpad'
                      or parts[index] == 'scratch' and parts[index - 1] == '.wuwei'), None)
        if found is None:
            return 0, ''
        from wuwei import brief, state, workspace
        data = state.read_state(root)
        seat = brief.seat_of(payload, data)
        base, other = found
        if seat is None or other == seat['item'] or other not in data['items']:
            return 0, ''
        reason = (f"scratch: {Path(*parts)} is in item {other}'s scratch directory; write item "
                  f"{seat['item']}'s temporary files in {base / seat['item'] / seat['role']}/")
        level = workspace.posture(workspace.load_config(root))[1]['seats']
        if level == 'block':
            return 1, reason
        if level == 'warn':
            print(f'warning: {reason}', file=sys.stderr)
        return 0, ''
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        return 2, str(exc)
```

- Order matters for latency (#346, #562): the `agent_id` test and a path walk come before any
  import or file read, so the main session and ordinary seat writes pay nothing measurable.
- `import sys` at module top (protect_state has none today).
- `GUARDS` gains `Guard('PreToolUse', 'Write|Edit|MultiEdit|NotebookEdit', check_scratch)`;
  `guards.MODULES['protect_state']` already selects those tools, so no MODULES change.

### cli/wuwei/guards/__init__.py

`AREAS` gains `'protect_state.check_scratch': 'seats'`. `level()` then gives a refusal at
`block` the line `posture: seats = block (set security.areas.seats)`. The check levels
`warn` and `off` itself, so the hook's `guard.would_refuse` path (an owner nudge under
guarded) is not reached for this check; it only sees exit 1 at `block` and exit 2.

### cli/wuwei/pr_actions.py `observe`

In `update`, at line 223-226, collect the names moved to `merged`:

```python
merged = []
...
            state._move(data, name, 'merged')
            merged.append(name)
```

(`merged = []` declared before `def update`; `_write_state` runs the callback once). After
`state._write_state(update, ...)` at line 227:

```python
import shutil
for name in merged:  # #647: the item's scratch goes with the confirmed merge
    shutil.rmtree(root / workspace.SCRATCH / name, ignore_errors=True)
```

`ignore_errors` because the directory may not exist (a seat that never wrote) and a symlink
in its place must not be followed (`rmtree` refuses it). Add
`# ponytail: the host scratchpad's <item>/ is not removed; the host clears its session scratchpad`.

### Docs

- `docs/site/reference.md`, table under "Seat briefs and the build loop": a row
  `| Scratch directory | Each brief names <your scratchpad>/<item>/<role>/, or .wuwei/scratch/<item>/<role>/
  when the host names no scratchpad; wuwei brief creates the workspace one, and an observed merge removes
  .wuwei/scratch/<item>/. A seat's Write into another item's directory prints a warning naming its own
  under observe and guarded, and is refused under strict (area seats). |`
- `docs/site/security.md`, the `seats` row: append `, and scratch directories
  (protect_state.check_scratch)` inside the "What it covers" cell. The level columns stay.

## What must not change

- `check_file`'s results and messages, and every existing protected path.
- The `guard.would_refuse` and `hook.warning` paths and their owner nudges.
- `traces.check` behaviour, its span session ids and its binding of `seat['transcript']`.
- The brief's existing header lines and their order (the line is appended after
  `Seat policy:`); `agent_launch` hashes the brief file as written, so nothing else moves.
- No absolute local path in any repository file (tests build paths from `tmp_path`).

## Test plan

- `tests/test_brief.py`: two builder briefs on items `X` and `Y` (fixture `day`) carry
  different `Scratch:` lines naming `X/builder/` and `Y/builder/` and the instruction text;
  `.wuwei/scratch/X/builder` and `.../Y/builder` exist after the writes. A refused brief
  (for example the unresolved ruling case) creates no scratch directory.
- `tests/test_protect_state.py`: a fixture state with items `A` and `B`, seat `b-a`
  (role `builder`, item `A`, brief `.wuwei/days/2026-09-28/briefs/b-a.md`, status `running`),
  and a subagent transcript at `<dir of transcript_path>/fixture/subagents/agent-x.jsonl`
  whose first user line is `WUWEI brief: .wuwei/days/2026-09-28/briefs/b-a.md`
  (`WUWEI_NOW` pinned to that day). Through `commands.hook.run` (as
  `test_discovered_guards_through_hook`), parametrized over `observe`, `guarded`, `strict`
  and over the bases `.wuwei/scratch` and `<tmp_path>/scratchpad`: a Write to `<base>/B/x.sh`
  exits 0 with `warning: scratch: ...` naming `<base>/A/builder/` on stderr and no stdout
  below strict; exits 2 with the reason and `posture: seats = block (set
  security.areas.seats)` under strict. Silent cases: `<base>/A/x.sh`, no `agent_id`,
  `<base>/notes/x.sh` (no such item), a missing subagent transcript.
- `tests/test_posture.py::test_guard_areas_table` passes unchanged (`seats` is an area).
- `tests/test_pr_actions.py`: with `.wuwei/scratch/A/builder/x` and `.wuwei/scratch/B/builder/y`,
  an observed merge of `A` (`main(['pr', 'state'])`, as
  `test_observed_merge_moves_raised_to_merged`) removes `.wuwei/scratch/A` and keeps
  `.wuwei/scratch/B`.
- `tests/test_traces.py`: existing subagent cases stay green after the helper move; add one
  for `brief.subagent_transcript` returning None without `agent_id` and raising on `''`.
