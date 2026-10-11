"""Write a seat's brief, record a small fix a seat found (#646), recover a stuck seat (#473),
record an ad-hoc seat's prompt before its launch (#676)."""

from pathlib import Path
import re
import sys

from wuwei import brief, sessions, state, workspace
from wuwei.exits import CLEAN, FINDINGS, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('seat', help='Brief, record, recover or stop a seat')
    actions = parser.add_subparsers(dest='action', required=True)
    write = actions.add_parser('brief', help='Write and log a seat brief')
    for name in ('role', 'item', 'name'):
        write.add_argument(name, nargs='?')
    write.add_argument('--worktree')
    write.add_argument('--pr')
    write.add_argument('--gate', action='store_true')
    write.add_argument('--track')
    body = write.add_mutually_exclusive_group()
    body.add_argument('--body', help='brief body text')
    body.add_argument('--file', help='read the brief body from PATH (- reads stdin)')
    write.set_defaults(func=run_brief)
    note = actions.add_parser('note', help='Record a small fix a seat found')
    note.add_argument('--fix', metavar='TITLE',
                      help='Record a small fix a seat found; wuwei next proposes it as an item')
    note.set_defaults(func=run_fix)
    stop = actions.add_parser('stop', help='Record a stuck seat\'s report, or stop it as unmeasured')
    stop.add_argument('name')
    how = stop.add_mutually_exclusive_group(required=True)
    how.add_argument('--verdict', metavar='FILE', help='the seat\'s report or verdict')
    how.add_argument('--unmeasured', metavar='REASON', help='one line: why no report is recorded')
    stop.set_defaults(func=run)
    start = actions.add_parser('start', help='Record an ad-hoc seat before its Agent launch (#676)')
    start.add_argument('--role', required=True, help='what the ad-hoc seat does, such as reviewer')
    start.add_argument('--adhoc', required=True, metavar='PROMPT', help='the exact prompt the Agent launch will use')
    start.set_defaults(func=start_adhoc)


def run_brief(args):
    from wuwei import dispatch
    try:
        if not all((args.role, args.item, args.name)):
            raise ValueError('expected ROLE ITEM NAME; run wuwei seat brief ROLE ITEM NAME --body TEXT')
        if args.body is not None:
            body = args.body
        elif args.file == '-':
            body = sys.stdin.read()
        elif args.file is not None:
            body = Path(args.file).read_text(encoding='utf-8')
        else:
            raise ValueError('brief body required: pass --body TEXT or --file PATH (--file - reads stdin)')
        role = 'sentinel-' + args.role if args.role in dispatch.GATE_ROLES else args.role
        path = brief.write(role, args.item, args.name, body,
                           worktree=args.worktree, pr=args.pr, gate=args.gate, track=args.track)
    except brief.Refused as exc:
        print(f'REFUSED: {exc}', file=sys.stderr)
        return 1
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei seat brief: {exc}', file=sys.stderr)
        return 2
    print(path)
    return 0


def run_fix(args):
    """#646: today's seat_findings.<id>; plan add <id> --from-finding admits it as a small item."""
    from wuwei.tracker import ABSOLUTE
    if args.fix is None:
        print('wuwei seat note: pass --fix "<title>"', file=sys.stderr)
        return UNRUN
    title = ' '.join(args.fix.split())
    words = re.findall(r'[a-z0-9]+', title.lower())
    reason = ('the title must be one line; pass --fix "<title>"' if not title or '\n' in args.fix
              else 'the title must be at most 120 characters' if len(title) > 120
              else 'the title must hold letters or digits' if not words
              else 'the title must not hold an absolute path; name the file from the repository root'
              if ABSOLUTE.search(title) else '')
    if reason:
        print(f'wuwei seat note: {reason}', file=sys.stderr)
        return FINDINGS
    ident = 'fix-' + '-'.join(words[:6])

    def update(data):
        if ident in data.get('seat_findings', {}) or ident in data['items']:
            raise state.StateError(f'{ident} is already recorded; wuwei next proposes it')
        data.setdefault('seat_findings', {})[ident] = {
            'scope': title, 'evidence': 'seat finding', 'track': 'SLICE', 'at': workspace.now().isoformat()}
    try:
        state._write_state(update, workspace.find_workspace(), kind='finding.noted',
                           payload={'id': ident, 'title': title})
    except state.StateError as exc:
        print(f'wuwei seat note: {exc}', file=sys.stderr)
        return FINDINGS
    print(ident)
    return CLEAN


def refuse(code, message):
    print(f'wuwei seat: {message}', file=sys.stderr)
    return code


def start_adhoc(args):
    """#676: record an ad-hoc seat's role and prompt digest, so its launch is labelled with it."""
    from wuwei.redact import redact
    root = workspace.find_workspace()
    brief.read_day(root)
    brief.identifier(args.role)
    if not args.adhoc.strip():
        raise ValueError('pass the agent prompt to --adhoc')
    state.append_event('seat adhoc', {'role': args.role, 'sha256': brief.prompt_digest(args.adhoc),
                                      'prompt': redact(args.adhoc.strip().splitlines()[0])[:200]}, root)
    print(f'ad-hoc {args.role} recorded; launch it with the Agent tool (subagent_type general-purpose) '
          'and this same prompt; it runs as an adhoc seat and wuwei why adhoc lists it')
    return CLEAN


def run(args):
    root = workspace.find_workspace()
    data = state.read_state(root)
    name = args.name
    seat = brief.seats(data).get(name)
    if seat is None:
        return refuse(FINDINGS, f'{name} is not a seat today; run wuwei next for the next step')
    if not (seat['status'] == 'running' or seat['status'] == 'unmeasured' and seat.get('by') != 'owner'):
        return refuse(FINDINGS, f'{name} is {seat["status"]}; nothing to stop; run wuwei next for the next step')
    if args.verdict is not None and seat['role'] == 'adhoc':
        return refuse(FINDINGS, f'{name} is an adhoc seat with no report to record; '
                      f'run wuwei seat stop {name} --unmeasured "<reason>"')
    reason = args.unmeasured
    if reason is not None and (not reason.strip() or '\n' in reason):
        return refuse(UNRUN, 'pass a one-line reason to --unmeasured')
    if sessions.current() not in (None, data.get('planner_session_id')):
        return refuse(FINDINGS, 'seat stop runs from the planner session; run it there')
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
