"""Owner goals commands."""

import sys

from wuwei.commands import _owner_edit


def register(subparsers):
    goals = subparsers.add_parser('goals', help='show or edit owner goals')
    goals.set_defaults(func=show)
    actions = goals.add_subparsers(dest='action')
    _owner_edit.register(actions)


def show(args):
    """#362: bare goals prints one line per goal, or how to set the first one."""
    from wuwei import goals, promotion, workspace
    root = workspace.find_workspace()
    path = promotion.safe_path(root, '.wuwei/memory/goals.md', label='goals')
    text = path.read_text(encoding='utf-8') if path.is_file() else ''
    if not goals.defined(text):
        print('No goals yet: run /wuwei:wuwei-plan and approve the proposed goals, or bin/wuwei goals edit.')
        return 0
    try:
        found = goals.parse(text)
    except ValueError as exc:
        print(f'wuwei goals: {exc}; fix it with bin/wuwei goals edit', file=sys.stderr)
        return 1
    for name, goal in found.items():
        print(f'{name} (priority {goal["priority"]}): {goal["outcome"]}; measure: {goal["measure"]}; '
              f'target: {goal["target"]} by {goal["date"]}')
    return 0
