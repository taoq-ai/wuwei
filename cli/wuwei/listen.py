"""The listener: poll the inbound source into the inbox and wake the planner."""

import json
import os

from wuwei import control_plane, inbox, obligations, outward, registry, remote, shepherd, state, watch, workspace
from wuwei.exits import DAMAGED

CLOCK_SECONDS = 120
# ponytail: fixed probe interval; a 304 is free, so no config.
PROBE_SECONDS = 30


def _path(root):
    return root / '.wuwei' / 'inbox' / 'cursor.json'


def cursor(root):
    """Cursor per source, the inbox line count the last wake covered and the count handled."""
    try:
        data = json.loads(_path(root).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return {'cursors': {}, 'woken': 0}
    if not (isinstance(data, dict) and isinstance(data.get('cursors'), dict)
            and all(isinstance(k, str) and isinstance(v, str) for k, v in data['cursors'].items())
            and type(data.get('woken')) is int and data['woken'] >= 0
            and type(data.get('handled', 0)) is int and data.get('handled', 0) >= 0):
        raise ValueError(f'invalid listen cursor; {DAMAGED}')
    return data


def _save(root, data):
    _path(root).parent.mkdir(parents=True, exist_ok=True)
    workspace.atomic_write(_path(root), json.dumps(data, sort_keys=True) + '\n', mode=0o600)


AUTOSTART_OFF = 'Shepherd autostart is off; nothing started.'
FALLBACK = 'PR #{number} changed; details are on the host.'
LOOP_FALLBACK = 'Item {item} is going back and forth; details are on the host.'


def notify(root, config, waiting):
    """Send each new summarised pr.changed and negotiation.loop to the owner DM once."""
    from wuwei.pr_actions import ACTIONS
    rows = watch.records(workspace.day_dir(root) / 'events.jsonl')
    sent = {(row['payload'].get('pr'), row['payload'].get('at')) for row in rows if row['kind'] == 'pr.notified'}
    states = {ref: episode['state'] for ref, episode in waiting}
    full = workspace.verbosity(config, 'nudges') == 'full'
    for row in rows:
        ref, text = row['payload'].get('pr'), row['payload'].get('summary')
        if row['kind'] != 'pr.changed' or not isinstance(text, str) or (ref, row['ts']) in sent:
            continue
        fields = row['payload'].get('fields')
        if full and isinstance(fields, list) and fields and all(isinstance(name, str) for name in fields):
            text += f' (fields: {", ".join(fields)})'
        if ref in states:
            text += '. ' + (f'Shepherd starts: {ACTIONS[states[ref]][0]}.' if config['shepherd']['autostart']
                            else AUTOSTART_OFF)
        result = control_plane.notify(text, root=root, transport=remote.TRANSPORT)
        if result.exit == 1:
            result = remote.TRANSPORT.dm(FALLBACK.format(number=ref.split('#')[-1]), root=root)
        if result.exit:
            print(f'listen PR notify unmeasured: {result.reason}', flush=True)
            return 2
        state.append_event('pr.notified', {'pr': ref, 'at': row['ts']}, root)
    notified = {row['payload'].get('item') for row in rows if row['kind'] == 'negotiation.notified'}
    tickets = None
    for row in rows:
        item, text = row['payload'].get('item'), row['payload'].get('reason')
        if row['kind'] != 'negotiation.loop' or not isinstance(text, str) or item in notified:
            continue
        tickets = state.read_state(root).get('tickets', {}) if tickets is None else tickets
        if tickets.get(item, {}).get('id'):
            text += f" Ticket: {tickets[item]['id']}."
        result = control_plane.notify(text, root=root, transport=remote.TRANSPORT)
        if result.exit == 1:
            result = remote.TRANSPORT.dm(LOOP_FALLBACK.format(item=item), root=root)
        if result.exit:
            print(f'listen loop notify unmeasured: {result.reason}', flush=True)
            return 2
        notified.add(item)
        state.append_event('negotiation.notified', {'item': item}, root)
    return 0


def prs(root, config, tags):
    """Probe owned PRs; run the shared full read only on a change, a failed probe or the backstop."""
    try:
        host, refs = watch.owned(root, config)
        modified = False
        for ref in refs:
            result = host.probe(ref, tags.get(ref, {}), root=root)
            data = result.data if result.exit == 0 and isinstance(result.data, dict) else {}
            if type(data.get('modified')) is bool and isinstance(data.get('tags'), dict):
                modified |= data['modified']
                tags[ref] = data['tags']
            else:
                modified = True
                tags.pop(ref, None)
        last = watch.saved(root).get('poll_at')
        if not modified and last is not None and (
                workspace.now() - obligations._time(last)).total_seconds() < config['pr']['poll_seconds']:
            return 0
        if watch.poll_prs(root) == 2:
            tags.clear()
            return 2
        return 0
    except watch.ERRORS as exc:
        print(f'listen PR poll unmeasured: {exc}', flush=True)
        return 2


def tick(root, tags=None):
    """Clock, poll, store, cursor, PRs, responder, wake, in that order: each step is safe to repeat."""
    tags = {} if tags is None else tags
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
            # The cursor is an epoch watermark: every successful poll moves it to the
            # poll start, so a quiet stretch does not pin it and grow each re-read.
            start = str(int(now.timestamp()))
            last = result.data[-1]['ts'] if result.data else start
            try:
                data['cursors'][source] = max(last, start, key=float)
            except ValueError:
                data['cursors'][source] = last
            _save(root, data)
    code = max(code, prs(root, config, tags))
    if config['responder']['enabled']:
        # ponytail: reads the whole inbox per tick; keep a line count when it grows large.
        rows = inbox.read(root)
        count = len(rows)
        # Saved before acting: a crash drops a command, it never runs one twice.
        data.setdefault('handled', data['woken'])
        for index in range(data['handled'], count):
            data['handled'] = index + 1
            _save(root, data)
            if remote.handle(root, rows[index]) == 2:
                code = 2  # a refused command is a normal poll; only an unrun one is 2
        # Decisions routed on the host reach the DM here; the listener is the only DM sender.
        if os.environ.get('SLACK_OWNER_DM_CHANNEL'):
            try:
                if remote.escalate_new(root, remote.TRANSPORT) == 2:
                    code = 2
            except (OSError, UnicodeError, ValueError, KeyError, TypeError, RuntimeError) as exc:
                print(f'listen escalate unmeasured: {exc}', flush=True)
                code = 2
            try:
                if notify(root, config, shepherd.pending(root)) == 2:
                    code = 2
            except watch.ERRORS as exc:
                print(f'listen PR notify unmeasured: {exc}', flush=True)
                code = 2
        if count > data['woken']:
            watch.mark_wake(root, inbox=count, kind='listen: wake', payload={'inbox': count})
            data['woken'] = count
            _save(root, data)
        if config['shepherd']['autostart']:
            # ponytail: one blocking shepherd turn per tick, like a command turn; a background
            # process when turns outgrow the poll interval.
            try:
                waiting = shepherd.pending(root)
                if waiting and shepherd.headless(root, *waiting[0]) == 2:
                    code = 2
            except watch.ERRORS as exc:
                print(f'listen shepherd unmeasured: {exc}', flush=True)
                code = 2
    return code


def run(root=None, *, once=False, sleep=None):
    """One listener per workspace; stop cleanly on SIGTERM, SIGINT or interruption."""
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    if not config['owner']['name'].strip():
        print('listen ' + outward.OWNER_UNSET, flush=True)
    delay = min(config['listen']['poll_seconds'], CLOCK_SECONDS, PROBE_SECONDS, config['pr']['poll_seconds'])
    tags = {}  # ETags live in memory only: a restart costs one full read.
    return watch.serve(root, 'listen', lambda root: tick(root, tags), delay, once=once, sleep=sleep)
