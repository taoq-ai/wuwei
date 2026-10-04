"""Where the day stands and the one next step, read from the day's files only."""

import json
import os
import re
import sys

from wuwei import brief, integrity, state, workspace
from wuwei.decision import answered
from wuwei.exits import CLEAN, UNRUN, DAMAGED

HEADER = 'WUWEI orientation'
TERMINAL = ('merged', 'parked', 'escalated')
POSTURES = {
    'observe': ('Observe posture is on: guards record what they would refuse and let the call '
                'through. Records (state, events, config, verdicts, decisions) and owner-only actions '
                '(deploys, merges, approvals, approve-tier messages) still refuse. bin/wuwei shadow '
                'report lists the would-be refusals.'),
    'guarded': ('Posture guarded: records, publishing and plugin integrity block; seat launches, '
                'outward text and MCP findings below the floor warn. A refusal names its reason and '
                'the accepted form: use that form, never a way around it.'),
    'strict': ('Posture strict: every guard area blocks. A refusal names its reason and the '
               'accepted form: use that form, never a way around it.'),
}
ERRORS = (OSError, ValueError, KeyError, TypeError, UnicodeError)
EXECUTABLE = ('wuwei is the absolute path in .wuwei/executable: read it once and use it as the '
              'first word of a plain command, never through a variable')


def register(subparsers):
    parser = subparsers.add_parser('next', help='Print where the day stands and the one next step')
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)


def _row(name, text, command):
    return {'state': name, 'step': text, 'command': command}


def approved(data):
    """Approved items in queue order, less those a seat decision carried or parked."""
    disposed = {str(record.get('item_disposition')).split(' ', 1)[-1]
                for record in data.get('decision_outcomes', {}).values()
                if isinstance(record, dict) and record.get('decided_by') == 'seat'
                and str(record.get('item_disposition')).startswith(('carried ', 'parked '))}
    return [name for name in data['approved_items'] if name in data['items'] and name not in disposed]


def step(root):
    """The first due step; root None means no workspace here.
    ponytail: one row, not a list; the first due item wins and status --line shows the rest."""
    if root is None:
        return _row('no-workspace', 'No WUWEI workspace here; run this in a host terminal in the '
                    'project directory to create one in observe posture.',
                    'bin/wuwei setup --shadow')
    config = workspace.load_config(root)
    # Not calibrate.approved: hook paths must not import calibrate (test_hooks pins it).
    calibration = root / '.wuwei/calibration.json'
    if (not config['repos'] or not calibration.is_file()
            or not json.loads(calibration.read_text(encoding='utf-8'))):
        return _row('setup', 'Setup is incomplete; run this in a host terminal to complete '
                    'the repositories, calibration and interview.', 'bin/wuwei setup')
    directory = workspace.day_dir(root)
    if not (directory / 'plan.md').is_file():
        return _row('plan', 'No plan for today yet; start the day with the plan skill.',
                    '/wuwei:wuwei-plan')
    data = state.read_state(directory=directory)
    if not data['gate_approved']:
        return _row('gate', 'Morning gate open: answer the one Morning gate question, '
                    f'"Approve today\'s plan as proposed?", in days/{directory.name}/plan.md; '
                    'the plan is approved only on your answer.',
                    '/wuwei:wuwei-plan')
    routes = data.get('decision_routes', {})
    if not isinstance(routes, dict):
        raise ValueError(f'invalid decision ledger; {DAMAGED}')
    for identifier in routes:
        if answered(data, identifier) is None:
            return _row('decision', f'Decision {identifier} waits for your answer; read it and '
                        'pick an option.', f'wuwei decision show {identifier} --widget')
    seats = brief.seats(data)
    if stuck := brief.stuck(data):
        return _row('stuck', f'Seat {stuck[0]} ended with no recorded result; run the command with its '
                    'report as the file, or stop it with --unmeasured "<reason>".',
                    f'wuwei seat stop {stuck[0]} --verdict <file>')
    running = {seat['item'] for seat in seats.values() if seat['status'] == 'running'}
    items = data['items']
    names = approved(data)
    building = sum(items[name]['phase'] in state.BUILD_PHASES for name in names)
    queued = sum(items[name]['phase'] == 'planned' for name in names)
    waiting = None
    for name in names:
        phase = items[name]['phase']
        if phase in TERMINAL or name in running:
            continue
        # Inline, not wuwei.tracker: next runs on hook paths.
        ticket = data.get('tickets', {}).get(name, {}).get('id')
        label = f'{name} ({ticket})' if ticket else name
        if phase in state.BUILD_PHASES:
            return _row('build', f'{label} is in {phase}; run the build loop and do the step it '
                        'returns.', f'wuwei build next {name}')
        if phase in ('gate', 'delta'):
            from wuwei import docs  # Local: only an item at the gate needs it.
            if docs.unmet(config, items[name]):
                return _row('docs', f"{name} (tier {items[name]['gates']['tier']}) has no docs value; "
                            'record it before the quality gate.',
                            docs.command(config, name).removeprefix('bin/'))
            return _row('verdicts', f'{label} is at {phase}; collect the gate verdicts and launch '
                        'the gate seats it names.', f'wuwei dispatch next {name}')
        if phase == 'raised':
            pr = items[name].get('pr')
            return _row('pr', f'{label} has PR {pr} open; act on its review state.',
                        f'wuwei pr act {pr}')
        if phase == 'planned' and building < data['cap']:
            return _row('dispatch', f'{min(queued, data["cap"] - building)} planned item(s) can '
                        f'start, {building} of CAP {data["cap"]} building; run the launch set, '
                        'brief each start and launch the set in one turn.',
                        'wuwei dispatch next --all')
        if phase == 'planned' and waiting is None:
            waiting = label
    names = sorted(name for name, seat in seats.items() if seat['status'] == 'running')
    builders = sorted((seat.get('started_at') or '', name) for name, seat in seats.items()
                      if seat['status'] == 'running' and seat['role'] == 'builder')
    if waiting and builders:
        return _row('wait', f'{waiting} waits: {building} of CAP {data["cap"]} building; '
                    f'{builders[0][1]} started first ({builders[0][0] or "start unrecorded"}) and '
                    'is expected to free first; SubagentStop records each result.',
                    'wuwei status --line')
    if names:
        return _row('wait', f'Seats running: {", ".join(names)}; SubagentStop records each result.',
                    'wuwei status --line')
    # ponytail: health from recorded watch and heartbeat events, not a doctor run (#346 budget).
    from wuwei.commands.status import scan
    _, watch, _, beat, _ = scan(directory, {**data, 'now': workspace.now().isoformat()})
    if watch == 'dead' or beat == 'degraded':
        return _row('doctor', f'Watch {watch}, heartbeat {beat}; run the doctor and fix what it '
                    'names.', 'wuwei doctor')
    if (directory / 'report.md').is_file() and data.get('close_requested'):
        return _row('closed', 'Report written and close requested; rerun close until it exits 0. '
                    'Tomorrow starts with /wuwei:wuwei-plan.', 'wuwei close')
    return _row('close', 'Every approved item is merged, parked, carried or escalated; run the '
                'report skill to retro, report and close the day.', '/wuwei:wuwei-report')


def line(row):
    return f"{row['state']}: {row['step']} Run: {row['command']}"


def steps(skill):
    """The first sentence of each numbered step in skills/<skill>/SKILL.md.
    ponytail: first sentence only to keep SessionStart short; the skill path carries the rest."""
    path = integrity.PLUGIN / 'skills' / skill / 'SKILL.md'
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError) as exc:
        return [f'steps unmeasured: {exc}; read {path}']
    found = []
    for text in lines:
        if re.match(r'\d+\. ', text):
            match = re.match(r'(\d+\. .+?\.)(?=\s|$)', text)
            found.append(match.group(1) if match else text)
    return found


def orientation(row, posture, spec=None, session=None):
    """The SessionStart block; paths are computed and only the plan or report skill is read.
    spec: the spec engine and its effective mode (5.10). session: the payload's session id."""
    plugin = integrity.PLUGIN
    role = os.environ.get('WUWEI_SEAT_ROLE')
    if (isinstance(role, str) and role and '/' not in role and not role.startswith(('_', '.'))
            and (plugin / 'charters' / f'{role}.md').is_file()):
        entry = [f'You are the {role} seat: follow {plugin}/charters/{role}.md and your brief; '
                 'the planner session runs the day.']
    elif row['state'] == 'plan':
        entry = [f'Start the day now; no command needed. Steps (full text: {plugin}/skills/wuwei-plan/SKILL.md):',
                 f'- Register this session as the planner: `wuwei plan session {session or "<session id>"}` '
                 '(add --take-over when it names another planner).',
                 *steps('wuwei-plan'), 'Do this now.']
    elif row['state'] == 'close':
        entry = [f'The day is closable. Steps (full text: {plugin}/skills/wuwei-report/SKILL.md):',
                 *steps('wuwei-report'), 'Do this now.']
    else:
        entry = []
    return '\n'.join([
        HEADER,
        "WUWEI runs this workspace's coding day the way a careful engineering team works: the "
        'planner session ranks the work, seats build and review each change in their own '
        'worktree, and merges follow a policy.',
        f'The owner answers questions and decisions; the session runs the commands ({EXECUTABLE}) '
        'and never asks the owner to edit a file.',
        'Day loop: plan, morning gate, dispatch builders, gates verify, PR and merge, report and '
        'close.',
        POSTURES[posture],
        *([f'Spec: {spec}'] if spec else []),
        f'Next: {line(row)}',
        *entry,
        'Reference: wuwei guide (every command, the accepted forms and the rules; the same text is '
        'the guide block in the memory.export_to file); run wuwei next when the next step is unclear; '
        f'owner guide: {plugin}/docs/site/daily.md',
    ])


def run(args):
    try:
        try:
            root = workspace.find_workspace()
        except FileNotFoundError:
            root = None
        row, code = step(root), CLEAN
    except ERRORS as exc:
        row, code = _row('unmeasured', str(exc), 'wuwei doctor'), UNRUN
        print(f'wuwei next: {exc}', file=sys.stderr)
    print(json.dumps(row) if args.json else line(row))
    return code
