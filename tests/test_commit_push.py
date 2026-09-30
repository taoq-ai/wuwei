"""Both enforcement anchors share the source harness's ordered identity policy."""

import importlib
import os
from pathlib import Path

import pytest

from wuwei.registry import Result
from fakes.vcs import Fake


OWNER = {'name': 'Builder', 'email': 'builder@example.test'}
OTHER = {'name': 'Other', 'email': 'other@example.test'}
SHA = 'a' * 40
OLD = 'b' * 40


def set_fast_checks(root, checks):
    """Seed trusted or malformed on-disk evidence for guard policy tables."""
    from wuwei import state
    state._write_state(lambda data: data.update(fast_checks=checks), root, reserved=False)


def guard():
    path = Path(__file__).resolve().parents[1] / 'cli/wuwei/guards/commit_push.py'
    assert path.exists(), 'commit/push guard is missing'
    return importlib.import_module('wuwei.guards.commit_push')


@pytest.mark.parametrize('author,committer,head,code,reason', [
    (OWNER, OWNER, None, 0, ''),
    (OTHER, OTHER, None, 1, 'GIT_AUTHOR_IDENT'),
    (OWNER, OTHER, None, 1, 'GIT_COMMITTER_IDENT'),
    (OWNER, OWNER, {'author': OWNER, 'committer': OWNER}, 0, ''),
    (OTHER, OWNER, {'author': OTHER, 'committer': OTHER}, 1, 'GIT_AUTHOR_IDENT'),
    (OWNER, OTHER, {'author': OTHER, 'committer': OTHER}, 1, 'GIT_COMMITTER_IDENT'),
    (OWNER, OWNER, {'author': OTHER, 'committer': OWNER}, 1, 'HEAD'),
    (OWNER, OWNER, {'author': OWNER, 'committer': OTHER}, 1, 'HEAD'),
    ({}, OWNER, None, 2, 'identity'),
    (OWNER, OWNER, {}, 2, 'identity'),
])
def test_source_harness_refusals_in_order(author, committer, head, code, reason):
    result = guard().identity_check(OWNER, {'author': author, 'committer': committer}, head)
    assert result[0] == code
    assert reason in result[1]


@pytest.mark.parametrize('expected', [{}, {'name': '', 'email': 'x'}, None])
def test_missing_expected_identity_fails_closed(expected):
    assert guard().identity_check(expected, {'author': OWNER, 'committer': OWNER})[0] == 2


def test_opaque_interpreter_names_direct_push_command(workspace_case):
    root, _ = workspace_case
    code, reason = guard().check(payload(root, 'python3 -c "import subprocess; subprocess.run([\'git\', \'push\', \'-f\'])"'))
    assert code == 2
    assert 'git push origin HEAD:refs/heads/<branch>' in reason


@pytest.fixture
def workspace_case(tmp_path, monkeypatch):
    from wuwei import registry, state

    for key in list(os.environ):
        if key.startswith('GIT_'):
            monkeypatch.delenv(key)
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / 'repo').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('''
[[repos]]
name = "example/project"
path = "repo"
default_branch = "main"
fast_checks = ["unit"]
identity = {name = "Builder", email = "builder@example.test"}
''')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00Z')
    from fakes.integrity import seed
    seed(tmp_path)
    set_fast_checks(tmp_path, {'example/project': {'unit': {'sha': SHA, 'exit': 0}}})
    context = {'path': str(tmp_path / 'repo'), 'common_dir': str(tmp_path / 'repo/.git'),
               'author': dict(OWNER), 'committer': dict(OWNER)}
    push = {'head': {'sha': SHA, 'author': dict(OWNER), 'committer': dict(OWNER)},
            'updates': [{'source': SHA, 'destination': 'refs/heads/feature'}], 'force': False, 'remote': 'origin'}
    fake = Fake({'commit_context': Result(0, context), 'push_context': Result(0, push),
                 'repo_context': Result(0, {key: context[key] for key in ('path', 'common_dir')}),
                 'head': Result(0, push['head']),
                 'push_commits': Result(0, {'commits': [push['head']]}),
                 'merge_base': Result(0, {'sha': OLD})})
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake)
    return tmp_path, fake


def payload(root, command):
    return {'cwd': str(root / 'repo'), 'tool_name': 'Bash',
            'tool_input': {'command': command}}


@pytest.mark.parametrize('command,code', [
    ('git commit -m safe', 0), ('git push', 2),
    ('git push -u origin HEAD:refs/heads/feature', 0),
    ('sh -c "git commit -m safe"', 0), ('(git push origin HEAD:refs/heads/feature)', 0),
    ('env GIT_AUTHOR_EMAIL=builder@example.test git commit -m safe', 0),
    ('git -c user.email=builder@example.test commit -m safe', 0),
    ('git -c user.email=x commit', 1),
    ('git -cuser.email=x commit', 1),
    ('GIT_AUTHOR_EMAIL=x git commit', 1),
    ('env GIT_COMMITTER_NAME=Other git commit', 1),
    ('git commit --author="Other <other@example.test>"', 1),
    ('git commit --author="Builder <builder@example.test>" -m safe', 0),
    ('git commit --amend', 2), ('git commit -C HEAD', 2),
    ('git commit --amend --reset-author -m safe', 0),
    ('git commit --no-verify', 1),
    ('git push --force', 1), ('git push -f', 1), ('git push -vf', 1),
    ('git push --force-with-lease', 1), ('git push --force-with-lease=main:abc', 1),
    ('git push --force-if-includes', 1), ('git push --mirror', 1),
    ('git push origin +HEAD:feature', 1),
    ('sh -c \'git push --force\'', 1), ('env command git push --force', 1),
    ('bash -c \'git push --force\'', 1),
    ('zsh -c \'git push --force\'', 1),
    ('exec git push --force', 1),
    ('git -C . push --force', 1),
    ('node -e "require(\'child_process\').execSync(\'git push --force\')"', 2),
    ('perl -e "system(\'git push --force\')"', 2),
    ('python3 -c "import subprocess; subprocess.run([\'git\',\'push\',\'-f\'])"', 2),
    ('printf x | xargs git push', 2),
    ('git push "$REMOTE"', 2), ('git push --receive-pack=helper', 2),
    ('git -c core.hooksPath=/dev/null push', 2),
    ('GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=user.email GIT_CONFIG_VALUE_0=x git commit', 2),
    ('git -C', 0), ('git push "', 2),
    ('cd other; git push', 2), ('git config user.email x; git commit', 2),
    ('GIT_AUTHOR_EMAIL=x; git commit', 2),
    ('npm test', 0), ('git status', 0),
    ('./push.sh', 2), ('sh push.sh', 2), ('bash push.sh', 2),
    ('./run.sh', 0), ('sh run.sh', 0), ('bash run.sh', 0),
])
def test_bash_table(workspace_case, command, code):
    root, fake = workspace_case
    (root / 'repo/push.sh').write_text('git push --force\n')
    (root / 'repo/run.sh').write_text('echo ok\n')
    result = guard().check(payload(root, command))
    assert result[0] == code, result
    if code:
        assert result[1]


@pytest.mark.parametrize('command,repo_suffix,settings,env', [
    ('git -C child -C .. commit', 'repo', {}, {}),
    ('git -c user.email=builder@example.test commit', 'repo', {'user.email': OWNER['email']}, {}),
    ('GIT_DIR=other/.git GIT_WORK_TREE=other git commit', 'repo', {},
     {'GIT_DIR': 'other/.git', 'GIT_WORK_TREE': 'other'}),
])
def test_context_forwarded_to_vcs(workspace_case, command, repo_suffix, settings, env):
    root, fake = workspace_case
    assert guard().check(payload(root, command))[0] == 0
    operation, args, context = fake.calls[0]
    assert operation == 'commit_context'
    assert args == (str(root / repo_suffix), settings, env)
    assert context == root


@pytest.mark.parametrize('head_field', ['author', 'committer'])
def test_push_checks_head_identity(workspace_case, head_field):
    root, fake = workspace_case
    fake.results['push_context'].data['head'][head_field] = OTHER
    result = guard().check(payload(root, 'git push origin feature'))
    assert result[0] == 1 and 'HEAD' in result[1]


@pytest.mark.parametrize('change,code', [
    ({'updates': [{'source': SHA, 'destination': 'refs/heads/main'}]}, 1),
    ({'updates': [{'source': OLD, 'destination': 'refs/heads/feature'}]}, 1),
    ({'updates': [{'source': SHA, 'destination': 'refs/tags/v1'}]}, 2),
    ({'updates': []}, 2), ({'updates': None}, 2), ({'force': True}, 1),
    ({'head': {}}, 2), ({'force': 'false'}, 2),
])
def test_push_context_policy(workspace_case, change, code):
    root, fake = workspace_case
    fake.results['push_context'].data.update(change)
    assert guard().check(payload(root, 'git push origin feature'))[0] == code


@pytest.mark.parametrize('record,code', [
    ({'sha': SHA, 'exit': 0}, 0), ({'sha': OLD, 'exit': 0}, 1),
    ({'sha': SHA, 'exit': 1}, 1), ({'sha': SHA, 'exit': 2}, 1),
    (None, 1), ({}, 2), ({'sha': SHA, 'exit': False}, 2),
    ({'sha': SHA, 'exit': '0'}, 2), ({'sha': SHA, 'exit': 3}, 2),
])
def test_fast_checks_are_bound_to_head(workspace_case, record, code):
    from wuwei import state
    root, _ = workspace_case
    checks = {} if record is None else {'unit': record}
    set_fast_checks(root, {'example/project': checks})
    assert guard().check(payload(root, 'git push origin feature'))[0] == code


@pytest.mark.parametrize('operation', ['commit_context', 'push_context'])
@pytest.mark.parametrize('result', [Result(2, None, 'offline'), Result(0, {}), Result(0, None)])
def test_port_errors_fail_closed(workspace_case, operation, result):
    root, fake = workspace_case
    fake.results[operation] = result
    assert guard().check(payload(root, 'git push origin feature'))[0] == 2


@pytest.mark.parametrize('settings,env', [({'user.name': 'Other'}, {}), ({}, {'GIT_DIR': 'other/.git'})])
def test_identity_free_context_refuses_overrides(workspace_case, settings, env):
    root, fake = workspace_case
    with pytest.raises(ValueError, match='identity-free'):
        guard().context(root / 'repo', settings, env, root, identity=False)
    assert not fake.calls


def test_unconfigured_repository_is_unmeasured(workspace_case):
    root, fake = workspace_case
    original = fake._call
    def call(operation, args, context):
        result = original(operation, args, context)
        if operation == 'commit_context' and len(fake.calls) == 1:
            result.data['common_dir'] = str(root / 'other/.git')
        return result
    fake._call = call
    assert guard().check(payload(root, 'git commit'))[0] == 2


@pytest.mark.parametrize('text', [
    'HOME=alternate git push', 'XDG_CONFIG_HOME=alternate git push',
    'PATH=alternate git push', 'env -i git push', 'env -u GIT_AUTHOR_EMAIL git commit',
    'exec -c git push',
])
def test_context_changes_and_scripts_fail_closed(workspace_case, text):
    root, _ = workspace_case
    assert guard().check(payload(root, text))[0] == 2


def test_inherited_git_config_cannot_change_push_destination(workspace_case, monkeypatch):
    root, _ = workspace_case
    monkeypatch.setenv('GIT_CONFIG_PARAMETERS', "'remote.origin.push'='HEAD:refs/heads/main'")
    assert guard().check(payload(root, 'git push origin feature'))[0] == 2


def test_tool_hook_routes_and_translates_guard(workspace_case, monkeypatch, capsys):
    import io
    import json
    import sys
    from types import SimpleNamespace
    from wuwei.commands.hook import run
    root, _ = workspace_case
    event = payload(root, "sh -c 'git push --force'")
    event.update(session_id='example', transcript_path='transcript.jsonl', hook_event_name='PreToolUse')
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(event)))
    assert run(SimpleNamespace(event='PreToolUse')) == 2
    output = capsys.readouterr()
    assert json.loads(output.out)['hookSpecificOutput']['permissionDecision'] == 'deny'
    assert 'force-push' in output.err


def test_common_directory_override_fails_closed(workspace_case):
    root, _ = workspace_case
    assert guard().check(payload(root, 'GIT_COMMON_DIR=other/.git git push'))[0] == 2


@pytest.mark.parametrize('command', [
    'python3 -m pytest -q', 'python3 script.py', './run.sh', '.venv/bin/pytest -q',
    'node server.js', 'for x in a b; do echo "$x"; done', 'X=1; echo $X',
    'grep -rn git .',
])
def test_unrelated_commands_through_bin(workspace_case, command):
    import json
    import subprocess
    root, _ = workspace_case
    event = payload(root, command)
    event.update(session_id='test', transcript_path='trace', hook_event_name='PreToolUse')
    result = subprocess.run([str(Path(__file__).resolve().parents[1] / 'bin/wuwei'),
                             'hook', 'PreToolUse'], input=json.dumps(event),
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_no_workspace_allows_relevant_command(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert guard().check(payload(tmp_path, 'git push --force')) == (0, '')


def test_missing_config_in_existing_workspace_blocks(workspace_case):
    root, _ = workspace_case
    (root / '.wuwei/config.toml').unlink()
    assert guard().check(payload(root, 'git commit'))[0] == 2


@pytest.mark.parametrize('command', [
    'git add . && git commit -m x', 'git commit -am x',
    'git commit --fixup HEAD', 'git commit --fixup=HEAD',
    'git commit --trailer "Reviewed-by: Someone" -m x',
])
def test_ordinary_commit_options(workspace_case, command):
    root, _ = workspace_case
    assert guard().check(payload(root, command))[0] == 0


@pytest.mark.parametrize('verb', ['merge', 'revert', 'cherry-pick', 'rebase', 'am',
                                  'commit-tree', 'notes', 'status'])
@pytest.mark.parametrize('override', ['-c user.email=x', 'ENV'])
def test_all_identity_overrides_are_checked(workspace_case, verb, override):
    root, _ = workspace_case
    text = (f'GIT_AUTHOR_EMAIL=x git {verb}' if override == 'ENV'
            else f'git {override} {verb}')
    assert guard().check(payload(root, text))[0] == 1


@pytest.mark.parametrize('options', ['core.hooksPath /tmp/other', '--unset core.hooksPath',
                                    '--unset-all core.hooksPath', '--worktree core.hooksPath x',
                                    'set core.hooksPath x'])
def test_hook_config_writes_refused(workspace_case, options):
    root, _ = workspace_case
    assert guard().check(payload(root, 'git config ' + options))[0] == 1


@pytest.mark.parametrize('anchor', ['bash', 'pre-push'])
@pytest.mark.parametrize('kind', ['author', 'committer'])
def test_entire_pushed_range_identity(workspace_case, monkeypatch, anchor, kind):
    root, fake = workspace_case
    commits = [{'sha': SHA, 'author': OWNER, 'committer': OWNER},
               {'sha': OLD, 'author': OWNER, 'committer': OWNER}]
    commits[1][kind] = OTHER
    fake.results['push_commits'] = Result(0, {'commits': commits})
    if anchor == 'bash':
        result = guard().check(payload(root, 'git push origin feature'))[0]
    else:
        from test_git_hook import invoke
        result = invoke(workspace_case, monkeypatch, anchor,
                        f'refs/heads/feature {SHA} refs/heads/feature {"c"*40}\n')
    assert result == 1
    assert any(call[0] == 'push_commits' for call in fake.calls)


@pytest.mark.parametrize('result', [Result(2, None, 'unavailable'), Result(0, {}),
                                    Result(0, {'commits': [{}]})])
def test_range_read_fails_closed(workspace_case, result):
    root, fake = workspace_case
    fake.results['push_commits'] = result
    assert guard().check(payload(root, 'git push origin feature'))[0] == 2


@pytest.mark.parametrize('branch', ['production', 'release/v1'])
def test_environment_branch_refused(workspace_case, branch):
    root, fake = workspace_case
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('\n[environments]\nproduction = "Production"\n"release/*" = "Release"\n')
    fake.results['push_context'].data['updates'][0]['destination'] = 'refs/heads/' + branch
    assert guard().check(payload(root, 'git push origin ' + branch))[0] == 1


@pytest.mark.parametrize('command', ['git push', 'git push origin', 'git push -n origin feature'])
def test_push_needs_explicit_ref_and_hooks(workspace_case, command):
    root, _ = workspace_case
    result = guard().check(payload(root, command))
    assert result[0] != 0


@pytest.mark.parametrize('command', [
    "sh -c 'GIT_AUTHOR_EMAIL=x; git commit'",
    'git config core.hooksPath get', 'git config set core.hooksPath --get',
])
def test_local_parser_context_cannot_hide_mutation(workspace_case, command):
    root, _ = workspace_case
    assert guard().check(payload(root, command))[0] != 0


@pytest.mark.parametrize('message', ['-am', '-author', '-a'])
def test_commit_message_is_not_expanded_as_options(workspace_case, message):
    root, _ = workspace_case
    assert guard().check(payload(root, 'git commit -m ' + message))[0] == 0


@pytest.mark.parametrize('verb', ['merge', 'revert', 'cherry-pick', 'rebase', 'am', 'commit-tree', 'notes'])
def test_commit_creating_verbs_check_effective_identity(workspace_case, verb):
    root, fake = workspace_case
    fake.results['commit_context'].data['committer'] = OTHER
    assert guard().check(payload(root, 'git ' + verb))[0] == 1


def test_config_environment_identity_override_on_read_verb(workspace_case):
    root, _ = workspace_case
    command = 'GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=user.email GIT_CONFIG_VALUE_0=x git status'
    assert guard().check(payload(root, command))[0] == 2


@pytest.mark.parametrize('command', [
    'git "pu"sh --force origin HEAD:refs/heads/main',
    'g"it" push --force',
    r'git pu\sh -f origin main',
    "g''it -c user.email=evil@x commit -m x",
    "git 're'vert",
    r"$'\147it' push -f",
    r"$'\147it' $'\160ush' -f",
    '${TOOL} ${VERB} -f',
    '$(printf %s g it) $(printf %s pu sh) -f',
    'g?t pu?h -f',
    'git "$VERB" origin main',
    "sh -c 'git $VERB origin main'",
    'git p* -f origin main',
])
def test_obfuscated_guarded_commands_are_not_skipped(workspace_case, command):
    root, fake = workspace_case
    if command == "git 're'vert":
        fake.results['commit_context'].data['committer'] = OTHER
    result = guard().check(payload(root, command))
    assert result[0] in (1, 2), result


@pytest.mark.parametrize('verb', ['commit -m x', 'merge topic', 'revert HEAD',
                                  'cherry-pick topic', 'rebase main', 'am patch',
                                  'commit-tree HEAD^{tree}', 'notes add -m x'])
@pytest.mark.parametrize('separator', ['&&', ';', '||', '|'])
def test_push_after_commit_creation_is_refused(workspace_case, verb, separator):
    root, fake = workspace_case
    command = f'git {verb} {separator} git push origin feature'
    result = guard().check(payload(root, command))
    assert result[0] == 1, result
    assert not any(call[0] == 'push_context' for call in fake.calls)


def test_push_before_commit_can_use_current_evidence(workspace_case):
    root, _ = workspace_case
    assert guard().check(payload(root, 'git push origin feature && git commit -m x'))[0] == 0


@pytest.mark.parametrize('options', [
    'extensions.worktreeConfig false', '--unset extensions.worktreeConfig',
    '--unset-all extensions.worktreeConfig', '--local extensions.worktreeConfig false',
    'set extensions.worktreeConfig false',
    '--remove-section core', '--remove-section extensions',
    '--rename-section core disabled', '--rename-section extensions disabled',
    '--local --remove-section core', '--worktree --rename-section core disabled',
    '--remove-section=core', '--rename-section=extensions disabled',
    'remove-section extensions', 'rename-section extensions disabled',
])
def test_worktree_hook_disabling_config_is_refused(workspace_case, options):
    root, _ = workspace_case
    assert guard().check(payload(root, 'git config ' + options))[0] == 1


@pytest.mark.parametrize('command', [
    'rm -f .git/worktrees/feature/wuwei-workspace',
    'command rm -- /repo/.git/worktrees/feature/wuwei-workspace',
    "sh -c 'rm /repo/.git/worktrees/feature/wuwei-workspace'",
    'rm ../.wuwei/executable',
])
def test_hook_pointer_removal_is_refused(workspace_case, command):
    root, _ = workspace_case
    assert guard().check(payload(root, command))[0] == 1


@pytest.mark.parametrize('command', [
    'git config --get extensions.worktreeConfig', 'git config get core.hooksPath',
    'git config --remove-section user', 'rm temporary.txt',
])
def test_commands_not_disabling_hooks_still_pass(workspace_case, command):
    root, _ = workspace_case
    assert guard().check(payload(root, command))[0] == 0


@pytest.mark.parametrize('command', [
    'echo $(date)', 'echo $(date) > out.txt', 'git rev-parse HEAD > $(mktemp)',
])
def test_unrelated_substitutions_do_not_make_commit_push_relevant(workspace_case, command):
    root, fake = workspace_case
    assert guard().check(payload(root, command)) == (0, '')
    assert not fake.calls


@pytest.mark.parametrize('form', [
    'git -C {repo} {action}',
    'git -C{repo} {action}',
    'git -C {root} -C repo {action}',
    'cd {repo} && git {action}',
    '(cd {repo} && git {action})',
    "sh -c 'cd {repo} && git {action}'",
    'pushd {repo} && git {action}',
    'git --git-dir={repo}/.git --work-tree={repo} {action}',
    'git --git-dir {repo}/.git --work-tree {repo} {action}',
    'GIT_DIR={repo}/.git GIT_WORK_TREE={repo} git {action}',
    'git --git-dir={repo}/.git {action}',
    'git --work-tree={repo} {action}',
])
@pytest.mark.parametrize('action,code', [
    ('push --force origin main', 1),
    ('push origin main', 1),
    ('push origin feature', 0),
    ('commit --author="Other <other@example.test>"', 1),
    ('commit -m safe', 0),
    ('push', 2),
])
def test_outside_cwd_targets_configured_repository(workspace_case, monkeypatch, form, action, code):
    root, fake = workspace_case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    if action == 'push origin main':
        fake.results['push_context'].data['updates'][0]['destination'] = 'refs/heads/main'
    command = form.format(root=root, repo=root / 'repo', action=action)
    event = {'cwd': str(root.parent), 'tool_input': {'command': command}}
    result = guard().check(event)
    assert result[0] == code, result
    if code:
        assert result[1]
    else:
        assert any(call[0] == 'commit_context' for call in fake.calls)


@pytest.mark.parametrize('form', [
    'git -C {target} push --force',
    'cd {target} && git push --force',
    '(cd {target} && git push --force)',
    'git --git-dir={gitdir} push --force',
    'GIT_DIR={gitdir} git push --force',
])
def test_outside_managed_worktree_target(workspace_case, monkeypatch, form):
    root, fake = workspace_case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    target = root.parent / (root.name + '-worktree')
    gitdir = root.parent / (root.name + '-metadata')
    target.mkdir()
    gitdir.mkdir()
    (target / '.git').write_text(f'gitdir: {gitdir}\n')
    (gitdir / 'wuwei-workspace').write_text(str(root) + '\n')
    fake.results['commit_context'].data['path'] = str(gitdir)
    result = guard().check({'cwd': str(root.parent), 'tool_input': {
        'command': form.format(target=target, gitdir=gitdir)}})
    assert result[0] == 1, result


@pytest.mark.parametrize('selected', [False, True])
@pytest.mark.parametrize('command', [
    'git push --force origin main', 'git commit --no-verify',
    'git -C . push --force', 'cd . && git push --force',
    'git --git-dir=.git --work-tree=. push --force',
    'GIT_DIR=.git git push --force',
])
def test_unrelated_target_passes_with_or_without_workspace_context(workspace_case, monkeypatch, selected, command):
    root, fake = workspace_case
    if not selected:
        monkeypatch.delenv('WUWEI_WORKSPACE')
    outside = root.parent / (root.name + '-unrelated')
    outside.mkdir()
    result = guard().check({'cwd': str(outside), 'tool_input': {'command': command}})
    assert result == (0, ''), result
    assert fake.calls == []


@pytest.mark.parametrize('command', [
    'python3 -m pytest -q', 'for x in a b; do echo "$x"; done', 'export X=1',
])
def test_irrelevance_precedes_normalization(workspace_case, monkeypatch, command):
    from wuwei import shell
    root, _ = workspace_case
    monkeypatch.setattr(shell, 'normalize', lambda *_: pytest.fail('irrelevant call parsed'))
    assert guard().check(payload(root, command)) == (0, '')


@pytest.mark.parametrize('command', [
    'git -C {repo} push --force && git push origin feature',
    '(cd {repo} && git status); git -C {repo} push --force',
    'cd {repo} && (cd child && git status); git push --force',
    'cd {repo} && popd && git push --force',
    'cd {repo} && git commit -m safe && git push origin feature',
])
def test_compound_target_cannot_escape_rules(workspace_case, monkeypatch, command):
    root, _ = workspace_case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    result = guard().check({'cwd': str(root.parent), 'tool_input': {
        'command': command.format(repo=root / 'repo')}})
    assert result[0] in (1, 2), result


def test_inherited_repository_target_is_scoped(workspace_case, monkeypatch):
    root, _ = workspace_case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    monkeypatch.setenv('GIT_DIR', str(root / 'repo/.git'))
    assert guard().check({'cwd': str(root.parent), 'tool_input': {
        'command': 'git push --force'}})[0] == 1


def test_outside_push_preserves_actionable_port_reason(workspace_case, monkeypatch):
    root, fake = workspace_case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    reason = 'detached HEAD; check out a branch before pushing'
    fake.results['push_context'] = Result(2, None, reason)
    result = guard().check({'cwd': str(root.parent), 'tool_input': {
        'command': f'git -C {root / "repo"} push origin feature'}})
    assert result[0] == 2 and reason in result[1]


@pytest.mark.parametrize('command', [
    'env -i git push --force', 'exec -c git commit -m safe',
    'GIT_AUTHOR_EMAIL=x; git commit',
    'git -c core.hooksPath=elsewhere push --force',
    'git --no-optional-locks push --force',
])
def test_unrelated_overrides_do_not_block(workspace_case, monkeypatch, command):
    root, _ = workspace_case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    assert guard().check({'cwd': str(root.parent), 'tool_input': {'command': command}}) == (0, '')


def test_relative_cd_context_reaches_vcs(workspace_case, monkeypatch):
    root, fake = workspace_case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    result = guard().check({'cwd': str(root.parent), 'tool_input': {
        'command': f'cd {root.name}/repo && git commit -m safe'}})
    assert result == (0, '')
    assert fake.calls[0][1][0] == str(root / 'repo')


@pytest.mark.parametrize('command', [
    'git push "$REMOTE"', 'git push "',
    'for ref in main; do git push origin "$ref"; done',
    'python3 -c "print(\'git push\')"',
])
def test_unrelated_parse_failures_pass(workspace_case, monkeypatch, command):
    root, _ = workspace_case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    assert guard().check({'cwd': str(root.parent), 'tool_input': {'command': command}}) == (0, '')


@pytest.mark.parametrize('command', [
    'git -C {repo} push "$REMOTE"', 'git -C {repo} push "',
    'for ref in main; do git -C {repo} push origin "$ref"; done',
    'sh -c \'git -C {repo} push "$REMOTE"\'',
])
def test_target_parse_failures_are_scoped(workspace_case, monkeypatch, command):
    root, _ = workspace_case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    result = guard().check({'cwd': str(root.parent), 'tool_input': {
        'command': command.format(repo=root / 'repo')}})
    assert result[0] == 2 and 'plain command' in result[1], result


def test_target_workspace_wins_over_unrelated_environment(workspace_case, monkeypatch):
    root, _ = workspace_case
    other = root.parent / (root.name + '-other-workspace')
    (other / '.wuwei').mkdir(parents=True)
    (other / '.wuwei/config.toml').write_text('repos = []\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(other))
    result = guard().check({'cwd': str(root.parent), 'tool_input': {
        'command': f'git -C {root / "repo"} push --force'}})
    assert result[0] == 1, result


@pytest.mark.parametrize('command', [
    'cd repo && git commit -m safe',
    '(cd repo && git commit -m safe)',
    'sh -c "cd repo && git commit -m safe"',
])
def test_workspace_root_cd_does_not_read_obsolete_cwd(workspace_case, command):
    root, fake = workspace_case
    original = fake._call
    def call(operation, args, context):
        if operation == 'commit_context' and args[0] == str(root):
            return Result(2, None, 'not a Git repository')
        return original(operation, args, context)
    fake._call = call
    result = guard().check({'cwd': str(root), 'tool_input': {'command': command}})
    assert result == (0, ''), result


def test_subshell_directory_is_restored_for_outside_push(workspace_case, monkeypatch):
    root, _ = workspace_case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    result = guard().check({'cwd': str(root.parent), 'tool_input': {
        'command': f'(cd {root / "repo"} && git add x); git push --force'}})
    assert result == (0, ''), result


@pytest.mark.parametrize('command', [
    'eval "cd {repo}"; git push --force',
    '(cd {repo} && git push --force) &',
    'echo $(date); git -C {repo} push --force',
    'git -C {repo} -c core.pager=cat push --force',
])
def test_wrapped_directory_targets_fail_closed(workspace_case, monkeypatch, command):
    root, _ = workspace_case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    result = guard().check({'cwd': str(root.parent), 'tool_input': {
        'command': command.format(repo=root / 'repo')}})
    assert result[0] in (1, 2), result


@pytest.mark.parametrize('separator', [';', '||', '&'])
def test_failed_or_background_cd_keeps_original_target(workspace_case, monkeypatch, separator):
    root, _ = workspace_case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    result = guard().check({'cwd': str(root.parent), 'tool_input': {
        'command': f'cd absent && echo skipped {separator} git -C {root.name}/repo push --force'}})
    assert result[0] in (1, 2), result
