"""Guard modules expose a plain GUARDS list; private modules are helpers."""

from contextvars import ContextVar
from importlib import import_module
import pkgutil
import re
import sys
from typing import Callable, NamedTuple

from wuwei.exits import CLEAN, FINDINGS


EVENTS = ('PreToolUse', 'PostToolUse', 'SubagentStop', 'SessionStart', 'PreCompact', 'Stop')
# Each built-in guard module's events and, per event, the tools its matchers select
# (None: any tool). discover() skips a module the hook's event and tool cannot run;
# a module missing here is imported for every event. tests/test_hooks.py pins this
# to the modules' GUARDS.
MODULES = {
    'agent_launch': {'PreToolUse': 'Agent', 'SubagentStop': None},
    'commit_push': {'PreToolUse': 'Bash'},
    'decision': {'PostToolUse': 'Write|Edit|MultiEdit|NotebookEdit|Bash',
                 'PreToolUse': 'AskUserQuestion'},
    'deploy': {'PreToolUse': 'Bash'},
    'integrity': {'PreToolUse': None, 'SessionStart': None},
    'lifecycle': {'SessionStart': None, 'PreCompact': None, 'Stop': None,
                  'SubagentStop': None},
    'outward': {'PreToolUse': None},
    'pr': {'PreToolUse': 'Bash'},
    'protect_state': {'PreToolUse': 'Write|Edit|MultiEdit|NotebookEdit|Bash'},
    'stop': {'Stop': None},
    'traces': {'PostToolUse': None},
    'verdict': {'PostToolUse': 'Write|Edit|MultiEdit|NotebookEdit|Bash', 'SubagentStop': None},
}
# ponytail: the hook's (event, tool_name) travels in context, not as discover()
# arguments, because tests replace hook.discover with zero-argument stubs; make it a
# parameter when those stubs take arguments.
SELECTION = ContextVar('SELECTION', default=None)


class Guard(NamedTuple):
    event: str
    matcher: str | None
    check: Callable[[dict], tuple[int, str]]
    profile_relaxable: bool = False


def profile_result(result, profile, root, tool):
    """Apply the profile to a completed outward lint result only."""
    code, message = result
    if code == FINDINGS and profile == 'standard':
        from wuwei import state
        state.append_event('hook.warning', {'reason': message, 'tool': tool}, root)
        print(f'warning: {message}', file=sys.stderr)
        return CLEAN, ''
    return result


def discover():
    guards = []
    selection = SELECTION.get()
    for module in pkgutil.iter_modules(__path__, __name__ + '.'):
        name = module.name.rsplit('.', 1)[-1]
        if selection is not None and name in MODULES:
            event, tool = selection
            pattern = MODULES[name].get(event)
            if event not in MODULES[name] or (pattern is not None and isinstance(tool, str)
                                              and re.fullmatch(pattern, tool) is None):
                continue
        if not name.startswith('_'):
            records = import_module(module.name).GUARDS
            if not isinstance(records, list):
                raise ValueError(f'{module.name}: GUARDS must be a list')
            for guard in records:
                if not isinstance(guard, Guard) or not callable(guard.check):
                    raise ValueError(f'{module.name}: invalid guard record')
                if type(guard.profile_relaxable) is not bool:
                    raise ValueError(f'{module.name}: invalid profile_relaxable flag')
                if guard.matcher is not None and not isinstance(guard.matcher, str):
                    raise ValueError(f'{module.name}: invalid guard matcher')
                if guard.event not in EVENTS:
                    raise ValueError('unknown guard event')
                if guard.matcher is not None:
                    re.compile(guard.matcher)
            guards.extend(records)
    return guards
