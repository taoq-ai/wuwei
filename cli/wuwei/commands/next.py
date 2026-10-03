"""Where the day stands and the one next step, read from the day's files only."""

import json
import os
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


def register(subparsers):
    parser = subparsers.add_parser('next', help='Print where the day stands and the one next step')
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)


def _row(name, text, command):
    return {'state': name, 'step': text, 'command': command}


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
                        'pick an option.', f'wuwei decision show {identifier}')
    seats = brief.seats(data)
    running = {seat['item'] for seat in seats.values() if seat['status'] == 'running'}
    disposed = {str(record.get('item_disposition')).split(' ', 1)[-1]
                for record in data.get('decision_outcomes', {}).values()
                if isinstance(record, dict) and record.get('decided_by') == 'seat'
                and str(record.get('item_disposition')).startswith(('carried ', 'parked '))}
    items = data['items']
    approved = [name for name in data['approved_items'] if name in items and name not in disposed]
    building = sum(items[name]['phase'] in state.BUILD_PHASES for name in approved)
    queued = sum(items[name]['phase'] == 'planned' for name in approved)
    for name in approved:
        phase = items[name]['phase']
        if phase in TERMINAL or name in running:
            continue
        if phase in state.BUILD_PHASES:
            return _row('build', f'{name} is in {phase}; run the build loop and do the step it '
                        'returns.', f'wuwei build next {name}')
        if phase in ('gate', 'delta'):
            from wuwei import docs  # Local: only an item at the gate needs it.
            if docs.unmet(config, items[name]):
                return _row('docs', f"{name} (tier {items[name]['gates']['tier']}) has no docs value; "
                            'record it before the quality gate.',
                            docs.command(config, name).removeprefix('bin/'))
            return _row('verdicts', f'{name} is at {phase}; collect the gate verdicts and launch '
                        'the gate seats it names.', f'wuwei dispatch next {name}')
        if phase == 'raised':
            pr = items[name].get('pr')
            return _row('pr', f'{name} has PR {pr} open; act on its review state.',
                        f'wuwei pr act {pr}')
        if phase == 'planned' and building < data['cap']:
            return _row('dispatch', f'{queued} planned item(s) queued, {building} of CAP '
                        f'{data["cap"]} building; create the worktree for {name}, then wuwei '
                        f'brief builder {name} <name> --worktree <path> and wuwei build next {name}.',
                        f'wuwei worktree add {name}')
    names = sorted(name for name, seat in seats.items() if seat['status'] == 'running')
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


def orientation(row, posture, spec=None):
    """The SessionStart block; paths are computed, no file is read. spec: the spec engine
    and its effective mode (5.10)."""
    plugin = integrity.PLUGIN
    role = os.environ.get('WUWEI_SEAT_ROLE')
    if (isinstance(role, str) and role and '/' not in role and not role.startswith(('_', '.'))
            and (plugin / 'charters' / f'{role}.md').is_file()):
        entry = (f'You are the {role} seat: follow {plugin}/charters/{role}.md and your brief; '
                 'the planner session runs the day.')
    else:
        entry = (f'Start or resume the day with /wuwei:wuwei-plan (steps: '
                 f'{plugin}/skills/wuwei-plan/SKILL.md); run wuwei next whenever the next step '
                 'is unclear.')
    return '\n'.join([
        HEADER,
        "WUWEI runs this workspace's coding day the way a careful engineering team works: the "
        'planner session ranks the work, seats build and review each change in their own '
        'worktree, and merges follow a policy.',
        'The owner answers questions and decisions; the session runs the commands (wuwei is the '
        'absolute path in .wuwei/executable: read it once and use it as the first word of a plain '
        'command, never through a variable) and never asks the owner to edit a file.',
        'Day loop: plan, morning gate, dispatch builders, gates verify, PR and merge, report and '
        'close.',
        POSTURES[posture],
        *([f'Spec: {spec}'] if spec else []),
        f'Next: {line(row)}',
        entry,
        f'Guide: {plugin}/docs/site/agent.md (the whole flow for a session); owner guide: '
        f'{plugin}/docs/site/daily.md',
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
