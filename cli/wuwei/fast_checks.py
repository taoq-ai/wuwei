"""Run configured checks and produce reserved current-HEAD evidence."""

from pathlib import Path
import re

from wuwei import registry, state, workspace
from wuwei.guards.commit_push import context, data


def record(path):
    path = Path(path).resolve()
    root = workspace.find_workspace(path)
    repo, actual, vcs = context(path, {}, {}, root)
    records = {}

    def save():
        state._write_state(
            lambda value: value.setdefault('fast_checks', {}).update({repo['name']: records}),
            root, reserved=False, kind='fast_checks.record', payload={'repo': repo['name']})

    # Invalidate previous successes before any read or execution can fail.
    save()
    runner = registry.load('checks', workspace.load_config(root))
    sha = data(vcs.head(actual['path'], root=root))['sha']
    if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', sha):
        raise ValueError('invalid HEAD for fast checks')
    code = 0
    for command in repo['fast_checks']:
        result = runner.run(str(path), command, root=root)
        if (not isinstance(result, registry.Result) or type(result.exit) is not int
                or result.exit not in (0, 1, 2)):
            raise ValueError('invalid fast-check result')
        if data(vcs.head(actual['path'], root=root))['sha'] != sha:
            raise ValueError('HEAD changed during fast checks; rerun checks')
        records[command] = {'sha': sha, 'exit': result.exit}
        code = max(code, result.exit)
    save()
    return code
