"""Git output replay preserves paths and normalizes repository evidence."""

import importlib
from pathlib import Path
import subprocess

import pytest

from fakes.replay import install_replay, recordings


CASES = [c for c in recordings('vcs') if c['operation'] != 'worktree_add']


def adapter():
    return importlib.import_module('adapters.vcs.git')


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['operation'])
def test_read_recording(case, tmp_path, monkeypatch):
    calls = install_replay(monkeypatch, 'git', case['steps'])
    result = getattr(adapter(), case['operation'])(*case['args'], root=tmp_path)
    assert (result.exit, result.data, result.reason) == (0, case['data'], '')
    assert len(calls) == len(case['steps'])


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['operation'])
@pytest.mark.parametrize('response', [{'stdout': 'fatal: unavailable', 'exit': 128},
                                       {'stdout': 'malformed output'}])
def test_reads_fail_closed(case, response, tmp_path, monkeypatch, capsys):
    install_replay(monkeypatch, 'git', [response] * len(case['steps']))
    result = getattr(adapter(), case['operation'])(*case['args'])
    assert result.exit == 2 and result.data is None and result.reason
    assert result.reason in capsys.readouterr().err


@pytest.mark.parametrize('operation', ['status', 'diff_stat', 'log_since'])
def test_empty_collection_is_clean(operation, tmp_path, monkeypatch):
    case = next(c for c in CASES if c['operation'] == operation)
    install_replay(monkeypatch, 'git', [{'stdout': ''}])
    result = getattr(adapter(), operation)(*case['args'])
    assert result.exit == 0 and result.data == []


@pytest.mark.parametrize('failure', [FileNotFoundError(), subprocess.TimeoutExpired('git', 30)])
def test_unavailable_tool(failure, monkeypatch, capsys):
    def fail(*args, **kwargs):
        assert 0 < kwargs['timeout'] <= 30
        raise failure
    monkeypatch.setattr(subprocess, 'run', fail)
    result = adapter().head('/repo')
    assert result.exit == 2 and result.data is None
    assert result.reason in capsys.readouterr().err


@pytest.mark.parametrize('exit_code', [0, 128])
def test_worktree_creation(exit_code, tmp_path, monkeypatch):
    case = next(c for c in recordings('vcs') if c['operation'] == 'worktree_add')
    case['steps'][0]['exit'] = exit_code
    install_replay(monkeypatch, 'git', case['steps'])
    result = adapter().worktree_add(*case['args'], root=tmp_path)
    assert (result.exit, result.data) == ((0, case['data']) if exit_code == 0 else (2, None))


@pytest.mark.parametrize('code,expected', [(0, 0), (1, 1), (128, 2)])
def test_rebase_port_reports_conflict_and_errors(code, expected, monkeypatch, tmp_path):
    conflict = tmp_path / 'rebase-merge'
    conflict.mkdir()
    steps = [{'argv': ['-C', '/repo', 'rebase', '--', 'origin/main'], 'exit': code}]
    if code == 1:
        steps.append({'argv': ['-C', '/repo', 'rev-parse', '--git-path', 'rebase-merge'],
                      'stdout': str(conflict) + '\n'})
    calls = install_replay(monkeypatch, 'git', steps)
    result = adapter().rebase('/repo', 'origin/main')
    assert result.exit == expected
    assert len(calls) == len(steps)


def test_push_port_uses_current_head_and_explicit_branch(monkeypatch):
    calls = install_replay(monkeypatch, 'git', [{'argv': ['-C', '/repo', 'push',
                                                '--force-with-lease=feature:' + 'a' * 40, 'origin',
                                                'HEAD:refs/heads/feature']}])
    assert adapter().push('/repo', 'origin', 'feature', 'a' * 40).exit == 0
    assert len(calls) == 1


def test_rebase_dirty_worktree_is_unavailable(monkeypatch):
    install_replay(monkeypatch, 'git', [
        {'argv': ['-C', '/repo', 'rebase', '--', 'origin/main'], 'exit': 1,
         'stderr': 'Please commit or stash them'},
        {'argv': ['-C', '/repo', 'rev-parse', '--git-path', 'rebase-merge'],
         'stdout': '/repo/.git/rebase-merge\n'},
        {'argv': ['-C', '/repo', 'rev-parse', '--git-path', 'rebase-apply'],
         'stdout': '/repo/.git/rebase-apply\n'},
    ])
    result = adapter().rebase('/repo', 'origin/main')
    assert result.exit == 2 and 'Please commit or stash them' in result.reason


def test_fetch_port_checks_current_host_base(monkeypatch):
    sha = 'b' * 40
    calls = install_replay(monkeypatch, 'git', [
        {'argv': ['-C', '/repo', 'fetch', '--no-tags', 'origin', 'main']},
        {'argv': ['-C', '/repo', 'rev-parse', '--verify', 'FETCH_HEAD^{commit}'],
         'stdout': sha + '\n'},
    ])
    assert adapter().fetch('/repo', 'origin', 'main', sha).data == {'sha': sha}
    assert len(calls) == 2


def test_worktree_identity_port(monkeypatch):
    calls = install_replay(monkeypatch, 'git', [{'stdout': 'true\n'}, {'stdout': ''}, {'stdout': ''}])
    result = adapter().worktree_identity('/repo', 'Builder', 'builder@example.test')
    assert result.exit == 0
    assert result.data == {'name': 'Builder', 'email': 'builder@example.test'}
    assert [call[-6:] for call in calls] == [
        ['-C', '/repo', 'config', '--local', '--get', 'extensions.worktreeConfig'],
        ['-C', '/repo', 'config', '--worktree', 'user.name', 'Builder'],
        ['-C', '/repo', 'config', '--worktree', 'user.email', 'builder@example.test']]



def test_worktree_identity_needs_worktree_config(monkeypatch):
    calls = install_replay(monkeypatch, 'git', [{'exit': 1}])
    result = adapter().worktree_identity('/repo', 'Builder', 'builder@example.test')
    assert result.exit == 1 and 'extensions.worktreeConfig' in result.reason
    assert len(calls) == 1

@pytest.mark.parametrize('operation,args', [
    ('merge_base', ['/repo', '--help']),
    ('diff_stat', ['/repo', '--output=/tmp/unwanted', 'HEAD']),
    ('log_since', ['/repo', '--all']),
    ('worktree_add', ['/repo', '--force', '/path']),
    ('worktree_checkout', ['/repo', '--force', '/path']),
    ('rebase', ['/repo', '--exec=touch unwanted']),
    ('push', ['/repo', 'origin', '--force']),
    ('fetch', ['/repo', '--force', 'main', 'b' * 40]),
    ('worktree_identity', ['/repo', '-x', 'b@example.test']),
    ('worktree_identity', ['/repo', 'A\nB', 'b@example.test']),
    ('worktree_identity', ['/repo', 'A', '<b@example.test>']),
    ('worktree_identity', ['/repo', ' ', 'b@example.test']),
])
def test_option_injection_never_spawns(operation, args, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('invalid input reached subprocess')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    result = getattr(adapter(), operation)(*args)
    assert result.exit == 2 and result.data is None


@pytest.mark.parametrize('args', [
    ('push', 'origin', 'HEAD'),
    ('push', '--force', 'origin', 'HEAD'),
    ('reset', '--hard', 'HEAD'),
    ('config', 'user.email', 'other@example.test'),
    ('commit', '--no-verify', '-m', 'bypass'),
    ('config', '--get', 'alias.push'),
    ('var', 'GIT_EDITOR'),
    ('rev-parse', '--verify', 'main'),
    ('merge-base', 'HEAD', '--all'),
    ('status', '--porcelain=v1', '-z', '--untracked-files=all', '--ignored'),
    ('diff', '--numstat', '-z', '--no-renames', '--output=/tmp/bypass', 'HEAD', '--'),
    ('log', '-z', '--format=%s', 'main..HEAD', '--'),
    ('log', '-z', '--format=%H%x00%an%x00%ae%x00%cn%x00%ce%x00%cI%x00%s', '--all..HEAD', '--'),
    ('worktree', 'add', '-b', '--force', '--', '/tmp/worktree'),
    ('config', '--worktree', 'user.signingkey', 'x'),
    ('config', '--worktree', 'user.name', '-x'),
    (),
])
def test_private_runner_rejects_unsupported_commands(args, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('unsupported command reached subprocess')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    with pytest.raises(ValueError):
        adapter()._run('/repo', *args)


def test_status_preserves_carriage_return_in_filename(tmp_path, monkeypatch):
    install_replay(monkeypatch, 'git', [{'stdout': '?? odd\rname\0'}])
    result = adapter().status('/repo')
    assert result.exit == 0 and result.data[0]['path'] == 'odd\rname'


def test_git_exit_is_explained(tmp_path, monkeypatch, capsys):
    # #362: the first stderr line and the repository now reach the reason, redacted and capped.
    install_replay(monkeypatch, 'git', [{'exit': 128, 'stderr': 'private repository path'}])
    result = adapter().head('/repo')
    assert result.exit == 2 and 'git exited 128' in result.reason
    assert 'git exited 128' in capsys.readouterr().err
    assert '/repo' in result.reason and 'private repository path' in result.reason


def test_stderr_line_and_fetch_hint(monkeypatch):
    install_replay(monkeypatch, 'git', [{'exit': 128, 'stderr':
                                         'fatal: Not a valid object name origin/main\nmore'}])
    result = adapter().merge_base('/repo', 'origin/main')
    assert result.exit == 2
    for text in ('git exited 128', 'merge-base', '/repo', 'fatal: Not a valid object name origin/main',
                 'run git -C /repo fetch origin'):
        assert text in result.reason, text
    assert 'more' not in result.reason


def test_stderr_line_redacted_and_capped(monkeypatch):
    secret = 'ghp_' + 'a' * 36
    install_replay(monkeypatch, 'git', [{'exit': 128, 'stderr': f'fatal: https://x:{secret}@github.com/a/b'}])
    result = adapter().head('/repo')
    assert secret not in result.reason and 'git exited 128' in result.reason
    install_replay(monkeypatch, 'git', [{'exit': 1, 'stderr': 'x' * 500}])
    result = adapter().head('/repo')
    assert 'x' * 200 in result.reason and 'x' * 201 not in result.reason
    install_replay(monkeypatch, 'git', [{'exit': 1, 'stderr': '\n  \n'}])
    result = adapter().head('/repo')
    assert result.reason == 'git.head: could not run: git exited 1 (show in /repo)'


def test_not_a_repository_is_named(monkeypatch):
    install_replay(monkeypatch, 'git', [{'exit': 128, 'stderr': 'fatal: not a git repository '
                                         '(or any of the parent directories): .git'}])
    result = adapter().head('/repo')
    assert result.exit == 2 and 'not a git repository' in result.reason
    assert 'git exited' not in result.reason


def test_inherited_git_dir_cannot_select_another_repository(tmp_path, monkeypatch):
    from pathlib import Path
    import os

    clean_env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    other = subprocess.run(['git', 'rev-parse', '--absolute-git-dir'],
                           cwd=Path(__file__).resolve().parents[1], env=clean_env,
                           capture_output=True, text=True, check=True).stdout.strip()
    subprocess.run(['git', 'init', str(tmp_path)], env=clean_env,
                   capture_output=True, check=True)
    monkeypatch.setenv('GIT_DIR', other)
    result = adapter().head(tmp_path)
    assert result.exit == 2 and result.data is None  # The requested repo has no commits.


def test_git_environment_is_scrubbed(monkeypatch):
    import os

    removed = ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR',
               'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_NAMESPACE',
               'GIT_CEILING_DIRECTORIES', 'GIT_DISCOVERY_ACROSS_FILESYSTEM',
               'GIT_CONFIG', 'GIT_CONFIG_COUNT', 'GIT_CONFIG_KEY_0', 'GIT_CONFIG_VALUE_0')
    for key in removed:
        monkeypatch.setenv(key, 'untrusted')
    retained = ('GIT_AUTHOR_NAME', 'GIT_AUTHOR_EMAIL', 'GIT_AUTHOR_DATE',
                'GIT_COMMITTER_NAME', 'GIT_COMMITTER_EMAIL', 'GIT_COMMITTER_DATE',
                'GIT_FUTURE_OPTION')
    for key in retained:
        monkeypatch.setenv(key, 'retained')
    monkeypatch.setenv('ADAPTER_TEST_KEEP', 'retained')

    def run(args, **kwargs):
        env = kwargs.get('env', os.environ)
        assert not any(key in env for key in removed)
        assert all(env.get(key) == 'retained' for key in retained)
        assert env['ADAPTER_TEST_KEEP'] == 'retained'
        return subprocess.CompletedProcess(args, 0,
            b'a' * 40 + b'\0Builder\0builder@example.test\0Builder\0builder@example.test\n', b'')
    monkeypatch.setattr(subprocess, 'run', run)
    assert adapter().head('/repo').exit == 0


def test_identity_reports_environment_overrides(tmp_path, monkeypatch):
    import os

    for key in list(os.environ):
        if key.startswith('GIT_'):
            monkeypatch.delenv(key)
    subprocess.run(['git', 'init', str(tmp_path)], capture_output=True, check=True)
    (tmp_path / '.git/config').write_text(
        '[user]\n\tname = Builder\n\temail = builder@example.test\n')
    monkeypatch.setenv('GIT_AUTHOR_EMAIL', 'author@example.test')
    monkeypatch.setenv('GIT_COMMITTER_EMAIL', 'committer@example.test')
    monkeypatch.setenv('GIT_DIR', str(tmp_path / 'missing-repository'))
    result = adapter().identity(tmp_path)
    assert result.exit == 0
    assert result.data['email'] == 'builder@example.test'
    assert result.data['author']['email'] == 'author@example.test'
    assert result.data['committer']['email'] == 'committer@example.test'


def test_recursion_failure_is_unavailable(monkeypatch):
    def fail(*args, **kwargs):
        raise RecursionError('private details')
    monkeypatch.setattr(subprocess, 'run', fail)
    result = adapter().head('/repo')
    assert result.exit == 2 and result.data is None
    assert 'private' not in result.reason


def test_real_path_smoke(tmp_path, monkeypatch):
    from fakes.replay import install_stub

    case = next(c for c in CASES if c['operation'] == 'head')
    calls = install_stub(tmp_path, monkeypatch, 'git', case['steps'])
    result = adapter().head(*case['args'])
    assert result.exit == 0 and result.data == case['data']
    assert len(calls.read_text().splitlines()) == 1

    install_stub(tmp_path, monkeypatch, 'git', [{'sleep': 10}])
    monkeypatch.setattr(adapter(), 'TIMEOUT', 0.05)
    result = adapter().head('/repo')
    assert result.exit == 2 and 'TimeoutExpired' in result.reason

    (tmp_path / 'tools/git').unlink()
    result = adapter().head('/repo')
    assert result.exit == 2 and 'FileNotFoundError' in result.reason


@pytest.mark.parametrize('exit_code,stdout,expected', [(0, 'a' * 40 + '\n', 0),
                                                       (1, '', 1), (128, '', 2)])
def test_resolve_commit(exit_code, stdout, expected, monkeypatch):
    calls = install_replay(monkeypatch, 'git', [{'stdout': stdout, 'exit': exit_code}])
    port = adapter()
    assert hasattr(port, 'resolve'), 'vcs must resolve approval-free commit claims'
    result = port.resolve('/repo', 'aaaaaaa')
    assert result.exit == expected
    assert calls[0][-4:] == ['rev-parse', '--verify', '--quiet', 'aaaaaaa^{commit}']
    if expected == 0:
        assert result.data == {'sha': 'a' * 40}


def test_changes_on_date_and_literal_paths(tmp_path, monkeypatch):
    api = adapter()
    assert hasattr(api, 'changes_on'), 'dated path evidence missing'
    calls = install_replay(monkeypatch, 'git', [{'stdout': '\nroles/a b.md\0roles/planner.md\0'}])
    result = api.changes_on(str(tmp_path), '2026-09-28')
    assert result.exit == 0 and result.data == ['roles/a b.md', 'roles/planner.md']
    assert '--since=2026-09-28T00:00:00' in calls[0]
    assert '--until=2026-09-28T23:59:59' in calls[0]


def test_changes_on_preserves_git_output_paths(tmp_path, monkeypatch):
    paths = ['docs/[draft].md', 'docs/question?.md', 'docs/star*.md', '-notes.md']
    install_replay(monkeypatch, 'git', [{'stdout': '\n' + '\0'.join(paths + paths) + '\0'}])
    result = adapter().changes_on(str(tmp_path), '2026-09-28')
    assert result.exit == 0
    assert result.data == sorted(paths)


@pytest.mark.parametrize('ref', ['HEAD', 'a' * 40])
@pytest.mark.parametrize('path', ['roles', '.'])
def test_read_tree_recording(tmp_path, monkeypatch, ref, path):
    api = adapter()
    assert hasattr(api, 'read_tree'), 'committed tree evidence missing'
    steps = [{'stdout': 'roles/a b.md\0'}, {'stdout': 'f' * 40 + ' blob 13\nlearned rule\n\n'}]
    calls, stdin = batch_replay(monkeypatch, steps)
    result = api.read_tree(str(tmp_path), ref, [path])
    assert result.exit == 0 and result.data == {'roles/a b.md': 'learned rule\n'}
    assert calls[-1][-2:] == ['cat-file', '--batch']
    assert stdin == [None, f'{ref}:roles/a b.md\n'.encode()]
    assert calls[0][-1] == path


def batch_replay(monkeypatch, steps):
    calls = install_replay(monkeypatch, 'git', steps)
    run, stdin = subprocess.run, []
    def record(argv, **kwargs):
        stdin.append(kwargs.get('input'))
        return run(argv, **kwargs)
    monkeypatch.setattr(subprocess, 'run', record)
    return calls, stdin


@pytest.mark.parametrize('output', ['HEAD:roles/a b.md missing\n', 'f' * 40 + ' commit 13\nlearned rule\n\n',
                                    'f' * 40 + ' blob 13\nlearned\n'])
def test_read_tree_batch_rejects_missing_or_non_blob(tmp_path, monkeypatch, output):
    batch_replay(monkeypatch, [{'stdout': 'roles/a b.md\0'}, {'stdout': output}])
    assert adapter().read_tree(str(tmp_path), 'HEAD', ['roles']).exit == 2


def test_read_tree_real_git_one_batch(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'
    (repo / 'dir').mkdir(parents=True)
    (repo / 'a b.md').write_text('rule\n')
    (repo / 'dir/c.bin').write_bytes(b'bin\xff\n\x00')
    git = ['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@localhost', '-c', 'commit.gpgSign=false']
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    subprocess.run([*git, 'add', '.'], check=True)
    subprocess.run([*git, 'commit', '-qm', 'init'], check=True)
    run, calls = subprocess.run, []
    monkeypatch.setattr(subprocess, 'run', lambda argv, **kw: calls.append(argv) or run(argv, **kw))
    result = adapter().read_tree(str(repo), 'HEAD', ['.'])
    assert result.exit == 0 and len(calls) == 2
    assert result.data == {'a b.md': 'rule\n', 'dir/c.bin': b'bin\xff\n\x00'.decode('utf-8', 'surrogateescape')}


@pytest.mark.parametrize('operation,args', [
    ('changes_on', ['--help']), ('changes_on', ['2026-09-31']),
    ('read_tree', ['--help', ['roles']]), ('read_tree', ['HEAD', ['../outside']]),
    ('read_tree', ['HEAD', [':(top)*']]), ('read_tree', ['HEAD', []]),
    ('read_tree', ['', ['roles']]),
])
def test_retro_port_rejects_injection(tmp_path, monkeypatch, operation, args):
    api = adapter()
    assert hasattr(api, operation)
    def forbidden(*args, **kwargs):
        pytest.fail('invalid input reached subprocess')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    assert getattr(api, operation)(str(tmp_path), *args).exit == 2


@pytest.mark.parametrize('operation,args', [('changes_on', ['2026-09-28']),
                                         ('read_tree', ['HEAD', ['roles']])])
def test_retro_port_failed_read(tmp_path, monkeypatch, operation, args):
    api = adapter()
    assert hasattr(api, operation)
    install_replay(monkeypatch, 'git', [{'exit': 128, 'stdout': 'fatal'}])
    assert getattr(api, operation)(str(tmp_path), *args).exit == 2


@pytest.mark.parametrize('stdout', ['feat: no separator\0', 'a\x1fb\x1fc\0'])
def test_recent_commits_rejects_malformed_records(stdout, monkeypatch):
    install_replay(monkeypatch, 'git', [{'stdout': stdout}])
    result = adapter().recent_commits('/repo')
    assert result.exit == 2 and result.data is None


def test_remote_url_reads_origin(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    assert adapter().remote_url(tmp_path).data == {'url': ''}
    subprocess.run(['git', '-C', str(tmp_path), 'remote', 'add', 'origin',
                    'https://github.com/acme/widget.git'], check=True)
    assert adapter().remote_url(tmp_path).data == {'url': 'https://github.com/acme/widget.git'}


def test_default_branch_from_git(tmp_path, capsys):
    def git(*args):
        subprocess.run(['git', '-C', str(tmp_path), *args], check=True, capture_output=True)

    git('init', '-q', '-b', 'trunk')
    git('-c', 'user.name=Pat Example', '-c', 'user.email=pat@example.test', 'commit', '-q', '--allow-empty',
        '-m', 'feat: start')
    assert adapter().default_branch(tmp_path).data == {'branch': 'trunk', 'source': 'the checked-out branch'}
    git('update-ref', 'refs/remotes/origin/develop', 'HEAD')
    git('symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/develop')
    assert adapter().default_branch(tmp_path).data == {'branch': 'develop', 'source': 'origin/HEAD'}
    git('symbolic-ref', '--delete', 'refs/remotes/origin/HEAD')
    git('checkout', '-q', '--detach')
    result = adapter().default_branch(tmp_path)
    assert result.exit == 2 and 'git.default_branch' in result.reason


def test_worktrees_and_checkout_existing_branch(tmp_path):
    repo = tmp_path / 'repo'

    def git(*args):
        return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True,
                              text=True).stdout.strip()

    subprocess.run(['git', 'init', '-q', '-b', 'main', str(repo)], check=True)
    git('-c', 'user.name=Pat Example', '-c', 'user.email=pat@example.test', 'commit', '-q',
        '--allow-empty', '-m', 'feat: start')
    git('branch', 'feature-x')
    git('branch', 'feature-y')
    git('worktree', 'add', '-q', '--detach', str(tmp_path / 'detached'))
    sha = git('rev-parse', 'HEAD')
    result = adapter().worktree_checkout(repo, 'feature-x', str(tmp_path / 'x'))
    assert result.exit == 0 and result.data == {'branch': 'feature-x', 'path': str(tmp_path / 'x')}
    assert git('branch', '--list', '--format=%(refname:short)').split() == ['feature-x', 'feature-y', 'main']
    rows = adapter().worktrees(repo).data
    by_path = {Path(row['path']).resolve(): row for row in rows}
    assert by_path[repo.resolve()] == {'path': by_path[repo.resolve()]['path'], 'head': sha, 'branch': 'main'}
    assert by_path[(tmp_path / 'x').resolve()]['branch'] == 'feature-x'
    assert by_path[(tmp_path / 'x').resolve()]['head'] == sha
    assert by_path[(tmp_path / 'detached').resolve()]['branch'] is None
    assert adapter().worktree_checkout(repo, 'feature-x', str(tmp_path / 'again')).exit == 2


@pytest.mark.parametrize('stdout', ['worktree /r\0HEAD x\0\0', 'HEAD ' + 'a' * 40 + '\0\0', 'worktree /r'])
def test_worktrees_rejects_malformed_records(stdout, monkeypatch):
    install_replay(monkeypatch, 'git', [{'stdout': stdout}])
    assert adapter().worktrees('/repo').exit == 2


def test_rehearse_revert_on_a_scratch_repository():
    # #557: the one real smoke test of the commit undo rehearsal.
    import tempfile
    git = adapter()
    with tempfile.TemporaryDirectory() as scratch:
        result = git.rehearse_revert(scratch)
        assert result.exit == 0 and result.data['reverted'] is True
        assert result.data['tree'] and (Path(scratch) / 'rehearsal.txt').read_text() == 'before\n'
    outside = Path(__file__).resolve().parents[1]
    for args in (('revert', '--no-edit', 'HEAD'), ('add', '--', 'rehearsal.txt'),
                 ('commit', '--quiet', '-m', 'WUWEI undo rehearsal'),
                 ('rev-parse', 'HEAD^{tree}', 'HEAD~2^{tree}')):
        with pytest.raises(ValueError, match='unsupported git command'):
            git._run(outside, *args, local=True)
