"""Gate verdict and seat retro lifecycle checks."""

from pathlib import Path
from fnmatch import fnmatch
import re

from wuwei.exits import CLEAN, FINDINGS, UNRUN
from wuwei.guards import Guard
from wuwei.verdict import lint_file, record_rejection, retro_fields


INTERPRETERS = ((r'(?:python|pypy)[\d.]*', 'c'), ('node', 'ep'),
                ('perl', 'eE'), ('ruby', 'e'), ('php', 'r'), ('lua', 'e'))


def required_text(payload, key, *, blank=False):
    value = payload.get(key)
    if not isinstance(value, str) or not blank and not value.strip():
        raise ValueError(f'missing or invalid {key}')
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
    from wuwei.workspace import day_dir, find_workspace

    root, path = None, '<unknown>'
    try:
        root = workspace_root(payload)
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
        role = payload.get('agent_type', '')
        role = role.rsplit(':', 1)[-1] if isinstance(role, str) else ''
        stop = payload.get('hook_event_name') == 'SubagentStop'
        if stop and not role.startswith('sentinel-'):
            return CLEAN, ''
        if not stop and not isinstance(tool_input, dict):
            raise ValueError('missing or invalid tool_input')
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
        if stop or bash:
            paths = sorted((day_dir(root) / 'decisions').glob('[gG][aA][tT][eE]-*.[mM][dD]'))
        else:
            key = 'notebook_path' if 'notebook_path' in tool_input else 'file_path'
            paths = [Path(cwd) / required_text(tool_input, key)]
        for path in paths:
            if not is_gate(path):
                continue
            results.append(lint_file(path, role=role, root=root))
        return (CLEAN, '') if stop and payload.get('stop_hook_active') else (
                max((code for code, _ in results), default=CLEAN),
                '\n'.join(message for code, message in results if code))
    except (OSError, ValueError, RuntimeError) as exc:
        message = f'verdict lint: {exc}'
        return record_rejection(path, UNRUN, message, root=root) if root else (UNRUN, message)


def check_retro(payload):
    # Keep persistence imports off unrelated hooks' startup path.
    from hashlib import sha256
    import json
    from wuwei import state, workspace

    try:
        root = workspace_root(payload)
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
        record = {'agent_id': agent_id, 'agent_type': agent_type, 'fields': fields,
                  'missing': missing, 'invalid': invalid}
        encoded = json.dumps(record, sort_keys=True) + '\n'
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
