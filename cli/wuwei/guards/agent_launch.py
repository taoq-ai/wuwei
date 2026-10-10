"""Require a logged brief and fresh evidence for WUWEI seats."""

import json
from pathlib import Path

from wuwei.guards import Guard, wuwei_role  # noqa: F401 (decision.py imports it from here)
from wuwei.exits import DAMAGED, PAYLOAD


def free_memory(config, root):
    from wuwei import brief, registry

    value = brief.read(registry.load('host', config).free_memory, root=root)
    if type(value) is not int or value < 0:
        raise ValueError('free memory unmeasured; retry; if it repeats, run bin/wuwei doctor, which tests the host adapter')
    return value


def check(payload):
    from wuwei import brief

    try:
        return _check(payload)
    except brief.Refused as exc:
        return 1, str(exc)
    except Exception as exc:
        return 2, f'agent launch could not run: {exc}'


def check_mcp(payload):
    """The MCP launch gate (#325) as its own record: mcp.cached applies the mcp posture and
    its floor (#331), so the seats level never relaxes it."""
    try:
        seat = _seat(payload)
        if seat is None:
            return 0, ''
        from wuwei import mcp
        measured = mcp.cached(seat[0])
        return measured.exit, measured.reason
    except Exception as exc:
        return 2, f'agent launch could not run: {exc}'


def _seat(payload):
    """(root, tool_input, role) for a WUWEI seat launch in a workspace, else None."""
    from wuwei import workspace

    inputs = payload.get('tool_input')
    if isinstance(inputs, dict):
        agent_type = inputs.get('subagent_type')
        if agent_type is None or isinstance(agent_type, str) and not wuwei_role(agent_type):
            return None
    root = workspace.guard_scope(payload)
    if root is None:
        return None
    inputs = payload.get('tool_input')
    if not isinstance(inputs, dict):
        raise ValueError(f'invalid tool_input; {PAYLOAD}')
    agent_type = inputs.get('subagent_type')
    if agent_type is None or isinstance(agent_type, str) and not agent_type.strip():
        return None
    if not isinstance(agent_type, str):
        raise ValueError(f'invalid Agent subagent_type; {DAMAGED}')
    if not wuwei_role(agent_type):
        return None
    return root, inputs, agent_type.rsplit(':', 1)[-1]


def _check(payload):
    from datetime import datetime
    import hashlib
    from wuwei import brief, registry, state, workspace

    seat = _seat(payload)
    if seat is None:
        return 0, ''
    root, inputs, role = seat
    for key in ('prompt', 'description', 'subagent_type'):
        if not isinstance(inputs.get(key), str) or not inputs[key].strip():
            raise ValueError(f'invalid Agent {key}; {DAMAGED}')
    prefix = brief.REFERENCE_PREFIX
    if not inputs['prompt'].startswith(prefix):
        raise brief.Refused('no logged brief reference at start of Agent prompt; '
                            f'write this first line: {prefix}<relative brief path>')
    relative = inputs['prompt'].splitlines()[0][len(prefix):]
    directory, _ = brief.read_day(root)
    path = root / relative
    if (Path(relative).is_absolute() or '..' in Path(relative).parts
            or path.parent != directory / 'briefs' or path.suffix != '.md'
            or path.resolve() != path):
        raise ValueError(f'invalid brief path; {DAMAGED}')
    try:
        rows = [json.loads(line) for line in (directory / 'events.jsonl').read_text().splitlines()]
        if any(not isinstance(row, dict) or not isinstance(row.get('kind'), str)
               or not isinstance(row.get('payload'), dict) for row in rows):
            raise ValueError(f'invalid event record; {DAMAGED}')
    except (OSError, ValueError) as exc:
        raise ValueError(f'events unavailable: {exc}') from exc
    matches = [row['payload'] for row in rows if row['kind'] == 'brief written'
               and row['payload'].get('path') == relative]
    if not matches:
        raise brief.Refused('no brief logged for this launch; write the brief first with bin/wuwei brief, then launch with the name it returns')
    if len(matches) != 1:
        raise ValueError(f'ambiguous brief events; {DAMAGED}')
    logged, = matches
    for key in ('name', 'item', 'role'):
        brief.identifier(logged.get(key))
    if logged['name'] != path.stem or type(logged.get('gate')) is not bool:
        raise ValueError(f'invalid logged brief metadata; {DAMAGED}')
    if role != logged['role']:
        raise brief.Refused('Agent role does not match logged brief role; write the brief again with bin/wuwei brief, then launch with the name and role it returns')
    if 'name' in inputs and inputs['name'] != logged['name']:
        raise brief.Refused('Agent name does not match logged brief name; write the brief again with bin/wuwei brief, then launch with the name and role it returns')
    if hashlib.sha256(path.read_bytes()).hexdigest() != logged.get('sha256'):
        raise brief.Refused('brief modified since it was logged; write the brief again with bin/wuwei brief, then launch with the name and role it returns')
    if logged.get('second_opinion'):
        raise brief.Refused('second-opinion brief runs through wuwei dispatch opinion, not Agent')
    config = workspace.load_config(root)
    runtime = registry.runtime_config(role, config, root)['adapters']['runtime']
    registry.validate('runtime', runtime)
    if runtime != 'claude':
        raise brief.Refused(f'{role} uses {runtime.capitalize()} runtime, not Agent; start it with bin/wuwei dispatch opinion <item> or bin/wuwei build <item> <brief> <worktree>')
    available = free_memory(config, root)
    floor = config['host']['free_memory_mb'] * 1024**2
    if available < floor:
        raise brief.Refused(f'free memory {available} bytes below floor {floor}; wait for a seat to finish, or ask the owner to lower host.free_memory_mb')
    event = {'name': logged['name'], 'item': logged['item']}
    def reserve(data):
        existing = brief.seats(data).get(logged['name'])
        build = data.get('builds', {}).get(logged['item'])
        resume = inputs.get('resume')
        stopped = bool(existing) and existing['status'] == 'stopped'
        # #614: Claude Code's Agent has no resume, so a fresh launch without one binds the
        # pending continue of the brief's own stopped seat; with resume it must still match.
        if role == 'builder':
            continuing = (stopped and bool(build) and build['status'] == 'ready'
                          and build['action']['action'] == 'continue'
                          and build.get('seat') == logged['name']
                          and (not resume or build.get('agent_id') == resume))
        elif resume or not stopped:
            continuing = stopped and existing.get('agent_id') == resume
        else:
            from wuwei import dispatch  # lazy: hook path (#346), only for a brief reuse
            continuing = dispatch.delta_due(
                data, logged['item'], logged['role'].removeprefix('sentinel-'), logged['name'])
        if role == 'builder' and resume and not continuing:
            raise brief.Refused('resume does not match the stopped builder; resume the builder named by bin/wuwei build next <item>')
        if not continuing and (logged['name'] in brief.seats(data) or any(
                row['kind'] == 'seat launched' and row['payload'].get('name') == logged['name']
                for row in rows)):
            raise brief.Refused('brief already used for a seat launch; write a fresh brief with bin/wuwei brief for this launch')
        stale = []
        for name, seat in brief.seats(data).items():
            if seat['status'] == 'running' and seat.get('started_at'):
                age = (workspace.now() - datetime.fromisoformat(seat['started_at'])).total_seconds()
                if age > config['host']['reservation_timeout_seconds']:
                    stale.append(name)
        stale_note = '; stale seat reservations: ' + ', '.join(stale) if stale else ''
        tree = logged.get('worktree')
        head = logged.get('head')
        if tree:
            vcs = registry.load('vcs', config)
            head = brief.read(vcs.head, tree, root=root)['sha']
            if not continuing and head != logged.get('head'):
                raise brief.Refused('worktree HEAD changed since brief was written; write the brief again with bin/wuwei brief, then launch with the name and role it returns')
        if logged['gate'] or logged['role'].startswith('sentinel-'):
            try:
                brief.gate_ready(data, logged['item'])
            except brief.Refused as exc:
                raise brief.Refused(str(exc) + stale_note) from exc
            tree = logged.get('worktree')
            if not isinstance(tree, str) or not tree:
                raise ValueError('gate requires a worktree; pass --worktree <path> to bin/wuwei brief')
            current_tree = data['items'][logged['item']].get('worktree')
            if current_tree and (root / current_tree).resolve() != Path(tree):
                raise brief.Refused('item worktree changed since brief was written; write the brief again with bin/wuwei brief, then launch with the name and role it returns')
            changes = brief.status(vcs, tree, root)
            if changes:
                raise brief.Refused(('gate launch on a dirty tree: ' + ', '.join(row['path'] for row in changes)
                                    + '; ask the builder to commit or discard them, then write the gate brief again'))
        running = [seat for seat in brief.seats(data).values() if seat['status'] == 'running']
        event.update(free_mib=available // 2**20, running=len(running))
        builders = sum(seat['role'] == 'builder' for seat in running)
        from wuwei import calibrate  # lazy: hook path (#346); #528: derived at launch
        limits = calibrate.host(root, config, running=len(running), free=available // 2**20,
                                policy=data['seat_policy'])
        if role == 'builder' and builders >= limits['cap']:
            raise brief.Refused(f'running build seats {builders} at CAP {limits["cap"]}; wait for a build seat to finish, then retry' + stale_note)
        if len(running) >= limits['seats']:
            raise brief.Refused(f'running seats {len(running)} at host seat ceiling host.seats={limits["seats"]}; wait for a seat to finish, or ask the owner to raise host.seats' + stale_note)
        if logged['item'] in data['items']:
            from wuwei import tracker  # lazy: hook path (#346)
            status, reason = tracker.check(data, config, logged['item'], data['items'][logged['item']])
            if status == 'missing':
                raise brief.Refused(reason)
        data['seats'][logged['name']] = {
            'id': logged['name'], 'role': logged['role'], 'item': logged['item'],
            'brief': relative, 'head': head, 'status': 'running',
            'started_at': workspace.now().isoformat(),
        }
        from wuwei.commands import build as build_command
        if role == 'builder':
            build_command.started(data, logged['item'], logged['name'], fresh=continuing and not resume)
    state._write_state(reserve, root, reserved=False, kind='seat launched', payload=event)
    return 0, ''


def stopping_seat(payload, root):
    """Resolve a stop to its registered seat and original day."""
    from datetime import date
    from wuwei import brief, state, workspace

    # Runtime IDs can repeat across days; only the transcript brief binds the stop.
    transcript = payload.get('agent_transcript_path')
    if not isinstance(transcript, str) or not transcript.strip():
        raise ValueError(f'missing or invalid agent_transcript_path; {PAYLOAD}')
    try:
        relative = brief.transcript_reference(transcript)
    except OSError:
        # #473: a missing transcript binds through the path the trace hook recorded on the seat.
        directory = workspace.day_dir(root)
        role = payload['agent_type'].rsplit(':', 1)[-1]
        name = next((key for key, seat in brief.seats(state.read_state(directory=directory)).items()
                     if seat['status'] == 'running' and seat.get('transcript') == transcript
                     and seat['role'] == role), None)
        if name is None:
            raise
        return directory, brief.identifier(name), role
    if relative is None:
        raise ValueError(f'SubagentStop has no brief reference; {PAYLOAD}')
    path = Path(relative)
    if (len(path.parts) != 5 or path.parts[:2] != ('.wuwei', 'days')
            or path.parts[3] != 'briefs' or path.suffix != '.md'
            or date.fromisoformat(path.parts[2]).isoformat() != path.parts[2]
            or (root / path).resolve() != root / path):
        raise ValueError(f'invalid stop brief path; {PAYLOAD}')
    directory = (root / path).parent.parent
    records = brief.seats(state.read_state(directory=directory))
    name = next((key for key, seat in records.items() if seat.get('brief') == relative), None)
    if name is None:
        raise ValueError(f'SubagentStop has no matching seat reservation; {PAYLOAD}')
    if records[name]['role'] != payload['agent_type'].rsplit(':', 1)[-1]:
        raise ValueError(f'SubagentStop role does not match seat reservation; {PAYLOAD}')
    role = records[name]['role']
    return directory, brief.identifier(name), role


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
        directory, name, role = stopping_seat(payload, root)
        data = state.read_state(directory=directory)
        reserved = brief.seats(data)[name]
        item = reserved['item']
    except Exception as exc:
        try:
            state.append_event('seat stop unmatched',
                               {'agent_id': payload.get('agent_id'), 'reason': str(exc)},
                               root, directory=directory)
        except Exception as log_error:
            import sys
            print(f'seat stop could not be recorded: {log_error}', file=sys.stderr)
        return 0, ''
    # #516: a stop of today's seat records the session row in its own write; lifecycle then skips its touch.
    from wuwei.guards.lifecycle import RECORDED, seen_row
    today = directory == workspace.day_dir(root)
    session = seen_row(payload, 'SubagentStop') if today else None
    try:
        if reserved['status'] == 'running':
            brief.stop_text(payload)
    except (OSError, ValueError) as exc:
        # #473: an unreadable report never leaves the seat running; the owner records it or stops it.
        # A refused stop (another agent, a resumed iteration) still leaves the seat as it was.
        try:
            state.stop_seat(name, root, directory=directory, agent_id=payload.get('agent_id'),
                            reason=str(exc), session=session)
            if session:
                payload[RECORDED] = str(root.resolve())
        except Exception as error:
            return 2, f'seat {name} could not be stopped: {exc}; {error}; run bin/wuwei doctor'
        return 2, (f'seat {name} stopped unmeasured: {exc}; record its report with bin/wuwei seat stop '
                   f'{name} --verdict <file>, or run bin/wuwei seat stop {name} --unmeasured "<reason>"')
    try:
        handled = False
        if role == 'builder' and today and item in data.get('builds', {}):
            from wuwei.commands import build
            handled = build.stopped(item, name, payload, root=root)
        if not handled:
            state.stop_seat(name, root, directory=directory, agent_id=payload.get('agent_id'), session=session)
            if session:
                payload[RECORDED] = str(root.resolve())
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        return 2, f'build result could not be recorded: {exc}'
    if payload.get('stop_hook_active'):
        return 0, ''
    if role == 'builder' and today:
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
            return 2, f'discovery unmeasured: {exc}'
    return 0, ''


GUARDS = [Guard('PreToolUse', 'Agent', check_mcp), Guard('PreToolUse', 'Agent', check),
          Guard('SubagentStop', None, stop)]
