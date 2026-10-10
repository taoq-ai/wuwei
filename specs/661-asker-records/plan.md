# Implementation Plan: The agent that asked a card records its answer

**Branch**: `661-asker-records` | **Date**: 2026-10-10 | **Spec**: `specs/661-asker-records/spec.md`

## Summary

One hook fix at the shared spot: `protect_state` treats `decision outcome` as the record
command it is (the same writer as `decide`), so the planner runs it for a card it asked
below strict. Around it: the planner's record refusals below strict name the card instead
of a host-terminal command (strict keeps the command, minus the card hash); `decision
outcome` takes #599's card hash (`--card`, also spelled `--from-card`); the parked-build line
names the card; doctor lists answered cards whose record never ran; I8 covers `decision
outcome`.

## Starting point

- **Prerequisite: #599 on main.** Before T001, check that `cli/wuwei/decision.py` defines
  `card_hash` and `no_card` and `cli/wuwei/commands/decide.py` registers `--card`. If they
  are missing, pull main first. If #599 is still not merged, build Phases 1, 3, 4, 5 and 6
  (none need it), leave T008 to T011 open and report them blocked on #599. Never copy #599's
  code into this branch.
- Line numbers below are on main `66b3720` (before #599); #599 does not touch
  `protect_state.py` or `build.py`, so those hold.

## Technical Context

Python 3.11+, stdlib only; pytest for tests. Run the touched files while building:
`python -m pytest -q tests/test_owner_edits.py tests/test_card_confirms.py tests/test_decision.py
tests/test_build.py tests/test_doctor.py tests/test_invariants.py tests/test_docs.py`, then the
full suite once.

## Constitution Check

- I stdlib: yes.
- II exits: no new exit. A hook refusal stays exit 1; the doctor row is ok, warn or
  unmeasured; an unknown hash is #599's exit 1 with its reason.
- III one behaviour, one function: the planner record rule stays in
  `protect_state._owner_action`; the card-hash rule stays in #599's `owner_confirm`; doctor
  reads `decision.answered` and `drafts.read`, nothing re-implemented.
- IV test first: every task pair in `tasks.md`.
- V ponytail: no new module, state key, event kind or config; one reason constant, one
  doctor helper, one build-line helper (replacing two copies of the same f-string).
- VII security and #530: seats and non-planner sessions refused as today (I8); strict
  unchanged except the hash words drop from the printed command; no new wall below strict.
- Hook path: no new read on the pass path. `_strict(cwd)` (one config read) runs only on
  the refusal branch, as #579's pace check already does.

## Changes, by file

1. `cli/wuwei/guards/protect_state.py`
   - `_GATE_EDITS` (line 188): add `('decision', 'outcome')`.
   - Asked-id check (line 278): `group in ('mcp', 'decide', 'decision', 'drafts')`.
   - New constant next to `GUARD_CONFIG` (line 106):
     ```python
     # #661: below strict the owner answers on a card; the planner never hands them a command.
     CARD_FIRST = ("The owner's answer on a card in this session records it: ask the card (bin/wuwei "
                   'decision show <id> --widget for a decision, the Draft card for a draft, the morning '
                   'gate for goals and voice), then run the record command the card names.')
     ```
   - The planner refusal (line 286) becomes:
     ```python
     if not _strict(cwd):  # #661: a card, never a host-terminal command below strict
         return 1, reason if group == 'config' else CARD_FIRST
     shown = argv if group not in ('decide', 'decision') else [
         word for before, word in zip(['', *argv], argv)
         if before not in ('--card', '--from-card') and not word.startswith(('--card', '--from-card'))]
     return 1, f'{reason} Run it in a host terminal: {shlex.join(shown)}'
     ```
     `reason` for `config set` is already card-first (#529 table row or `GUARD_CONFIG`).
   - Leave the `_OWNER_ACTIONS` texts alone: seats and other sessions still get them, and
     `guide.py:46` lists the table keys.
2. `cli/wuwei/commands/decision.py`
   - `register` (line 29): the `outcome` help becomes `"Record the owner's answer to a
     decision"` and it gains
     `outcome.add_argument('--card', '--from-card', dest='card', metavar='HASH', help=...)`
     with #599's help text. `owner_outcome` already reads `getattr(args, 'card', None)`
     after #599; no other change.
3. `cli/wuwei/commands/decide.py` (#599's `--card` line): add the `'--from-card'` spelling
   with `dest='card'`.
4. `cli/wuwei/commands/build.py`
   - One module-level helper used at lines 36 and 497 in place of the two copies:
     ```python
     def parked_line(item, action):
         """#661: a parked item names its card, never a host-terminal command."""
         ident = Path(action['decision']).stem
         return (f'build: parked {item}: {action["reason"]}; decision {ident}; ask the owner with '
                 f'bin/wuwei decision show {ident} --widget and run its record command, then resume the item')
     ```
     (`Path` is already imported there; check, else `from pathlib import Path`.)
5. `cli/wuwei/commands/doctor.py`
   - New `_unrecorded(root)` next to `_legacy_traces` (line 658):
     ```python
     def _unrecorded(root):
         """#661: cards the owner answered whose record command never ran today."""
         from wuwei import decision, drafts, sessions, state
         data = state.read_state(root)
         topics = {t for row in data.get('sessions', {}).values() for t in row.get('gate_asked', ())}
         queue = drafts.read(data)
         found = {t.split('=')[0] for t in topics if re.fullmatch(r'D-[1-9][0-9]*=[0-9a-f]{64}', t)
                  and t not in (sessions.card_topic(t.split('=')[0], 'Keep'),
                                sessions.card_topic(t.split('=')[0], 'Undo'))
                  and decision.answered(data, t.split('=')[0]) is None}
         found |= {t.split(':')[0] for t in topics if re.fullmatch(r'draft-[0-9a-f]{32}:(send|edit|text:.*)', t)
                   and queue.get(t.split(':')[0], {}).get('status') == 'pending'}
         return sorted(found)
     ```
     (Shape, not final text; keep it this small. `drafts.read` returns the validated
     queue; confirm its return value while building.)
   - In `_day` after the `trace decisions` block (line 628):
     ```python
     try:
         ids = _unrecorded(root)
         rows.append(_row('day', 'answered cards', 'warn' if ids else 'ok',
                          f'{", ".join(ids)} answered on a card, not recorded' if ids else 'none',
                          "the planner runs each card's record command (bin/wuwei decision show <id> "
                          '--widget prints it); under strict the owner runs it in a host terminal'))
     except (OSError, ValueError) as exc:
         rows.append(_row('day', 'answered cards', 'unmeasured', str(exc), 'wuwei state recover in a host terminal'))
     ```
6. `docs/specs/2026-09-24-wuwei-design.md` 9.2 row I8: Checked by names `bin/wuwei decision
   outcome D-1 once` with the two commands; Notes add `#661; below strict the planner's
   refusal names the card, never a host-terminal command`.
7. `tests/test_invariants.py`: `Rules.record` (line 241) adds `'bin/wuwei decision outcome
   D-1 once'` to its command tuple; `i8` (line 446) zips the names `('decide', 'decision
   outcome', 'config set')`. One more pair of `check_bash` calls per memoised case.
8. Docs: `docs/site/reference.md` host terminal table row for `decision outcome` gets the
   same note as `decide` (the planner records a decision it asked in the session, outside
   strict) and the doctor Day list (line 235) adds `answered cards not recorded`;
   `docs/site/concepts.md` line 212: "A decision it asked you in the session goes in with
   `wuwei decide` or `wuwei decision outcome`".

## Tests that change with the behaviour

- `tests/test_owner_edits.py`: below-strict planner refusals now equal `(1, CARD_FIRST)`
  (lines 202, 259, 266, 297, 310, 312); strict ones (195, 272, 345) are unchanged.
- `tests/test_doctor.py::test_day_rows`: the names list gains `answered cards` after
  `traces` (and #599's `session id`).
- Unchanged and must stay green: `tests/test_decision.py::test_agent_tool_cannot_invoke_owner_outcome`
  (no session id), `tests/test_launcher_relevance.py`, `tests/test_card_confirms.py:429`
  and `tests/test_mcp.py:1684` (strict).

## What must not change

- `_gate_edits`, `sessions.gate_topics`, `record_gate`: who counts as the planner and what
  counts as asked.
- Strict: every owner record command refused from a session with the host-terminal line.
- Seats and non-planner sessions: refused with the table reason.
- `owner_outcome`, `owner_confirm`, `card_hash`, `no_card` (#599's), `mcp.decide`.
- The `_OWNER_ACTIONS` table texts and keys.
