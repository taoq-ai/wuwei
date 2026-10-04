"""Recover a stuck seat: record its report from a file, or stop it as unmeasured (#473)."""

import sys

from wuwei import brief, integrity, sessions, state, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('seat', help='Recover a stuck seat')
    actions = parser.add_subparsers(dest='action', required=True)
    stop = actions.add_parser('stop', help='Record a stuck seat\'s report, or stop it as unmeasured')
    stop.add_argument('name')
    how = stop.add_mutually_exclusive_group(required=True)
    how.add_argument('--verdict', metavar='FILE', help='the seat\'s report or verdict')
    how.add_argument('--unmeasured', metavar='REASON', help='one line: why no report is recorded')
    stop.set_defaults(func=run)


def refuse(code, message):
    print(f'wuwei seat: {message}', file=sys.stderr)
    return code


def run(args):
    root = workspace.find_workspace()
    data = state.read_state(root)
    name = args.name
    seat = brief.seats(data).get(name)
    if seat is None:
        return refuse(FINDINGS, f'{name} is not a seat today; run wuwei next for the next step')
    if not (seat['status'] == 'running' or seat['status'] == 'unmeasured' and seat.get('by') != 'owner'):
        return refuse(FINDINGS, f'{name} is {seat["status"]}; nothing to stop; run wuwei next for the next step')
    reason = args.unmeasured
    if reason is not None and (not reason.strip() or '\n' in reason):
        return refuse(UNRUN, 'pass a one-line reason to --unmeasured')
    if workspace.posture(workspace.load_config(root))[0] == 'strict':
        try:
            if not integrity._host_confirm(name, prompt=f'Stop seat {name}.'):
                return refuse(FINDINGS, 'seat stop declined; rerun it in a host terminal and answer y')
        except OSError as exc:
            return refuse(UNRUN, f'{exc}; rerun wuwei seat stop there')
    elif sessions.current() not in (None, data.get('planner_session_id')):
        return refuse(FINDINGS, 'seat stop runs from the planner session or a host terminal; run it there')
    if reason is not None:
        state.stop_seat(name, root, reason=reason.strip(), by='owner')
        record = data.get('builds', {}).get(seat['item'])
        if seat['role'] == 'builder' and record and record.get('seat') == name and record['status'] == 'running':
            from wuwei.commands import build
            build._park(root, seat['item'], dict(record), f'seat {name} stopped unmeasured: {reason.strip()}', record)
        print(f'seat {name} stopped unmeasured')
        return CLEAN
    return stop_with_report(root, data, name, seat, args.verdict)


def stop_with_report(root, data, name, seat, path):
    """Run the registered SubagentStop guards on the stop the hook would have seen."""
    import json
    from pathlib import Path
    import tempfile
    from wuwei.guards import SELECTION, discover

    text = Path(path).read_text(encoding='utf-8')
    role = seat['role']
    if role.startswith('sentinel-'):
        from wuwei import verdict
        code, message = verdict.lint_file(path, role=role, root=root)
        if code:
            return refuse(code, message)
    record = data.get('builds', {}).get(seat['item']) or {}
    traced = seat.get('trace_sessions') or ['']
    agent_id = (record.get('agent_id') if record.get('seat') == name else None) or seat.get('agent_id') \
        or traced[-1].rpartition(':')[2] or name
    with tempfile.TemporaryDirectory() as directory:
        transcript = Path(directory) / 'agent.jsonl'
        transcript.write_text(
            json.dumps({'type': 'user', 'message': {'content': brief.REFERENCE_PREFIX + seat['brief']}}) + '\n'
            + json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': text}]}}) + '\n',
            encoding='utf-8')
        payload = {'hook_event_name': 'SubagentStop', 'cwd': str(root), 'stop_hook_active': False,
                   'agent_type': 'wuwei:' + role, 'agent_id': agent_id,
                   'agent_transcript_path': str(transcript), 'last_assistant_message': text}
        token = SELECTION.set(('SubagentStop', ''))
        try:
            guards = [guard for guard in discover() if guard.event == 'SubagentStop']
        finally:
            SELECTION.reset(token)
        results = [guard.check(payload) for guard in guards]
    code = max((result[0] for result in results), default=CLEAN)
    for result_code, message in results:
        if message:
            print(message, file=sys.stderr if result_code else sys.stdout)
    if not code:
        print(f'seat {name} stopped with its report recorded')
    return code
