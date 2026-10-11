"""SessionStart: the orientation, scoped session memory and orphan seats from the last day."""

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
    code, lines = 0, []
    try:
        row = next_command.step(root)
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
    try:
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


GUARDS = [Guard('SessionStart', None, session_start)]
