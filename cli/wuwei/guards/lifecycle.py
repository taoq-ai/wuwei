"""SessionStart: the orientation, scoped session memory and orphan seats from the last day."""

import os
from pathlib import Path

from wuwei import sessions, state, workspace
from wuwei.guards import Guard
from wuwei.exits import PAYLOAD

# watch.ERRORS; watch and memory import inside session_start.
ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError)


def scoped(payload):
    cwd = Path(payload['cwd'])
    if not cwd.is_absolute():
        raise ValueError(f'cwd must be absolute; {PAYLOAD}')
    return workspace.scope(cwd.resolve())


def session_start(payload):
    from wuwei import memory, watch
    try:
        context = scoped(payload)
        if context is None:
            return 0, ''
        root, config = context
    except ERRORS as exc:
        return 2, f'session unmeasured: {exc}'
    from wuwei.commands import next as next_command
    code, lines, findings = 0, [], []
    try:
        row = next_command.step(root, findings=findings)
    except ERRORS as exc:
        code, row = 2, next_command._row('unmeasured', str(exc), 'wuwei doctor')
    from wuwei import specmode
    session = payload.get('session_id')
    session = session if isinstance(session, str) and session.strip() else None
    lines.append(next_command.orientation(row, config['guards']['enforce'], specmode.label(config), session))
    try:
        if session:
            sessions.export(session)
    except ERRORS as exc:
        code = 2
        lines.append(f'session id not exported: {exc}')
    try:
        # Constraints are orientation (#358), outside the memory budget.
        day = state.read_state(root)
        lines.append(memory.constraints(root, day))
        content, size, tokens = memory.session_payload(root)
        lines.extend([content, f'Size: {size} bytes, {tokens} estimated tokens'])
        budget = config['memory']['budget_tokens']
        if tokens > budget:
            code = max(code, 1)
            lines.append(f'memory: the payload exceeds memory.budget_tokens ({tokens} > {budget}); '
                         'shorten .wuwei/memory/spine.md')
    except ERRORS as exc:
        code = 2
        lines.append(f'memory unmeasured: {exc}')
    code = max(code, 2 if any(row['kind'] == 'unmeasured' for row in findings) else int(bool(findings)))
    if findings:
        lines.append('Housekeeping:')
        lines.extend(f"{row['why']}: {row['command']}" for row in findings)
    return code, '\n'.join(lines)


def stop(payload):
    """Advisory planner wake: use the same read-only next row and never spin (#949)."""
    from hashlib import sha256
    import json
    from wuwei.commands import next as next_command
    try:
        context = scoped(payload)
    except ERRORS as exc:
        return 2, f'Stop unmeasured: {exc}'
    if context is None:
        return 0, ''
    root, _ = context
    directory = workspace.day_dir(root)
    if not state.day_started(directory) or payload.get('agent_id') or os.environ.get('WUWEI_SEAT_ROLE'):
        return 0, ''
    data = state.read_state(root)
    session = payload['session_id']
    if session != data.get('planner_session_id') or data.get('close_requested'):
        return 0, ''
    rows = list(sessions._rows(root))
    if any(kind == 'day.closed' for kind, _ in rows):
        return 0, ''
    limit = workspace.load_config(root)['guards']['stop_max_blocks']
    if sum(kind == 'hook.stop_blocked' for kind, _ in rows) >= limit:
        if not any(kind == 'hook.stop_capped' for kind, _ in rows):
            state.append_event('hook.stop_capped', {'limit': limit,
                               'reason': 'Daily Stop block cap reached; planner wake is off.'},
                               root, timeout=0.05)
        return 0, ''
    last = next((row for kind, row in reversed(rows)
                 if kind == 'hook.stop_blocked' and row.get('session') == session), None)
    row = next_command.step(root)
    if row['state'] not in ('set', 'refill', 'lead', 'propose') or row.get('decision'):
        return 0, ''
    signature = sha256(json.dumps([row['state'], sorted(set(next_command.named(row)))]).encode()).hexdigest()
    if payload.get('stop_hook_active') and last and last.get('signature') == signature:
        return 0, ''
    state.append_event('hook.stop_blocked', {'session': session, 'signature': signature,
                                            'state': row['state']}, root, timeout=0.05)
    return 1, f"wuwei next: {row['state']}. Run wuwei next --json and carry out its row."


GUARDS = [Guard('SessionStart', None, session_start), Guard('Stop', None, stop)]
