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


@pytest.mark.parametrize('passing', [True, False])
def test_passing_close_writes_the_week_digest(tmp_path, monkeypatch, passing):
    from argparse import Namespace
    from wuwei import closing, pr_actions, state, steward
    from wuwei.commands import close
    (tmp_path / '.wuwei/memory/notes').mkdir(parents=True)
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-10-03T18:00:00+02:00')
    state._write_state(lambda data: None, tmp_path, reserved=False)
    monkeypatch.setattr(pr_actions, 'evaluate', lambda root: (0, []))
    monkeypatch.setattr(closing, 'unresolved', lambda *a, **k: (0, ''))
    monkeypatch.setattr(steward, 'run', lambda *a, **k: 0)
    monkeypatch.setattr(closing, 'check', lambda root: (0, '') if passing else (1, 'refused'))
    args = Namespace(check=None, widget=False)
    digest = tmp_path / '.wuwei/memory/digests/2026-W40.md'
    assert close.run(args) == (0 if passing else 1)
    assert digest.is_file() == passing
    closed = [row for row in (tmp_path / '.wuwei/days/2026-10-03/events.jsonl').read_text().splitlines()
              if '"day.closed"' in row]
    assert len(closed) == int(passing)  # #551: next reads it to say the day is done
    if passing:
        before = digest.read_bytes()
        assert close.run(args) == 0 and digest.read_bytes() == before
