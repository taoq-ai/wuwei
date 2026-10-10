"""Run configured checks and produce reserved current-HEAD evidence."""

from pathlib import Path
import re
import shlex
import time

from wuwei import registry, state, workspace
from wuwei.guards.commit_push import context, data
from wuwei.exits import ADAPTER_DATA, DAMAGED

RELATIVE = ('.venv/', 'venv/', 'node_modules/.bin/')
# #600: an empty fast-check list is a state, not a wall
NONE = 'fast checks: none configured; CI and the gates are the evidence'


def interpreter(command, worktree, repo, root, config):
    """(path, source) when the check's first word is a relative interpreter, else None.

    source is checks.python, worktree, main worktree or missing (#520).
    """
    word = command.split(None, 1)[0] if command.strip() else ''
    if not word.startswith(RELATIVE):
        return None
    main = (Path(root) / Path(repo['path']).expanduser()).resolve()
    setting = config['checks']['python']
    if setting and Path(word).name.startswith('python'):
        return main / Path(setting).expanduser(), 'checks.python'
    for path, source in ((Path(worktree) / word, 'worktree'), (main / word, 'main worktree')):
        if path.exists():
            return path, source
    return Path(worktree) / word, 'missing'


def commands(root, config, repo, tree):
    """#579: the checks the day's pace runs and the push guard takes as evidence: steady the
    fast checks; careful the fast checks then repos.tests; fast repos.tests on the test files the
    diff changes. Without repos.tests, a changed test file or a readable diff: the fast checks."""
    from wuwei import dispatch, merge, pace
    checks, tests = list(repo['fast_checks']), repo.get('tests', '')
    try:
        current = pace.current(state.read_state(root), config)
    except (OSError, ValueError, KeyError, TypeError):
        current = 'steady'
    if not tests or current == 'steady':
        return checks
    if current == 'careful':
        return checks + [tests]
    globs = dict(dispatch.CLASS_PATHS)['TEST']
    try:
        _, changes = dispatch._changes(root, config, {'worktree': str(tree)})
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return checks
    touched = [change['path'] for change in changes
               if merge.matched(change['path'], globs) and (Path(tree) / change['path']).is_file()]
    return [' '.join([tests, *map(shlex.quote, touched)])] if touched else checks


def record(path):
    path = Path(path).resolve()
    root = workspace.find_workspace(path)
    repo, actual, vcs = context(path, {}, {}, root, identity=False)
    records = {}
    from wuwei.commands.build import check_binding
    builds = [check_binding(item, build) for item, build in state.read_state(root).get('builds', {}).items()
              if build['status'] == 'running' and Path(build['worktree']) == path]
    if len(builds) > 1:
        raise ValueError('multiple running builds share the check worktree; wait for one build to finish, or run each build in its own worktree (bin/wuwei worktree add <item>)')
    binding = builds[0] if builds else None

    def save():
        state._write_state(
            lambda value: value.setdefault('fast_checks', {}).update({repo['name']: records}),
            root, reserved=False, kind='fast_checks.record', payload={'repo': repo['name']})

    # Invalidate previous successes before any read or execution can fail.
    save()
    config = workspace.load_config(root)
    runner = registry.load('checks', config)
    sha = data(vcs.head(actual['path'], root=root))['sha']
    if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', sha):
        raise ValueError(f'invalid HEAD for fast checks; {DAMAGED}')
    from wuwei.brief import status
    clean = not status(vcs, str(path), root) if binding else False
    code = 0
    for command in commands(root, config, repo, path):
        started = time.monotonic()
        found = interpreter(command, path, repo, root, config)
        run = command
        if found and found[1] in ('checks.python', 'main worktree'):
            run = shlex.quote(str(found[0])) + command.lstrip()[len(command.split(None, 1)[0]):]
        result = runner.run(str(path), run, timeout=repo['check_timeout_seconds'], root=root)
        if (not isinstance(result, registry.Result) or type(result.exit) is not int
                or result.exit not in (0, 1, 2)):
            raise ValueError(f'invalid fast-check result; {ADAPTER_DATA}')
        if data(vcs.head(actual['path'], root=root))['sha'] != sha:
            raise ValueError('HEAD changed during fast checks; rerun checks')
        records[command] = {'sha': sha, 'exit': result.exit, 'data': result.data,
                            'reason': result.reason, 'worktree': str(path), 'build': binding,
                            'clean': clean and not status(vcs, str(path), root),
                            'seconds': round(time.monotonic() - started, 1)}
        if found:
            records[command]['interpreter'] = str(found[0]) if found[1] != 'missing' else None
        code = max(code, result.exit)
    save()
    return code
