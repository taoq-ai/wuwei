"""Gate verdict and seat retro lifecycle checks."""

from pathlib import Path
from fnmatch import fnmatch
import re

from wuwei.exits import CLEAN, FINDINGS, UNRUN, DAMAGED, PAYLOAD
from wuwei.guards import Guard
from wuwei.verdict import RETRO_KEYS, lint_file, record_rejection, retro_fields


INTERPRETERS = ((r'(?:python|pypy)[\d.]*', 'c'), ('node', 'ep'),
                ('perl', 'eE'), ('ruby', 'e'), ('php', 'r'), ('lua', 'e'))


def required_text(payload, key, *, blank=False):
    value = payload.get(key)
    if not isinstance(value, str) or not blank and not value.strip():
        raise ValueError(f'missing or invalid {key}; {DAMAGED}')
    return value


def workspace_root(payload):
    from wuwei.workspace import find_workspace

    cwd = required_text(payload, 'cwd')
    try:
        return find_workspace(cwd)
    except FileNotFoundError:
        return None


def is_gate(path):
    return any(p.parent.name.lower() == 'decisions' and fnmatch(p.name.lower(), 'gate-*.md')
               for p in (path, path.resolve()))


def check_write(payload):
    from wuwei.workspace import day_dir, find_workspace, guard_scope

    root, path = None, '<unknown>'
    try:
        role = payload.get('agent_type', '')
        role = role.rsplit(':', 1)[-1] if isinstance(role, str) else ''
        stop = payload.get('hook_event_name') == 'SubagentStop'
        if stop and not role.startswith('sentinel-'):
            return CLEAN, ''
        root = guard_scope(payload) if stop else workspace_root(payload)
        tool_input = payload.get('tool_input')
        if root is None and payload.get('tool_name') != 'Bash' and isinstance(tool_input, dict):
            target = tool_input.get('notebook_path', tool_input.get('file_path'))
            if isinstance(target, str):
                path = Path(payload['cwd']) / target
                if is_gate(path):
                    try:
                        root = find_workspace(path.parent)
                    except FileNotFoundError:
                        pass
        if root is None:
            return CLEAN, ''
        cwd = required_text(payload, 'cwd')
        if not stop and not isinstance(tool_input, dict):
            raise ValueError(f'missing or invalid tool_input; {PAYLOAD}')
        results = []
        bash = not stop and payload.get('tool_name') == 'Bash'
        if bash:
            command = required_text(tool_input, 'command', blank=True)
            if 'gate-' not in command.lower():
                return CLEAN, ''
            path = '<opaque gate file>'
            # Refuse literal interpreter snippets without parsing shell paths.
            for program, flags in INTERPRETERS:
                if re.search(r'\b' + program + r'''["']?\s+(?:[^\n;&|]*?\s)?'''
                             r'(?:-[a-zA-Z]*[' + flags + r']|--eval(?:=|\b))', command):
                    results.append(record_rejection(path, FINDINGS,
                                   'verdict lint: opaque interpreter gate write', root=root))
                    break
        if stop:
            from wuwei.guards.agent_launch import stopping_seat
            directory, name, role = stopping_seat(payload, root)
            paths = sorted((directory / 'decisions').glob(f'[gG][aA][tT][eE]-{name}.[mM][dD]'))
        elif bash:
            paths = sorted((day_dir(root) / 'decisions').glob('[gG][aA][tT][eE]-*.[mM][dD]'))
        else:
            key = 'notebook_path' if 'notebook_path' in tool_input else 'file_path'
            paths = [Path(cwd) / required_text(tool_input, key)]
        for path in paths:
            if not is_gate(path):
                continue
            code, message = lint_file(path, role=role, root=root)
            results.append((code, f'{path}: {message}' if stop and code else message))
        return (CLEAN, '') if stop and payload.get('stop_hook_active') else (
                max((code for code, _ in results), default=CLEAN),
                '\n'.join(message for code, message in results if code))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        message = f'verdict lint: {exc}'
        return record_rejection(path, UNRUN, message, root=root) if root else (UNRUN, message)


def _light(payload, root):
    """#567: whether the stopping seat's item runs at light depth; False when unresolved."""
    from wuwei import brief, dispatch, state, workspace
    from wuwei.guards.agent_launch import stopping_seat
    try:
        try:
            directory, name, _ = stopping_seat(payload, root)
            data = state.read_state(directory=directory)
        except (OSError, ValueError, KeyError, TypeError):
            data = state.read_state(root)
            name = next((key for key, seat in brief.seats(data).items()
                         if seat.get('agent_id') == payload['agent_id']), None)
        seat = brief.seats(data)[name]
        row = data['items'][seat['item']]
        if seat['role'] == 'builder' and not (row.get('gates') or {}).get('tier'):
            # The brief's prediction saw an empty diff; judge the diff the builder leaves.
            return dispatch.tier(root, workspace.load_config(root), {'flags': {}, **row})['tier'] == 'light'
        return dispatch.depth(row, gate=seat['role'].startswith('sentinel-')) == 'light'
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        return False


def check_retro(payload, *, root=None):
    # Keep persistence imports off unrelated hooks' startup path.
    import json
    from wuwei import state, workspace

    try:
        root = workspace_root(payload) if root is None else workspace.find_workspace(root)
        if root is None:
            return CLEAN, ''
        agent_type = payload.get('agent_type')
        charters = Path(__file__).resolve().parents[3] / 'charters'
        if (not isinstance(agent_type, str)
                or agent_type.rsplit(':', 1)[-1] not in {p.stem for p in charters.glob('*.md')}):
            return CLEAN, ''
        agent_id = required_text(payload, 'agent_id')
        text = required_text(payload, 'last_assistant_message', blank=True)
        fields, missing, invalid = retro_fields(text)
        if len(missing) == len(RETRO_KEYS) and _light(payload, root):
            fields, missing = dict.fromkeys(RETRO_KEYS, 'none'), []  # #567: optional as a whole
        record = {'agent_id': agent_id, 'agent_type': agent_type, 'fields': fields,
                  'missing': missing, 'invalid': invalid}
        encoded = json.dumps(record, sort_keys=True) + '\n'
        from hashlib import sha256
        digest = sha256(encoded.encode()).hexdigest()
        directory = workspace.day_dir(root)
        evidence = directory / 'retro' / f'{digest}.json'
        evidence.parent.mkdir(parents=True, exist_ok=True)
        workspace.atomic_write(evidence, encoded)
        record['evidence'] = evidence.relative_to(root).as_posix()
        kind = 'retro.gap' if missing or invalid else 'retro.captured'
        state.append_event(kind, record, directory=directory)
        failures = [f"retro note missing '{key}:' line" for key in missing]
        failures += [f"retro note has duplicate '{key}:' lines" for key in invalid]
        if payload.get('stop_hook_active'):
            return CLEAN, ''
        return (FINDINGS, '\n'.join(failures)) if failures else (CLEAN, '')
    except (OSError, ValueError, RuntimeError) as exc:
        return UNRUN, f'retro capture: {exc}'


GUARDS = [Guard('PostToolUse', 'Write|Edit|MultiEdit|NotebookEdit|Bash', check_write),
          Guard('SubagentStop', None, check_write),
          Guard('SubagentStop', None, check_retro)]
