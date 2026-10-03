"""Guard modules expose a plain GUARDS list; private modules are helpers."""

from collections import namedtuple
from contextvars import ContextVar
from importlib import import_module
import os
import re
import sys

from wuwei.exits import CLEAN, FINDINGS, PAYLOAD


EVENTS = ('PreToolUse', 'PostToolUse', 'SubagentStop', 'SessionStart', 'PreCompact', 'Stop')
# Each built-in guard module's events and, per event, the tools its matchers select
# (None: any tool). discover() skips a module the hook's event and tool cannot run;
# a module missing here is imported for every event. tests/test_hooks.py pins this
# to the modules' GUARDS.
MODULES = {
    'agent_launch': {'PreToolUse': 'Agent', 'SubagentStop': None},
    'commit_push': {'PreToolUse': 'Bash'},
    'decision': {'PostToolUse': 'Write|Edit|MultiEdit|NotebookEdit|Bash|AskUserQuestion',
                 'PreToolUse': 'AskUserQuestion', 'SubagentStop': None},
    'deploy': {'PreToolUse': 'Bash'},
    'integrity': {'PreToolUse': None, 'SessionStart': None},
    'lifecycle': {'SessionStart': None, 'PreCompact': None, 'Stop': None,
                  'SubagentStop': None},
    'outward': {'PreToolUse': None},
    'pr': {'PreToolUse': 'Bash'},
    'protect_state': {'PreToolUse': 'Write|Edit|MultiEdit|NotebookEdit|Bash'},
    'spec': {'PreToolUse': 'Write|Edit|MultiEdit|NotebookEdit',
             'PostToolUse': 'Write|Edit|MultiEdit|NotebookEdit|Bash', 'SubagentStop': None},
    'stop': {'Stop': None},
    'traces': {'PostToolUse': None},
    'verdict': {'PostToolUse': 'Write|Edit|MultiEdit|NotebookEdit|Bash', 'SubagentStop': None},
}
# #331: the posture area of each guard check; 'module.function' overrides its module. A test
# pins the keys to MODULES. None: the check applies its own posture (the MCP launch gate in
# mcp.cached; spec mode's own mode setting), so the hook enforces it as returned.
AREAS = {'agent_launch': 'seats', 'agent_launch.check_mcp': None, 'commit_push': 'publish',
         'decision': 'records', 'deploy': 'publish', 'integrity': 'integrity',
         'lifecycle': 'records', 'outward': 'outward', 'pr': 'publish',
         'protect_state': 'records', 'spec': None, 'stop': 'publish', 'traces': 'records',
         'verdict': 'records'}
# Owner-only actions block in every posture (#331 floor): the deployment ban (4.7), the merge
# policy, approvals and owner markers (4.6), and approve-tier messages and canary egress (4.9).
OWNER_ONLY = frozenset({'deploy', 'pr', 'outward.check_tier'})
# The missing-reviewer refusal names its ways out, so the hook adds no posture line to it.
REVIEWER_WAYS_OUT = ("bin/wuwei config set shepherd.min_reviewers 0, or "
                     "bin/wuwei config set shepherd.reviewers '[\"login\"]'")
# This guard never reads shepherd.reviewers, so that way out goes through pr raise.
NO_REVIEWER = ('PR create requires a named --reviewer in the same command; or '
               'bin/wuwei config set shepherd.min_reviewers 0; or set '
               'shepherd.reviewers and raise with bin/wuwei pr raise')


def level(check, levels):
    """(module, area, level, line) for one guard check under resolved area levels. A check
    with no area blocks with no posture line."""
    module = check.__module__.rsplit('.', 1)[-1]
    key = f'{module}.{getattr(check, "__name__", "")}'
    area = AREAS.get(key, AREAS.get(module))
    if area is None:
        return module, None, 'block', ''
    if key in OWNER_ONLY or module in OWNER_ONLY:
        return module, area, 'block', f'posture: {area} = block (owner-only action; no setting lowers it)'
    from wuwei.workspace import FLOORS
    if area in FLOORS:
        return module, area, 'block', f'posture: {area} = block (floor; no setting lowers it)'
    return module, area, levels[area], f'posture: {area} = {levels[area]} (set security.areas.{area})'
# ponytail: the hook's (event, tool_name) travels in context, not as discover()
# arguments, because tests replace hook.discover with zero-argument stubs; make it a
# parameter when those stubs take arguments.
SELECTION = ContextVar('SELECTION', default=None)


# check(payload) -> (exit, message); matcher None runs for any tool.
Guard = namedtuple('Guard', 'event matcher check profile_relaxable', defaults=(False,))


def __getattr__(name):
    # discover() lists modules itself (_modules); guards.pkgutil stays addressable.
    if name == 'pkgutil':
        import pkgutil
        return pkgutil
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def profile_result(result, profile, root, tool):
    """Apply the profile to a completed outward lint result only."""
    code, message = result
    if code == FINDINGS and profile == 'standard':
        from wuwei import state
        state.append_event('hook.warning', {'reason': message, 'tool': tool}, root)
        print(f'warning: {message}', file=sys.stderr)
        return CLEAN, ''
    return result


def _modules(paths):
    """pkgutil.iter_modules for source modules and packages, without the inspect import
    (about 4 ms) pkgutil pays on every hook."""
    seen = set()
    for directory in paths:
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            continue
        for filename in names:
            name = filename[:-3] if filename.endswith('.py') else filename
            if (name == '__init__' or '.' in name or name in seen
                    or name == filename and not os.path.isfile(os.path.join(directory, name, '__init__.py'))):
                continue
            seen.add(name)
            yield name


def discover():
    guards = []
    selection = SELECTION.get()
    for name in _modules(__path__):
        if selection is not None and name in MODULES:
            event, tool = selection
            pattern = MODULES[name].get(event)
            if event not in MODULES[name] or (pattern is not None and isinstance(tool, str)
                                              and re.fullmatch(pattern, tool) is None):
                continue
        if not name.startswith('_'):
            module = f'{__name__}.{name}'
            records = import_module(module).GUARDS
            if not isinstance(records, list):
                raise ValueError(f'{module}: GUARDS must be a list; reinstall the plugin, then run bin/wuwei doctor')
            for guard in records:
                if not isinstance(guard, Guard) or not callable(guard.check):
                    raise ValueError(f'{module}: invalid guard record; reinstall the plugin, then run bin/wuwei doctor')
                if type(guard.profile_relaxable) is not bool:
                    raise ValueError(f'{module}: invalid profile_relaxable flag; reinstall the plugin, then run bin/wuwei doctor')
                if guard.matcher is not None and not isinstance(guard.matcher, str):
                    raise ValueError(f'{module}: invalid guard matcher; reinstall the plugin, then run bin/wuwei doctor')
                if guard.event not in EVENTS:
                    raise ValueError(f'unknown guard event; {PAYLOAD}')
                if guard.matcher is not None:
                    re.compile(guard.matcher)
            guards.extend(records)
    return guards
