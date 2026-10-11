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
    'answers': {'PostToolUse': 'AskUserQuestion'},
    'commit_push': {'PreToolUse': 'Bash'},
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
# #837: one switch, guards.enforce. The floor blocks whatever it says (constitution VII):
# records written by the workflow and the owner's merge, approve, admin, deploy and outward send
# edges. Keys are modules or 'module.function'; a LOG_ONLY function is not on its module's floor.
FLOOR = frozenset({'answers', 'lifecycle', 'verdict', 'deploy', 'pr', 'protect_state',
                   'outward.check_send'})
# B5 lead call (#837): no new walls. With guards.enforce on these still only log, as under the
# old guarded default: the outward lint, another item's scratch directory,
# the traces recorder (it never refuses, even when it raises) and the launch capacity and
# ticket refusals (next never offers a launch past CAP).
LOG_ONLY = frozenset({'outward', 'protect_state.check_scratch', 'traces'})
# Launch refusal text that only logs: CAP, the host seat ceiling, free memory, a missing ticket.
CAPACITY = ('running build seats', 'host seat ceiling', 'free memory', ' has no ticket: ')
# The missing-reviewer refusal names its ways out.
REVIEWER_WAYS_OUT = ("bin/wuwei config set shepherd.min_reviewers 0, or "
                     "bin/wuwei config set shepherd.reviewers '[\"login\"]'")
# This guard never reads shepherd.reviewers, so that way out goes through pr raise.
NO_REVIEWER = ('PR create requires a named --reviewer in the same command; or '
               'bin/wuwei config set shepherd.min_reviewers 0; or set '
               'shepherd.reviewers and raise with bin/wuwei pr raise')

# #530: the prefix of every PR create refusal; raising is gated by evidence, not the floor.
RAISE = 'pr raise: '
# #530, #524: a session merge goes through bin/wuwei merge; approval and override stay
# the owner's (design 9.2, I1 exempt). The floor.
MERGE = ('merge policy', 'admin merge', 'PR approval', 'branch protection',
         'a shepherd seat never merges')
# Canary and honeytoken egress, owner disposition markers and (#725) a seat launch naming a
# brief that does not exist: the records floor.
RECORDS_FLOOR = ('outward: security.', 'owner disposition markers must be posted by the owner',
                 'brief .wuwei/days/')


def _keys(check):
    module = check.__module__.rsplit('.', 1)[-1]
    return module, f'{module}.{getattr(check, "__name__", "")}'


def floor(check, reason):
    """True when the refusal blocks whatever guards.enforce says."""
    if reason.startswith(MERGE + RECORDS_FLOOR):
        return True
    module, key = _keys(check)
    return ((key in FLOOR or module in FLOOR and key not in LOG_ONLY)
            and not (reason == NO_REVIEWER or reason.startswith(RAISE)))


def logs(check, reason):
    """True when the refusal only logs with guards.enforce on (B5 lead call)."""
    module, key = _keys(check)
    return (key in LOG_ONLY or module in LOG_ONLY
            or module == 'agent_launch' and any(part in reason for part in CAPACITY))


# ponytail: the hook's (event, tool_name) travels in context, not as discover()
# arguments, because tests replace hook.discover with zero-argument stubs; make it a
# parameter when those stubs take arguments.
SELECTION = ContextVar('SELECTION', default=None)


# check(payload) -> (exit, message); matcher None runs for any tool.
Guard = namedtuple('Guard', 'event matcher check profile_relaxable', defaults=(False,))


def wuwei_role(agent_type):
    """A WUWEI seat's agent type: wuwei:<role> or a shipped charter name."""
    if not isinstance(agent_type, str):
        return False
    from pathlib import Path
    charters = Path(__file__).resolve().parents[3] / 'charters'
    return agent_type.startswith('wuwei:') or agent_type.rsplit(':', 1)[-1] in {
        p.stem for p in charters.glob('*.md')}


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
