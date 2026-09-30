"""The listener: poll the inbound source into the inbox and wake the planner."""

import json

from wuwei import inbox, obligations, outward, registry, remote, watch, workspace

CLOCK_SECONDS = 120


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
            # The cursor is an epoch watermark: every successful poll moves it to the
            # poll start, so a quiet stretch does not pin it and grow each re-read.
            start = str(int(now.timestamp()))
            last = result.data[-1]['ts'] if result.data else start
            try:
                data['cursors'][source] = max(last, start, key=float)
            except ValueError:
                data['cursors'][source] = last
            _save(root, data)
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
        if count > data['woken']:
            watch.mark_wake(root, inbox=count, kind='listen: wake', payload={'inbox': count})
            data['woken'] = count
            _save(root, data)
    return code


def run(root=None, *, once=False, sleep=None):
    """One listener per workspace; stop cleanly on SIGTERM, SIGINT or interruption."""
    root = workspace.find_workspace(root)
    config = workspace.load_config(root)
    if not config['owner']['name'].strip():
        print('listen ' + outward.OWNER_UNSET, flush=True)
    delay = min(config['listen']['poll_seconds'], CLOCK_SECONDS)
    return watch.serve(root, 'listen', lambda root: tick(root), delay, once=once, sleep=sleep)
