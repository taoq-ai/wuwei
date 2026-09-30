# Implementation Plan: Session registry: several Claude Code sessions in one workspace, with one planner

**Branch**: `260-session-registry` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/260-session-registry/spec.md`

## Summary

One new core module, `cli/wuwei/sessions.py`, owns the registry: one upsert function that
every producer calls inside its own state write, one reader that turns state into rows
(role, age, stale), one claim check, and the `CLAUDE_ENV_FILE` export. The hooks that
already run (SessionStart and Stop in `guards/lifecycle.py`, plus a new SubagentStop entry
there) call it in one `state._write_state` each. `plan.session` refuses a second planner
unless `--take-over`. `brief.write` and `workspace.create_worktree` claim the item inside
the writes they already do or next to their gate check. `status` counts live sessions and
nudges on a stale planner. No new port, adapter, fake or dependency.

## Technical Context

**Language/Version**: Python 3.11+, stdlib only at runtime (`os`, `shlex`, `datetime`)

**Primary Dependencies**: none

**Storage**: today's `state.json` through `state._write_state` (atomic, locked); two new
root keys `sessions` and `claims`; events `session.seen` and `item.claimed`, plus
`previous` on `plan.session`

**Testing**: pytest in process. Hooks through `wuwei.commands.hook.run` with a payload on
stdin (as `tests/test_hooks.py` does with `fixture(event)`), guards called directly as
`tests/test_watch.py::test_only_registered_planner_consumes_wake` does, CLI through
`wuwei.__main__.main`. Time through `WUWEI_NOW`.

**Target Platform**: macOS and Linux hosts running Claude Code

**Project Type**: CLI plugin

**Performance Goals**: SessionStart gains exactly one state write and one small append to
`CLAUDE_ENV_FILE`, no extra state read. Stop reuses the write's returned state for the
planner lookup (its existing `read_state` goes away on the normal path). SubagentStop gains
one state write. `status --line` gains no extra file read (config is cached by
`workspace.load_config`).

**Constraints**: exits 0/1/2; refusals exit 2 with the claimant or planner named; no
absolute local paths, em-dashes or emojis in anything written.

**Scale/Scope**: code in 11 files (1 new module, 1 new command), docs in 3, template 1,
skill 1; tests in 1 new and 7 existing files.

## Constitution Check

- I Stdlib only: yes.
- II Three-state exits: `sessions` 0 or 2; `plan session` refusal 2; claim refusal 2 via the
  existing `ValueError` paths (`commands/plan.py`, `commands/brief.py`, `wuwei.__main__`
  for `worktree`). Stop and SubagentStop return 0 with a reason on registry failure so a
  bookkeeping fault never blocks a turn end (same rule as the existing planner wake).
- III One behaviour, one function: upsert in `sessions.record`, liveness in
  `sessions.rows`, claim in `sessions.claim`. Hooks, `plan`, `brief` and `worktree` call
  them; none re-implement them.
- IV Test first: every implementation task in tasks.md follows its failing test.
- V Simplicity: no new port or class; planner role is derived from `planner_session_id`
  (single source of truth) instead of being stored twice; the hand-over reuses the
  `plan.session` event kind.
- VII Security: `sessions` and `claims` are producer-only (default-deny in
  `state._protected`, named in `STATE_PRODUCERS`); new event kinds are reserved in
  `EVENT_PRODUCERS`; no message text is stored; the env export quotes the id with
  `shlex.quote`.

## Design

### New module `cli/wuwei/sessions.py`

```python
ROLES = ('adhoc', 'seat-host', 'remote')

def current():            # os.environ.get('WUWEI_SESSION_ID') or None (stripped, nonempty)
def stale_seconds(root):  # config['sessions']['stale_seconds'] when .wuwei/config.toml exists,
                          # else workspace.SCHEMA['sessions']['stale_seconds'][1]
def record(data, session_id, *, hook, cwd, role=None, thread=None):
    # Upsert data['sessions'][session_id]; mutates data only.
    # Insert: {'role': 'adhoc', 'started': now, 'cwd': cwd}. Every call: last_seen=now,
    # last_hook=hook. role (must be in ROLES) and thread (nonempty str) overwrite when given.
    # Raises ValueError on a nonstring or empty session_id, unknown role, or a non-object
    # 'sessions'. now = workspace.now().isoformat().
def touch(root, session_id, *, hook, cwd, role=None, thread=None):
    # Returns None without writing when today's state.json does not exist.
    # Otherwise state._write_state(lambda data: record(...), root, reserved=False,
    #   kind='session.seen', payload={'session_id': session_id, 'hook': hook})
    # and returns the written state. This is the producer #65 calls with role='remote'.
def rows(data, now, stale):
    # List sorted by 'started': session_id, role ('planner' when equal to
    # data.get('planner_session_id'), else the stored role), started, last_seen,
    # age_seconds, idle_seconds (ints), stale (idle_seconds >= stale), last_hook,
    # items (sorted items whose claims value is this id), cwd, and thread when present.
    # Raises ValueError on malformed 'sessions' or 'claims'.
def claim(data, item, session_id, now, stale, *, cwd):
    # holder = data.get('claims', {}).get(item). When holder is set, differs from
    # session_id, and rows(...) shows holder live (present and not stale): raise
    # ValueError(f'{item} is claimed by live session {holder}; brief it from that session '
    #            f'or wait until it is stale ({stale}s without hook activity)').
    # When session_id is known: data.setdefault('claims', {})[item] = session_id and
    # record(data, session_id, hook=f'claim {item}', cwd=cwd).
def claim_item(root, item):
    # state._write_state(lambda data: claim(data, item, current(), workspace.now(),
    #   stale_seconds(root), cwd=str(Path.cwd())), root, reserved=False,
    #   kind='item.claimed', payload={'item': item, 'session': current()})
def export(session_id):
    # When CLAUDE_ENV_FILE is set: append f'export WUWEI_SESSION_ID={shlex.quote(session_id)}\n'.
```

The refusal is a plain `ValueError`, never `state.StateError` or `brief.Refused` (both are
`ValueError` subclasses caught earlier as exit 1).

### Hooks: `cli/wuwei/guards/lifecycle.py`

- Private helper `_seen(root, payload, event)`: `hook` is `event`, suffixed `:<source>` for
  SessionStart or `:<agent_type>` for SubagentStop when that field is a nonempty string;
  calls `sessions.touch(root, payload['session_id'], hook=hook, cwd=payload['cwd'])` only
  when `session_id` is a nonempty string (guards are also called directly without it),
  else returns None.
- `session_start`: after `code, lines = 0, []`, one `try`: `sessions.export(session_id)`
  then `_seen(root, payload, 'SessionStart')`; on `watch.ERRORS` set `code = 2` and append
  `session registry unmeasured: <exc>`. Nothing else in the function changes.
- `stop`: keep the `stop_hook_active` early return and scope check. Replace
  `state.read_state(root).get('planner_session_id')` with
  `data = _seen(root, payload, 'Stop')`, falling back to `state.read_state(root)` only when
  `_seen` returned None. The rest (planner comparison, `watch.wake(root, consume=True)`,
  the `planner wake unmeasured` reason) is unchanged.
- New `subagent_stop(payload)`: scope check, `_seen(root, payload, 'SubagentStop')`,
  return `(0, '')`; on `watch.ERRORS` return `(0, f'session registry unmeasured: {exc}')`.
- `GUARDS` gains `Guard('SubagentStop', None, subagent_stop)`.
- `cli/wuwei/guards/__init__.py` `MODULES['lifecycle']` gains `'SubagentStop': None`
  (`tests/test_hooks.py` pins MODULES to GUARDS).

### Planner: `cli/wuwei/plan.py` and `cli/wuwei/commands/plan.py`

`session(session_id, root=None, *, take_over=False)`:

1. Validate as today.
2. `current = state.read_state(root).get('planner_session_id')`;
   `previous = current if current not in (None, session_id) else None`.
3. `previous and not take_over`: raise `ValueError(f'planner session {previous} is
   registered; to hand over, run from this session: wuwei plan session {session_id}
   --take-over')` (exit 2 through the existing `except` in `commands/plan.py`).
4. `_write_state(update, root, reserved=False, kind='plan.session', payload={'session_id':
   session_id, **({'previous': previous} if previous else {})})` where `update` raises
   `ValueError('planner changed during registration; retry')` if
   `data.get('planner_session_id') != current`, then sets `planner_session_id` and calls
   `sessions.record(data, session_id, hook='plan session', cwd=str(Path.cwd()))`.

`commands/plan.py`: `session.add_argument('--take-over', action='store_true')` and pass
`take_over=args.take_over`.

### Claims

- `cli/wuwei/brief.py` `write`: before the lock, `session = sessions.current()` and, for
  `role == 'builder'`, `payload['session'] = session` when known (add it where `payload`
  is built). Inside `update(fresh)`, before `workspace.atomic_write(output, ...)`:
  `if role == 'builder': sessions.claim(fresh, item, session, workspace.now(),
  config['sessions']['stale_seconds'], cwd=str(Path.cwd()))`. The existing `except
  BaseException` path keeps no file behind because the refusal precedes the write.
- `cli/wuwei/workspace.py` `create_worktree`: right after the `gate_approved` check and
  before `vcs.worktree_add`, `sessions.claim_item(root, Path(path).name)` (the only caller,
  `commands/worktree.py`, passes `root / 'worktrees' / item`). Placing it after the gate
  check keeps the claim from creating day state before the morning gate.

### Status and nudges: `cli/wuwei/commands/status.py`

- `scan`: after the decision-routes loop, with `root = directory.parents[2]` and
  `now = datetime.fromisoformat(classified_state['now'])`, find the `planner` row of
  `sessions.rows(classified_state, now, sessions.stale_seconds(root))`; when it is stale add
  `current[('session.planner_stale',)] = {'tier': 'nudge', 'source':
  'session.planner_stale', 'lane': 'Work', 'reason': f'planner session {id} stale: no hook
  activity for {idle}s; take over from the live session with: wuwei plan session <session
  id> --take-over'}`. Skip the config read when `planner_session_id` has no registry row.
- `snapshot`: `result['sessions'] = sum(not row['stale'] for row in
  sessions.rows(data, workspace.now(), sessions.stale_seconds(directory.parents[2])))`.
- `run`: when `data['sessions']`, append `f'sessions {data["sessions"]}'` after the phase
  parts and before `reply`/`meeting`, so every existing substring assertion
  (`pages 0 | nudges 0 | watch off`) and the documented no-plan example stay true.

### New command `cli/wuwei/commands/sessions.py`

`wuwei sessions` (auto-discovered by `wuwei.__main__`): `root = workspace.find_workspace()`,
`data = state.read_state(root)` (fresh defaults when no day state, so `[]`), print
`json.dumps(sessions.rows(data, workspace.now(), sessions.stale_seconds(root)))`, return 0;
`(OSError, ValueError, KeyError, TypeError)` print `wuwei sessions: <exc>` to stderr and
return 2.

### Producer-only and silence

- `cli/wuwei/state.py` `STATE_PRODUCERS`: `'sessions': 'wuwei hook SessionStart, Stop and
  SubagentStop or wuwei plan session'`, `'claims': 'wuwei brief builder or wuwei worktree
  add'`. (Protection itself is already default-deny in `_protected`; the entries name the
  producer in the refusal.)
- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: `'session.seen': 'wuwei hook
  SessionStart, Stop and SubagentStop'`, `'item.claimed': 'wuwei worktree add'`.
- `cli/wuwei/signal.py` `SILENT`: add `'session.seen'` and `'item.claimed'` (otherwise
  every turn end would become a nudge through `status.scan`).

### Config, template, docs, skill

- `cli/wuwei/workspace.py` `SCHEMA`: `"sessions": {"stale_seconds": (int, 3600, 1)}`.
- `templates/workspace/config.toml`: `[sessions]` table with `stale_seconds = 3600`.
- `docs/site/configuration.md`: row for `sessions.stale_seconds`.
- `docs/site/reference.md`: a short `## Sessions` section (registry, `wuwei sessions`,
  `WUWEI_SESSION_ID`, claims and the exit 2 refusals, `--take-over`, stale planner nudge)
  and one sentence in `## Watch state` that the line shows `sessions N` when N >= 1.
- `skills/wuwei-plan/SKILL.md` line 10: resuming planning in a new session the same day
  uses `wuwei plan session "${CLAUDE_SESSION_ID}" --take-over`; the first registration of
  the day stays plain.

## What must not change

- `planner_session_id` stays the single planner field and its only writer is
  `plan.session`; `guards/stop.py` is untouched (its planner history from `plan.session`
  events now also sees take-overs, which is the current behaviour for replacements).
- Wake delivery (`watch.wake`, `lifecycle.stop` planner comparison) is unchanged.
- No hook creates today's `state.json`; the existing "day state missing" refusals in
  `close`, `report`, `pr_actions.evaluate`, `brief.read_day` and `guards/stop.py` keep
  their meaning.
- `brief.write` evidence-race check (`state changed while collecting brief evidence`)
  compares only items, seat policy and gate fields, so a concurrent registry touch never
  forces a retry; keep it that way.
- Gate and sentinel briefs, lead and steward briefs are never refused by a claim.
- Existing behaviour without `WUWEI_SESSION_ID` and without claims is byte-for-byte the
  same apart from the extra `item.claimed` event on `worktree add`.

## Deferred

- `stop <session>` and the listener's `touch(..., role='remote', thread=...)` call: #65.
- A producer for `seat-host`: whichever issue gives a session that role.
