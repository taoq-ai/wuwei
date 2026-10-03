"""Fixed adapter operations and the shared three-state result."""

from collections import namedtuple
from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import sys

from wuwei import state
from wuwei.exits import UNRUN


PARAMETERS = {
    'editor': {'edit': ('path', 'command')},
    'tts': {'speak': ('text', 'rate', 'out')},
    'calendar': {'events': ('since', 'until')},
    'transcripts': {'recent': ('since',)},
    'inbound': {'poll': ('since',)},
    'redactor': {'redact': ('text',)},
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
    'code_host': {'auth_status': (), 'viewer_login': (), 'pr': ('ref',), 'checks': ('ref', 'sha'), 'reviews': ('ref',),
                  'commits': ('ref',),
                  'threads': ('ref',), 'protection': ('repo', 'branch'),
                  'files': ('ref',), 'history': ('repo', 'start', 'branch', 'patches'),
                  'author_login': ('repo', 'email'), 'token_scopes': ('variable',),
                  'create_pr': ('draft',), 'request_reviewers': ('ref', 'logins'),
                  'comment': ('ref', 'text', 'thread'), 'merge': ('ref', 'sha'),
                  'revert_pr': ('ref',), 'merged_prs': ('repo',), 'probe': ('ref', 'tags'),
                  'default_branch': ('repo',)},
    'vcs': {'workspace_init': ('repo',),
            'workspace_changes': ('repo',),
            'workspace_commit': ('repo', 'paths'), 'workspace_owner_commit': ('repo', 'paths'),
            'resolve': ('repo', 'sha'), 'identity': ('repo',), 'remote_url': ('repo',), 'head': ('repo',), 'merge_base': ('repo', 'ref'),
            'fetch': ('repo', 'remote', 'branch', 'expected'),
            'rebase': ('repo', 'ref'), 'push': ('repo', 'remote', 'branch', 'expected'),
            'status': ('repo',), 'diff_stat': ('repo', 'base', 'head'),
            'log_since': ('repo', 'sha'), 'worktree_add': ('repo', 'branch', 'path'),
            'changes_on': ('repo', 'day'), 'read_tree': ('repo', 'ref', 'paths'),
            'branches': ('repo', 'pattern'),
            'pushed_branches': ('repo',),
            'authorship': ('repo', 'branch', 'paths', 'days'), 'branch': ('repo',),
            'repo_context': ('repo',), 'commit_context': ('repo', 'settings', 'env'),
            'push_context': ('repo', 'remote', 'refspecs'), 'hooks_path': ('repo', 'path'),
            'worktree_identity': ('repo', 'name', 'email'),
            'push_commits': ('repo', 'remote', 'destination', 'local_sha', 'remote_sha', 'default_branch'),
            'recent_commits': ('repo',)},
}
INTERFACES = {kind: tuple(operations) for kind, operations in PARAMETERS.items()}

ADAPTERS = Path(__file__).resolve().parents[2] / 'adapters'


def known(kind):
    """List installed public module names without importing external tools."""
    if kind not in INTERFACES:
        raise ValueError(f'unknown adapter kind: {kind}')
    # os.listdir, not Path.glob: config validation lists 14 kinds on every hook.
    directory = ADAPTERS / kind
    try:
        names = os.listdir(directory)
    except (FileNotFoundError, NotADirectoryError):
        return []
    return sorted(name[:-3] for name in names
                  if name.endswith('.py') and name[:-3].isidentifier() and not name.startswith('_')
                  and os.path.isfile(directory / name))


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


Result = namedtuple('Result', 'exit data reason', defaults=(None, ''))


def data(result):
    if not isinstance(result, Result) or type(result.exit) is not int or result.exit != 0:
        raise ValueError(getattr(result, 'reason', '') or 'VCS operation unavailable')
    if not isinstance(result.data, dict):
        raise ValueError('malformed VCS data')
    return result.data


def together(*calls):
    """Run independent calls concurrently, the first in this thread; results and the first
    error keep call order. Plain threads: concurrent.futures imports logging (hook start)."""
    if not calls:
        return []
    from threading import Thread
    outcomes = [None] * len(calls)

    def run(index):
        try:
            outcomes[index] = (True, calls[index]())
        except BaseException as exc:
            outcomes[index] = (False, exc)
    threads = [Thread(target=run, args=(index,)) for index in range(1, len(calls))]
    for thread in threads:
        thread.start()
    run(0)
    for thread in threads:
        thread.join()
    for ok, value in outcomes:
        if not ok:
            raise value
    return [value for _, value in outcomes]


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
                if code == 1 and reason == outward.APPROVAL_REQUIRED:
                    from wuwei import drafts
                    draft_id = drafts.create(root, config, kind, operation.__name__,
                                             operation.__module__.rsplit('.', 1)[-1],
                                             inputs, reason)
                    reason += f'; stored draft {draft_id}; wuwei drafts approve {draft_id}'
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
