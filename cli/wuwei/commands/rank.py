"""Order scored candidates from JSON input."""

import json
from pathlib import Path
import sys

from wuwei import goals, rank, workspace
from wuwei.exits import CLEAN, UNRUN


def register(subparsers):
    parser = subparsers.add_parser('rank', help='Rank candidate JSON using workspace goals')
    parser.add_argument('input', type=Path)
    parser.set_defaults(func=run)


def candidate_template(goal, framework):
    components = ('value', 'time_criticality', 'risk_reduction', 'job_size') if framework == 'wsjf' else ('reach', 'impact', 'confidence', 'effort')
    score = ({'value': 5, 'time_criticality': 3, 'risk_reduction': 2, 'job_size': 2}
             if framework == 'wsjf' else
             {'reach': 10, 'impact': 1, 'confidence': 0.8, 'effort': 2})
    return {'id': 'EXAMPLE-1', 'goal': goal, 'evidence': 'Replace with source path',
            'scope': 'Replace with scope', 'overlap': 'none', 'track': 'SLICE',
            'flags': {'trust_surface': False, 'boundary_relevant': False, 'agent_surface': False},
            'score': score, 'evidence_lines': {key: 'Replace with evidence' for key in components}}


def run(args):
    try:
        root = workspace.find_workspace()
        config = workspace.load_config(root)
        text = (root / '.wuwei/memory/goals.md').read_text(encoding='utf-8')
        if str(args.input) == 'template':
            goal_list = goals.parse(text)
            print(json.dumps([candidate_template(next(iter(goal_list)), config['prioritisation']['framework'])], indent=2))
            return CLEAN
        source = sys.stdin.read() if str(args.input) == '-' else args.input.read_text(encoding='utf-8')
        rows = json.loads(source)
        if isinstance(rows, dict):  # a whole lead JSON, such as proposal.json
            text, _ = goals.proposed(text, rows.get('goals'))
            rows = rows.get('candidates')
        goal_list = goals.parse(text)
        print(json.dumps(rank.rank(rows, config['prioritisation']['framework'], goal_list)))
        return CLEAN
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei rank: {exc}', file=sys.stderr)
        return UNRUN
