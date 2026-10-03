"""Specification mode in item worktrees (design 5.10); the rules live in wuwei.specmode,
imported only once a path lies in an item's recorded worktree (#346)."""

from wuwei.exits import CLEAN, UNRUN
from wuwei.guards import Guard

ERRORS = (OSError, ValueError, KeyError, TypeError, UnicodeError)
WRITES = 'Write|Edit|MultiEdit|NotebookEdit'


def _item(payload, path):
    """(root, item, row, worktree) for the item whose recorded worktree holds path, deepest
    first; None outside every item worktree."""
    from pathlib import Path
    from wuwei import state, workspace
    root = workspace.guard_scope(payload)
    if root is None or path is None:
        return None
    path = (Path(payload['cwd']) / path).resolve()
    found = []
    for item, row in state.read_state(root)['items'].items():
        if isinstance(row.get('worktree'), str) and row['worktree']:
            tree = (root / row['worktree']).resolve()
            if path.is_relative_to(tree):
                found.append((len(tree.parts), item, row, tree))
    if not found:
        return None
    _, item, row, tree = max(found, key=lambda match: match[0])
    return root, item, row, tree, path


def _target(payload):
    inputs = payload.get('tool_input')
    if not isinstance(inputs, dict):
        return None
    value = inputs.get('notebook_path', inputs.get('file_path'))
    return value if isinstance(value, str) and value else None


def check_edit(payload):
    """PreToolUse: refuse a source edit while a step before implementation is not done."""
    try:
        found = _item(payload, _target(payload))
        if found is None:
            return CLEAN, ''
        root, item, row, tree, path = found
        from wuwei import specmode, workspace
        config = workspace.load_config(root)
        if specmode.mode(config) == 'off' or specmode.own(config['spec']['engine'], tree, path):
            return CLEAN, ''
        return specmode.check(root, config, item, row, tree, build=False, where='edit')
    except ERRORS as exc:
        return UNRUN, f'spec mode: {exc}'


def check_record(payload):
    """PostToolUse: one spec.step event per step whose artifact is now done; never refuses."""
    try:
        found = _item(payload, payload['cwd'] if payload.get('tool_name') == 'Bash' else _target(payload))
        if found is None:
            return CLEAN, ''
        root, item, row, tree, _ = found
        from wuwei import specmode, workspace
        specmode.record(root, workspace.load_config(root), item, row, tree)
        return CLEAN, ''
    except ERRORS as exc:
        return UNRUN, f'spec mode: {exc}'


def check_stop(payload):
    """SubagentStop: a builder's last message names its spec artifacts."""
    if payload.get('stop_hook_active') or payload.get('agent_type') != 'wuwei:builder':
        return CLEAN, ''
    from pathlib import Path
    from wuwei import brief, state, workspace
    from wuwei.guards.agent_launch import stopping_seat
    try:
        root = workspace.find_workspace(payload.get('cwd'))
        directory, name, _ = stopping_seat(payload, root)
    except (FileNotFoundError, ValueError, OSError):
        return CLEAN, ''  # agent_launch.stop records an unmatched stop.
    try:
        data = state.read_state(directory=directory)
        item = brief.seats(data)[name]['item']
        row = data['items'][item]
        if not isinstance(row.get('worktree'), str) or not row['worktree']:
            return CLEAN, ''
        from wuwei import specmode
        text = payload.get('last_assistant_message')
        return specmode.named(root, workspace.load_config(root), item, row,
                              (root / Path(row['worktree'])).resolve(), text if isinstance(text, str) else '')
    except ERRORS as exc:
        return UNRUN, f'spec mode: {exc}'


GUARDS = [Guard('PreToolUse', WRITES, check_edit),
          Guard('PostToolUse', WRITES + '|Bash', check_record),
          Guard('SubagentStop', None, check_stop)]
