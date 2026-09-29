"""Read-only pushed branch evidence through the VCS boundary."""

import subprocess

import pytest

from adapters.vcs import git
from fakes.replay import install_replay


@pytest.mark.parametrize('output,expected,names', [
    ('', 0, []),
    ('refs/remotes/origin/feature-A\nrefs/remotes/backup/feature-A\n'
     'refs/remotes/origin/HEAD\nrefs/remotes/origin/topic/nested\n',
     0, ['feature-A', 'topic/nested']),
    ('error body\n', 2, None),
])
def test_pushed_branches(monkeypatch, tmp_path, output, expected, names):
    install_replay(monkeypatch, 'git', [{'argv': ['-C', str(tmp_path),
        'for-each-ref', '--format=%(refname)', 'refs/remotes/'], 'stdout': output}])
    result = git.pushed_branches(str(tmp_path))
    assert result.exit == expected
    assert result.data == names


@pytest.mark.parametrize('error', [FileNotFoundError(), subprocess.TimeoutExpired('git', 30)])
def test_pushed_branches_tool_failure(monkeypatch, tmp_path, error):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(git.subprocess, 'run', fail)
    result = git.pushed_branches(str(tmp_path))
    assert result.exit == 2 and 'could not run' in result.reason
