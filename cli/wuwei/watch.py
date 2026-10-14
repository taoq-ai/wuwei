"""Day record readers and PR evidence helpers."""

import json
import re

from wuwei import obligations, registry, state, workspace
from wuwei.references import pull_request
from wuwei.exits import DAMAGED


ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError)


def records(path, kinds=()):
    """Read complete event records; missing streams are empty, corrupt ones fail."""
    try:
        text = path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return []
    if kinds:
        text = ''.join(line for line in text.splitlines(keepends=True)
                       if any(f'"{kind}"' in line for kind in kinds))
    return _rows(text)


def _rows(text):
    if text and not text.endswith('\n'):
        raise ValueError(f'incomplete event line; {DAMAGED}')
    rows = []
    for line in text.splitlines():
        # The decoder refuses what json.dumps(allow_nan=False) would (NaN, Infinity and
        # floats that overflow): half the cost of encoding every row again.
        row = json.loads(line, parse_constant=_not_json, parse_float=_finite)
        if (not isinstance(row, dict) or not isinstance(row.get('kind'), str)
                or not isinstance(row.get('payload'), dict)):
            raise ValueError(f'invalid event record; {DAMAGED}')
        obligations._time(row['ts'])
        rows.append(row)
    return rows


def _not_json(value):
    raise ValueError(f'Out of range float values are not JSON compliant: {value}')


def _finite(text):
    value = float(text)
    if value in (float('inf'), float('-inf')):
        _not_json(text)
    return value


def days(root):
    today = workspace.now().date().isoformat()
    return sorted((p for p in (root / '.wuwei/days').glob('*')
                   if p.is_dir() and re.fullmatch(r'\d{4}-\d{2}-\d{2}', p.name)
                   and p.name <= today), reverse=True)


# The last events text health decoded and its rows: SessionStart asks for watch health,
# and an unchanged day decodes once. Only health reads it (kinds and stamps).


def saved(root):
    value = state.read_state(root).get('watch', {})
    if not isinstance(value, dict):
        raise ValueError(f'invalid watch state; {DAMAGED}')
    return value


def save(root, changes, kind='watch: observation', payload=None):
    def update(data):
        data.setdefault('watch', {}).update(changes)
    return state._write_state(update, root, kind=kind, payload=payload)


def owned(root, config):
    data = state.read_state(root)
    host = registry.load('code_host', config)
    refs = sorted({pull_request(ref) for ref in data['raised_prs'] + data['claimed_prs']})
    return host, refs


def previous(root):
    for directory in days(root):
        if directory != workspace.day_dir(root):
            value = state.read_state(directory=directory).get('watch', {})
            if not isinstance(value, dict):
                raise ValueError(f'invalid prior watch state; {DAMAGED}')
            return value
    return {}


def evidence(host, ref, root):
    from wuwei import derive
    found = derive.listing(workspace.day_dir(root))
    row = found['pulls'].get(ref)
    repo, number = ref.rsplit('#', 1)
    if (found['repos'].get(repo) or {}).get('failed'):
        raise ValueError('PR listing is unmeasured; run wuwei next to refresh it')
    if (isinstance(row, dict) and isinstance(row.get('author'), str)
            and type(row.get('draft')) is bool and row.get('mergeable') in
            ('mergeable', 'conflicting', 'unknown') and row.get('state') == 'open'):
        pr = {'repo': repo, 'number': int(number), 'state': 'open',
              'merged': False, 'head': row.get('head'),
              'mergeable': {'mergeable': True, 'conflicting': False, 'unknown': None}[row['mergeable']],
              'author': row['author'], 'draft': row['draft'], 'branch': row.get('branch'),
              'base_sha': None, 'updated_at': (found['repos'].get(repo) or {}).get('at') or found['fetched_at']}
    else:
        pr = obligations._read(host.pr, ref, root=root)
    if (pr['state'] not in ('open', 'closed') or
            f'{pr["repo"]}#{pr["number"]}' != ref or
            not isinstance(pr['head'], str) or
            not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', pr['head']) or
            (pr['mergeable'] is not None and type(pr['mergeable']) is not bool)):
        raise ValueError(f'invalid PR evidence; {DAMAGED}')
    obligations._time(pr['updated_at'])
    reviews, threads = obligations._evidence(host, ref, root)
    checks = obligations._list(obligations._read(host.checks, ref, pr['head'], root=root))
    if pr.get('base_sha') is None and (pr['mergeable'] is None or pr['mergeable'] is False or any(
            check.get('state') == 'completed' and check.get('conclusion') not in
            ('success', 'neutral', 'skipped') for check in checks)):
        live = obligations._read(host.pr, ref, root=root)
        if live['head'] != pr['head']:
            raise ValueError('PR head moved since the cached listing; run wuwei next to refresh it')
        pr = live
    for check in checks:
        if (not isinstance(check, dict) or check.get('sha') != pr['head']
                or not isinstance(check.get('name'), str) or not check['name']
                or not isinstance(check.get('state'), str) or not check['state']
                or 'conclusion' not in check):
            raise ValueError(f'invalid checks evidence; {DAMAGED}')
    return dict(pr=pr, reviews=reviews, threads=threads, checks=checks)



def background(root, argv):
    """Run next's command in this recorded process, with no child shell."""
    import os
    import time
    from wuwei import sessions
    if argv == ['wuwei', 'pr', 'wait']:
        purpose = 'pr-wait'
    elif len(argv) == 2 and argv[0] == 'sleep' and argv[1].isascii() and argv[1].isdigit():
        purpose = 'sleep'
    else:
        raise ValueError('background accepts only wuwei pr wait or sleep seconds; run wuwei next for its command')
    config = workspace.load_config(root)
    host = registry.load('host', config)
    found = host.processes(root=root)
    if found.exit:
        raise ValueError(found.reason)
    row = found.data.get(os.getpid())
    if not row:
        raise ValueError('background process identity unmeasured; run wuwei doctor --section processes')
    state.append_event('process.started', {**row, 'purpose': purpose,
                       'session_id': sessions.current(), 'day': workspace.day_dir(root).name,
                       'started_at': workspace.now().isoformat()}, root)
    if argv[0] == 'sleep':
        time.sleep(int(argv[1]))
        return 0
    from wuwei.__main__ import main
    return main(argv[1:])


def _terminal(item):
    return (item.get('phase') in ('merged', 'parked') or item.get('status') == 'done'
            or (item.get('disposition') or {}).get('kind') == 'parked')


def housekeeping(root, *, reap=False, closing=False, orphans=False, data=None, live_waits=None):
    """Cached-state-only findings shared by next, SessionStart, doctor and close.

    Only matching process.started records authorize signals. All other cleanup is listed
    in one plain owner listing. Current seats use the existing verdict recovery path.
    """
    from datetime import datetime
    from pathlib import Path
    import shlex
    import os
    from wuwei import brief, derive, sessions
    rows, code = [], 0
    inspect = orphans or closing
    try:
        config = workspace.load_config(root)
        if config['adapters']['host'] == 'none' and not (inspect or reap):
            return 0, []
        host = registry.load('host', config)
        measured = host.processes(orphans=inspect, root=root)
        if measured.exit:
            raise ValueError(measured.reason)
        processes = measured.data
        histories = [(directory, data if data is not None and directory == workspace.day_dir(root)
                      else state.read_state(directory=directory), records(directory / 'events.jsonl',
                          ('process.started', 'process.cleanup_failed', 'process.orphan_listed', 'day.closed')))
                     for directory in days(root)]
        latest_items, pulls = {}, {}
        for directory, data, events in reversed(histories):
            latest_items.update(data['items'])
            pulls.update(derive.listing(directory)['pulls'])
        refs = {ref for _, data, _ in histories for ref in data['raised_prs'] + data['claimed_prs']}
        refs.update(item['pr'] for item in latest_items.values() if item.get('pr'))
        refs.difference_update(item['pr'] for item in latest_items.values() if item.get('pr') and _terminal(item))
        open_prs = any(pulls.get(ref, {}).get('state') not in ('merged', 'closed') for ref in refs)
        failed = {(r['payload']['pid'], r['payload']['identity'], r['payload']['command']): r['payload']['reason']
                  for _, _, events in histories for r in events if r['kind'] == 'process.cleanup_failed'}

        listed = {(r['payload']['pid'], r['payload']['identity'])
                  for directory, _, events in histories if directory == workspace.day_dir(root)
                  for r in events if r['kind'] == 'process.orphan_listed'}
        roots, trees, active = set(), {}, set()
        latest = set()
        for directory, data, events in histories:
            for name, item in data['items'].items():
                if not item.get('worktree'):
                    continue
                if not isinstance(item['worktree'], str):
                    raise ValueError(f'item {name} unmeasured: invalid worktree; run wuwei doctor')
                tree = (root / item['worktree']).resolve()
                roots.add(tree)
                if (name, tree) in latest:
                    continue
                latest.add((name, tree))
                if not _terminal(item):
                    active.add(tree)
                elif tree.is_dir():
                    trees[tree] = (name, item, directory)
        waiting, owned = False, set()
        # Oldest wait for this session and day wins. A stale PID is never ownership.
        for directory, data, events in reversed(histories):
            closed = closing or any(row['kind'] == 'day.closed' for row in events)
            for event in events:
                if event['kind'] != 'process.started' or event['payload']['purpose'] not in ('pr-wait', 'sleep', 'timer'):
                    continue
                record = event['payload']
                pid = record['pid']
                process = processes.get(pid)
                if pid == os.getpid() or not process or not all(record.get(key) and record[key] == process.get(key)
                                          for key in ('command', 'identity')):
                    continue
                if pid in owned:
                    continue
                owned.add(pid)
                item = latest_items.get(record.get('item'), {})
                failure = failed.get((pid, record['identity'], record['command']))
                if failure:
                    rows.append({'kind': 'unreaped', 'why': failure, 'command': 'wuwei doctor --section processes'})
                    continue
                reason = 'day closed' if closed else 'item finished' if _terminal(item) else ''
                if record['purpose'] == 'pr-wait':
                    obsolete = (directory != workspace.day_dir(root)
                                or record.get('day', directory.name) != workspace.day_dir(root).name
                                or record.get('session_id') != sessions.current())
                    reason = ('day closed' if closed else 'obsolete session or day' if obsolete else
                              'PRs no longer open' if not open_prs else 'duplicate pr wait' if waiting else '')
                    if not reason:
                        waiting = True
                        if live_waits is not None:
                            live_waits.append(pid)
                if reason:
                    finding = {'kind': 'process', 'why': f'pid {pid}: {reason}',
                               'command': 'wuwei next --housekeeping', 'day': directory.name}
                    if reap:
                        result = host.terminate_process(record, 1, root=root)
                        if result.exit == 0 and result.data is True:
                            state.append_event('process.reaped', {**record, 'reason': result.reason or reason, 'source_day': directory.name}, root)
                            continue
                        code = max(code, result.exit or 2)
                        finding.update({'kind': 'unreaped', 'reap_failed': True,
                                        'why': finding['why'] + ': ' + (result.reason or 'exit unconfirmed')})
                        state.append_event('process.cleanup_failed', {**record, 'reason': finding['why']}, root)
                    rows.append(finding)
            if not inspect and directory != workspace.day_dir(root):
                continue
            seats = dict(brief.seats(data))
            for item, build in data.get('builds', {}).items():
                if directory == workspace.day_dir(root) and build.get('job') and build.get('seat') not in seats:
                    seats[f'build:{item}'] = {**build, 'item': item, 'build_only': True}
            for name, seat in seats.items():
                if seat['status'] != 'running' or not seat.get('started_at'):
                    continue
                last = datetime.fromisoformat(seat['started_at']).timestamp()
                transcript = seat.get('transcript') or (seat.get('job') or {}).get('transcript')
                if transcript:
                    try:
                        last = max(last, (root / transcript).stat().st_mtime)
                    except OSError:
                        pass  # unreadable is not evidence of recent activity
                if workspace.now().timestamp() - last > config['host']['reservation_timeout_seconds']:
                    command = brief.recovery(name, seat)
                    kind = 'seat'
                    if seat.get('build_only'):
                        kind = 'build'
                        command = shlex.join(['wuwei', 'build', seat['item'], seat['brief'], seat['worktree']])
                    elif directory != workspace.day_dir(root):
                        kind, command = 'historical-seat', 'Inspect the retained day records and seat transcript; no automatic recovery.'
                    rows.append({'kind': kind, 'why': f'{name} ({directory.name}): no transcript activity since {datetime.fromtimestamp(last).isoformat()}',
                                 'command': command, 'day': directory.name, 'item': seat['item']})
        if not inspect:
            return max(code, int(bool(rows))), rows
        ancestors, pid = {os.getpid()}, processes.get(os.getpid(), {}).get('ppid', os.getppid())
        while pid > 1 and pid not in ancestors:
            ancestors.add(pid)
            pid = processes.get(pid, {}).get('ppid', 1)
        for pid, process in processes.items():
            if process.get('error'):
                code = 2
                rows.append({'kind': 'unmeasured', 'why': f'pid {pid}: {process["error"]}',
                             'command': 'wuwei doctor --section processes'})
            cwd = process.get('cwd')
            if (pid > 1 and pid not in ancestors and pid not in owned and process['ppid'] == 1 and cwd
                    and not any(Path(cwd).resolve().is_relative_to(path) for path in active)
                    and Path(cwd).resolve().is_relative_to(root.resolve())):
                if not any(Path(cwd).resolve().is_relative_to(path) for path in roots):
                    identity = (pid, process.get('identity'))
                    if identity in listed:
                        continue
                    state.append_event('process.orphan_listed', dict(zip(('pid', 'identity'), identity)), root)
                    listed.add(identity)
                rows.append({'kind': 'orphan', 'why': f'pid {pid}: {process["command"]} (cwd {cwd})',
                             'command': f'kill -TERM {pid}'})
        for tree, (name, item, directory) in trees.items():
            if tree in active:
                continue
            repo = next((repo for repo in config['repos'] if repo['name'] == item.get('repo')), None)
            repo = repo or (config['repos'][0] if len(config['repos']) == 1 else None)
            # git -C inside the tree is sufficient to identify its repository when not configured.
            base = (root / repo['path']).resolve() if repo else tree
            rows.append({'kind': 'worktree', 'why': f'{name}: finished worktree {tree}', 'day': directory.name,
                         'command': shlex.join(['git', '-C', str(base), 'worktree', 'remove', '--', str(tree)])})
    except ERRORS as exc:
        code = 2
        rows.append({'kind': 'unmeasured', 'why': f'housekeeping unmeasured: {exc}',
                     'command': 'wuwei doctor --section processes'})
    return max(code, int(bool(rows))), rows
