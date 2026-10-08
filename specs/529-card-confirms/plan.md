# Implementation Plan: An answer on an Ask card is the confirmation of a config write

**Branch**: `529-card-confirms` | **Spec**: `spec.md`

## Summary

One recording rule at the shared spot: `record_gate` (the PostToolUse hook that already
records which cards the planner asked) also records the owner's answer per card, hashed, as
#493 does for drafts. Two record commands read it through one helper,
`sessions.card_answered`: `calibrate --answer` (interview cards, four new rows) and
`config set --from-card D-n` (decision cards). Both write through the existing owner edit
frame `setup._edit` with an always-yes confirm, the pattern `outbound.apply` already uses.
`config set` in a session without a card stops with exit 1 naming the card command instead
of reading an empty answer. Strict changes nothing: `gate_topics` returns no topics there.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. All tests in process on neutral fixtures in
`tmp_path` (workspace helpers from `tests/test_config_writer.py`, `tests/test_drafts.py`
and `tests/test_owner_actions.py`; PostToolUse payloads built as in the #493 draft-card
tests). Commands are run as `run(args)` with `argparse.Namespace`, never a subprocess.

## Constitution Check

- Test first: every behaviour in `tasks.md` has its failing test before its code. Pass.
- Exits: 0 written, 1 a finding (no card, wrong answer, strict in a session), 2 unreadable
  input (unchanged `_edit` paths). Pass.
- No forgeable trust: the only trusted input is `gate_asked`, written by `record_gate`
  inside `state._write_state` (reserved state; `gate.asked` event); `config.set` is a
  CLI-only event kind (the event command accepts only `note`). Pass.
- Scope: everything acts inside a workspace (`find_workspace`); the hook path keeps its
  scope check. Pass.
- No new refusal under observe or guarded (spec FR-012). Pass.
- Ponytail: no new module, no new config key; one helper pair in `sessions.py`, one
  assignment parser in `setup.py`. Pass.

## Changes

### `cli/wuwei/sessions.py` (shared helper, hook-safe imports only)

```python
def card_topic(card, answer):
    """#529: the gate topic of an owner's card answer; the answer hashed as #493 does."""
    text = answer.strip().removesuffix(' (Recommended)').strip()
    return f'{card}={hashlib.sha256(text.encode()).hexdigest()}'


def card_answered(root, card, answer):
    """The calling planner session recorded this card answer (never under strict)."""
    return card_topic(card, answer) in gate_topics(root, current())[0]
```

### `cli/wuwei/guards/decision.py` (`record_gate`, `_draft_answer`)

- Split the label read out of `_draft_answer` into `_answer(payload, text)`: the answer
  string for that question from `tool_response.answers`, stripped, or `None`.
  `_draft_answer` calls it (behaviour unchanged).
- In the loop, after the existing branches: when the question is a Morning gate question
  (`gate_question(question, root)`) or the `D-n` branch matched, and `header` is a string
  and `_answer(...)` is not `None`, add `sessions.card_topic(header, answer)`. Goals,
  Voice, D-n and draft topics stay as they are.

### `cli/wuwei/interview.py`

- Four workspace rows appended to `QUESTIONS` (first choice = shipped default; no first
  person; header at most 12 characters):
  - `cap`, header `CAP`, "How many items may build at once by default? (CAP)": `1`, `2`,
    `3` -> `{'cap': n}`; free: `_count('cap')`, "a whole number of 1 or more".
  - `seats`, header `Seats`, "How many agents may run on this machine at once? (host.seats)":
    `4`, `6`, `8` -> `{'host.seats': n}`; free: `_count('host.seats')`.
  - `tier`, header `Outbound`, "What happens to a message no rule narrows? (outbound.default_tier)":
    `Send`, `Ask`, `Block` -> `{'outbound.default_tier': 'send'|'ask'|'block'}`.
  - `learn`, header `Connectors`, "How does WUWEI learn a connector it does not know? (outbound.learn)":
    `Card`, `Auto`, `Off` -> `{'outbound.learn': 'card'|'auto'|'off'}`.
- `_count(key)`: returns a parser `text -> {key: int(text)}` that raises `ValueError` for
  anything but a whole number of 1 or more (stdlib `str.isdecimal`).
- Repository row `gates`: header `Reviewers` -> `Review depth` (headers become unique; the
  workspace row `reviewers` keeps `Reviewers`).
- `settings()` and `describe()`: an effect is a config key when it is not a charter role
  or `voice` (`name not in (*ROLES, 'voice')`) instead of `'.' in name`, so the top-level
  `cap` key is a setting. `_path` already maps `cap` to `((), 'cap')`.
- `widgets(root, repos, ids=())`: with ids, the named rows (`_selected(ids, repos)`) are
  printed even when answered; without ids, unchanged.
- `card_for(key)`: the id of the first workspace row whose choices set `key`, else `None`
  (used by the FR-008 message).

### `cli/wuwei/commands/calibrate.py`

- `--questions` becomes `nargs='*', metavar='QUESTION'`; the three `args.questions`
  truth tests become `args.questions is not None`; `--questions` passes the ids to
  `interview.widgets(root, repos, args.questions)`.
- `_interview`, after `interview.record(...)` on the `--answer` path: for each picked id
  whose row is workspace scope and `sessions.card_answered(root, row['header'], answer)`,
  take `interview.settings({qid: answer}, config)`; when it is not empty, call
  `setup.card_write(root, 'calibrate', <settle change>, <dotted keys>, qid)`. Print the existing
  `describe` lines; print the existing `Next:` line only when an answer was not written
  from its card or has charter or voice effects. A failing `card_write` returns its exit.

### `cli/wuwei/commands/setup.py`

- `assignment(title)`: `(key, value)` for an option title `<key> = <TOML value>` whose key
  passes `_parts`, else `None` (`title.partition(' = ')`, `tomllib.loads(f'value = {v}')`).
- `card_write(root, label, change, keys, card)`: `_edit(label, 'change', lambda *a, **k:
  True, change, root)` where `change(root, raw)` returns the new text; on exit 0 append
  `config.set` `{'keys': keys, 'card': card}` with `state.append_event`. One function for
  both record commands (`calibrate` passes `lambda _, raw: _settle(raw, settings)` and the
  dotted keys of `settings`; `set_value` passes its existing `change` and `[args.key]`).
- `set_value(args, confirm=None)`:
  1. `card = getattr(args, 'from_card', None)`; `session = sessions.current()`.
  2. Strict (`workspace.posture(config)[0] == 'strict'`): if `session` and `confirm is
     None`, print `config set: under strict a card answer is not a confirmation; run
     bin/wuwei config set KEY VALUE in a host terminal` and return 1; otherwise ignore the
     card and run today's path.
  3. Outside strict, with `card`: read today's record (`decision.today_path`, `evaluate`);
     find the option whose `assignment(title)` equals `(args.key, parsed args.value)`;
     require `sessions.card_answered(root, card, title)`; any miss returns 1 with a
     message naming `bin/wuwei decision show <card> --widget`. Then `card_write(...)`
     with the existing `change`; on 0, unless `decision.answered(state, card)` already
     equals that option, call `commands.decision.owner_outcome(Namespace(id=card,
     option=option))` (its `owner_confirm` passes through the asked `D-n` topic) and
     return its code with its message on failure.
  4. Without `card`, `session` set and `confirm is None`: return 1 with the FR-008 message
     (`interview.card_for(key)` picks the interview form or the decision form). Never
     opens `/dev/tty`.
  5. Otherwise today's `_edit` path with the prompt.

### `cli/wuwei/commands/config.py` (`register`)

- `set` gains `--from-card D-n` (`dest='from_card'`, validated against
  `decision.DECISION_ID`; a bad id is exit 1 with the expected form).

### `cli/wuwei/guards/protect_state.py`

- `_GATE_EDITS` gains `('config', 'set')`, so under strict the planner's refusal ends with
  `Run it in a host terminal: <command>` (existing branch).
- In the `_GATE_EDITS` branch, next to the `mcp`, `decide`, `drafts` line: `config set`
  passes when the word after `--from-card` (or the `--from-card=` value) is a `D-n` in
  `edits[0]` and there is no `xargs`.
- The `('config', 'set')` reason names the card path: ask it on a card (`bin/wuwei
  calibrate --questions <id>`, or a decision whose options read `<key> = <value>`) and run
  the card's record command; under strict the owner runs `bin/wuwei config set <key>
  <value>` in a host terminal. `GUARD_CONFIG` names the same card path for guard keys.

### `cli/wuwei/commands/decision.py` (`show`)

- `CONFIG_RECORD = 'wuwei config set <key> <value> --from-card {id}'`; `show --widget`
  passes it to `record_widget` when any option title has an `assignment`.

### `cli/wuwei/commands/event.py`, `cli/wuwei/signal.py`

- Producer row `'config.set': 'wuwei config set --from-card or wuwei calibrate --answer'`;
  `config.set` added to `signal.py`'s `SILENT` kinds.

### Docs

- `docs/specs/2026-09-24-wuwei-design.md` 5.2 `Records`: one sentence, (owner, 2026-10-05,
  #529): outside strict the owner's answer on a card is the confirmation of the config
  write its record command makes (`calibrate --answer`, `config set --from-card D-n`); a
  `config set` in a session without a card exits 1 naming the card; strict keeps the host
  terminal.
- `skills/wuwei-plan/SKILL.md`: step 4 (first-day interview: the record writes the
  config, no `config promote` for those keys; `Change something` on CAP or seats: run
  `wuwei calibrate --questions cap seats`, ask, record, then update the lead JSON), the
  Owner questions paragraph (a config question outside the interview is a decision record,
  `Class: other`, `Decided-by: owner`, option titles `<key> = <value>`, routed with
  `decision route D-n`), Unknown connectors (`config set` on
  guard settings needs a card).
- `docs/site/concepts.md` (owner commands paragraph), `docs/site/security.md` (guard
  settings sentence), `docs/site/configuration.md` (first paragraph): one clause each.
- The generated guide (`wuwei guide`, `agent.md` if pinned) is regenerated, not edited.

## Builder changes to this plan

- Headers: `test_docs.py::test_interview_options_lead_with_plain_words` forbids glossary
  words (CAP, seat, gate) in headers and leads, so the rows use `At once` (cap), `Agents`
  (seats) and `Review depth` (the repository row `gates`). Seats labels read `4 agents`,
  `6 agents`, `8 agents`: a bare `6` would read as the sixth choice at the setup terminal.
- `config set --from-card` also exits 1 before writing when the owner already answered
  `D-n` with another option (the outcome step would refuse it after the write).
- The T028 invariants were not added: `tests/test_invariants.py` is not on this base.

## Reuse

- `setup._edit` and `config.offer` (owner edit frame and diff print), with the always-yes
  confirm as in `commands/outbound.py:apply`.
- `sessions.gate_topics` (planner session, strict returns nothing), `state._write_state`
  in `record_gate`, `decision.answered`, `commands/decision.owner_outcome`,
  `decision.today_path`, `decision.evaluate`, `decision.options`, `interview.settings`,
  `interview._selected`, `setup._parts`.

## Must not change

- The `Confirm? [y/N]` path in a host terminal, for every posture.
- Strict: no card answer is recorded or honoured; every record command is printed for a
  host terminal.
- Goals, Voice, D-n and draft gate topics and their consumers; `drafts approve` rules.
- `config promote`, `config add-repo`, `setup` flow (except asking four more rows).
- Seats never pass `config set` (payloads with `agent_id`).
- Hook latency: `record_gate` imports nothing new beyond `hashlib` via `sessions`.

## Tests touched by design (allowed edits only)

- `tests/test_interview.py::test_question_table_fits_widgets_and_every_choice_validates`:
  the id list gains `cap`, `seats`, `tier`, `learn`; the key assertion accepts a top-level
  schema key (`cap`).
- Any test pinning the `gates` header `Reviewers` or the old `config set` reason text:
  update the literal only.
- The guide snapshot, if pinned: regenerate.
