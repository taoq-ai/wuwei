# Implementation Plan: Mandate block in briefs, assume-and-record, time-boxed external waits, ask metrics, and a negotiation-loop nudge per work item

**Branch**: `302-negotiation-loop` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

## Summary

Seven small changes at the spots every caller already routes through, no new module:

1. `brief.launch_prompt` appends one generated mandate block (class levels from one table in
   `decision.py`, the promoted interview `risk` line, `deploy.deny`).
2. A SubagentStop guard reuses `guards.decision.check_question` on a seat's last message;
   Codex `result` and the headless shepherd call the same helper.
3. The verdict lint starts a finding at `Assumption:`; gate brief headers say to review them.
4. `decision route --external <item>` marks the item; the watch sweep applies
   `decisions.wait_hours`.
5. `steward.review` gains the loop detector (one function over the day's events and
   records), writing a producer-only `negotiation_loops` entry and one `negotiation.loop`
   event per item per day.
6. Signal tier, listener DM, `loops N` on the status line.
7. Two metrics in `metrics.collect`; docs, charters, planner skill, config template.

## Technical Context

Python 3.11 stdlib, pytest dev-only. Run `python -m pytest -q` from the repository root.
Every write goes through `state._write_state` or `state.append_event`; events are read with
`watch.records`. No subprocess in the core; the DM goes through `remote.TRANSPORT` exactly as
`listen.notify` does for PRs today.

## Constitution Check

- I stdlib: yes. II three-state exits: the stop guard returns 0, 1 or 2 (2 when a cited
  record cannot be read, from `check_question`); the sweep's new step counts an error as
  `unreadable` and never as clean. III one behaviour, one function: question detection
  lives in `guards.decision.unrecorded`; the class table in `decision.CLASSES`; the loop
  detector in `steward.negotiation`; record-to-item attribution in `decision.naming`, shared
  by the detector and the metric. IV test first: tasks.md orders a failing test before each
  change. V ponytail: no new module, no abstraction, one table; shortcuts carry `ponytail:`
  comments (question heuristic, hourly weekday count, mtime as record time). VII security:
  new state keys and events are producer-only; the DM passes the outward lint with a fixed
  fallback; no refusal is weakened.
- Scope (spec 9.1): the stop guard acts only inside a workspace (`workspace.scope` through
  `check_question`) and only for WUWEI agent types (`agent_launch.wuwei_role`); outside it
  returns 0.

## Changes by file

### `cli/wuwei/decision.py`

- `CLASSES = {'approach': (2, 3), 'retry': (2, 3), 'park': (2, 3), 'accept-residual': (2, 3),
  'defer': (0, 3), 'scope-cut': (0, 3), 're-plan': (0, 3), 'dependency-bump': (0, 3),
  'merge': (3, 3), 'message': (0, 1), 'other': (0, 1)}` (default, ceiling), in the 5.8.1
  table order. Comment: a new class is a design amendment, not config.
- `level(config, name)`: `0` when `config['decisions']['cruise']['enabled']` is false, else
  `min(CLASSES[name][0], config['decisions']['cruise']['levels'].get(name, 3))`.
  `# ponytail: memory/cruise.json (running level, #283) does not exist yet; the default stands in.`
- `naming(directory, items)`: `{record id: [item, ...]}` for `directory/'decisions'` files
  `D-*.md` and `C-*.md` (skip symlinks), matching each item id as a whole word
  (`(?<![\w-])id(?![\w-])`) only on lines that start with `Question:` or `Context:` of the
  record's `verdict.active_text`. Records that name nothing map to `[]`.
- `route_owner(identifier, fields, root, item=None)`: unchanged when `item` is None. With an
  item, the same `_write_state` call also sets `data['items'][item]['assumption'] =
  {'kind': 'external', 'decision': identifier, 'day': day_dir.name, 'since': now iso,
  'status': 'waiting'}` (refuse an unknown item with `StateError`), and the `decision.routed`
  payload gains `'item': item`. The "already routed is a no-op" early return applies only when
  no item is given or the item already carries this decision.
- `weekday_hours(start, end, zone)`: whole hours from `start` to `end` whose start falls on
  Monday to Friday in `zone` (`workspace.zone(config)`, None is the machine zone).
  `# ponytail: hourly steps; a wait spanning months walks a few thousand hours.`
- `waits(root)`: the time box, called by `watch.sweep`. For each item of today's state whose
  `assumption.status == 'waiting'`: read the record `.wuwei/days/<day>/decisions/<id>.md`
  (refuse a symlink) and that day's state (`state.read_state(directory=...)`); skip when
  `answered(that_state, id)` is not None or `weekday_hours(since, now, zone) <
  config['decisions']['wait_hours']`. Else `fields, _ = evaluate(text)`; confirm when
  `fields['Reversibility'] == 'two-way'` and `item['goal'] != 'unplanned'` and not
  `item['flags']['trust_surface']`: one `_write_state` setting `assumption.status =
  'confirmed'` with kind `decision.waited`, payload `{'item', 'id', 'outcome': 'confirmed',
  'recommendation': fields['Recommendation']}`. Otherwise park: status `'parked'`, and when
  the phase is not already `parked`, `escalated` or `merged`, `phase = 'parked'`, `status =
  'blocked'`, `decision = id`; same kind, `outcome: 'parked'`. Returns the number of items
  changed. Errors propagate; `watch.sweep` counts them.

### `cli/wuwei/workspace.py`

- `SCHEMA`: add `"decisions": {"wait_hours": (int, 24, 1), "cruise": {"enabled": (bool, True),
  "levels": {"*": (int, None, 0, 3)}}}`; extend `"steward"` with `"loop_window_hours": (int,
  4, 1)` and `"loop_threshold": (int, 9, 1)`.
- `load_config`, after the deploy check: for each `name, value` in
  `config['decisions']['cruise']['levels']`, raise `ConfigError` for a name not in
  `decision.CLASSES` (`decisions.cruise.levels.<name>: unknown class; use one of ...`) or a
  value above its ceiling (`... above its ceiling L<n>`). Import `decision` locally, as
  `registry` is today.

### `cli/wuwei/brief.py`

- `mandate(root)`: returns the block below; reads config with `workspace.load_config`, levels
  with `decision.level`, the interview line with `promotion.safe_path(root,
  '.wuwei/charters/lead.md', label='lead charter')` (absent file: no line) and the first
  `^- risk: (.+)$` line after `interview.BLOCK`, and `config['deploy']['deny']`.
- `launch_prompt`: `... + '\n\n' + mandate(root)`. The first line is unchanged, so
  `transcript_reference`, `agent_launch.check` and every `prompt + '\n\n' + feedback` caller
  keep working.
- `write`: in the `if gate:` header block, after the `Verdict file:` line, append
  `Assumptions: review the item's Assumptions: in its spec and PR body as findings of kind
  Assumption: (severity, file:line, failure scenario, blocks yes or no).`

Mandate text (lists joined with `, `; a list part is omitted when empty; `Decide and record:`
is `none.` when it has no part):

```
Mandate (design 5.2):
Decide alone: what the brief, your charter and the engineering standards already answer.
Decide and record: two-way open questions inside the item: take your recommendation and record it under Assumptions: in the spec or PR body (what was assumed, why, what would overturn it). Decision records of class <L2/L3 classes except approach>: write the record and run wuwei decision route D-n.
Go to the owner, as a decision record you cite by id: one-way doors (when unsure, it is one-way), messages to people, scope agreed with other people, deploys, trust-boundary findings, anything outside the item's goals, decision records of class <L0/L1 classes>. Trust surface: <risk line>. Commands the owner runs: <deploy.deny>. A confirmation from a person outside the loop is never a precondition: write the record, run wuwei decision route D-n --external <item> and continue reversible work.
Nothing else is a question.
```

The assumption sentence appears only while `approach` runs at L2 or L3; below that,
`approach` joins the owner class list.

### `adapters/runtime/codex.py`

- `dispatch`: append `' ' + brief.mandate(root)` to the prompt (reuse, no second text).
- `result`: after the retro check, `code, reason = unrecorded(text, root)` from
  `wuwei.guards.decision`; a nonzero code returns `registry.Result(code, output, reason)`
  before the retro result.

### `cli/wuwei/guards/decision.py`

- `QUESTION = re.compile(r'\?\s*$', re.M)`.
- `unrecorded(text, root)`: `(0, '')` when no line of `verdict.active_text(text)` matches
  `QUESTION`; else `check_question({'cwd': str(root), 'tool_name': 'SubagentStop',
  'tool_input': {'question': text}})`. `# ponytail: a line ending in '?' is a question;
  tighten if retro gaps show false positives.`
- `check_stop(payload)`: return `(0, '')` when `payload.get('stop_hook_active') is True`, the
  agent type is not `agent_launch.wuwei_role`, or `workspace.guard_scope(payload)` is None.
  Else `code, message = unrecorded(required_text(payload, 'last_assistant_message',
  blank=True), root)`. On `code == 1`, try `agent_launch.stopping_seat(payload, root)` for
  the seat's item; when it resolves and `steward.SAFE_ID` matches the item and the
  sanitised agent id, call `steward.add_notes(root, [{'id':
  f'{item}-question-{agent}', 'item': item, 'text': f'{item}: a {role} seat asked the owner a
  question without a decision record; write it (wuwei decision template), route it and cite
  D-n, or record the assumption under Assumptions:'}])`; a failure to resolve the seat
  writes no note. Errors are exit 2 with `decision question:` prefix, as `check_question`.
- `GUARDS`: add `Guard('SubagentStop', None, check_stop)`.

### `cli/wuwei/guards/__init__.py`

- `MODULES['decision']`: add `'SubagentStop': None` (`tests/test_hooks.py` derives it).

### `cli/wuwei/shepherd.py`

- `headless`: after a turn with `result.exit != 2`, `code, reason =
  unrecorded(result.data['result'], root)`; nonzero returns `finish(code, f'asked without a
  decision record: {reason}', reason=reason, session=sid)`.

### `cli/wuwei/verdict.py`

- `finding_blocks`: `explicit = re.match(r'^\s*(?:Severity:\s*' + SEVERITY +
  r'|(?:[-*+]\s+)?Assumption:)', line, re.I)`. The per-block checks (severity, file:line,
  blocks, scenario) are unchanged, so an assumption finding needs all four.

### `cli/wuwei/steward.py`

- `add_notes(root, notes)`: the existing dedupe write from `review` (lines 29-36) moved
  verbatim; `review` calls it. Producer label for `steward_notes` becomes `wuwei steward run
  or wuwei hook SubagentStop`.
- `negotiation(root)`: the loop detector, called at the end of `review` (so on the sweep, at
  close and on every `dispatch next`). Returns the payloads it raised.
  - Inputs: `config['steward']`, today's `watch.records(day/'events.jsonl')` (absent file:
    no rows), `state.read_state(root)`, `decision.naming(day, items)` with each record's
    `st_mtime` as its time, `now = workspace.now()`, `start = now -
    timedelta(hours=loop_window_hours)`.
  - Per item in `data['items']` with `SAFE_ID`, not in `data.get('negotiation_loops', {})`:
    `records` (named records with time >= start), `verdicts` (`gate.received` with that
    item, ts >= start), `redispatches` (`brief written` with that item whose
    `(item, role)` already had a `brief written` earlier today, ts >= start; role `steward`
    never counts), `continuations` (`build.fix_opened` for the item, ts >= start),
    `fix_rounds` (`build.fix_opened` for the item today).
  - Trigger: `records + verdicts + redispatches + continuations > loop_threshold` or
    `fix_rounds >= 2`.
  - `last`: the two latest of the counted exchanges as `HH:MM <text>` with texts `<id>
    recorded`, `<role> review <verdict>`, `<role without sentinel-> restarted`, `fix
    requested`.
  - `past_goal`: `goals.parse(memory/goals.md)[item['goal']]['date'] < now.date().isoformat()`;
    any `OSError`, `ValueError` or `KeyError` is False.
  - `reason`: `f'{item} is going back and forth: {records} records, {verdicts} reviews,
    {redispatches} restarts and {continuations} fix requests in {hours} hours, {fix_rounds}
    fix rounds today; last: {last[0]}; {last[1]}'` (with one or zero exchanges, only those).
    No word in the outward default patterns (`seat`, `agent`, `steward`, `gate verdict`,
    `queue`, `wuwei`).
  - Write per item: `state._write_state(update, root, reserved=False,
    kind='negotiation.loop', payload=payload)`; `update` raises a module-level `_Raised`
    when the item is already in `negotiation_loops` (a concurrent review got there first),
    else sets `data.setdefault('negotiation_loops', {})[item] = payload`; the caller catches
    `_Raised` only.

### `cli/wuwei/dispatch.py`

- `next_step`: the steward-note refusal becomes `f'steward note {id} requires planner
  acknowledgement: {text}'`.

### `cli/wuwei/commands/decision.py`

- `route` parser: `--external ITEM`. `decide`: with `args.external`, validate the record,
  `brief.identifier(args.external)`, call `route_owner(args.id, fields, root,
  item=args.external)` and return `(0, 'owner')` regardless of `route(fields)`.

### `cli/wuwei/watch.py`

- `sweep`: after `digest`, `counts['external_waits'] = decision.waits(root)` inside
  `try/except ERRORS` that adds 1 to `unreadable` and prints `watch external waits
  unmeasured: <exc>`. Not added to `owed` (it acts; the nudge comes from its event).

### `cli/wuwei/signal.py`

- `classify`: `if kind == 'negotiation.loop': return ('page' if payload.get('past_goal') is
  True else 'nudge'), lane`. Add `negotiation.notified` to `SILENT`. `decision.waited` keeps
  the default nudge (Decisions lane by prefix).

### `cli/wuwei/listen.py`

- `notify`: also send each `negotiation.loop` row's `payload['reason']` once through
  `control_plane.notify(..., transport=remote.TRANSPORT)`, keyed by
  `negotiation.notified {'item'}` rows; on notify exit 1 send `LOOP_FALLBACK = 'Item {item}
  is going back and forth; details are on the host.'` through `remote.TRANSPORT.dm`; any
  other failure returns 2 as for PRs. Record `state.append_event('negotiation.notified',
  {'item': item}, root)` after a send.

### `cli/wuwei/commands/status.py`

- `scan`: count `kind == 'negotiation.loop'` (today's events, before the `SILENT` skip) into
  a `loops` counter; return it as a fifth value. Callers updated (`attention`, `snapshot`).
- `snapshot`: `result['loops']`; `line`: `parts.append(f'loops {n}')` when `n`, placed after
  `nudges`.

### `cli/wuwei/metrics.py`

- `collect`: `asks_per_item` and `unnecessary_asks`, both `UNMEASURED` when `data is None`.
  `asks_per_item`: `Counter` over `data.get('decision_routes', {})` ids of the items
  `decision.naming(directory, data['items'])` gives for each id, or `'day'` when none.
  `unnecessary_asks`: ids in `decision_routes` where `decision.answered(data, id) ==
  routes[id]['recommendation']`. The report and retro dump `collect` as is.

### `cli/wuwei/state.py`, `cli/wuwei/commands/event.py`

- `STATE_PRODUCERS['negotiation_loops'] = 'wuwei steward run or wuwei dispatch next'`;
  `steward_notes` label as above; `_producer_error` item map: `'assumption': 'wuwei decision
  route --external or wuwei sweep'`.
- `EVENT_PRODUCERS`: `'negotiation.loop': 'wuwei steward run or wuwei dispatch next'`,
  `'negotiation.notified': 'wuwei listen'`, `'decision.waited': 'wuwei sweep'`.

### Charters, skill, agents, template, docs

- `charters/_common.md`: Evidence and gates item 5 becomes the negotiation budget (one fix
  round plus one delta check per gate; residual non-blocking findings are review notes in
  the PR body; a trust-boundary security finding always blocks; exceeding the budget parks
  the item with a decision record for a design reconsideration, never another round).
  Decisions item 1 opens with assume and record (two-way open questions inside the item go
  under `Assumptions:`, not a record) and keeps the record shape; item 2 says the launch
  prompt's mandate says what the seat decides alone, records and sends to the owner, and a
  question to the owner cites a valid decision id in every runtime. Bump the frontmatter
  version (1.0.0 to 1.1.0). Keep the existing anchors `A trust-boundary security finding
  always blocks`, `decision record`, `Reversibility:`.
- `skills/wuwei-plan/SKILL.md`: one sentence in "Item dispatch and receive": never ask the
  owner what a seat's mandate lets it decide; a `negotiation.loop` nudge is a report, the
  negotiation budget stops rounds; a question note from SubagentStop is acknowledged after
  the record exists.
- `agents/*.md`: regenerate with `python3 -P -m wuwei agents build`.
- `templates/workspace/config.toml`: `[decisions]` with `wait_hours = 24` and a commented
  `# [decisions.cruise]` example (`enabled = true`, `levels = { approach = 2 }`) saying the
  levels feed the mandate and cruise answering is not built; under `[steward]`
  `loop_window_hours = 4` and `loop_threshold = 9`.
- `docs/site/configuration.md`: Sections row `[decisions]`, `[decisions.cruise]` replaces the
  "refuses it today" row and points to a new `## Decisions` heading with
  `decisions.wait_hours`, `decisions.cruise.enabled`, `decisions.cruise.levels`; the two
  steward keys in Host, build and memory. Every paragraph naming cruise says auto-answering
  is not built.
- `docs/site/concepts.md`: under "Decision classes and cruise levels", the mandate block,
  assume and record, external confirmation and the time box, negotiation loops (not built
  stays for cruise answering).
- `docs/site/daily.md`: section 5 says what the owner sees: `loops N`, the loop nudge or
  page and DM, external waits confirmed or parked after `decisions.wait_hours`.
- `docs/site/reference.md`: `decision route D-n --external <item>`, the steward ack id
  forms `<item>-fix-3` and `<item>-question-<agent>`, the `Assumption:` finding kind in
  "Gate verdict layout", the three new events.

## Tests touched beyond new ones

- `tests/test_charters.py` `RULES`: the `cycle budget` row's anchor becomes the new
  negotiation budget phrase in `_common.md`.
- `tests/test_signal_status.py::test_emitted_kinds_have_intended_tiers`: add
  `negotiation.loop: nudge`, `negotiation.notified: silent`, `decision.waited: nudge`.
- `tests/test_guard_mutation.py` `PROBES`: row for `('decision', 'SubagentStop', None,
  'check_stop')` with an observable exit 1.
- `tests/test_state_allowlist.py`: rows for `negotiation_loops`, `items.A.assumption` and the
  three event kinds.
- `tests/test_docs.py`: existing tests must stay green (sections, keys, cruise "not built").

## What must not change

- `agent_launch.check` and `transcript_reference` (first prompt line stays the reference).
- `decision.route`, `decision.lint`, `decision.evaluate` and the record field set (no
  `Class:` field: #283).
- `build.next_action`, `build.open_fix` budget rules, `dispatch.next_step` flow other than the
  refusal text. The loop signal never parks, re-plans or blocks.
- `status.scan` stays one pass over `events.jsonl`.
- `control_plane.notify` and `remote.dm` unchanged; the listener stays the only DM sender.
- No new module, no new dependency, no subprocess in `cli/`.

## Deferred

- #283: cruise auto-answering, `margin`, `max_per_day`, `undo_minutes`, `memory/cruise.json`,
  `Class:` on records, promotion and demotion (they can read `unnecessary_asks`).
- Cross-day owner answers to an external record (per-day ledger, existing).
