# Implementation Plan: Error budget per decision class

**Branch**: `558-error-budget` | **Spec**: `spec.md`

## Summary

One new module, `cli/wuwei/budget_classes.py`, reads the window (cruise answers and the
events against them) from the day event streams, computes each class's allowance, spent
count and burn rate, and, from the steward run, lowers a spent class or restores a refilled
one through the existing promote writer `promotion.cruise_level`, and writes one burn-rate
nudge a day. The four single demotion triggers in `cruise.py` and their two call sites are
deleted, not kept beside the budget. `cruise.propose` skips a spent class and a class with a
budget event since its last change. One read-only command prints the table; the status line
reads the hold from `memory/cruise.json`, which it already loads.

## Technical Context

Python 3.11+ stdlib only; pytest dev-only. Tests in process on neutral fixtures in
`tmp_path`, reusing `tests/test_cruise.py` helpers (`config`, `ledger`, `later`,
`raise_to`, `agree`, `propose`, `answer`, `status_line`) and the `ws`, `record`, `route`
helpers of `tests/test_decision_classes.py`. Time is moved with `WUWEI_NOW`. Budget events
are written straight into a day's `events.jsonl` with `state.append_event` under a given
`WUWEI_NOW` (the event writer stamps the shared clock), so one test needs no 20 real routes.

## Constitution Check

- III one behaviour, one function: window and event selection live only in
  `budget_classes.select` (shared with #559); the spend rule only in
  `budget_classes.measure`; level writes only through `promotion.cruise_level`. Pass.
- II exits: a damaged event stream or `cruise.json` raises `ValueError`; `wuwei steward`
  already turns it into exit 2 with the reason, and `wuwei cruise budget` does the same.
  Nothing reports clean when unmeasured. Pass.
- No forgeable trust: `cruise.burn` is reserved to `wuwei steward run` in
  `EVENT_PRODUCERS`; the hold lives in `memory/cruise.json`, already refused to seats by
  `protect_state` (`cli/wuwei/guards/protect_state.py:304`). The counted events are
  CLI-written kinds (`decision.decided`, `decision.reversed`, `cruise.carded`), already
  reserved. A seat cannot raise a level by forging anything; forging could at most lower
  one, which it cannot do either. Pass.
- #530: no new refusal anywhere. A spent class runs one level lower, so its records route
  to the owner as a card (L1) or a question (L0). Pass.
- #551: the burn nudge's next action is a command (`Run: wuwei cruise budget` through
  `nudges.ACTIONS`); a lowering needs no planner step. No skill or charter prose. Pass.
- Ponytail: no new state file, no new class, no per-event storage; the hold is one optional
  key in the existing `cruise.json`. Pass.

## Changes

### New: `cli/wuwei/budget_classes.py`

```python
"""#558 error budget per decision class (design 5.8.1): the window reader, shared with #559."""

def select(root, days, now=None):
    """(answers, events) of the last `days` days, oldest first.
    answers: [{'day', 'id', 'class', 'at', 'items', 'option'}] for each decision.decided whose
    payload rule starts with 'cruise ' (at = the event ts).
    events: [{'class', 'at', 'kind', 'label', 'day', 'id'}] where day and id name the answer:
      undo      decision.reversed with undo true on a (day, id) answer
      reversal  decision.reversed (no undo) on the same (day, id) as a cruise answer
      sample    cruise.carded kind sample, then an owner decision.decided on that card with
                another option; the answer comes from the card's source path
      escaped   an answer whose items meet metrics._escaped(root)[1]; at = the answer's at
    Day directories from watch.days(root) dated on or after the window start; rows from
    watch.records (a damaged stream raises ValueError). Events and answers before the
    window start are dropped."""

def measure(answered, spent, recent, cruise):
    """(allowance, burn, state) for one class; pure.
    allowance = cruise['budget_share'] * answered
    burn = recent * cruise['budget_window_days'] / (2 * allowance), inf when allowance is 0
    and recent > 0, 0.0 when both are 0
    state = 'spent' if spent > allowance and spent >= 2
            else 'warn' if burn >= cruise['burn_warn'] else 'ok'"""

def table(root, config, now=None):
    """One row per class in decision.CLASSES but merge: {'class', 'level' (decision.level),
    'answered', 'spent', 'allowance', 'burn', 'state', 'events' (labels), 'held' (class in
    running['budget'])}. recent = events with at in the last 48 hours."""

def evaluate(root):
    """The steward step. For each row of table(root, load_config(root)):
    - spent, not held, level > 0: promotion.cruise_level(root, name, level - 1,
      'budget spent: <class>, <n> events over <allowance:g> allowed in <days> days: <labels>',
      '.wuwei/days/<day>/decisions/<id>.md' of the latest event,
      hold=<running level before: running['levels'].get(name, CLASSES[name][0])>)
    - held, not spent: promotion.cruise_level(root, name, running['budget'][name],
      'budget refilled: <class> back to L<n>, <n> events over <allowance:g> allowed', CRUISE)
    - warn and no cruise.burn of this class in today's events: state.append_event('cruise.burn',
      {'class', 'events': labels, 'reason': '<class> burns its error budget at <burn:.1f>x:
      <labels>'}, root)  (no float in the payload: the event writer refuses inf)
    Returns the rows."""
```

Labels: `undo <day> D-3`, `reversal <day> D-3`, `sample <day> D-9 of <day> D-3`,
`escaped <item> <day> D-3`. They name the events the ledger line and the nudge must name.

### `cli/wuwei/promotion.py`, `cruise_level` (line 45)

Add a keyword `hold=None`. After setting the level: `data.setdefault('budget', {})`; with
`hold` an int store `budget[name] = hold`, otherwise pop `name`; drop the `budget` key when
empty, so a workspace with no held class keeps today's `{levels, changed}` shape (the
existing `test_ten_agreements_propose_a_raise` asserts it). Every other write (an owner
raise) clears a hold.

### `cli/wuwei/cruise.py`

- `running` (line 20): accept an optional `budget` dict of known classes to int levels 0..3
  in the shape check; anything else is `DAMAGED` like today.
- Delete `lower` (84), `streak` (92), `escaped` (233).
- `answered` (126): drop the `previous` parameter and the sample and reversal branches; keep
  the raise branch. Docstring: reversals and samples count in the error budget (#558).
- `propose` (172): after the autonomous and enabled check, `spent = {row['class'] for row in
  budget_classes.table(root, config) if row['state'] == 'spent'}` and `_, events =
  budget_classes.select(root, cruise['promote_days'])`; skip a class in `spent` or with any
  event whose `at` is after `run['changed'].get(name, '')`. Raise card text (lines 201 and
  203): replace "an undo or a reversal lowers it again" and "An undo, a reversal or three
  thin-margin escalations lower it again" with the budget wording ("Reversals and escaped
  defects spend its error budget; a spent budget lowers it one level.").
- `label` (105): append ` · budget <sorted held classes joined by ', '> spent` when
  `running.get('budget')`, to both the on and off forms.
- Keep `thin`, `rule`, `level`, `window`, `agreements`, `_days`, `_card`, `gate_widgets`,
  `evidence` unchanged.

### `cli/wuwei/commands/decision.py`

- `decide` (lines 70-76): keep `thin` and `route_owner(..., thin=thin)`; delete the
  `if thin: cruise.streak(...)` lines.
- `owner_outcome` (line 235): `cruise.answered(root, args.id, args.option)`.
- `undo` (line 295): delete the `cruise.lower(...)` line. Nothing else in undo changes.

### `cli/wuwei/steward.py`, `review` (lines 23-25)

Replace `cruise.escaped(root)` with `budget_classes.evaluate(root)` (local import, same
place, same comment style: `# #558: the error budget lowers, restores and warns`). `review`
is reached from `steward run` and from every `dispatch next` (`cli/wuwei/dispatch.py:158`),
as `cruise.escaped` was, so a refilled window is restored at the next planner step. The
extra cost is one read of the window's event streams per call (a CLI command, never a hook);
the failure surface is unchanged, because `metrics._escaped` already reads every day's
events and raises on a damaged stream.

### New: `cli/wuwei/commands/cruise.py`

`wuwei cruise budget`: subparser `cruise` with required action `budget` (#559 adds
`calibration` beside it). Prints a header and one aligned row per table row:
`class level answered spent allowance burn state` (level as `L<n>`, allowance `:g`, burn
`:.1f` or `inf`). Exit 1 when any row is not `ok`, else 0; `(OSError, UnicodeError,
ValueError, KeyError, TypeError)` print `wuwei cruise budget: <reason>` to stderr and exit 2.

### Registration and reservation

- `cli/wuwei/commands/__init__.py`: add `'cruise budget'` to `READ_ONLY`.
- `cli/wuwei/__main__.py` `GROUPS`: add `cruise` to the Owner group after `promote`.
- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: `'cruise.burn': 'wuwei steward run'`.
- `cli/wuwei/commands/nudges.py` `ACTIONS`: `'cruise.burn': ('{reason}', 'wuwei cruise budget')`.
- `cli/wuwei/signal.py`: nothing; an unknown kind is already a nudge.

### Config: `cli/wuwei/workspace.py`

- `SCHEMA['decisions']['cruise']` (line 142): `"budget_share": (float, 0.1)`,
  `"budget_window_days": (int, 14, 1)`, `"burn_warn": (float, 2.0)`.
- Check next to the margin check (line 688): `if not 0 < share <= 0.5: raise
  ConfigError('decisions.cruise.budget_share: expected a number above 0 and at most 0.5;
  the owner fixes it with bin/wuwei config set decisions.cruise.budget_share <value> in a
  host terminal')`.
- `templates/workspace/config.toml` (lines 273-280): three commented lines under
  `# [decisions.cruise]`.

### Design spec and invariants

- `docs/specs/2026-09-24-wuwei-design.md` 5.8.1: the config sentence names the three keys;
  "Promotion and demotion" replaces "The CLI lowers a class one level at once ... records
  why." with an "Error budget (owner, 2026-10-08, #558)" paragraph (the spec's FR-002 and
  FR-003 in prose), adds "and the budget unspent" to the promotion condition, keeps the
  weekly sample (its different answers count as reversals); "Kill switch" names the status
  line budget part. The amendment says plainly that the restore is the one level raise
  without a morning-gate card, and only back to the level the budget took away (the hold),
  never above it or the ceiling.
- 9.2: row `I11` (next free id on the base): "A class runs lower only when its error budget
  is spent (more events than the allowance and at least two), never on a single event and
  never through a refusal" | checked by `budget_classes.measure` on 3 of 20, 2 of 20 in 48
  hours, none, 1 of 5, and no single-trigger lowering left in `cruise` | #558; the lowered
  class routes to a card and is restored when the window refills.
- `tests/test_invariants.py`: `i11(case, rules)` returning the memoized result of a
  `budget_rule()` helper (pure, posture independent, so it adds no measurable time to the
  walk), added to `INVARIANTS`.

### Docs

- `docs/site/concepts.md` (line 387): the levels sentence says levels go down when the
  error budget is spent and come back when it refills; one short "Error budget" paragraph.
- `docs/site/daily.md` (lines 395-406): undo and reversal no longer lower the class at once;
  the ledger paragraph describes the budget, the burn nudge and `wuwei cruise budget`; the
  status line paragraph shows `cruise L2 · budget defer spent`.
- `docs/site/configuration.md`: three key rows after `promote_days`; the paragraph at line
  191 lists the budget instead of the single triggers.
- `docs/site/reference.md`: Commands row `bin/wuwei cruise`.
- `README.md` line 38: "a reversal lowers the class" becomes "reversals spend the class's
  error budget".

## Reuse

`promotion.cruise_level` (the one level writer and its ledger line), `decision.level` and
`decision.running`, `watch.days` and `watch.records`, `metrics._escaped`,
`state.append_event`, `workspace.now` and `load_config`, the nudge pipeline (an event that
is not `SILENT` is a nudge with its payload `reason`), the `calibration.drift` dedupe
pattern for one nudge a day.

## Must not change

- The cruise answer conditions (`cruise.rule`), the undo window and the undo flow itself
  (the record still goes back to the owner), `agreements`, the weekly sample cards and the
  raise card flow.
- The `decision.decided` and `decision.reversed` payloads (the reader joins by day and id).
- The `thin` flag on route rows and `cruise.thin`.
- The status line cost: no event read on the hook path.
- `merge` class behaviour (the merge policy decides; it is not in the table).

## Test files

- New `tests/test_budget_classes.py`: select, measure, table, evaluate, the command, the
  steward wiring, the promotion gate and the status line part.
- `tests/test_cruise.py`: rewrite the single-trigger tests (thin streak, undo, reversal,
  sample, escaped, steward wiring) to assert the level is unchanged.
- `tests/test_signal_status.py`: `'cruise.burn': 'nudge'` in the expected map.
- `tests/test_docs.py` `test_cruise_mode_ships`: the three new keys in configuration.md.
- `tests/test_invariants.py`: `i11`.
