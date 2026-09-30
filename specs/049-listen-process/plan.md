# Implementation Plan: `wuwei listen` process, inbox and service templates

**Branch**: `049-listen-process` | **Spec**: `specs/049-listen-process/spec.md`

## Summary

One new core module, `cli/wuwei/listen.py` (a `tick` and a `run`), and one thin command,
`cli/wuwei/commands/listen.py`. Everything else is the watch's existing code made to take
a name: health, unit path, service install, templates, the lock and signal loop, and the
planner wake marker. `inbox.store` gains dedup by `(source, id)`. The cursor per source
and the woken count live in `.wuwei/inbox/cursor.json`, already protected by the state
guard. Session start reports a dead listener.

## Technical Context

Python 3.11+, stdlib only at runtime, pytest for tests. No subprocess in the core: the
inbound source is `registry.load('inbound', config)`, service calls go through the
existing `registry.watch_service()` adapter. State writes go through
`state._write_state` (day state) and `workspace.atomic_write` (cursor file); inbox lines
through `inbox.store` only.

## Constitution Check

- I Stdlib only: yes (`json`, and what `watch.py` already imports).
- II Three-state exits: `listen --once` 0 nothing new, 1 new events stored, 2 could not
  run (source failed, store failed, corrupt cursor or inbox, inbound `none`, lock held).
  Health: 0 off or alive, 1 dead, 2 unmeasured.
- III One behaviour, one function: dedup lives only in `inbox.store`; health in
  `watch.health`; the wake marker in `watch.mark_wake`; the loop in `watch.serve`; unit
  install in `commands/watch.service`. The listener calls them, it copies none.
- IV Test first: tasks.md orders every test before its implementation.
- V Ponytail: no new base class, no webhook server, no second template pair, no config
  for the clock interval, no new state key (the listener's clock due time and wake reuse
  the `watch` key the watch already owns).
- VII Security: `.wuwei/inbox/` (inbox and cursor) is already guard-protected (#48);
  `listen uninstall` becomes an owner action; `listen: clock` and `listen: wake` are
  producer-reserved; `responder.enabled` lives in `config.toml`, which seats cannot
  write.

## Design

### 1. `cli/wuwei/inbox.py`: dedup and a reader

Add `read(root)`: the stored events, oldest first; a missing inbox is `[]`; a corrupt
line raises `ValueError` (`json.loads`).

```python
def read(root):
    """Stored events, oldest first; a missing inbox is empty, a corrupt line fails."""
    try:
        text = (Path(root) / '.wuwei' / 'inbox' / 'inbox.jsonl').read_text(encoding='utf-8')
    except FileNotFoundError:
        return []
    return [json.loads(line) for line in text.splitlines()]
```

In `store`, after the shape validation and before `registry.load('redactor', ...)`:

```python
    try:
        seen = {(row['source'], row['id']) for row in read(root)}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return Result(2, None, f'inbox: unreadable: {exc}')
    fresh = []
    for event in events:
        if (event['source'], event['id']) not in seen:
            seen.add((event['source'], event['id']))
            fresh.append(event)
    events = fresh
```

The return stays `Result(1 if findings else 0, len(events))`, now the count stored. An
empty `events` after dedup returns `Result(0, 0)` without loading the redactor.
`# ponytail: reads the whole inbox per store; index ids when the inbox grows large.`
Only the singleton listener writes the inbox, so reading outside `state.lock` is safe.

### 2. `cli/wuwei/watch.py`: four shared helpers take a name or an inbox count

a. `health(root, clocks=None, name='watch')` (lines 45-65). Replace the three watch
   literals: event kind `f'{name}: clock'`, deadline
   `workspace.load_config(root)[name]['dead_seconds']`, unit
   `workspace.watch_unit(root, name=name)[1]`, and the messages `f'{name} dead: ...'`,
   `f'{name} off: ...'`, `f'{name} health unmeasured: ...'`. Watch output is unchanged.

b. `mark_wake(root, *, prs=(), inbox=0, kind, payload)`: lift the `mark` closure out of
   `poll` (lines 355-370) into a module function and make it carry `inbox`:

   ```python
   def mark_wake(root, *, prs=(), inbox=0, kind, payload):
       """Merge into the planner wake; an unseen marker keeps its PRs and inbox count."""
       def mark(data):
           value = data.setdefault('watch', {})
           prior = previous(root) if 'wake' not in value else {}
           pending = value.get('wake', prior.get('wake'))
           seen = value.get('wake_seen_at', prior.get('wake_seen_at'))
           if pending and not prs and inbox <= pending.get('inbox', 0):
               return  # already covered: a listener restart must not wake twice
           at, refs, count = workspace.now(), set(prs), inbox
           if pending:
               at = max(at, obligations._time(pending['at']) + timedelta(microseconds=1))
               if seen != pending['at']:
                   refs.update(pending['prs'])
                   count = max(count, pending.get('inbox', 0))
           value['wake'] = {'at': at.isoformat(), 'prs': sorted(refs),
                            **({'inbox': count} if count else {})}
       state._write_state(mark, root, reserved=False, kind=kind, payload=payload)
   ```

   `poll` calls `mark_wake(root, prs=changes, kind='pr.changed', payload={'pr': ref,
   'fields': fields})` with its first change, then appends the rest as today. PR-only
   markers are byte-identical to today's.

c. `wake(root, consume=False)` (lines 469-493): read `count = value.get('inbox', 0)`,
   require `type(count) is int and count >= 0` (else `ValueError('invalid inbox wake')`),
   raise `empty planner wake marker` only when there are no refs and no count, and build
   the message from `refs + ([f'inbox to line {count}'] if count else [])`. A PR-only
   notice is unchanged.

d. `serve(root, name, tick, delay, *, once=False, sleep=None, blind=lambda: False)`:
   lift the body of `run` (lines 426-466) with `.wuwei/{name}.lock`, the message
   `f'{name} could not run: another {name} holds the workspace lock'`, and the loop
   `code = tick(root); if once: return code; if stopping: break; if blind(): return 2;
   sleep(delay)`. `watch.run` becomes: find the workspace, load config, define `blind()`
   (the existing `saved(root)` failure check that prints `watch blind: ...`), and return
   `serve(root, 'watch', tick, min(...same five values...), once=once, sleep=sleep,
   blind=blind)`. `tick` is looked up at call time so tests that monkeypatch `watch.tick`
   keep working.

### 3. `cli/wuwei/workspace.py`

- `watch_unit(root, platform=sys.platform, name='watch')` (lines 289-296): label
  `'wuwei-' + ('' if name == 'watch' else f'{name}-') + <hash>`. The watch label is
  unchanged, so installed watch units stay valid.
- `SCHEMA`: add `"listen": {"poll_seconds": (int, 60, 1), "dead_seconds": (int, 300, 1)}`
  and `"responder": {"enabled": (bool, True)}`.

### 4. `cli/wuwei/listen.py` (new, the listener core)

```python
"""The listener: poll the inbound source into the inbox and wake the planner."""

import json

from wuwei import inbox, obligations, registry, watch, workspace

CLOCK_SECONDS = 120


def _path(root):
    return root / '.wuwei' / 'inbox' / 'cursor.json'


def cursor(root):
    """Cursor per source and the inbox count the last wake covered."""
    try:
        data = json.loads(_path(root).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {'cursors': {}, 'woken': 0}
    if not (isinstance(data, dict) and isinstance(data.get('cursors'), dict)
            and all(isinstance(k, str) and isinstance(v, str) for k, v in data['cursors'].items())
            and type(data.get('woken')) is int and data['woken'] >= 0):
        raise ValueError('invalid listen cursor')
    return data


def _save(root, data):
    _path(root).parent.mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(_path(root), json.dumps(data, sort_keys=True) + '\n', mode=0o600)


def tick(root):
    config = workspace.load_config(root)
    now = workspace.now()
    last = watch.saved(root).get('listen_clock_at')
    if last is None or (now - obligations._time(last)).total_seconds() >= CLOCK_SECONDS:
        watch.save(root, {'listen_clock_at': now.isoformat()}, kind='listen: clock')
    data, source, code = cursor(root), config['adapters']['inbound'], 0
    result = registry.load('inbound', config).poll(data['cursors'].get(source, ''), root=root)
    if result.exit == 2 or not isinstance(result.data, list):
        print(f'listen poll unmeasured: {result.reason or "malformed data"}', flush=True)
        code = 2
    else:
        stored = inbox.store(root, config, result.data)
        if stored.exit == 2:
            print(f'listen store unmeasured: {stored.reason}', flush=True)
            code = 2
        else:
            code = int(bool(stored.data))
            if result.data:
                data['cursors'][source] = result.data[-1]['ts']
                _save(root, data)
    if config['responder']['enabled']:
        # ponytail: reads the whole inbox per tick; keep a line count when it grows large.
        count = len(inbox.read(root))
        if count > data['woken']:
            watch.mark_wake(root, inbox=count, kind='listen: wake', payload={'inbox': count})
            data['woken'] = count
            _save(root, data)
    return code


def run(root=None, *, once=False, sleep=None):
    root = workspace.find_workspace(root)
    delay = min(workspace.load_config(root)['listen']['poll_seconds'], CLOCK_SECONDS)
    return watch.serve(root, 'listen', tick, delay, once=once, sleep=sleep)
```

Order matters and is the restart-safety argument: clock, then poll, then store, then
cursor, then wake, then `woken`. Each step is idempotent on retry (store dedups; the
wake compares against the marker).

### 5. `cli/wuwei/commands/watch.py`: installer takes a name

- `add(subparsers, name, help)`: today's `register` body with `name` for the parser,
  `dest=f'{name}_action'` and the help strings; returns the parser.
- `register(subparsers)`: `add(subparsers, 'watch', 'Supervise workspace activity and
  owned PRs').set_defaults(func=run)`.
- `run(args)`: `return service(args, 'watch', watch.run)` (kept: `tests/test_env_credentials.py`
  calls it with `watch_action`).
- `service(args, name, loop)`: today's `run` body with every `watch` literal replaced by
  `name` (messages render identically for the watch), `workspace.watch_unit(root,
  platform, name=name)`, and two value changes: `'@COMMAND@': name`, and the logs
  `.wuwei/{name}.stdout.log` / `.wuwei/{name}.stderr.log`. The action is
  `getattr(args, f'{name}_action')`; no action calls `loop(once=args.once)`.

### 6. `templates/wuwei-watch.plist`, `templates/wuwei-watch.service`

Replace the literal command with `@COMMAND@`: plist
`<string>@PLUGIN_ROOT@/bin/wuwei</string><string>@COMMAND@</string>`; service
`Description=WUWEI workspace @COMMAND@` and `ExecStart="@PLUGIN_ROOT@/bin/wuwei" @COMMAND@`.
Rendered watch units are byte-identical. No new template files.

### 7. `cli/wuwei/commands/listen.py` (new, thin)

```python
"""Run or install the workspace listener."""

from wuwei import listen, workspace
from wuwei.commands import watch as service


def register(subparsers):
    service.add(subparsers, 'listen', 'Poll the inbound source into the workspace inbox'
                ).set_defaults(func=run)


def run(args):
    if (args.listen_action != 'uninstall' and
            workspace.load_config(workspace.find_workspace())['adapters']['inbound'] == 'none'):
        raise ValueError('listen could not run: adapters.inbound is "none"; configure an inbound source')
    return service.service(args, 'listen', listen.run)
```

### 8. `cli/wuwei/guards/lifecycle.py` (`session_start`, after line 37)

```python
    listen_code, message = watch.health(root, name='listen')
    if listen_code:
        code = max(code, listen_code)
        lines.append(message)
```

Off and alive are silent; the watch lines above are unchanged.

### 9. Reserved producers and signal tiers

- `cli/wuwei/guards/protect_state.py` `_OWNER_ACTIONS`: add
  `('listen', 'uninstall'): 'Listener uninstall requires the owner terminal, outside agent tools.'`
  with the same one-line comment as the watch row.
- `cli/wuwei/commands/event.py` `EVENT_PRODUCERS`: `'listen: clock': 'wuwei listen'`,
  `'listen: wake': 'wuwei listen'`.
- `cli/wuwei/signal.py` `SILENT`: add `'listen: clock'`, `'listen: wake'`.
- `cli/wuwei/state.py` `STATE_PRODUCERS['watch']`: `'wuwei watch or wuwei listen'`.

### 10. Docs

- `docs/site/configuration.md`: rows for `listen.poll_seconds`, `listen.dead_seconds`,
  `responder.enabled`; a short "Running the listener" section after "Running the watch":
  what it polls and stores, `listen install [--dry-run]` and `listen uninstall`, the
  kill switch (events stored, planner not woken), dead after `listen.dead_seconds`
  without a clock line (reported at session start), and that `adapters.inbound = "none"`
  refuses to run.
- `docs/site/concepts.md` (line 32) and `docs/site/reference.md` (Host terminal
  actions): add `wuwei listen uninstall` to the owner-only commands.

## Shared helpers reused

`inbox.store` (the only inbox writer), `registry.load` and `Result`, `watch.saved` and
`watch.save`, `watch.previous`, `obligations._time`, `state._write_state`,
`workspace.atomic_write`, `workspace.find_workspace`, `workspace.load_config`,
`workspace.now`, `registry.watch_service()` and `adapters/watch_service.py` unchanged.

## Must not change

- The watch: its label, its rendered units, its lock file, its messages, its tick and
  sweep, `status --line`, `nudges` and the cockpit. Every test in `tests/test_watch.py`
  and `tests/test_quiet_sweeps.py` passes unmodified except the added guard row.
- `adapters/watch_service.py` allowlist; `adapters/inbound/none.py`; the redactor.
- `inbox.store`'s validation, redaction and fail-closed order; only dedup is added.
- `templates/workspace/config.toml`: no new keys (defaults suffice, as in #48).
- No webhook server, no subprocess in `listen.py`, no `claude -p` launch.

## Test plan

New file `tests/test_listen.py`. Fixture: `tmp_path` workspace with `.wuwei/config.toml`
holding `[adapters]\ninbound = "fake"`, memory files as in `tests/test_watch.py` (session
start needs them), `WUWEI_WORKSPACE` and `WUWEI_NOW` set; `registry.validate` patched to
accept `fake`; `registry.load` patched to return a fake inbound
(`SimpleNamespace(poll=...)` that records each `since` and returns queued `Result`s) for
`inbound` and the real module otherwise. Events built with a helper `event(id, ts, text)`.

- dedup: `inbox.store` with a batch holding an id already stored and a repeated id
  returns the count of new events and leaves one line per `(source, id)`.
- cursor: first poll `since == ''`; after a batch the next poll gets the last `ts`; a
  fresh process (re-read from disk) gets the same; an empty poll leaves it; a failing
  poll (`Result(2, None, 'down')`) and a failing store leave it and return 2.
- restart mid-batch (acceptance 1): patch `state.append_jsonl` to raise `KeyboardInterrupt`
  on the second inbox line; `listen.tick` raises; unpatch; tick again with the same batch;
  inbox ids are exactly the batch, once each; cursor is the last `ts`.
- kill switch (acceptance 2): `[responder]\nenabled = false`: tick stores the batch, no
  `listen: wake` event, `watch.wake(root) == ''`, `woken` stays 0; set it back to true:
  one tick wakes once.
- wake: enabled tick marks `inbox` = line count; `lifecycle.session_start` shows
  `planner wake` with `inbox to line N`; `plan session planner` then `lifecycle.stop`
  consumes it once; a second tick with no new events writes no wake.
- wake crash: patch `listen._save` to raise after the wake was marked; next tick does not
  change the marker's `at` and the planner is not re-notified.
- merge: a pending unseen PR wake plus an inbox wake yields one marker with both; a PR
  poll after an unseen inbox wake keeps the inbox count.
- health (acceptance 3): `listen: clock` then advance 299 s: session start silent about
  the listener; 300 s: `listen dead`, exit 1; no clock and no unit: silent; unit file
  present (under `XDG_CONFIG_HOME` or `HOME`) and no clock: `listen dead`.
- install: `main(['listen', 'install', '--dry-run'])` prints a unit containing `listen`
  and a `wuwei-listen-` label and writes nothing; install and uninstall with a fake
  `registry.watch_service` on `linux`; the watch dry-run output is unchanged
  (`watch` command, `wuwei-` label without `listen`).
- none: config `inbound = "none"`: `main(['listen', '--once'])` and
  `main(['listen', 'install', '--dry-run'])` return 2 with the reason; `listen uninstall`
  returns 0.
- shutdown and singleton: holding `.wuwei/listen.lock` makes `listen.run(once=True)`
  return 2; a `sleep` that raises `KeyboardInterrupt` makes `run` return 0; SIGTERM from
  inside the tick finishes the tick and returns 0 without sleeping.
- reserved: `main(['event', 'listen: clock']) == 1` and the same for `listen: wake`.

Existing files: `tests/test_quiet_sweeps.py` guard table gains
`('bin/wuwei listen uninstall', 1)`; `tests/test_docs.py`
`test_host_terminal_actions_and_morning_references` gains `'listen uninstall'`;
`tests/test_workspace.py` `test_config_defaults_and_independence` gains the `listen` and
`responder` defaults. `tests/test_signal_status.py`
`test_emitted_kinds_have_intended_tiers` gains `listen: clock` and `listen: wake` as silent
(its emitted-kinds set must match exactly).

Full suite: `python -m pytest -q`.
