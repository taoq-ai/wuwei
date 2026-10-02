# Implementation Plan: wuwei why

**Branch**: `312-why` | **Date**: 2026-10-02 | **Spec**: [spec.md](spec.md)

## Summary

One new read-only command module, `cli/wuwei/commands/why.py`, that walks records the
producers already write and prints one line per step. Two producers gain fields they
already hold in hand and drop today: the hook's `hook.refusal` gets the guard modules and
the redacted target (both computed a few lines earlier for shadow mode), and the owner
outcome's `decision.decided` / `decision.reversed` gets `decided_by: owner`. The board adds
one `./why.json` file. No new event kind, no new state key, no new config key, no new
shared helper beyond one function extracted inside `hook.py`.

## Technical Context

Python 3.11+ stdlib only; pytest for tests. Reads only; never writes.

## Constitution Check

- I stdlib: yes.
- II fail closed: a corrupt `events.jsonl` (`watch.records` raises), an unreadable state
  (`state.read_state` raises) or an unreadable verdict file in a decision view exits 2
  through `__main__`'s handler; a missing target is exit 1; a missing step prints
  `not recorded`, never a guess.
- III one behaviour, one function: event reading stays in `watch.records` / `watch.days`;
  decision parsing in `decision.evaluate`, `decision._scored`, `decision.present` and
  `decision.naming`; verdict findings in `verdict.finding_blocks`; producer names in
  `commands/event.EVENT_PRODUCERS`; target redaction in one `hook.redacted_target`.
- IV test first: tasks.md orders every test before its code.
- V ponytail: no event ids added to the writer (the line number is the id), no new
  verbosity surface, no cruise model (fields print `not recorded` until cruise lands), no
  trace reading, one module.
- VII security: `target` is redacted exactly as shadow events are; the command writes
  nothing, so it needs no guard.

## Design

### 1. Hook: record guard and target on a refusal (`cli/wuwei/commands/hook.py`)

- Extract the redaction at lines 111-114 into a module function used by `shadow` and
  `refuse`:

  ```python
  def redacted_target(payload, root):
      """The normalised target as refusal records store it, credentials and canaries redacted."""
      from wuwei import security
      from wuwei.redact import redact
      return security.redact(redact(target(payload)), security.load(root))
  ```

  In `shadow`, `shown = redacted_target(payload, root)` replaces the three lines; behaviour
  is unchanged (the #308 tests must pass untouched).
- `shadow` returns the enforced `(guard, reason)` pairs instead of bare reasons:
  `reasons` becomes `enforced`, both `reasons.append(reason)` become
  `enforced.append((guard, reason))`, docstring "return the enforced refusals".
- `run`, lines 80-91:

  ```python
  enforced = refusals
  if (refusals and args.event != 'SessionStart'
          and payload.get('session_id') != HEARTBEAT_SESSION):
      enforced = shadow(payload, refusals, root)
  reasons = [message for _, message in enforced]
  ...
  if reasons:
      return refuse(args.event, '\n'.join(reasons), cwd=payload.get('cwd'),
                    record=payload.get('session_id') != HEARTBEAT_SESSION,
                    refusals=enforced, payload=payload)
  ```

- `refuse(event, reason, *, malformed=False, cwd=None, record=True, refusals=(), payload=None)`.
  Inside the existing `if root is not None:` block, before the existing `try` that appends:

  ```python
  details = {'reason': reason}
  if refusals:
      details['refusals'] = [{'guard': guard, 'reason': message} for guard, message in refusals]
      try:
          details['target'] = redacted_target(payload, root)
      except Exception:
          pass  # A record without its target reads "not recorded" in wuwei why; never lose the refusal.
  ```

  and append `details` instead of `{'reason': reason}`. Every other `refuse` caller
  (malformed payloads, discovery errors) is unchanged and records `{'reason'}` only.
- Budget: this runs only on the refusal path, after the guards; `target` was already
  computed there in shadow mode. No import moves to the top of the module.

### 2. Owner outcome names its decider (`cli/wuwei/commands/decision.py`)

Line 132: `payload={'id': args.id, 'option': args.option, 'decided_by': 'owner',
'reversibility': fields['Reversibility']}`. Nothing else reads this payload by exact
shape (checked: `metrics.py` counts kinds; `status.py:68` reads `id`).

### 3. The command (`cli/wuwei/commands/why.py`, new)

Module docstring: `"""Explain from recorded events why an item, a decision or a refusal is where it is."""`

Imports: `re`, `sys`; `from wuwei import decision, references, state, verdict, watch, workspace`;
`from wuwei.commands.event import EVENT_PRODUCERS`; `from wuwei.exits import CLEAN, FINDINGS`.

```python
NOT = 'not recorded'
EVENT_ID = r'\d{4}-\d{2}-\d{2}:[1-9][0-9]*'


class Missing(Exception):
    """The target has no record (exit 1)."""  # not LookupError: a KeyError must stay exit 2


def register(subparsers):
    parser = subparsers.add_parser('why', help='Explain from records why an item, decision or refusal happened')
    parser.add_argument('target', nargs='+', help='an item, owner/repo#n, D-n, an event id or "last refusal"')
    parser.add_argument('--full', action='store_true', help='add event ids and evidence paths')
    parser.set_defaults(func=run)


def level(root, full):
    return 'full' if full else workspace.verbosity(workspace.load_config(root), 'report')


def run(args):
    root = workspace.find_workspace()
    target = ' '.join(args.target)
    try:
        if target == 'last refusal' or re.fullmatch(EVENT_ID, target):
            steps = refusal(root, target)
        elif re.fullmatch(decision.DECISION_ID, target):
            steps = decided(root, target)
        else:
            steps = item(root, target)
    except Missing as exc:
        print(f'wuwei why: {exc}', file=sys.stderr)
        return FINDINGS
    print('\n'.join(render(steps, level(root, args.full))))
    return CLEAN
```

A step is a tuple `(text, event_id_or_None, [workspace-relative paths])`.

```python
def render(steps, level):
    if level != 'full':
        return [text for text, _, _ in steps]
    return [f'{text} (event {event or NOT}' + ''.join(f'; {path}' for path in paths) + ')'
            for text, event, paths in steps]
```

#### 3a. `item(root, name)`

1. If `'#' in name`: `ref = references.pull_request(name)` (a `ValueError` exits 2); scan
   `watch.days(root)` (newest first) with `state.read_state(directory=day)` for the first
   item whose `pr == ref`; none raises `Missing(f'no item links {ref}')`.
2. Days: `[(day, data) for day in reversed(watch.days(root)) if name in (data :=
   state.read_state(directory=day))['items']]`; empty raises
   `Missing(f'no recorded item {name}')`.
3. For each `(day, data)`, `row = data['items'][name]`, `rel = lambda path:
   str(path.relative_to(root))`, `ids` = the day's `D-` ids for the item (Assumption A10):
   `{ident for ident, names in decision.naming(day, [name]).items() if names and
   ident.startswith('D-')}`, plus `row.get('decision')` and
   `row.get('assumption', {}).get('decision')` when they are strings. For
   `number, event in enumerate(watch.records(day / 'events.jsonl'), 1)`, with
   `ident = f'{day.name}:{number}'`, `kind`, `payload`:

   | Event | Group | Text |
   |---|---|---|
   | `plan.approved` / `state.import` with `name in payload.get('approved_items', [])` | queued | `queued: goal {row['goal']}, score {k} {v}, ...` from the candidate with `id == name` in `day / 'proposal.json'`; `score not recorded` when the file or the candidate or its `score` is absent. Path: `proposal.json` |
   | `state.import` with `name in payload.get('items', [])` (and not approved) | queued | `queued: carried over from an earlier day, goal {row.get('goal', NOT)}` |
   | `plan.added` with `payload.get('item') == name` | queued | as approved, score from `data.get('discovery_candidates', {}).get(name, {}).get('score')`. Path: `state.json` |
   | `gate.tiered` with `payload.get('item') == name` | tier | `tier: {tier} ({'; '.join(reasons)})`, no parenthesis when `reasons` is empty |
   | `gate.received` with `payload.get('item') == name` | gate | `gate {role} {round}: {verdict}`, then `, blocking: {first lines joined by '; '}` when the verdict file has blocking findings, or `, blocking findings not recorded` when `data['gate_verdicts']` has no `{name}:{role}:{round}` entry or its `file` does not exist. Path: the `file` value |
   | `decision.decided` / `decision.reversed` / `decision.routed` / `decision.waited` with `payload.get('id') in ids or payload.get('item') == name` | decision | decided: `decision {id}: {question}: {option} by {payload.get('decided_by') or NOT}`; reversed: `... : reversed to {option} by ...`; routed: `decision {id}: {question}: routed to the owner`; waited: `decision {id}: {question}: {outcome} by {EVENT_PRODUCERS['decision.waited']} after decisions.wait_hours`. Path: `decisions/{id}.md` of that day |
   | any event with `name in payload.get('phase_changes', {})` | phase | `phase {phase} by {EVENT_PRODUCERS.get(kind, kind)}` |
   | `merge.auto` with `payload.get('pr') == row.get('pr')` | merge | `merge {pr}: cleared by the merge policy at head {head[:12]}, checks {name conclusion, ...}, approvals {a, b or none}` from `payload['evidence']`. Paths: each `evidence['verdicts'][*]['path']` |

   One event can feed two groups (for example `decision.decided` with a `phase_changes`).
   `question` is `(verdict.rows(verdict.active_text(text), 'Question') or [NOT])[0].strip()`
   from that day's `decisions/{id}.md`, `NOT` when the file is absent; it never lints the
   record. Blocking findings: `[block.strip().splitlines()[0] for block in
   verdict.finding_blocks(verdict.active_text(text)) if re.search(verdict.BLOCKS_YES,
   block, re.I)]`, as `dispatch.receive` computes them.
4. After the walk, each id in `ids` that no decision event named adds
   `decision {id}: {question}: decided not recorded` (no event; path the record).
5. Output: groups in the order queued, tier, gate, decision, phase, merge. An empty group
   adds one step with no event and no path: `queued: not recorded`, `tier: not recorded`,
   `gate verdicts: not recorded`, and `merge policy check: not recorded` only when the
   newest row's phase is `merged`. Then the now step from the newest `(day, row)`:
   `now: {phase} ({status})`, plus `, waiting on decision {row['decision']}` (or
   `, waiting on: not recorded`) for `parked` / `escalated`; else
   `, waiting on external confirmation {id}` when `assumption.status == 'waiting'`; else
   `, waiting on {action}` when `data.get('watch', {}).get('actions', {}).get(row.get('pr'))`
   has an `action`. Path: that day's `state.json`.

#### 3b. `refusal(root, target)`

- `last refusal`: the first `(day, number, event)` scanning `watch.days(root)` (newest
  first) and each day's `watch.records` from the end, with `kind == 'hook.refusal'`; none
  raises `Missing('no recorded refusal')`.
- An event id `YYYY-MM-DD:n`: the day directory must be in `watch.days(root)` and the line
  must exist and be a `hook.refusal`; otherwise `Missing(f'no recorded refusal {target}')`.
- Steps, each with the event id and no path:
  `refusal at {event['ts']}`, `command: {payload.get('target') or NOT}`, then per entry of
  `payload.get('refusals') or [{'guard': None, 'reason': payload['reason']}]`:
  `guard: {guard or NOT}`, `rule: {before}`, `fix: {after or NOT}` with
  `before, _, after = reason.partition('; ')` (Assumption A3).

#### 3c. `decided(root, ident)`

- `path = decision.today_path(ident, root)`; not a file raises
  `Missing(f'no decision record {ident} today')`. `fields, scores =
  decision.evaluate(text)` (an invalid record exits 2); `_, _, wants, _ =
  decision._scored(fields)`.
- Steps, path `rel(path)` and no event: each line of `decision.present(ident, fields,
  'brief')`; `weights: {criterion} {weight}, ...`; `margin: {m:.2f}` with
  `m = (scores[chosen] - max(s for o, s in scores.items() if o != chosen)) /
  (10 * sum(int(row[1]) for row in wants))`; `class: {Class: line or NOT}` (read with
  `verdict.rows(verdict.active_text(text), 'Class')`).
- Today's events (`watch.records(workspace.day_dir(root) / 'events.jsonl')`): the last
  `decision.decided` / `decision.reversed` with `payload.get('id') == ident` gives
  `level: L{n}` when its `decided_by` matches `@L(\d)`, else `level: not recorded`, and
  `decided: {option} by {decided_by or NOT}` with its event id; none gives
  `level: not recorded` and `decided: not recorded`.

### 4. Board (`cli/wuwei/commands/board.py`)

In `read`, after `files = {...}` (line 137):

```python
from wuwei.commands import why
try:
    chains = {name: why.render(why.item(root, name), why.level(root, False)) for name in data['items']}
except (OSError, ValueError, KeyError, TypeError, UnicodeError, why.Missing) as exc:
    chains = {'unmeasured': str(exc)}
files['./why.json'] = json.dumps(chains)
```

`TOOL['description']` gains: `, and why each item is where it is (why.json)` before the
final sentence. The text table is unchanged.

### 5. Docs (`docs/site/reference.md`)

- Commands table, after the `worktree` row:
  `| \`bin/wuwei why\` | Explains from recorded events why an item, a decision or a refusal is where it is. | [Why](#why) |`
- New `## Why` section after `## Shadow mode`: targets and resolution order; the step order
  and the `not recorded` rule; `--full` and `owner.verbosity.report`; the event id
  `<YYYY-MM-DD>:<line>`; the `hook.refusal` payload `{reason, refusals: [{guard, reason}],
  target}` and the rule/fix split at the first `; `; `decided_by: owner` on owner answers;
  the board's `why.json`; exits 0, 1, 2.

## Must not change

- `hook.refusal` keeps `reason` exactly (promotion `adherence_counts`, brief pack, metrics
  read it). Malformed-payload refusals keep `{'reason'}` only. Heartbeat refusals stay
  unrecorded.
- `guard.would_refuse` payload and every #308 test.
- `decision.decided` from the seat route; `state.json`, `STATE_PRODUCERS`,
  `EVENT_PRODUCERS`, `signal.py` tiers: no new kinds or keys.
- The board text output and every existing board test.
- No write anywhere from `why`.

## Project structure

```
cli/wuwei/commands/why.py        new
cli/wuwei/commands/hook.py       redacted_target, shadow returns pairs, refuse records details
cli/wuwei/commands/decision.py   decided_by: owner in the owner outcome payload
cli/wuwei/commands/board.py      ./why.json
docs/site/reference.md           commands row, ## Why
tests/test_why.py                new
tests/test_hooks.py              refusal payload and end-to-end last refusal
```

## Notes from implementation

- The board also catches `AttributeError` (a payload field of the wrong type), so a
  malformed record reads `unmeasured` there instead of failing the board.
- The commands row sits after `watch`, keeping the table alphabetical.
- T011 passed without code changes: `Missing` and the `__main__` handler already cover
  every exit (T012 needed nothing).
- The `level` line of the decision view carries the event id only when it came from a
  recorded `decided_by`.
