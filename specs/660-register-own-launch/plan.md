# Implementation Plan: a launch the planner makes itself is registered

**Branch**: `660-register-own-launch` | **Date**: 2026-10-10 | **Spec**: `spec.md`

## Summary

Four small changes at the spots every caller already routes through. One marker reader in
`brief.py` lets the launch guard and the transcript readers find `WUWEI brief:` on any line.
The launch guard keeps the text around WUWEI's prompt as the seat's `planner_note`, and routes a
typed launch with no marker to the existing adhoc registration (#676) with a warning, or
refuses it under strict. The hook shows the planner every launch refusal it lets through.
The stop guard sends a typed stop with no brief to the existing adhoc stop. `why <item>`
prints the note. `dispatch` needs no change: once the seat registers, its existing rules stop
offering the launch.

## Technical Context

Python 3.11+, stdlib only (`re`); pytest for tests. The launch and stop guards run once per
agent. The extra work at launch is one regeneration of the launch prompt (`brief.launch_prompt`,
the function `build next` and `dispatch next` already call) for brief seats, and one state
read for a typed launch with no marker. At stop it is one read of the transcript's first user
rows for typed agents.

## Constitution Check

- I (stdlib): `re` only.
- II (exits): a launch refusal stays exit 1 (`brief.Refused`); an unreadable launch prompt for
  the note falls back, never refuses (the note is not evidence); the stop path never refuses.
- III (one behaviour, one function): the marker read lives once in `brief.reference`; the
  adhoc registration and stop are reused, not copied.
- IV (test first): every behaviour has a test task before its implementation task.
- V (ponytail): no new state key except the seat's `planner_note`, no new event kind, no new module,
  no new hook event; `dispatch.py` is not touched.
- VII (security): the note is redacted (`wuwei.redact.redact`) and capped at 500 characters;
  `why` output is redacted again by `render`. Item inference reads only today's plan ids.
- Guard rule change: adds invariant I47 to design 9.2 and `tests/test_invariants.py`
  (constitution, Workflow). Use the next free id on main at build time if I47 is taken.

## Design

### `cli/wuwei/brief.py`

New, next to `transcript_reference` (line 158):

```python
def reference(text):
    """#660: the brief path of the first line of text that starts with the marker, else None."""
    return next((line[len(REFERENCE_PREFIX):] for line in text.splitlines()
                 if line.startswith(REFERENCE_PREFIX)), None)
```

`transcript_reference(path)`: for each of `_user_messages(path)`, return `reference(content)`
when it is not None; else None. Same callers, same return.

### `cli/wuwei/guards/agent_launch.py`

1. `check` (line 24): `except brief.Refused as exc: return 1, f'seat not registered: {exc}'`.
2. `_check` (lines 125-129): replace the `startswith` test and the first-line slice with
   `relative = brief.reference(inputs['prompt'])`; when None, return
   `_unbriefed(payload, root, inputs, role)`. Everything after (path validation, logged brief,
   hash, role, name, capacity, `reserve`) is unchanged.
3. After the hash check passes, `note = _note(inputs['prompt'], relative, path, root, role)`;
   in `reserve`, the seat dict gains `'planner_note': note` only when `note` is nonempty.
4. New `_note(prompt, relative, path, root, role)`:
   - `own = brief.launch_prompt(path, security.agent_path(root, role), root=root)`, `None`
     on `OSError` or `ValueError`.
   - `text = prompt.replace(own, '', 1) if own and own in prompt else
     prompt.replace(brief.REFERENCE_PREFIX + relative, '', 1)`.
   - return `redact(text.strip())[:NOTE]` with `NOTE = 500`
     (`# ponytail: a continue round's feedback reads as note; subtract it if noisy`).
5. New `_named_item(data, inputs)`: the one key of `data['items']` that appears as a whole
   word (`(?<![\w.-])<re.escape(item)>(?![\w.-])`) in the Agent `name`, `description` and
   `prompt` strings joined; None for zero or several.
6. New `_unbriefed(payload, root, inputs, role)`:
   - with no `state.json`, refuse naming `wuwei brief` (exit 1, as today); else
     `_, data = brief.read_day(root)`; `item = _named_item(data, inputs)`;
     `command = f'bin/wuwei brief {role} {item or "<item>"} <name>'`.
   - `seats` level `block` (`workspace.posture(workspace.load_config(root))[1]['seats']`):
     raise `brief.Refused(f'no WUWEI brief: line in the Agent prompt; write the brief with
     {command}, then launch with the prompt bin/wuwei build next or bin/wuwei dispatch next
     returns')`. Nothing is written.
   - Else `return _adhoc(payload, role=role)`.
7. `_adhoc(payload, role=None)` (line 73), extended, not copied. With `role` (an unbriefed
   typed launch):
   - skip the `ADHOC` strict refusal (the caller decided);
   - in `reserve(data)`: `item = _named_item(data, inputs) or name`; the seat gets
     `item=item`, `label=role` (type stays the Agent type, for example `wuwei:builder`);
     `event.update(name=name, item=item)` (today `item=name`; for an untyped launch it stays
     `name`);
   - return `1, UNBRIEFED.format(name=..., item=..., role=role)` where `UNBRIEFED` reads
     `unbriefed launch registered as adhoc seat {name} for {item}: the Agent prompt has no
     WUWEI brief: line, so WUWEI cannot receive or continue it; write the brief with
     bin/wuwei brief {role} {item} <name>, then launch with the prompt bin/wuwei build next
     {item} or bin/wuwei dispatch next {item} returns`. When no item was named, `{item}` in
     the commands is the literal `<item>` and `for {item}` reads `for no item of today's
     plan`.
   Without `role` the behaviour is #676's, byte for byte (`0, ''`).
8. `stop` (line 327): `if not wuwei_role(payload.get('agent_type')) or _unbriefed_stop(payload):
   return _stop_adhoc(payload, root)`. New `_unbriefed_stop(payload)`: True when
   `brief.transcript_reference(payload['agent_transcript_path'])` is None; False on
   `OSError`, `ValueError`, `KeyError`, `TypeError` (unreadable keeps today's brief path and
   its #473 fallback).

### `cli/wuwei/commands/hook.py`

- `posture(payload, refusals, root, warned=None)` (line 249): in the `warn` branch, after the
  `guard.would_refuse` event is appended, `if warned is not None and guard == 'agent_launch':
  warned.append(f'{reason}\n{line}' if line else reason)`. Return value unchanged (tests call
  it directly).
- `run` (lines 119-139): `warned = []`, passed to `posture`; after the `if reasons: return
  refuse(...)` line and before the Stop context print:
  `if warned: print(json.dumps({'hookSpecificOutput': {'hookEventName': args.event,
  'additionalContext': '\n'.join(warned)}}))`. Only `agent_launch` (PreToolUse `Agent`)
  can fill it.

### `cli/wuwei/commands/why.py`

- `GROUPS` (line 16): `'seat'` after `'worktree'`.
- In `item`'s event loop, beside `worktree.created` (line 134):
  `kind == 'seat launched' and payload.get('item') == name`: `seat = data['seats'].get(
  payload.get('name'), {})`; with `seat.get('note')`:
  `seat <name> (<role>): planner note: <note>`; else with `seat.get('role') == 'adhoc'`:
  `seat <name> (<type>, unbriefed): prompt: <prompt>`; else nothing. Evidence path
  `state.json` of that day. `render` redacts.

### Not changed

- `cli/wuwei/dispatch.py`: `_seats` (line 537) skips a logged brief whose name is a seat and
  adds the `receive` command for a stopped one; `build.next_action` refuses while the bound
  build runs; `launch_set` treats an item with a running seat as busy. All of that works once
  the seat registers. The acceptance test proves it.
- `brief.REFERENCE_PREFIX`, `brief.launch_prompt`, `stopping_seat`, `check_mcp`, `_seat`,
  `adhoc_seat`, `traces.py`, `seat.py`, `watch.py`, `scanner.py`: unchanged. Traces of a
  brief seat whose marker is not first bind through the new `transcript_reference`; traces of
  an unbriefed seat bind through the existing digest path because it is an adhoc seat.
- An untyped launch (#676) keeps exit 0 with no warning.
- Other guards' `warn` refusals stay record-only.

### Docs

- `docs/specs/2026-09-24-wuwei-design.md` 4.1, `Agent` launch row (line 172): the marker line
  may stand on any line of the prompt and the text around WUWEI's prompt is kept as the seat's
  planner note (`why <item>`); under strict a WUWEI seat type launched with no marker is
  refused naming `bin/wuwei brief <role> <item> <name>`; below strict it registers as an
  adhoc seat with that warning, and every launch refusal the posture lets through is shown to
  the session as `seat not registered: <reason>` (#660).
- Design 9.2, row I47: `| I47 | A typed Agent launch inside a day is never silently
  unregistered: below strict it registers a seat or the session is shown its reason; a launch
  with no brief marker registers as an adhoc seat naming wuwei brief, and under strict it is
  refused naming wuwei brief | per posture, agent_launch.check levelled by hook.posture on a
  launch with no marker and on a marker naming an unlogged brief | #660; the marker may stand
  on any line; the note is kept on the seat |`.
- `docs/site/recovery.md` (Seat launch contract, line 132): the line may stand anywhere;
  notes before or after WUWEI's prompt are kept and `wuwei why <item>` shows them; a launch
  without it registers as an adhoc seat with a warning below strict and is refused under
  strict; replace "Do not prepend instructions to the prompt" and "a missing first line is
  refused".

## What must not change

- The brief launch contract: every check after the marker read in `_check`, `stopping_seat`,
  `check_mcp`, and their tests apart from the ones listed below.
- The `seat launched` event payload keys; the seat keys other than the new `planner_note`.
- `hook.posture`'s return value and its `guard.would_refuse` record.
- `hooks/hooks.json`, `guards.EVENTS`, `guards.MODULES`, `guards.AREAS`.
- An unreadable SubagentStop transcript still takes the brief path (#473).

## Existing tests whose contract changes

- `tests/test_agent_launch.py::test_guard_table`: `nested-marker` becomes `(0, '')` (the
  marker on line 2 binds); `no-marker` stays exit 1 with `brief` in the reason, now the
  unbriefed warning (the fixture runs under the default guarded posture).
- `tests/test_agent_launch.py` line 542: the second-opinion refusal reads
  `seat not registered: second-opinion brief runs through wuwei dispatch opinion, not Agent`.
- `tests/test_invariants.py`: `INVARIANTS` and `READS` (`'I47': (0,)`) pick up I47.
- `tests/test_launch_contract.py::test_missing_first_line_names_contract` is replaced: a
  launch with no brief line now registers an adhoc seat and names `bin/wuwei brief`, and
  `Instructions:\nWUWEI brief: brief.md` now reads the marker on line 2 and fails closed on
  the invalid path (exit 2), instead of refusing for a missing first line.
- Anything that compares a launch refusal exactly gains the `seat not registered: ` prefix;
  substring checks are unaffected.
