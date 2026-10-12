"""Measure at session start and warn; no tool call is refused for integrity (#839)."""

from wuwei import integrity, workspace
from wuwei.guards import Guard


def session_start(payload):
    try:
        root = workspace.guard_scope(payload)
        if root is None:
            return 0, ''
        # The workspace history read (git child processes) runs while the plugin files hash
        # and the signature verifies; SessionStart is a wall-time budget.
        from wuwei.registry import together
        result, local = together(lambda: integrity.check(root), lambda: integrity.workspace_check(root))
        return max(result.exit, local.exit), '\n'.join(
            message for message in (result.reason, local.reason) if message)
    except (OSError, ValueError, TypeError) as exc:
        return 2, str(exc) if isinstance(exc, workspace.ConfigError) else f'integrity unmeasured: {exc}; run bin/wuwei doctor'


GUARDS = [Guard('SessionStart', None, session_start)]
