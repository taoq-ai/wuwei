"""Register WUWEI launches on a logged brief or private prompt, with shared guards."""

import json
from pathlib import Path

from wuwei.guards import Guard, wuwei_role
from wuwei.exits import DAMAGED, PAYLOAD


def free_memory(config, root):
    from wuwei import brief, registry

    value = brief.read(registry.load('host', config).free_memory, root=root)
    if type(value) is not int or value < 0:
        raise ValueError('free memory unmeasured; retry; if it repeats, run bin/wuwei doctor, which tests the host adapter')
    return value


def free_percent(config, root):
    """#898: the share of the host free, 0-100, from the host adapter."""
    from wuwei import brief, registry

    value = brief.read(registry.load('host', config).free_percent, root=root)
    if type(value) is not int or not 0 <= value <= 100:
        raise ValueError('free memory percentage unmeasured; retry; if it repeats, run bin/wuwei doctor, which tests the host adapter')
    return value


def check(payload):
    from wuwei import brief

    try:
        return _check(payload)
    except brief.Refused as exc:
        return 1, f'seat not registered: {exc}'
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


UNRECORDED = ('no build record for {item}: a builder launches only from the action bin/wuwei build next '
              '{item} returns; run it and launch with its prompt. Work already done outside the record comes '
              'back with bin/wuwei build reconcile {item} --worktree {worktree}')


def _named_items(data, inputs):
    """All items named in Agent metadata or explicit Item: prompt lines."""
    import re
    text = '\n'.join(value for key in ('name', 'description')
                     if isinstance(value := inputs.get(key), str))
    explicit = {line.removeprefix('Item:').strip() for line in inputs.get('prompt', '').splitlines()
                if line.startswith('Item:')}
    return [item for item in data['items']
            if item in explicit or re.search(rf'(?<![\w.-]){re.escape(item)}(?![\w.-])', text)]


def _unbriefed(root, inputs, role):
    """#955: the prompt is the private brief; share the typed launch checks."""
    from wuwei import brief, registry, workspace
    from wuwei.commands.agents import ROLES

    if role not in ROLES:
        raise ValueError('unknown Agent role; use a WUWEI seat role')
    if role == 'planner':
        raise brief.Refused('planner is not an ad-hoc seat role; use the existing planner session')
    _, data = brief.read_day(root)
    config = workspace.load_config(root)
    named = _named_items(data, inputs)
    item = named[0] if len(named) == 1 else None
    current = data['items'].get(item, {})
    tree = (root / current['worktree']).resolve() if current.get('worktree') else None
    head, paths = None, []
    if tree:
        vcs = registry.load('vcs', config)
        head = brief.read(vcs.head, tree, root=root)['sha']
        repo = brief.worktree_repo(root, config, tree)
        ref = config['brief']['remote'] + '/' + repo.get('default_branch', 'main')
        base = brief.read(vcs.merge_base, tree, ref, root=root)['sha']
        changed = brief.status(vcs, tree, root) + brief.read(vcs.diff_stat, tree, base, head, root=root)
        paths = [row['path'] for row in changed]
        paths += [row['original_path'] for row in changed if row.get('original_path')]
        paths.append(tree.name + '/')
    brief.check_paths(inputs['prompt'], paths, config, current.get('track', 'SLICE'))
    return {'item': item, 'role': role, 'gate': bool(item) and role.startswith('sentinel-'),
            'worktree': str(tree) if tree else None, 'head': head}


def _adhoc(payload):
    """#676: an untyped launch in a day is an adhoc seat, labelled by wuwei seat start --adhoc
    when it recorded its prompt."""
    from wuwei import brief, sessions, state, workspace
    from wuwei.redact import redact

    inputs = payload.get('tool_input')
    if not isinstance(inputs, dict):
        return 0, ''
    root = workspace.guard_scope(payload)
    if root is None or not state.day_started(workspace.day_dir(root)):
        return 0, ''
    prompt = inputs.get('prompt')
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError(f'invalid Agent prompt; {DAMAGED}')
    kind = inputs.get('subagent_type')
    kind = kind.strip() if isinstance(kind, str) and kind.strip() else 'general-purpose'
    digest = brief.prompt_digest(prompt)
    started = [row['payload'] for row in brief.events(root)
               if row['kind'] == 'seat adhoc' and row['payload'].get('sha256') == digest]
    session = payload.get('session_id')
    event = {'role': 'adhoc', 'type': kind}

    def reserve(data):
        taken = [int(name[6:]) for name in brief.seats(data)
                 if name.startswith('adhoc-') and name[6:].isdigit()]
        name = f'adhoc-{max(taken, default=0) + 1}'
        event.update(name=name, item=name)
        data['seats'][name] = {
            'id': name, 'role': 'adhoc', 'item': name, 'type': kind,
            'label': started[-1]['role'] if started else kind,
            'launcher': (isinstance(session, str) and sessions.registered(data, session)) or 'adhoc',
            'prompt': redact(prompt.strip().splitlines()[0])[:200], 'prompt_sha256': digest,
            'status': 'running', 'started_at': workspace.now().isoformat()}
    state._write_state(reserve, root, kind='seat launched', payload=event)
    return 0, ''


NOTE = 500


def _note(prompt, relative, path, root, role):
    """#660: the planner's text around WUWEI's own launch prompt, redacted and capped."""
    from wuwei import brief, security
    from wuwei.redact import redact
    try:
        own = brief.launch_prompt(path, security.agent_path(root, role), root=root)
    except (OSError, ValueError):
        own = None
    # ponytail: a continue round's appended feedback reads as note; subtract it if noisy.
    text = (prompt.replace(own, '', 1) if own and own in prompt
            else prompt.replace(brief.REFERENCE_PREFIX + relative, '', 1))
    return redact(text.strip())[:NOTE]


def _check(payload):
    from datetime import datetime
    import hashlib
    from wuwei import brief, registry, state, workspace

    seat = _seat(payload)
    if seat is None:
        return _adhoc(payload)
    root, inputs, role = seat
    for key in ('prompt', 'description', 'subagent_type'):
        if not isinstance(inputs.get(key), str) or not inputs[key].strip():
            raise ValueError(f'invalid Agent {key}; {DAMAGED}')
    relative = brief.reference(inputs['prompt'])
    adhoc = relative is None
    directory, _ = brief.read_day(root)
    if adhoc:
        if 'agent_id' in payload:
            raise brief.Refused('a seat cannot launch an ad-hoc seat; use the seat report to return the task to the planner')
        logged, rows, note = _unbriefed(root, inputs, role), brief.events(root), ''
    else:
        path = root / relative
        if (Path(relative).is_absolute() or '..' in Path(relative).parts
                or path.parent != directory / 'briefs' or path.suffix != '.md'
                or path.resolve() != path):
            raise ValueError(f'invalid brief path; {DAMAGED}')
        if not path.exists():  # #725: its prefix is in RECORDS_FLOOR, so it always blocks
            return 2, (f'brief {path.relative_to(root)} does not exist; '
                       f'run bin/wuwei seat brief {role} <item> <name> first')
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
            raise brief.Refused('no brief logged for this launch; write the brief first with bin/wuwei seat brief, then launch with the name it returns')
        if len(matches) != 1:
            raise ValueError(f'ambiguous brief events; {DAMAGED}')
        logged, = matches
        for key in ('name', 'item', 'role'):
            brief.identifier(logged.get(key))
        if logged['name'] != path.stem or type(logged.get('gate')) is not bool:
            raise ValueError(f'invalid logged brief metadata; {DAMAGED}')
        if role != logged['role']:
            raise brief.Refused('Agent role does not match logged brief role; write the brief again with bin/wuwei seat brief, then launch with the name and role it returns')
        if 'name' in inputs and inputs['name'] != logged['name']:
            raise brief.Refused('Agent name does not match logged brief name; write the brief again with bin/wuwei seat brief, then launch with the name and role it returns')
        if hashlib.sha256(path.read_bytes()).hexdigest() != logged.get('sha256'):
            raise brief.Refused('brief modified since it was logged; write the brief again with bin/wuwei seat brief, then launch with the name and role it returns')
        note = _note(inputs['prompt'], relative, path, root, role)
    if logged.get('second_opinion'):
        raise brief.Refused('second-opinion brief runs through wuwei dispatch opinion, not Agent')
    config = workspace.load_config(root)
    runtime = registry.runtime_config(role, config, root)['adapters']['runtime']
    if role == 'builder':  # #845: a routed build runs on the runtime its record binds
        runtime = state.read_state(root).get('builds', {}).get(logged['item'], {}).get('runtime', runtime)
    registry.validate('runtime', runtime)
    if runtime != 'claude':
        raise brief.Refused(f'{role} uses {runtime.capitalize()} runtime, not Agent; start it with bin/wuwei dispatch opinion <item> or bin/wuwei build <item> <brief> <worktree>')
    available = free_memory(config, root)
    floor = config['host']['free_memory_mb'] * 1024**2
    if available < floor:
        raise brief.Refused(f'free memory {available} bytes below floor {floor}; wait for a seat to finish, or ask the owner to lower host.free_memory_mb')
    event = {'item': logged['item']}
    unrecorded = UNRECORDED.format(item=logged['item'], worktree=logged.get('worktree') or '<path>')
    def reserve(data):
        nonlocal relative, unrecorded
        if adhoc:
            # The transcript has no launch description: different items need distinct prompts.
            if any(seat['status'] == 'running' and seat['role'] == role
                   and seat.get('prompt_sha256') == brief.prompt_digest(inputs['prompt'])
                   and seat.get('launcher_session_id') == payload.get('session_id', '')
                   and not seat.get('trace_sessions') and not seat.get('agent_id')
                   and (seat['item'] if seat['item'] in data['items'] else None) != logged['item']
                   for seat in brief.seats(data).values()):
                raise brief.Refused('same prompt is awaiting binding to another item; '
                                    'add an Item: <item> line to the prompt, then retry')
            names = set(brief.seats(data)) | {path.stem for path in (directory / 'briefs').glob('adhoc-*.md')}
            taken = [int(name[6:]) for name in names
                     if name.startswith('adhoc-') and name[6:].isdigit()]
            logged['name'] = f'adhoc-{max(taken, default=0) + 1}'
            logged['item'] = logged['item'] or logged['name']
            relative = (directory / 'briefs' / (logged['name'] + '.md')).relative_to(root).as_posix()
        event.update(name=logged['name'], item=logged['item'])
        existing = brief.seats(data).get(logged['name'])
        build = data.get('builds', {}).get(logged['item'])
        # #901 (owner decision): a builder runs on its build record; with guards.enforce off the
        # seat registers as before and the hook logs the refusal (#892 continues it)
        named = _named_items(data, inputs) if adhoc and role == 'builder' else []
        if role == 'builder' and (named if adhoc else build is None):
            if named:
                item = named[0]
                unrecorded = UNRECORDED.format(item=item, worktree=data['items'][item].get('worktree') or '<path>')
            if config['guards']['enforce']:
                raise brief.Refused(unrecorded)
            event['unrecorded'] = True
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
                data, logged['item'], logged['role'].removeprefix('sentinel-'), logged['name'], root)
        if role == 'builder' and resume and not continuing:
            raise brief.Refused('resume does not match the stopped builder; resume the builder named by bin/wuwei build next <item>')
        if not continuing and (logged['name'] in brief.seats(data) or any(
                row['kind'] == 'seat launched' and row['payload'].get('name') == logged['name']
                for row in rows)):
            raise brief.Refused('brief already used for a seat launch; write a fresh brief with bin/wuwei seat brief for this launch')
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
                raise brief.Refused('worktree HEAD changed since brief was written; write the brief again with bin/wuwei seat brief, then launch with the name and role it returns')
        if logged['gate'] or not adhoc and logged['role'].startswith('sentinel-'):
            try:
                brief.gate_ready(data, logged['item'], head)
            except brief.Refused as exc:
                raise brief.Refused(str(exc) + stale_note) from exc
            tree = logged.get('worktree')
            if not isinstance(tree, str) or not tree:
                if adhoc:
                    raise ValueError(f'ad-hoc sentinel requires an item worktree; run bin/wuwei dispatch next {logged["item"]} for the next step')
                raise ValueError('gate requires a worktree; pass --worktree <path> to bin/wuwei seat brief')
            current_tree = data['items'][logged['item']].get('worktree')
            if current_tree and (root / current_tree).resolve() != Path(tree):
                raise brief.Refused('item worktree changed since brief was written; write the brief again with bin/wuwei seat brief, then launch with the name and role it returns')
            changes = brief.status(vcs, tree, root)
            if changes:
                raise brief.Refused(('gate launch on a dirty tree: ' + ', '.join(row['path'] for row in changes)
                                    + '; ask the builder to commit or discard them, then write the gate brief again'))
        running = [seat for seat in brief.seats(data).values() if seat['status'] == 'running']
        event.update(free_mib=available // 2**20, running=len(running))
        live = brief.live(data)  # #898: adhoc and handed-back seats hold no slot
        from wuwei.dispatch import host  # lazy: hook path (#346); #528: derived at launch
        from wuwei.commands.next import building, slot  # #910: the launch set's build slot count
        limits = host(root, config, running=len(live), free=available // 2**20,
                                policy=data['seat_policy'])
        cap = limits['cap']
        adhoc_builders = [seat['id'] for seat in live if seat['role'] == 'builder' and seat.get('prompt_sha256')]
        if role == 'builder' and not slot(data, logged['item'], max(0, cap - len(adhoc_builders))):
            holders = building(data) + adhoc_builders
            raise brief.Refused(f'build slots {len(holders)} at CAP {cap}: held by {", ".join(holders[:cap])}; '
                                'wait for a build to hand off, then retry' + stale_note)
        if len(live) >= limits['seats']:
            raise brief.Refused(f'running seats {len(live)} at host seat ceiling host.seats={limits["seats"]}; wait for a seat to finish, or ask the owner to raise host.seats' + stale_note)
        if adhoc:
            path = root / relative
            path.parent.mkdir(exist_ok=True)
            if path.parent.resolve() != path.parent:
                raise ValueError('brief directory must not be a symlink; use the day directory')
            workspace.atomic_write(path, inputs['prompt'], replace=False)
        data['seats'][logged['name']] = {
            'id': logged['name'], 'role': logged['role'], 'item': logged['item'],
            'brief': relative, 'head': head, 'status': 'running',
            'started_at': workspace.now().isoformat(),
        }
        if adhoc:
            data['seats'][logged['name']].update(prompt_sha256=brief.prompt_digest(inputs['prompt']),
                                                 launcher_session_id=payload.get('session_id', ''))
        if note:
            data['seats'][logged['name']]['planner_note'] = note
        from wuwei.commands import build as build_command
        if role == 'builder' and not adhoc:
            build_command.started(data, logged['item'], logged['name'], fresh=continuing and not resume)
    state._write_state(reserve, root, kind='seat launched', payload=event)
    if event.get('unrecorded'):
        return 1, (f'{unrecorded}. Seat {logged["name"]} is registered (guards.enforce is off), so bin/wuwei '
                   f'build next {logged["item"]} continues it once it stops')
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
        prompt = brief.first_prompt(transcript)
        digest = brief.prompt_digest(prompt) if prompt else None
        role = payload['agent_type'].rsplit(':', 1)[-1]
        session = f"{payload.get('session_id', '')}:{payload['agent_id']}"
        matches = []
        for directory in sorted((root / '.wuwei/days').glob('????-??-??'), reverse=True):
            if not state.day_started(directory):
                continue
            records = brief.seats(state.read_state(directory=directory))
            name = brief.adhoc_seat({'seats': records}, digest, session, role=role) if digest else None
            if name is not None and records[name]['role'] == role:
                matches.append((directory, brief.identifier(name), role))
                if records[name].get('transcript') == transcript:
                    return matches[-1]
        if len(matches) != 1:
            raise ValueError(f'SubagentStop has no unique prompt reservation; {PAYLOAD}')
        return matches[0]
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


def _stop_adhoc(payload, root):
    """#676: stop the adhoc seat of an untyped subagent, else record subagent.untraced.
    Never refuses: a blocked SubagentStop would trap the agent."""
    from wuwei import brief, state, workspace
    from wuwei.redact import redact

    if not state.day_started(workspace.day_dir(root)):
        return 0, ''
    try:
        prompt = brief.first_prompt(payload['agent_transcript_path'])
        if prompt is None:
            raise ValueError('its transcript has no prompt; run wuwei doctor')
        name = brief.adhoc_seat(state.read_state(root), brief.prompt_digest(prompt),
                                f"{payload['session_id']}:{payload['agent_id']}", role='adhoc')
        if name is None:
            raise LookupError('no adhoc seat matches its prompt; register agents with wuwei seat start --adhoc and run wuwei doctor')
        state.stop_seat(name, root, agent_id=payload.get('agent_id'))
    except Exception as exc:
        try:
            state.append_event('subagent.untraced', {
                'agent_type': redact(str(payload.get('agent_type'))),
                'agent_id': redact(str(payload.get('agent_id'))), 'reason': str(exc)}, root)
        except Exception as log_error:
            import sys
            print(f'untraced subagent could not be recorded: {log_error}', file=sys.stderr)
    return 0, ''


def _unbriefed_stop(payload, root):
    """#660: a typed stop whose readable transcript names no brief is an unbriefed adhoc seat;
    an unreadable one keeps the brief path and its #473 fallback."""
    from wuwei import brief
    try:
        if brief.transcript_reference(payload['agent_transcript_path']) is not None:
            return False
        from wuwei import state
        prompt = brief.first_prompt(payload['agent_transcript_path'])
        data = state.read_state(root)
        name = brief.adhoc_seat(data, brief.prompt_digest(prompt),
                               f"{payload.get('session_id', '')}:{payload.get('agent_id', '')}",
                               role=payload.get('agent_type', '').rsplit(':', 1)[-1]) if prompt else None
        return name is not None and data['seats'][name]['role'] == 'adhoc'
    except (OSError, ValueError, KeyError, TypeError):
        return False


def stop(payload):
    from wuwei import brief, state, workspace

    try:
        root = workspace.find_workspace(payload.get('cwd'))
    except FileNotFoundError:
        return 0, ''
    if not wuwei_role(payload.get('agent_type')) or _unbriefed_stop(payload, root):
        return _stop_adhoc(payload, root)
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
    today = directory == workspace.day_dir(root)
    try:
        if role == 'builder' and today and not reserved.get('prompt_sha256') and item in data.get('builds', {}):
            from wuwei.commands import build
            try:
                if build.stopped(item, name, payload, root=root):
                    return 0, ''
            except build.Mismatch as exc:
                return 2, f'build result could not be recorded: {exc}'  # never another agent's seat
        if reserved['status'] == 'stopped':
            return 0, ''  # repeated stop outside a continued build
        if reserved['status'] == 'running':
            brief.stop_text(payload)
        state.stop_seat(name, root, directory=directory, agent_id=payload.get('agent_id'))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        return _unrecorded(payload, root, directory, name, reserved, exc)
    return 0, ''


def _unrecorded(payload, root, directory, name, reserved, exc):
    """#473, #905: a stop whose report cannot be recorded never leaves the bound seat running;
    it stops unmeasured with the reason, and a readable report is kept for the owner. A seat
    changed since the stop read it (relaunched, or its result recorded) is left as it is."""
    from wuwei import brief, state
    if reserved['status'] != 'running':
        return 2, f'build result could not be recorded: {exc}'
    try:  # the bound agent's own words, never a payload message that may differ from them
        text = brief.tail_turn(payload['agent_transcript_path'])[0]
        report = brief.keep_report(root, directory, name, text) if text.strip() else None
    except (OSError, ValueError, KeyError, TypeError):
        report = None
    try:
        state.stop_seat(name, root, directory=directory, agent_id=payload.get('agent_id'),
                        reason=str(exc), report=report, expected=reserved)
        state.append_event('seat.result_gap', {'name': name, 'reason': str(exc)}, root, directory=directory)
    except ValueError:  # the seat changed since this stop read it: its result recorded, or relaunched
        return 2, (f'seat {name} changed during its stop (its result is recorded, or it was launched '
                   f'again); a later step failed: {exc}; run bin/wuwei next for the step')
    except Exception as error:
        return 2, f'seat {name} could not be stopped: {exc}; {error}; run bin/wuwei doctor'
    return 2, (f'seat {name} stopped unmeasured: {exc}; record its report with bin/wuwei seat stop '
               f'{name} --verdict{"" if report else " <file>"}, or run bin/wuwei seat stop {name} '
               '--unmeasured "<reason>"')


GUARDS = [Guard('PreToolUse', 'Agent', check), Guard('SubagentStop', None, stop)]
