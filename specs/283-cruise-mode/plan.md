# Implementation Plan: Cruise mode

**Branch**: `283-cruise-mode` | **Spec**: `spec.md`

## Summary

One running-level store (`memory/cruise.json`) with one writer in the promote module, one
level function (`decision.level`) that reads it, and one decision point inside the existing
#530 `mandate()` that turns a taken record into a cruise answer when the 5.8.1 conditions
hold. Undo, demotion and promotion all land through the same writer. The status line, the
nudges, the digest and the listener read the outcome row the CLI already writes. Cruise
logic that is not routing lives in one new module, `cli/wuwei/cruise.py`.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. Tests in process on neutral fixtures in
`tmp_path`, reusing `tests/test_decision.py` (`VALID`, `save`, `events`, `SUPERVISED`) and
`tests/test_decision_classes.py` (`record`, `ws`, `route`, `LEAD`). New tests go in
`tests/test_cruise.py`. Time comes from `WUWEI_NOW`.

## Constitution Check

- III one behaviour one function: level in `decision.level`, the cruise rule in
  `cruise.rule`, the level writer in `promotion.cruise_level`, the undo in
  `commands/decision.py:undo`. Pass.
- II exits: undo 0/1/2; a damaged `cruise.json` is exit 2 with the reason. Pass.
- No forgeable trust: levels are read from `cruise.json` (protect-state guard, written only
  by `promotion.cruise_level`); agreements and reversals from `decision_outcomes`,
  `decision_routes` and `cruise_cards`, all producer-only state; the card answers come
  through `wuwei decide` (owner confirmation). A seat-written `Decided-by: cruise ...` line
  gains nothing: the CLI derives the rule at route time. Pass.
- No new refusal under observe or guarded (FR-017). Pass.
- Ponytail: no new adapter, no new command group; one new module, one new subcommand
  (`decision undo`), one new state key, one new event kind. Pass.

## Changes

### `cli/wuwei/workspace.py`

- `SCHEMA['decisions']['cruise']`: add `"margin": (float, 0.2)`, `"max_per_day": (int, 20,
  0)`, `"undo_minutes": (int, 60, 1)`, `"promote_agreements": (int, 10, 1)`,
  `"promote_days": (int, 14, 1)`.
- In the post-load checks next to the levels loop (`workspace.py:685`): refuse
  `decisions.cruise.margin` unless `0 < margin <= 1` with the same "the owner fixes it with
  bin/wuwei config set" tail.

### `cli/wuwei/decision.py`

- Keep `MARGIN = 0.2` for `cisr` (design 5.8 pins 0.2 for ambiguity); update its comment
  (the cruise margin is `decisions.cruise.margin`).
- `running(root)`: read `.wuwei/memory/cruise.json` through `promotion.safe_path`; missing
  file is `{'levels': {}, 'changed': {}}`; a symlink, invalid JSON, a non-dict, an unknown
  class or a non-int level raises `ValueError` with `DAMAGED`.
- `level(config, name, running=None)`: `0` if not `cruise['enabled']` or
  `config['autonomy']['mode'] == 'supervised'`, else `min((running or {}).get('levels',
  {}).get(name, CLASSES[name][0]), cruise['levels'].get(name, CLASSES[name][1]),
  CLASSES[name][1])`. Remove the ponytail comment at line 44.
- `evaluate`: `Decided-by` accepts `seat|owner|mandate` or `re.fullmatch(r'cruise
  ([a-z-]+)@L([23])', value)` with the class in `CLASSES`; keep the existing message.
- `route_owner(identifier, fields, root, item=None, thin=False)`: the route row and the
  `decision.routed` payload gain `class` (`fields.get('Class')`), `thin` and `at`
  (`workspace.now().isoformat()`).
- `seat_outcome`: the row gains `class`.
- `record_widget(..., hidden=False)`: when hidden, options in record order, no
  `(Recommended)` mark, the question without the reasoning (sample cards).

### `cli/wuwei/cruise.py` (new)

- `BLAST = r'(?i)\s*(?:own branch|own pr|workspace)\b'`.
- `rule(root, ident, fields, scores, config, data)`: the FR-004 conditions; returns
  `{'rule': f'cruise {cls}@L{n}', 'class': cls, 'level': n, 'at': now, 'items': items}`
  plus `undo_until` at L2, or `None`. Items from `decision.naming(workspace.day_dir(root),
  data['items']).get(ident, [])`; the budget counts today's outcome rows with `rule`.
- `thin(fields, scores, config, running)`: class set, `decision.level(...) >= 2` and
  `decision.margin(fields, scores) < config['decisions']['cruise']['margin']`.
- `lower(root, name, reason, evidence)`: `promotion.cruise_level(root, name,
  max(0, level - 1), reason, evidence)` where `level` is the class's current effective
  level; no-op at 0.
- `streak(root, name)`: today's route and outcome rows of `name` with `at` after
  `running['changed'][name]`, ordered by `at`; when the last three are routes with `thin`,
  `lower(..., 'three thin-margin escalations', <route record path>)`. `ponytail:` one day.
- `agreements(root, name, config, running)`: over `watch.days(root)` within `promote_days`,
  outcome rows of `name` dated after `changed[name]`: owner rows whose `option ==
  recommendation`, and rows with `rule` whose `undo_until` is absent or past.
- `propose(root, config)`: under autonomous with cruise on, for each class but `merge`
  whose level is below `min(ceiling, configured level)`, with `agreements >=
  promote_agreements` and no raise card for it in the window, write the raise card; once a
  week (no sample card in the last seven days), one sample card per class with a cruise
  answer in those days (the latest). Cards are written with `grants._record` (add a
  `revisit` parameter, default the grants text) or a copy of the source record through
  `decision.decided_record(text, 'pending', 'owner')`, then `decision.write`,
  `decision.route_owner`, and one `_write_state` that sets `cruise_cards[D-n]` (event
  `cruise.carded`, producer `wuwei plan propose`).
- `gate_widgets(root, config)`: unanswered `cruise_cards` (no owner outcome) as
  `decision.record_widget`, sample cards with `hidden=True`.
- `answered(root, ident, option, data)`: called by `owner_outcome` before its state write;
  raise card with option `raise` lands `promotion.cruise_level(root, cls, level, 'raise
  approved D-n', evidence)`; sample card with an option other than the card's lowers with
  `weekly sample D-n`; a previous outcome with `rule` and a different option lowers with
  `reversal D-n`.
- `escaped(root)`: `metrics._escaped(root)` gives the escaped items; for each class, once
  per call, lower when an outcome row with `rule` in the window, after `changed[cls]`, names
  an escaped item (reason `escaped defect <item> D-n`).
- `label(config, running)`: `top = max(level(config with enabled forced on, name, running)
  for name in CLASSES if name != 'merge')`; `f'cruise L{top}'` when on, `f'cruise off |
  L{top}'` when off.

### `cli/wuwei/promotion.py`

- `cruise_level(root, name, level, reason, evidence)`: validate `name in CLASSES` and `0 <=
  level <= ceiling`; read `decision.running(root)`; set `levels[name]` and
  `changed[name] = now`; `workspace.atomic_write` the JSON; `state.append_jsonl(ledger,
  {date, run_id: uuid4().hex, target: '.wuwei/memory/cruise.json', action: 'raise' if up
  else 'lower', status: 'landed', reason, evidence})`. `ponytail:` not committed to workspace
  history here; the next `promote` commit carries the ledger.
- `_target`: a proposal naming `.wuwei/memory/cruise.json` is rejected with "cruise levels
  move only through the owner's card, undo or a demotion; nothing to promote".

### `cli/wuwei/commands/decision.py`

- `mandate()`: after the existing checks, `found = cruise.rule(root, ident, fields, scores,
  config, data)`; `record = {**seat_outcome(fields, scores, by='mandate'), **(found or
  {})}`; the event payload is `{'id': ident, **record}` with `decided_by` set to
  `found['rule']` when found; the record text uses `decided_record(..., found['rule'] if
  found else 'mandate')`. Still returns `'mandate'`.
- `decide()`: when routing to the owner, pass `thin=cruise.thin(...)` to `route_owner`,
  then `cruise.streak(root, cls)` for a thin route.
- `owner_outcome`: the owner row gains `class` and `recommendation`; call
  `cruise.answered(...)` before the state write (as grants and outbound learn do); the
  `decision.reversed` payload gains `class`.
- `undo(args, *, root=None, where=None)` and `register`: `decision undo <id> [--answer
  LABEL]`. Read state; no `undo_until` is exit 1 (FR-006 text); past is exit 1; `Keep` is
  exit 0 `kept`; confirm with `where or owner_confirm(root, sessions.card_topic(id, 'Undo'), digest,
  prompt)` (#529: the gate topic of the owner's `Undo` answer on that card, so a `Keep`
  answer cannot confirm an undo; the host terminal y/N otherwise); one
  `_write_state` that pops the outcome and sets the route row in the `route_owner` shape
  (`reversibility`, `recommendation`, `cisr`, `class`, `thin: False`, `at`) plus `undone:
  True`, kind `decision.reversed`; write the record; `cruise.lower(root, cls,
  f'undo {id}', evidence)`; print `owner: ask with wuwei decision show <id> --widget`.
- `show --widget`: for an outcome with an open `undo_until`, print the Keep/Undo widget
  (`decision.widget`, header `D-n`, question `D-n: Taken as <title> by <rule>. Undo it before
  <HH:MM>?`, options `Keep` with `(Recommended)` and `Undo`) with record `wuwei decision
  undo {id} --answer "<label>"`. The question cites `D-n`, whose record lints clean, so the
  question guard allows it and the PostToolUse hook records the gate topic that
  `owner_confirm` reads. Any other mandate outcome still prints `[]`.

### `cli/wuwei/closing.py`

- Line 194: compare `fields['Decided-by']` with `record.get('rule', record['decided_by'])`
  so a cruise `park` disposition is collected.

### `cli/wuwei/commands/status.py` and `cli/wuwei/commands/nudges.py`

- `scan`: after the routes loop, one row per outcome with `undo_until` after now: `{'tier':
  'nudge', 'source': 'decision.cruise', 'lane': 'Decisions', 'reason': f'{id} taken as
  {option} by {rule}, undo until {HH:MM}'}`; sort key `(row['source'] != 'decision.cruise',
  row['source'] != 'pr.changed')`.
- `snapshot`: `result['cruise'] = cruise.label(config, decision.running(root))` when config
  exists; `line`: append it just before the `meeting` part, so the existing
  `pages | nudges | watch` substrings in tests stay contiguous.
- `nudges.ACTIONS['decision.cruise'] = ('{reason}', 'wuwei decision show {id} --widget')`.

### `cli/wuwei/watch.py` (`digest`)

- Sort pending by `(not value.get('rule'), ident)`; line `- {id}: {option}` plus ` ({rule})`
  when present.

### `cli/wuwei/listen.py`, `cli/wuwei/remote.py`, `cli/wuwei/signal.py`

- `listen.notify`: for `decision.decided` events with `undo_until` and no `decision.notified`
  for that id, `control_plane.notify(text)` and append `decision.notified {'id'}`.
- `remote.parse`: `undo d-n` returns `('undo', 'D-N')`; `handle`: verb `undo` runs
  `decision_command.undo(SimpleNamespace(id=..., answer='Undo'), root=root, where='in the
  owner DM')` and DMs the result line; add `undo D-n` to the DM vocabulary text.
- `signal.SILENT` gains `decision.notified` and `cruise.carded`.

### `cli/wuwei/state.py`, `cli/wuwei/commands/event.py`

- `STATE_PRODUCERS['cruise_cards'] = 'wuwei plan propose'`; `EVENT_PRODUCERS`
  `decision.notified: 'wuwei listen'`, `cruise.carded: 'wuwei plan propose'`.

### `cli/wuwei/plan.py`, `cli/wuwei/commands/plan.py`

- `plan.propose`: after `grants.plan(...)`, `cruise.propose(root, config)`.
- `plan gate`: `[gate, *grants.gate_widgets(...), *cruise.gate_widgets(...)]`.

### `cli/wuwei/steward.py`, `cli/wuwei/metrics.py`

- `metrics._escaped(root)`: split from `_escaped_by_tier` (returns `merged, escaped`);
  `_escaped_by_tier` calls it.
- `steward.review`: call `cruise.escaped(root)` after `negotiation(root)`.

### `cli/wuwei/brief.py`, `cli/wuwei/profiles.py`, `cli/wuwei/guards/protect_state.py`

- `brief.mandate`: `decision.level(config, name, decision.running(root))`.
- `profiles.DENIED`: `('decisions.cruise.margin', lambda new, old: new < old)`,
  `('decisions.cruise.max_per_day', lambda new, old: new > old)`.
- `_protected_name`: `tail == ('memory', 'cruise.json')` is protected.

### Docs and template

- `docs/site/daily.md` section 5: cruise answers, the nudge and its card, `decision undo`
  from the card, the terminal or the DM, `cruise L<n>` / `cruise off | L<n>` in the status
  line. `docs/site/reference.md`: `decision undo` row and paragraph; the `why` note no longer
  says not built. `configuration.md`: the five keys; drop "not built". `concepts.md`: the
  cruise paragraph describes what ships. README "What ships today" names cruise mode.
  `templates/workspace/config.toml`: the cruise block comment lists the keys and defaults.
- `tests/test_docs.py`: `test_cruise_mode_is_designed_not_built` becomes a test that the
  pages name `decision undo`, `cruise off` and the five keys.

## What must not change

- `decision route` output words (`mandate`, `seat`, `owner`) and the #530 routing outcome of
  every record: a record the mandate takes stays taken, one it sends to the owner stays
  with the owner.
- `cisr` and its 0.2 threshold; the supervised legacy route.
- The `decided_by` value in state (`mandate`) and every reader of it (close, report, next,
  digest).
- The merge policy and the `merge` class.
- `wuwei promote` for charters, notes and voice.

## Existing tests that change

- `tests/test_workspace.py:1132`: `decisions.cruise.margin` is a known key now; replace the
  row with an out-of-range margin.
- `tests/test_docs.py:798`: the "not built" test (see Docs).
- Any test that asserts the full status line text gains the cruise part only where its
  workspace has a config.
