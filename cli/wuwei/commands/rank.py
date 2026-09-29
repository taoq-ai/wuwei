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


def run(args):
    try:
        root = workspace.find_workspace()
        config = workspace.load_config(root)
        goal_list = goals.parse((root / '.wuwei/memory/goals.md').read_text(encoding='utf-8'))
        rows = json.loads(args.input.read_text(encoding='utf-8'))
        print(json.dumps(rank.rank(rows, config['prioritisation']['framework'], goal_list)))
        return CLEAN
    except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
        print(f'wuwei rank: {exc}', file=sys.stderr)
        return UNRUN
