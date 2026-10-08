"""#579: wuwei pace prints the day's pace, the advice and why, the inputs and the balance."""

import json
import sys

from wuwei.exits import CLEAN, UNRUN


def run(args):
    from wuwei import brief, calibrate, goals, pace, state, workspace
    try:
        root = workspace.find_workspace()
        config, data = workspace.load_config(root), state.read_state(root)
        running = sum(seat['status'] == 'running' for seat in brief.seats(data).values())
        limits = calibrate.host(root, config, running=running)
        path = workspace.day_dir(root) / 'proposal.json'
        proposal = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        merged = {name for name, row in data['items'].items() if row['phase'] == 'merged'}
        try:
            goal_list = goals.parse((root / '.wuwei/memory/goals.md').read_text(encoding='utf-8'))
        except ValueError:
            goal_list = {}  # no goals yet: the advice names no goal date
        advice = pace.advise(root, config, {
            'candidates': [row for row in proposal.get('candidates', []) if row.get('id') not in merged],
            'envelope': data.get('envelope') or proposal.get('envelope', {})}, goal_list, limits, workspace.now())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'wuwei pace: {exc}', file=sys.stderr)
        return UNRUN
    print(f"Pace: {pace.current(data, config)} (advice {advice['pace']}; your default {advice['wish']})")
    print('Advice: ' + advice['lines'][0])
    print(f"Inputs: {pace.host_line(root, limits, config)}; wish {advice['wish']}; {advice['budget']}")
    print(f"Balance: binding {advice['binding']}" + (f"; {advice['unlock']}" if advice['unlock'] else ''))
    return CLEAN


def register(subparsers):
    parser = subparsers.add_parser('pace', help="Print the day's pace, the advice and why, and the host line")
    parser.set_defaults(func=run)
