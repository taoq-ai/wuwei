"""Fixed adapter operations and the shared three-state result."""

from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

from wuwei import state
from wuwei.exits import UNRUN


PARAMETERS = {
    'editor': {'edit': ('path', 'command')},
    'tts': {'speak': ('text', 'rate', 'out')},
    'calendar': {'events': ('since', 'until')},
    'transcripts': {'recent': ('since',)},
    'integrity': {'sign': ('manifest', 'key'), 'verify': ('manifest', 'signature', 'key')},
    'host': {'free_memory': ()},
    'checks': {'run': ('path', 'command')},
    'tracker': {'backlog': ('filter',), 'claim': ('item',), 'transition': ('item', 'state'),
                'create': ('draft',), 'history': ('item',), 'created': ('item',)},
    'chat': {'post': ('channel', 'text', 'thread'), 'dm': ('text',),
             'sent': ('channel', 'owner')},
    'review_bot': {'score': ('pr',), 'open_findings': ('pr',)},
    'runtime': {'dispatch': ('role', 'brief_path', 'worktree', 'write'),
                'status': ('job',), 'result': ('job',),
                'continue_job': ('job', 'feedback')},
    'scanner': {'audit': ('path',), 'gate': ('result', 'threshold'),
                'traces': ('file',), 'mcp': ('servers',)},
    'code_host': {'auth_status': (), 'pr': ('ref',), 'checks': ('ref', 'sha'), 'reviews': ('ref',),
                  'commits': ('ref',),
                  'threads': ('ref',), 'protection': ('repo', 'branch'),
                  'files': ('ref',), 'history': ('repo', 'start', 'branch', 'patches'),
                  'author_login': ('repo', 'email'),
                  'create_pr': ('draft',), 'request_reviewers': ('ref', 'logins'),
                  'comment': ('ref', 'text', 'thread'), 'merge': ('ref', 'sha'),
                  'revert_pr': ('ref',)},
    'vcs': {'workspace_init': ('repo',),
            'workspace_changes': ('repo',),
            'workspace_commit': ('repo', 'paths'), 'workspace_owner_commit': ('repo', 'paths'),
            'resolve': ('repo', 'sha'), 'identity': ('repo',), 'head': ('repo',), 'merge_base': ('repo', 'ref'),
            'status': ('repo',), 'diff_stat': ('repo', 'base', 'head'),
            'log_since': ('repo', 'sha'), 'worktree_add': ('repo', 'branch', 'path'),
            'changes_on': ('repo', 'day'), 'read_tree': ('repo', 'ref', 'paths'),
            'branches': ('repo', 'pattern'),
            'pushed_branches': ('repo',),
            'authorship': ('repo', 'branch', 'paths', 'days'), 'branch': ('repo',),
            'commit_context': ('repo', 'settings', 'env'),
            'push_context': ('repo', 'remote', 'refspecs'), 'hooks_path': ('repo', 'path'),
            'push_commits': ('repo', 'remote', 'destination', 'local_sha', 'remote_sha', 'default_branch')},
}
INTERFACES = {kind: tuple(operations) for kind, operations in PARAMETERS.items()}

ADAPTERS = Path(__file__).resolve().parents[2] / 'adapters'


def known(kind):
    """List installed public module names without importing external tools."""
    if kind not in INTERFACES:
        raise ValueError(f'unknown adapter kind: {kind}')
    return sorted(path.stem for path in (ADAPTERS / kind).glob('*.py')
                  if path.is_file() and path.stem.isidentifier()
                  and not path.stem.startswith('_'))


def validate(kind, name, *, for_config=False):
    """Validate installed names, allowing the reserved default in config only."""
    names = known(kind)
    if name not in names:
        raise ValueError(f'adapters.{kind}: unknown adapter {name!r}; '
                         f'known names: {", ".join(names)}')


def load(kind, config):
    """Load only an installed implementation selected by validated config."""
    name = config['adapters'][kind]
    validate(kind, name)
    module_name = f'adapters.{kind}.{name}'
    spec = spec_from_file_location(module_name, ADAPTERS / kind / f'{name}.py')
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(module_name, None)
        raise
    return module


def runtime_config(role, config, root):
    """Apply the approved role runtime to a single adapter selection."""
    policy = state.read_state(root)['seat_policy'].get(role, {})
    if not policy:
        return config
    selected = policy.get('runtime')
    if not isinstance(selected, str) or not selected:
        raise ValueError(f'invalid runtime policy for {role}')
    return {**config, 'adapters': {**config['adapters'], 'runtime': selected}}


@dataclass(frozen=True)
class Result:
    exit: int
    data: object = None
    reason: str = ''


def record_none(kind, call, root=None, *, measurement=True):
    """Record an unavailable operation without logging its arguments."""
    reason = 'tracker adapter is none' if kind == 'tracker' else ('unmeasured' if measurement else 'no adapter configured')
    try:
        state.append_event('adapter: none', {
            'adapter': 'none', 'kind': kind, 'call': call,
            'exit': UNRUN, 'reason': reason, 'performed': False,
        }, root=root)
    except (OSError, ValueError) as exc:
        reason = f'could not record adapter event: {exc}'
    print(f'{kind}.{call}: {reason}', file=sys.stderr)
    return Result(UNRUN, None, reason)


def outward_operation(kind):
    """Enforce policy at text-bearing ports, including direct module callers."""
    from functools import wraps
    from inspect import signature

    def decorate(operation):
        parameters = signature(operation)

        @wraps(operation)
        def call(*args, **kwargs):
            from wuwei import outward, workspace
            try:
                inputs = dict(parameters.bind(*args, **kwargs).arguments)
                start = inputs.pop('root', None)
                if kind == 'chat' and operation.__name__ == 'dm':
                    inputs['is_dm'] = True
                root = workspace.find_workspace(start)
                config = workspace.load_config(root)
                code, reason = outward.check_call(inputs, root, config, {kind})
                if code:
                    return Result(code, inputs.get('text') if kind == 'chat' and code == 1
                                  and not reason.startswith('outward: security.') else None, reason)
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                return Result(UNRUN, None, 'outward: cannot validate port call')
            return operation(*args, **kwargs)
        return call
    return decorate


def watch_service():
    """Load the fixed local service manager adapter only when installation runs."""
    spec = spec_from_file_location('adapters.watch_service', ADAPTERS / 'watch_service.py')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
