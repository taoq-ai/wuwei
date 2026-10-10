"""Synthetic probes: the watch proves the hooks still refuse, allow and answer in budget."""

import json
import os
from pathlib import Path
import time

from wuwei import integrity, registry, sessions, state, watch, workspace
from wuwei.commands.hook import HEARTBEAT_SESSION

PROBES = (  # data: order is the page order; docs/site/reference.md lists every row
    ('refused', 'hook PreToolUse refuses git push --force origin main (exit 2)'),
    ('allowed', 'hook PreToolUse allows ls -la (exit 0)'),
    ('state_write', "hook PreToolUse refuses a Write to today's state.json (exit 2)"),
    ('state', 'state.lock taken within 1 s and day state read'),
    ('integrity', 'cached integrity verdict clean and no plugin file newer than it'),
    ('config', 'config.toml loads and selected adapters have their credentials'),
    ('clocks', 'watch and listener clocks alive or off'),
    ('status_line', 'status --line exits 0 within 200 ms wall'),
    ('read_loop', 'hook PreToolUse allows a for loop over echo and cat in .wuwei (exit 0)'),
    ('git_read', 'hook PreToolUse allows git grep (exit 0)'),
    ('planner', 'planner session live, or no planner today'),
    ('memory', 'free memory at or above host.free_memory_mb'),
    ('seats', 'no seat handed back or stopped unmeasured without a recorded result'),
)
# #347: a loop the guards cannot parse but that only reads must pass every Bash guard;
# #470: the owner's echo shape, and a git read the old deploy list did not know.
READ_LOOP = 'for r in a b; do echo "### $r"; cat .wuwei/$r/report.json; done'
GIT_READ = 'git grep -n probe'
STATUS_LINE_BUDGET_MS = 200  # ponytail: one wall sample, the p95 lives in the latency benchmarks
CODES = {'ok': 0, 'degraded': 1, 'unmeasured': 2}


def _hook(root, tool, inputs):
    return ('hook', 'PreToolUse'), json.dumps({
        'session_id': HEARTBEAT_SESSION, 'transcript_path': os.devnull, 'cwd': str(root / '.wuwei'),
        'hook_event_name': 'PreToolUse', 'tool_name': tool, 'tool_input': inputs})


def _exit(result, want):
    code, line, _ = result
    if code is None:
        return 'unmeasured', 'timeout'
    if code == want:
        return 'ok', f'exit {code}'
    return 'failed', f'exit {code}' + (f': {line}' if line else '')


def _status_line(result):
    code, _, ms = result
    if code != 0:
        return _exit(result, 0)
    if ms > STATUS_LINE_BUDGET_MS:
        return 'failed', f'{ms} ms over {STATUS_LINE_BUDGET_MS} ms'
    return 'ok', f'{ms} ms'


def _state(root):
    directory = workspace.day_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with (directory / 'state.lock').open('a') as lock:
        try:
            state.lock_ex(lock, 'state.lock', timeout=1)
        except TimeoutError as exc:
            return 'failed', str(exc)
        waited = round((time.monotonic() - start) * 1000)
        try:
            state.read_state(root)
        except ValueError as exc:
            return 'failed', str(exc)
    return 'ok', f'{waited} ms'


def _integrity(root):
    result = integrity.fresh(root)
    return ('ok', 'clean') if result.exit == 0 else ('failed', result.reason)


def _config(root):
    from wuwei import env
    from wuwei.commands.config import missing
    try:
        env.load(root)  # #601: the watch is long-lived; read .wuwei/env at each beat, as doctor does
        names = missing(workspace.load_config(root))
    except ValueError as exc:  # ConfigError is one
        return 'failed', str(exc)
    return ('failed', 'missing ' + ', '.join(names)) if names else ('ok', 'complete')


def _clocks(root):
    stamps = {'watch': [], 'listen': []}
    for row in watch.records(workspace.day_dir(root) / 'events.jsonl'):
        name, _, rest = row['kind'].partition(': ')
        if rest == 'clock' and name in stamps:
            stamps[name].append(row['ts'])
    measured = {name: watch.health(root, stamps[name], name=name) for name in stamps}
    for code, result in ((1, 'failed'), (2, 'unmeasured')):
        if messages := [message for value, message in measured.values() if value == code]:
            return result, '; '.join(messages)
    return 'ok', ', '.join(f'{name} {"alive" if stamps[name] else "off"}' for name in stamps)


def _planner(root):
    data = state.read_state(root)
    planner = data.get('planner_session_id')
    if not planner:
        return 'ok', 'no planner'
    row = next((row for row in sessions.rows(data, workspace.now(), sessions.stale_seconds(root))
                if row['session_id'] == planner), None)
    if row is None:
        return 'failed', f'planner {planner} not registered'
    return ('failed' if row['stale'] or 'stopped' in row else 'ok'), f'idle {row["idle_seconds"]}s'


def _memory(root):
    from wuwei.guards.agent_launch import free_memory
    config = workspace.load_config(root)
    if config['adapters']['host'] == 'none':
        return 'unmeasured', 'host adapter none'  # the none adapter would append a nudge per call
    mib = free_memory(config, root) // 2**20
    return ('ok' if mib >= config['host']['free_memory_mb'] else 'failed'), f'{mib} MiB'


def _seats(root):
    from wuwei import brief
    names = brief.stuck(state.read_state(root))
    if not names:
        return 'ok', 'none stuck'
    return 'failed', (f'dead: {", ".join(names)}; run wuwei seat stop {names[0]} --verdict <file>, '
                      'or --unmeasured "<reason>"')


def measure(root):
    """Run every probe once: {name: {result: ok|failed|unmeasured, value}} in PROBES order."""
    root = Path(root)
    calls = [(('status', '--line'), ''),
             _hook(root, 'Bash', {'command': 'git push --force origin main'}),
             _hook(root, 'Bash', {'command': 'ls -la'}),
             _hook(root, 'Write', {'file_path': str(workspace.day_dir(root) / 'state.json'), 'content': ''}),
             _hook(root, 'Bash', {'command': READ_LOOP}),
             _hook(root, 'Bash', {'command': GIT_READ})]
    found = {}

    def during():
        # In process while the launcher calls run: the tick budget holds only when they overlap.
        for name, check in (('state', _state), ('integrity', _integrity), ('config', _config),
                            ('clocks', _clocks), ('planner', _planner), ('memory', _memory),
                            ('seats', _seats)):
            try:
                found[name] = check(root)
            except watch.ERRORS as exc:
                found[name] = 'unmeasured', str(exc)

    try:
        (status, refused, allowed, written, loop, git_read), _ = registry.watch_service().probe(calls, root / '.wuwei', during=during)
        found.update(refused=_exit(refused, 2), allowed=_exit(allowed, 0),
                     state_write=_exit(written, 2), status_line=_status_line(status),
                     read_loop=_exit(loop, 0), git_read=_exit(git_read, 0))
        # #422: the hook as the owner feels it; a timed-out call has no ms.
        timed = {name: result[2] for name, result in
                 (('refused', refused), ('allowed', allowed), ('state_write', written), ('read_loop', loop))
                 if result[0] is not None}
    except (OSError, ValueError) as exc:
        timed = {}
        if not found:
            during()
        found.update({name: ('unmeasured', str(exc)) for name in ('refused', 'allowed', 'state_write', 'status_line', 'read_loop', 'git_read')})
    return {name: {'result': found[name][0], 'value': found[name][1],
                   **({'ms': timed[name]} if name in timed else {})} for name, _ in PROBES}


def health(probes):
    results = {row['result'] for row in probes.values()}
    return 'degraded' if 'failed' in results else 'unmeasured' if 'unmeasured' in results else 'ok'


def _ping(root, status):
    from urllib.parse import urlsplit
    try:
        url = workspace.load_config(root)['watch']['ping_url']
    except workspace.ConfigError:
        return 'withheld'
    if not url:
        return 'off'
    if status != 'ok':
        return 'withheld'
    try:
        registry.watch_service().ping(url)
        return 'sent'
    except (OSError, ValueError) as exc:
        # Never the URL itself: its path and query carry the check token.
        try:
            host = urlsplit(url).hostname or 'invalid URL'
        except ValueError:
            host = 'invalid URL'
        print(f'heartbeat ping failed: {host}: {type(exc).__name__}', flush=True)
        return 'failed'


def beat(root):
    """The watch tick's step: probes, drift, page text, ping, then one heartbeat: clock record."""
    try:
        probes = measure(root)
        status = health(probes)
        prior = watch.saved(root).get('heartbeat', {}).get('probes', {})
        drift = [name for name, row in probes.items()
                 if row['result'] == 'failed' and prior.get(name, {}).get('result') == 'ok']
        first = next((name for name, row in probes.items() if row['result'] == 'failed'), None)
        page = '' if first is None else (('behaviour drift: ' if first in drift else '')
                                         + f'heartbeat {first} failed: {probes[first]["value"]}')
        record = {'health': status, 'probes': probes, 'drift': drift, 'page': page,
                  'ping': _ping(root, status)}
        changes = {'heartbeat': record}
        try:  # #659: status --line prints this when its own compute overruns its budget
            from wuwei.commands import status as line
            suffix = f' · as of {workspace.now():%H:%M}'
            changes['status_line'] = line.line(line.snapshot(workspace.day_dir(root), line=True),
                                               line.WIDTH - len(suffix)) + suffix
        except (*watch.ERRORS, RecursionError):
            pass  # no cache: status --line waits for its own compute
        watch.save(root, changes, kind='heartbeat: clock', payload=record)
        for name in drift:
            print(f'heartbeat: behaviour drift: {name}', flush=True)
        if page:
            print(page, flush=True)
        return CODES[status]
    except watch.ERRORS as exc:
        print(f'heartbeat unmeasured: {exc}', flush=True)
        return 2
