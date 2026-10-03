"""Scoped session memory, watch notices and compaction consistency checks."""

from pathlib import Path

from wuwei import sessions, state, workspace
from wuwei.guards import Guard

# watch.ERRORS; watch and memory import on the events that use them, not on SubagentStop.
ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError)


def scoped(payload):
    cwd = Path(payload['cwd'])
    if not cwd.is_absolute():
        raise ValueError('cwd must be absolute')
    return workspace.scope(cwd.resolve())


def _seen(root, payload, event):
    """Record hook activity in the registry; guards called directly may carry no id."""
    session_id = payload.get('session_id')
    if not isinstance(session_id, str) or not session_id.strip():
        return None
    detail = payload.get('source' if event == 'SessionStart' else 'agent_type')
    hook = f'{event}:{detail}' if isinstance(detail, str) and detail.strip() else event
    return sessions.touch(root, session_id, hook=hook, cwd=payload['cwd'])


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
    code, lines = 0, []
    try:
        row = next_command.step(root)
    except ERRORS as exc:
        code, row = 2, {'state': 'unmeasured', 'step': str(exc), 'command': 'wuwei doctor'}
    lines.append(next_command.orientation(row, workspace.posture(config)[0]))
    try:
        if isinstance(payload.get('session_id'), str) and payload['session_id'].strip():
            sessions.export(payload['session_id'])
        _seen(root, payload, 'SessionStart')
    except ERRORS as exc:
        code = 2
        lines.append(f'session registry unmeasured: {exc}')
    try:
        # Constraints are orientation (#358), outside the memory budget.
        lines.append(memory.constraints(root, state.read_state(root)))
        content, size, tokens = memory.session_payload(root)
        lines.extend([content, f'Size: {size} bytes, {tokens} estimated tokens'])
        budget = config['memory']['budget_tokens']
        if tokens > budget:
            code = max(code, 1)
            lines.append(f'memory: digests and rules exceed memory.budget_tokens ({tokens} > {budget}); '
                         'run wuwei consolidate')
        findings = memory.lint(root)
        code = max(code, int(bool(findings)))
        lines.extend(findings)
    except ERRORS as exc:
        code = 2
        lines.append(f'memory unmeasured: {exc}')
    health_code, message = watch.health(root)
    code = max(code, health_code)
    if message:
        lines.append(message)
    listen_code, message = watch.health(root, name='listen')
    if listen_code:
        code = max(code, listen_code)
        lines.append(message)
    try:
        notice = watch.wake(root)
        if notice:
            lines.append(notice)
        # Phone answers exist only for routed decisions: a day without routes skips the second
        # decode of its events (#346); health above already refused a broken events file.
        day = state.read_state(root)
        if day.get('decision_routes', {}) != {}:
            from wuwei.commands.status import attention
            lines.extend(row['reason'] for row in attention(
                workspace.day_dir(root), {**day, 'now': workspace.now().isoformat()})
                if row['source'] == 'decision.answered')
        for directory in watch.days(root):
            if directory == workspace.day_dir(root):
                continue
            seats = state.read_state(directory=directory)['seats']
            for name, seat in seats.items():
                if seat['status'] == 'running':
                    code = max(code, 1)
                    lines.append(f'orphan process candidate: {name} from {directory.name}; '
                                 'unclosed reservation, liveness unmeasured')
            break
    except ERRORS as exc:
        code = 2
        lines.append(f'session continuity unmeasured: {exc}')
    return code, '\n'.join(lines)


def pre_compact(payload):
    from wuwei import watch
    try:
        context = scoped(payload)
        if context is not None:
            watch.flush(context[0])
        return 0, ''
    except ERRORS as exc:
        return 2, f'compaction consistency unmeasured: {exc}'


def stop(payload):
    if payload.get('stop_hook_active'):
        return 0, ''
    try:
        context = scoped(payload)
        if context is None:
            return 0, ''
        root, config = context
        data = _seen(root, payload, 'Stop') or state.read_state(root)
        planner = data.get('planner_session_id')
        if not planner or payload.get('session_id') != planner:
            return 0, ''
        from wuwei import watch
        message = (watch.wake(root, consume=True)
                   or sessions.rotation(root, config, data, payload['session_id']))
        return int(bool(message)), message
    except ERRORS as exc:
        return 0, f'planner wake unmeasured: {exc}'


def subagent_stop(payload):
    try:
        context = scoped(payload)
        if context is not None:
            _seen(context[0], payload, 'SubagentStop')
        return 0, ''
    except ERRORS as exc:
        return 0, f'session registry unmeasured: {exc}'


GUARDS = [Guard('SessionStart', None, session_start),
          Guard('PreCompact', None, pre_compact), Guard('Stop', None, stop),
          Guard('SubagentStop', None, subagent_stop)]
