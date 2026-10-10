"""Session registry: every Claude Code session in the workspace, with one planner."""

from datetime import datetime, time
import os
from pathlib import Path
import shlex
import sys

from wuwei import state, workspace
from wuwei.exits import PAYLOAD, DAMAGED


ROLES = ('adhoc', 'seat-host', 'remote', 'shepherd')
COUNTED = {'Stop': 'turns', 'SessionStart:compact': 'compactions'}


def count(row, hook):
    """One counting rule for the registry write and the metrics replay."""
    if hook in COUNTED:
        row[COUNTED[hook]] = row.get(COUNTED[hook], 0) + 1


def current():
    """The calling session id that SessionStart exported, or None (host terminal)."""
    value = os.environ.get('WUWEI_SESSION_ID', '').strip()
    return value or None


def caller(root, card=False):
    """#599: the exported session id, else today's planner for a caller with no terminal on
    stdin or a --card record command; None for a host terminal."""
    if (session := current()) or (sys.stdin is not None and sys.stdin.isatty() and not card):
        return session
    return state.read_state(root).get('planner_session_id')


def gate_topics(root, session_id):
    """(topics and D-n records today's planner session asked through the gate, caller is that
    planner); strict asks nothing, so the owner runs the command (#357, #354)."""
    if not session_id:
        return frozenset(), False  # before any state read: a host terminal has no session
    data = state.read_state(root)
    if session_id != data.get('planner_session_id'):
        return frozenset(), False
    if workspace.posture(workspace.load_config(root))[0] == 'strict':
        return frozenset(), True
    return frozenset(data.get('sessions', {}).get(session_id, {}).get('gate_asked', ())), True


def card_topic(card, answer):
    """#529: the gate topic of the owner's answer to a card, hashed as #493 hashes drafts."""
    from hashlib import sha256
    text = answer.strip().removesuffix(' (Recommended)').strip()
    return f'{card}={sha256(text.encode()).hexdigest()}'


def card_answered(root, card, answer):
    """The calling planner session recorded this answer on that card; never under strict."""
    return card_topic(card, answer) in gate_topics(root, caller(root))[0]


def stale_seconds(root):
    if (root / '.wuwei/config.toml').is_file():
        return workspace.load_config(root)['sessions']['stale_seconds']
    return workspace.SCHEMA['sessions']['stale_seconds'][1]


def record(data, session_id, *, hook, cwd, role=None, thread=None):
    """Upsert one registry row inside the caller's state write."""
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError(f'session id must be a nonempty string; {PAYLOAD}')
    if role is not None and role not in ROLES:
        raise ValueError(f'session role must be one of {", ".join(ROLES)}; pass one of those roles')
    registry = data.setdefault('sessions', {})
    if not isinstance(registry, dict):
        raise ValueError(f'sessions: expected object; {DAMAGED}')
    now = workspace.now().isoformat()
    row = registry.setdefault(session_id, {'role': 'adhoc', 'started': now, 'cwd': cwd})
    row.update(last_seen=now, last_hook=hook)
    count(row, hook)
    if role is not None:
        row['role'] = role
    if isinstance(thread, str) and thread.strip():
        row['thread'] = thread


def registered(data, session_id):
    """The non-seat role the registry gives a trace session, or None (#352). A subagent's
    trace id is <session>:<agent>; an adhoc row (any SessionStart) is not a registration."""
    parent = session_id.split(':', 1)[0]
    if parent == data.get('planner_session_id'):
        return 'planner'
    row = data.get('sessions', {}).get(parent)
    role = row.get('role') if isinstance(row, dict) else None
    return role if role in ROLES and role != 'adhoc' else None


def touch(root, session_id, *, hook, cwd, role=None, thread=None, env_file=None):
    """Record hook activity; never creates today's state. env_file (SessionStart only, #599)
    says whether the session id reached later Bash calls."""
    if not (workspace.day_dir(root) / 'state.json').exists():
        return None
    payload = {'session_id': session_id, 'hook': hook}
    if env_file is not None:
        payload['env_file'] = env_file
    return state._write_state(
        lambda data: record(data, session_id, hook=hook, cwd=cwd, role=role, thread=thread),
        root, reserved=False, kind='session.seen', payload=payload)


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
        raise ValueError(f'sessions and claims: expected objects; {DAMAGED}')
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
    """Hand the session id to later Bash calls through Claude Code's env file; False without one."""
    path = os.environ.get('CLAUDE_ENV_FILE')
    if path:
        with open(path, 'a', encoding='utf-8') as stream:
            stream.write(f'export WUWEI_SESSION_ID={shlex.quote(session_id)}\n')
    return bool(path)
