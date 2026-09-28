"""Fixed adapter operations and the shared three-state result."""

from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

from wuwei import state
from wuwei.exits import UNRUN


PARAMETERS = {
    'tracker': {'claim': ('item',), 'transition': ('item', 'state'),
                'create': ('draft',), 'history': ('item',)},
    'chat': {'post': ('channel', 'text', 'thread'), 'dm': ('text',)},
    'review_bot': {'score': ('pr',), 'open_findings': ('pr',)},
    'runtime': {'dispatch': ('role', 'brief_path', 'worktree', 'write'),
                'status': ('job',), 'result': ('job',)},
    'scanner': {'audit': ('path',), 'gate': ('result', 'threshold'),
                'traces': ('file',), 'mcp': ('servers',)},
    'code_host': {'pr': ('ref',), 'checks': ('ref', 'sha'), 'reviews': ('ref',),
                  'threads': ('ref',), 'protection': ('repo', 'branch'),
                  'create_pr': ('draft',), 'request_reviewers': ('ref', 'logins'),
                  'comment': ('ref', 'text', 'thread'), 'merge': ('ref', 'sha'),
                  'revert_pr': ('ref',)},
    'vcs': {'identity': ('repo',), 'head': ('repo',), 'merge_base': ('repo', 'ref'),
            'status': ('repo',), 'diff_stat': ('repo', 'base', 'head'),
            'log_since': ('repo', 'sha'), 'worktree_add': ('repo', 'branch', 'path')},
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
        if kind == 'runtime' and name == 'claude':
            # ponytail: reserve the shipped default until #26 supplies its module.
            if for_config:
                return
            raise ValueError('adapters.runtime: claude unavailable until issue #26')
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


@dataclass(frozen=True)
class Result:
    exit: int
    data: object = None
    reason: str = ''


def record_none(kind, call, root=None, *, measurement=True):
    """Record an unavailable operation without logging its arguments."""
    reason = 'unmeasured' if measurement else 'no adapter configured'
    try:
        state.append_event('adapter: none', {
            'adapter': 'none', 'kind': kind, 'call': call,
            'exit': UNRUN, 'reason': reason, 'performed': False,
        }, root=root)
    except (OSError, ValueError) as exc:
        reason = f'could not record adapter event: {exc}'
    print(f'{kind}.{call}: {reason}', file=sys.stderr)
    return Result(UNRUN, None, reason)
