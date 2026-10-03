# Implementation Plan: Tool-sequence decisions apply to item seats only

**Branch**: `352-traces-seats-only` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

The S2 sweep (`scanner._trace_response`) queues an owner decision for every critical chain
of every session. Classify the session first: a seat keeps today's response; a session the
registry knows (the planner, its subagents, a shepherd or remote session) gets one silent
`traces.noted` event per day; an unknown session gets one `traces.unmatched` event per day,
or under strict one decision per session per day. The registry answer comes from one small
function in `sessions.py`; the posture from `workspace.posture`. `doctor --fix` gets one
allow-listed fix that closes today's decisions of the old shape. No new state key, file,
config key or port.

## Technical Context

Python 3.11+ stdlib runtime, pytest for tests. Reuse:

- `brief.seats(data)` and each seat's `trace_sessions` (the seat link the traces guard
  already binds), as `_trace_response` does today.
- `state.read_state`, `state._write_state`, `state.append_event`, `workspace.day_dir`,
  `workspace.atomic_write`.
- `workspace.posture(config)[0]` for the effective posture (maps `guards.mode = "shadow"` to
  observe).
- `watch.records(path)` to read today's events (already used by `trace_sweep` for its
  "not configured" line).
- `decision.answered`, `decision.today_path`, `decision.evaluate` in doctor.
- doctor's `_row`, `FIXES` contract `(command, preview(root) -> (text, token), apply(root,
  token) -> exit)`, and its one-digest batch.
- Tests: the `root` fixture style of `tests/test_quiet_sweeps.py` (in-process, a fake
  scanner port through `registry.load`), and the `ws` fixture and `fix(confirm)` helper of
  `tests/test_doctor.py`.

## Constitution Check

Stdlib only. Exits unchanged: an unreadable events file during the once-per-day check raises
`ValueError` inside `trace_sweep`'s existing handler, so the sweep reports `unmeasured`
(exit 2) and never clean. Principle VII: seats keep the full response in every posture;
unknown sessions stay visible as an event and are decided on under strict; nothing a seat can
write turns it into a registered session, because the seat check runs first and the seat
link comes from the brief reference, not from the registry. One behaviour, one function: the
classification lives in `_trace_response`, the registry question in `sessions.registered`.
Test first. Passes.

## Design

### 1. The registry question (`cli/wuwei/sessions.py`)

Add after `record`:

```python
def registered(data, session_id):
    """The non-seat role the registry gives a trace session, or None (#352). A subagent's
    trace id is <session>:<agent>; an adhoc row (any SessionStart) is not a registration."""
    parent = session_id.split(':', 1)[0]
    if parent == data.get('planner_session_id'):
        return 'planner'
    row = data.get('sessions', {}).get(parent)
    role = row.get('role') if isinstance(row, dict) else None
    return role if role in ROLES and role != 'adhoc' else None
```

`ROLES` is the existing tuple (`adhoc`, `seat-host`, `remote`, `shepherd`). No new state.

### 2. The sweep response (`cli/wuwei/scanner.py`)

`_trace_response(finding, root, posture)` returns whether the finding paged:

```python
def _trace_response(finding, root, posture):
    """Seats: page, park and one owner decision per chain. A registered session: one silent
    traces.noted per day. Unknown: one traces.unmatched per day, or under strict a page and
    one decision per session per day (#352). Returns True when the finding paged."""
    import hashlib
    import json
    from wuwei import brief, decision, sessions, watch

    session = finding['session_id']
    digest = hashlib.sha256(session.encode()).hexdigest()
    seat = any(session in seat.get('trace_sessions', [])
               for seat in brief.seats(state.read_state(root)).values())
    role = None if seat else sessions.registered(state.read_state(root), session)
    if not seat and (role or posture != 'strict'):
        kind = 'traces.noted' if role else 'traces.unmatched'
        if not any(row['kind'] == kind and row['payload'].get('session_digest') == digest
                   for row in watch.records(workspace.day_dir(root) / 'events.jsonl')):
            extra = ({'role': role, 'summary': f'traces: {role} session, chain noted'} if role
                     else {'posture': posture})
            state.append_event(kind, {'session_digest': digest, 'chain': finding['chain'], **extra}, root)
        return False
    state.append_event('scanner.finding', finding, root)
    key = hashlib.sha256(json.dumps(finding, sort_keys=True).encode()).hexdigest() if seat else digest
    ...  # the existing update(data) unchanged, except the Context line below
    return True
```

Read state once into a local (the snippet calls it twice only for brevity). Inside the
existing `update`, change only the `else` text of the `Context:` line (line 87) to
`'Session has no item reservation and no registration.'`; `Session digest:` already prints
`digest`, so reuse the local. The `used` and `queued[key]` logic is unchanged: strict unknown
decisions are keyed by the session digest, seat decisions by the finding as today.

`trace_sweep(root, config)`: compute `posture = workspace.posture(config)[0]` once before the
loop, sum the return values, and set `scanner_owed` to that sum instead of
`len(result.data['findings'])`.

### 3. Event tiers and producers

- `cli/wuwei/signal.py`: add `'traces.noted'` to `SILENT`; change the `guard.would_refuse`
  test to `if kind in ('guard.would_refuse', 'traces.unmatched'):` so an unknown session is
  silent under observe and a nudge under guarded and strict.
- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: `'traces.noted': 'wuwei sweep'`,
  `'traces.unmatched': 'wuwei sweep'` (every kind but `note` is already refused; this names
  the producer in the refusal).
- `cli/wuwei/state.py` `STATE_PRODUCERS['decision_outcomes']`: append
  `' or owner host wuwei doctor --fix'`.

### 4. doctor closes the old decisions (`cli/wuwei/commands/doctor.py`)

```python
LEGACY_TRACE = ('Question: How should this critical tool sequence be investigated?\n'
                'Context: Session has no matching item reservation.\n')
SUPERSEDED = 'superseded by wuwei doctor --fix: tool-sequence decisions apply to item seats only (#352)'


def _legacy_traces(root):
    """Today's pending, unanswered decisions the pre-#352 sweep wrote for a non-seat session."""
    from wuwei import decision, state
    data = state.read_state(root)
    return [path.stem for path in sorted((workspace.day_dir(root) / 'decisions').glob('D-*.md'))
            if not path.is_symlink()
            and (text := path.read_text(encoding='utf-8')).startswith(LEGACY_TRACE)
            and re.search(r'^Outcome: pending$', text, re.M)
            and decision.answered(data, path.stem) is None]
```

Add `import re` to doctor.

- `_day`: after the `nudges` row, `ids = _legacy_traces(root)`; when non-empty append
  `_row('day', 'trace decisions', 'warn', f'{", ".join(ids)} pending under the pre-#352 rule',
  'wuwei doctor --fix', apply='trace-decisions')`. On `(OSError, ValueError)` append an
  `unmeasured` row of the same name with the reason. No row when the list is empty, so
  `test_day_rows` keeps its exact row names.
- Preview: `_supersede_preview(root)` returns
  `(''.join(f'{ident}: Outcome: superseded ({SUPERSEDED})\n' for ident in ids), ids)` and
  raises `ValueError('nothing to supersede')` when `ids` is empty.
- Apply: `_supersede(root, token)`: if `_legacy_traces(root) != token`, print
  `trace-decisions: changed since the preview; nothing applied` and return 1. Otherwise for
  each id: read the record, `fields, _ = decision.evaluate(text)`, replace the first
  `^Outcome: pending$` line with `Outcome: superseded`, append `Notes: <SUPERSEDED>\n`
  (`evaluate` treats `Notes:` as a section break, and `report.decisions` still sees one
  `Outcome:`), `workspace.atomic_write` it, then one `state._write_state` per id setting
  `decision_outcomes[id] = {'option': 'superseded', 'outcome': 'superseded', 'decided_by':
  'owner', 'reversibility': fields['Reversibility']}` with `kind='decision.decided'` and the
  same payload as `commands/decision.py` `owner_outcome` (`id`, `option`, `decided_by`,
  `reversibility`). Return 0.
- `FIXES['trace-decisions'] = ('supersede pre-#352 tool-sequence decisions',
  _supersede_preview, _supersede)`, last in the dict.

The owner outcome is what makes `close`, `status` and `steward.decision_queue` stop listing
the record; the `Outcome:` line is what the board reads.

### 5. Docs

- `docs/site/security.md`, after the posture table's floors list: one paragraph: runtime
  trace chains page and decide only for seats; the planner and other registered sessions
  get one silent `traces.noted` event per day; an unknown session gets one
  `traces.unmatched` event per day, and under `strict` one owner decision per session per
  day; `--shadow` is observe.
- `docs/site/reference.md` Doctor fix table: row `` `trace-decisions` `` |
  `supersede pre-#352 tool-sequence decisions` | today has pending tool-sequence decisions
  the pre-#352 sweep wrote for a session with no item. Also add "pre-#352 trace decisions"
  to the Day and sessions list in the first paragraph. `tests/test_docs.py`
  `test_doctor_is_the_first_stop` checks the name and command.
- `docs/specs/2026-09-24-wuwei-design.md` S2: append "Amendment (owner trial, 2026-10-03,
  #352): only seats park and prompt; registered non-seat sessions are noted once per day,
  unknown sessions are noted once per day and prompt once per day under strict."

The payload key is `summary`, not `note`: `items.<id>.note` is the one generically writable
item field, so `tests/test_state_allowlist.py`'s reader inventory refuses any module that
reads or writes a `'note'` key (found while building).

## What must not change

- The traces guard (`cli/wuwei/guards/traces.py`): span recording and `trace_sessions`
  binding are untouched.
- The seat response: paging, parking via `state.PHASES`, the decision body, the per-finding
  key for seats, `scanner_decisions` as the dedupe record and its producer protection.
- The ZIRAN adapter (`adapters/scanner/ziran.py`) and the finding shape.
- `sessions.record`, `touch`, `rows`, `claim` and the registry schema; `claims` are not seat
  evidence.
- doctor's other fixes, its one-digest batch and `test_day_rows`' row list for a clean day.

## Tests (files)

- New `tests/test_traces_seats_only.py`: in-process. Fixture: `tmp_path` workspace with
  `.wuwei/config.toml` holding `[adapters]\nscanner = "ziran"\n` plus the posture under test,
  `WUWEI_WORKSPACE` and `WUWEI_NOW` set, `state._write_state(lambda data: None, ...)`, a
  non-empty `traces.jsonl` in the day directory, and `registry.load` patched so `scanner`
  returns a namespace whose `traces(file, root=None)` returns `Result(1, {'sessions_analyzed':
  2, 'findings': rows})`. `rows` lists Bash -> Write and Bash -> Edit for each session, each
  twice (the adapter dedupes in reality; repeats prove the sweep does too).
  Helpers count `decisions/D-*.md` and events by kind.
- `tests/test_watch.py`: the unmapped cases of `test_trace_sweep_parks_queues_and_pages`
  become strict (append `[security]\nposture = "strict"\n` to the config when not mapped)
  and assert the new `Context:` line; the mapped cases are unchanged.
- `tests/test_doctor.py`: extend `test_fix_allow_list_is_pinned` with `trace-decisions`;
  add the supersede tests with the `ws` fixture.
