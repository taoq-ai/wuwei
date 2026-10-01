"""Session registry: every Claude Code session in the workspace, with one planner."""

from datetime import datetime, time
import os
from pathlib import Path
import shlex

from wuwei import state, workspace


ROLES = ('adhoc', 'seat-host', 'remote')
COUNTED = {'Stop': 'turns', 'SessionStart:compact': 'compactions'}


def count(row, hook):
    """One counting rule for the registry write and the metrics replay."""
    if hook in COUNTED:
        row[COUNTED[hook]] = row.get(COUNTED[hook], 0) + 1


def current():
    """The calling session id that SessionStart exported, or None (host terminal)."""
    value = os.environ.get('WUWEI_SESSION_ID', '').strip()
    return value or None


def stale_seconds(root):
    if (root / '.wuwei/config.toml').is_file():
        return workspace.load_config(root)['sessions']['stale_seconds']
    return workspace.SCHEMA['sessions']['stale_seconds'][1]


def record(data, session_id, *, hook, cwd, role=None, thread=None):
    """Upsert one registry row inside the caller's state write."""
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError('session id must be a nonempty string')
    if role is not None and role not in ROLES:
        raise ValueError(f'session role must be one of {", ".join(ROLES)}')
    registry = data.setdefault('sessions', {})
    if not isinstance(registry, dict):
        raise ValueError('sessions: expected object')
    now = workspace.now().isoformat()
    row = registry.setdefault(session_id, {'role': 'adhoc', 'started': now, 'cwd': cwd})
    row.update(last_seen=now, last_hook=hook)
    count(row, hook)
    if role is not None:
        row['role'] = role
    if isinstance(thread, str) and thread.strip():
        row['thread'] = thread


def touch(root, session_id, *, hook, cwd, role=None, thread=None):
    """Record hook activity; never creates today's state."""
    if not (workspace.day_dir(root) / 'state.json').exists():
        return None
    return state._write_state(
        lambda data: record(data, session_id, hook=hook, cwd=cwd, role=role, thread=thread),
        root, reserved=False, kind='session.seen', payload={'session_id': session_id, 'hook': hook})


def _due(row, limits, zone):
    """The rotate_after reason this row has reached, or None."""
    for key in ('turns', 'compactions'):
        if limits[key] and row.get(key, 0) >= limits[key]:
            return f'{key} {row.get(key, 0)} >= {limits[key]}'
    if limits['clock']:
        clock = time.fromisoformat(limits['clock'])
        now = workspace.now().astimezone(zone)
        boundary = datetime.combine(now.date(), clock, now.tzinfo)
        if datetime.fromisoformat(row['started']).astimezone(zone) < boundary <= now:
            return f'clock {clock:%H:%M}'
    return None


def rotation(root, config, data, session_id):
    """Block once with the take-over instruction when rotate_after is due at a clean boundary."""
    row = data.get('sessions', {}).get(session_id)
    limits = config['sessions']['rotate_after']
    if row is None or 'rotated' in row or not any(limits.values()):
        return ''
    reason = _due(row, limits, workspace.zone(config))
    if (reason is None
            or any(seat.get('status') == 'running' for seat in data['seats'].values())
            or any(build.get('status') in ('running', 'check')
                   for build in data.get('builds', {}).values())):
        return ''
    from wuwei.decision import answered
    if any(answered(data, ident) is None for ident in data.get('decision_routes', {})):
        return ''
    payload = {'session_id': session_id, 'reason': reason,
               'turns': row.get('turns', 0), 'compactions': row.get('compactions', 0)}
    state._write_state(lambda fresh: fresh['sessions'][session_id].update(
        rotated=workspace.now().isoformat()), root, reserved=False, kind='session.rotated',
        payload=payload)
    return (f'planner rotation due ({reason}): finish this turn and end this session. Start a '
            'fresh Claude Code session in this workspace and run there: '
            'wuwei plan session "$WUWEI_SESSION_ID" --take-over. Goals, plan, decisions and '
            'briefs live in .wuwei/ and load at its SessionStart.')


def rows(data, now, stale):
    registry, claims = data.get('sessions', {}), data.get('claims', {})
    if not isinstance(registry, dict) or not isinstance(claims, dict):
        raise ValueError('sessions and claims: expected objects')
    result = []
    for session_id, row in registry.items():
        started, seen = (datetime.fromisoformat(row[key]) for key in ('started', 'last_seen'))
        idle = int((now - seen).total_seconds())
        result.append({'session_id': session_id,
                       'role': 'planner' if session_id == data.get('planner_session_id') else row['role'],
                       'started': row['started'], 'last_seen': row['last_seen'],
                       'age_seconds': int((now - started).total_seconds()),
                       'idle_seconds': idle, 'stale': idle >= stale,
                       'last_hook': row.get('last_hook'),
                       'items': sorted(item for item, holder in claims.items() if holder == session_id),
                       'cwd': row.get('cwd'), 'turns': row.get('turns', 0),
                       'compactions': row.get('compactions', 0),
                       **{key: row[key] for key in ('thread', 'stopped', 'rotated') if key in row}})
    return sorted(result, key=lambda row: row['started'])


def claim(data, item, session_id, now, stale, *, cwd):
    """Refuse an item another live session holds; otherwise record the caller as holder."""
    live = {row['session_id'] for row in rows(data, now, stale) if not row['stale']}
    holder = data.get('claims', {}).get(item)
    if holder in live and holder != session_id:
        raise ValueError(f'{item} is claimed by live session {holder}; brief it from that session '
                         f'or wait until it is stale ({stale}s without hook activity)')
    if session_id is not None:
        data.setdefault('claims', {})[item] = session_id
        record(data, session_id, hook=f'claim {item}', cwd=cwd)


def claim_item(root, item):
    """Claim an item for the calling session in its own write (worktree add)."""
    session_id = current()
    return state._write_state(
        lambda data: claim(data, item, session_id, workspace.now(), stale_seconds(root),
                           cwd=str(Path.cwd())),
        root, reserved=False, kind='item.claimed', payload={'item': item, 'session': session_id})


def export(session_id):
    """Hand the session id to later Bash calls through Claude Code's env file."""
    path = os.environ.get('CLAUDE_ENV_FILE')
    if path:
        with open(path, 'a', encoding='utf-8') as stream:
            stream.write(f'export WUWEI_SESSION_ID={shlex.quote(session_id)}\n')
