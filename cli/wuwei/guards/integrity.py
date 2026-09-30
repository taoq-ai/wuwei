"""Measure at session start; gate all tool calls using the cached verdict."""

from wuwei import integrity, workspace
from wuwei.guards import Guard


def check(payload):
    try:
        root = workspace.guard_scope(payload)
        if root is None:
            return 0, ''
        result = integrity.cached(root)
        return result.exit, result.reason
    except (OSError, ValueError, TypeError) as exc:
        return 2, str(exc) if isinstance(exc, workspace.ConfigError) else f'integrity unmeasured: {exc}'


def session_start(payload):
    try:
        root = workspace.guard_scope(payload)
        if root is None:
            return 0, ''
        result = integrity.check(root)
        local = integrity.workspace_check(root)
        return max(result.exit, local.exit), '\n'.join(
            message for message in (result.reason, local.reason) if message)
    except (OSError, ValueError, TypeError) as exc:
        return 2, str(exc) if isinstance(exc, workspace.ConfigError) else f'integrity unmeasured: {exc}'


GUARDS = [Guard('PreToolUse', None, check), Guard('SessionStart', None, session_start)]
