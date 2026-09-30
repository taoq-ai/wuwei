"""The listener: poll the inbound source into the inbox and wake the planner."""

import json

from wuwei import inbox, obligations, registry, watch, workspace

CLOCK_SECONDS = 120


def _path(root):
    return root / '.wuwei' / 'inbox' / 'cursor.json'


def cursor(root):
    """Cursor per source and the inbox line count the last wake covered."""
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
    """Clock, poll, store, cursor, wake, in that order: each step is safe to repeat."""
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
    """One listener per workspace; stop cleanly on SIGTERM, SIGINT or interruption."""
    root = workspace.find_workspace(root)
    delay = min(workspace.load_config(root)['listen']['poll_seconds'], CLOCK_SECONDS)
    return watch.serve(root, 'listen', lambda root: tick(root), delay, once=once, sleep=sleep)
