"""Require a logged brief and fresh evidence for WUWEI seats."""

from datetime import date, datetime
import json
from pathlib import Path

from wuwei.guards import Guard


def wuwei_role(agent_type):
    if not isinstance(agent_type, str):
        return False
    charters = Path(__file__).resolve().parents[3] / 'charters'
    return agent_type.startswith('wuwei:') or agent_type.rsplit(':', 1)[-1] in {
        p.stem for p in charters.glob('*.md')}


def free_memory(config, root):
    from wuwei import brief, registry

    value = brief.read(registry.load('host', config).free_memory, root=root)
    if type(value) is not int or value < 0:
        raise ValueError('free memory unmeasured')
    return value


def check(payload):
    from wuwei import brief

    try:
        return _check(payload)
    except brief.Refused as exc:
        return 1, str(exc)
    except Exception as exc:
        return 2, f'agent launch could not run: {exc}'


def _check(payload):
    import hashlib
    from wuwei import brief, registry, state, workspace

    try:
        root = workspace.find_workspace(payload.get('cwd'))
    except FileNotFoundError:
        return 0, ''
    inputs = payload.get('tool_input')
    if not isinstance(inputs, dict):
        raise ValueError('invalid tool_input')
    agent_type = inputs.get('subagent_type')
    if agent_type is None or isinstance(agent_type, str) and not agent_type.strip():
        return 0, ''
    if not isinstance(agent_type, str):
        raise ValueError('invalid Agent subagent_type')
    role = agent_type.rsplit(':', 1)[-1]
    if not wuwei_role(agent_type):
        return 0, ''
    for key in ('prompt', 'description', 'subagent_type'):
        if not isinstance(inputs.get(key), str) or not inputs[key].strip():
            raise ValueError(f'invalid Agent {key}')
    prefix = 'WUWEI brief: '
    if not inputs['prompt'].startswith(prefix):
        raise brief.Refused('no logged brief reference at start of Agent prompt')
    relative = inputs['prompt'].splitlines()[0][len(prefix):]
    directory, _ = brief.read_day(root)
    path = root / relative
    if (Path(relative).is_absolute() or '..' in Path(relative).parts
            or path.parent != directory / 'briefs' or path.suffix != '.md'
            or path.resolve() != path):
        raise ValueError('invalid brief path')
    try:
        rows = [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines()]
        if any(not isinstance(row, dict) or not isinstance(row.get('kind'), str)
               or not isinstance(row.get('payload'), dict) for row in rows):
            raise ValueError('invalid event record')
    except (OSError, ValueError) as exc:
        raise ValueError(f'events unavailable: {exc}') from exc
    matches = [row['payload'] for row in rows if row['kind'] == 'brief written'
               and row['payload'].get('path') == relative]
    if not matches:
        raise brief.Refused('no brief logged for this launch')
    if len(matches) != 1:
        raise ValueError('ambiguous brief events')
    logged, = matches
    for key in ('name', 'item', 'role'):
        brief.identifier(logged.get(key))
    if logged['name'] != path.stem or type(logged.get('gate')) is not bool:
        raise ValueError('invalid logged brief metadata')
    if role != logged['role']:
        raise brief.Refused('Agent role does not match logged brief role')
    if 'name' in inputs and inputs['name'] != logged['name']:
        raise brief.Refused('Agent name does not match logged brief name')
    if hashlib.sha256(path.read_bytes()).hexdigest() != logged.get('sha256'):
        raise brief.Refused('brief modified since it was logged')
    config = workspace.load_config(root)
    available = free_memory(config, root)
    floor = config['host']['free_memory_mb'] * 1024**2
    if available < floor:
        raise brief.Refused(f'free memory {available} bytes below floor {floor}')
    def reserve(data):
        if logged['name'] in brief.seats(data) or any(
                row['kind'] == 'seat launched' and row['payload'].get('name') == logged['name']
                for row in rows):
            raise brief.Refused('brief already used for a seat launch')
        stale = []
        for name, seat in brief.seats(data).items():
            if seat['status'] == 'running' and seat.get('started_at'):
                age = (workspace.now() - datetime.fromisoformat(seat['started_at'])).total_seconds()
                if age > config['host']['reservation_timeout_seconds']:
                    stale.append(name)
        stale_note = '; stale seat reservations: ' + ', '.join(stale) if stale else ''
        tree = logged.get('worktree')
        if tree:
            vcs = registry.load('vcs', config)
            if brief.read(vcs.head, tree, root=root)['sha'] != logged.get('head'):
                raise brief.Refused('worktree HEAD changed since brief was written')
        if logged['gate'] or logged['role'].startswith('sentinel-'):
            try:
                brief.gate_ready(data, logged['item'])
            except brief.Refused as exc:
                raise brief.Refused(str(exc) + stale_note) from exc
            tree = logged.get('worktree')
            if not isinstance(tree, str) or not tree:
                raise ValueError('gate requires a worktree')
            current_tree = data['items'][logged['item']].get('worktree')
            if current_tree and (root / current_tree).resolve() != Path(tree):
                raise brief.Refused('item worktree changed since brief was written')
            if brief.status(vcs, tree, root):
                raise brief.Refused('gate launch on a dirty tree')
        running = [seat for seat in brief.seats(data).values() if seat['status'] == 'running']
        builders = sum(seat['role'] == 'builder' for seat in running)
        if builders >= config['cap']:
            raise brief.Refused(f'running build seats {builders} at CAP {config["cap"]}' + stale_note)
        if len(running) >= config['host']['seats']:
            raise brief.Refused(f'running seats {len(running)} at host seat ceiling {config["host"]["seats"]}' + stale_note)
        data['seats'][logged['name']] = {
            'id': logged['name'], 'role': logged['role'], 'item': logged['item'],
            'brief': relative, 'head': logged.get('head'), 'status': 'running',
            'started_at': workspace.now().isoformat(),
        }
    state._write_state(reserve, root, reserved=False, kind='seat launched',
                      payload={'name': logged['name'], 'item': logged['item']})
    return 0, ''


def stop(payload):
    from wuwei import brief, state, workspace

    try:
        root = workspace.find_workspace(payload.get('cwd'))
    except FileNotFoundError:
        return 0, ''
    if not wuwei_role(payload.get('agent_type')):
        return 0, ''
    directory = None
    try:
        # Runtime IDs can repeat across days; only the transcript brief binds the stop.
        relative = brief.transcript_reference(payload['agent_transcript_path'])
        if relative is None:
            raise ValueError('SubagentStop has no brief reference')
        path = Path(relative)
        if (len(path.parts) != 5 or path.parts[:2] != ('.wuwei', 'days')
                or path.parts[3] != 'briefs' or path.suffix != '.md'
                or date.fromisoformat(path.parts[2]).isoformat() != path.parts[2]
                or (root / path).resolve() != root / path):
            raise ValueError('invalid stop brief path')
        directory = (root / path).parent.parent
        records = brief.seats(state.read_state(directory=directory))
        name = next((key for key, seat in records.items() if seat.get('brief') == relative), None)
        if name is None:
            raise ValueError('SubagentStop has no matching seat reservation')
        if records[name]['role'] != payload['agent_type'].rsplit(':', 1)[-1]:
            raise ValueError('SubagentStop role does not match seat reservation')
        role = records[name]['role']
        state.stop_seat(name, root, directory=directory)
    except Exception as exc:
        try:
            state.append_event('seat stop unmatched',
                               {'agent_id': payload.get('agent_id'), 'reason': str(exc)},
                               root, directory=directory)
        except Exception as log_error:
            import sys
            print(f'seat stop could not be recorded: {log_error}', file=sys.stderr)
        return 0, ''
    if role == 'builder' and directory == workspace.day_dir(root):
        try:
            from wuwei import dispatch
            dispatch.discovery('seat-free', root)
        except (OSError, ValueError, RuntimeError) as exc:
            try:
                state.append_event('discovery.unmeasured', {'reason': str(exc)},
                                   root, directory=directory)
            except Exception as log_error:
                import sys
                print(f'discovery failure could not be recorded: {log_error}', file=sys.stderr)
    return 0, ''


GUARDS = [Guard('PreToolUse', 'Agent', check), Guard('SubagentStop', None, stop)]
