"""Scoped session memory, watch notices and compaction consistency checks."""

from pathlib import Path

from wuwei import memory, state, watch, workspace
from wuwei.guards import Guard


def scoped(payload):
    cwd = Path(payload['cwd'])
    if not cwd.is_absolute():
        raise ValueError('cwd must be absolute')
    return workspace.scope(cwd.resolve())


def session_start(payload):
    try:
        context = scoped(payload)
        if context is None:
            return 0, ''
        root, _ = context
    except watch.ERRORS as exc:
        return 2, f'session unmeasured: {exc}'
    code, lines = 0, []
    try:
        content, size, tokens = memory.session_payload(root)
        lines.extend([content, f'Size: {size} bytes, {tokens} estimated tokens'])
        findings = memory.lint(root)
        code = int(bool(findings))
        lines.extend(findings)
    except watch.ERRORS as exc:
        code = 2
        lines.append(f'memory unmeasured: {exc}')
    health_code, message = watch.health(root)
    code = max(code, health_code)
    if message:
        lines.append(message)
    try:
        notice = watch.wake(root)
        if notice:
            lines.append(notice)
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
    except watch.ERRORS as exc:
        code = 2
        lines.append(f'session continuity unmeasured: {exc}')
    return code, '\n'.join(lines)


def pre_compact(payload):
    try:
        context = scoped(payload)
        if context is not None:
            watch.flush(context[0])
        return 0, ''
    except watch.ERRORS as exc:
        return 2, f'compaction consistency unmeasured: {exc}'


def stop(payload):
    if payload.get('stop_hook_active'):
        return 0, ''
    try:
        context = scoped(payload)
        if context is None:
            return 0, ''
        root, _ = context
        planner = state.read_state(root).get('planner_session_id')
        if not planner or payload.get('session_id') != planner:
            return 0, ''
        message = watch.wake(root, consume=True)
        return int(bool(message)), message
    except watch.ERRORS as exc:
        return 0, f'planner wake unmeasured: {exc}'


GUARDS = [Guard('SessionStart', None, session_start),
          Guard('PreCompact', None, pre_compact), Guard('Stop', None, stop)]
