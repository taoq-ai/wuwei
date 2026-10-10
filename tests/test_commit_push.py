"""Both enforcement anchors share the source harness's ordered identity policy."""

import importlib
import os
import re
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


def test_list_refusal_names_the_command(workspace_case):
    root, _ = workspace_case
    code, reason = guard().check(payload(root, 'python3 -m pytest -q && git commit -m x'))
    assert code == 2
    assert 'python3 -m pytest -q' in reason
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
[spec]
engine = "none"
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
    ('git commit -m safe', 0), ('git push', 1),
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
    ('cd other; git push', 1), ('git config user.email x; git commit', 2),
    ('GIT_AUTHOR_EMAIL=x; git commit', 2),
    ('npm test', 0), ('git status', 0),
    ('./push.sh', 2), ('sh push.sh', 2), ('bash push.sh', 2),
    ('./run.sh', 0), ('sh run.sh', 0), ('bash run.sh', 0),
    ('git commit -qn -m x', 1), ('git commit -nm x', 1),
    ('git commit -qC HEAD', 2), ('git commit -qZ', 2),
    ('x=$(pwd); echo $x', 0), ('cd $(git rev-parse --show-toplevel) && ls', 0),
    ('git push $(cat remote) main', 2), ('echo $(git push origin main)', 2),
    ('x=$(pwd); $x push', 2),
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
    ({'updates': [{'source': SHA, 'destination': 'refs/tags/v1'}]}, 0),  # the deploy guard's release card gates it
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


def test_identity_free_context_refuses_push(workspace_case):
    root, fake = workspace_case
    with pytest.raises(ValueError, match='push checks need the commit identity'):
        guard().context(root / 'repo', {}, {}, root, push=('origin', ['feature']), identity=False)
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
    'git commit -qm "wip"', 'git commit -sm wip', 'git commit -qam wip',
    'git commit -vqm wip', 'git commit -qmmsg', 'git add -A && git commit -qm wip',
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
    ('push', 1),
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


def test_configured_checkout_is_not_read_twice(workspace_case):
    root, fake = workspace_case
    (root / 'repo/.git').mkdir()
    fake.results['commit_context'].data['common_dir'] = str((root / 'repo/.git').resolve())
    assert guard().check(payload(root, 'git commit -m safe')) == (0, '')
    assert [call[0] for call in fake.calls] == ['commit_context']


def test_push_context_overlaps_repository_context(workspace_case):
    import threading
    root, fake = workspace_case
    barrier = threading.Barrier(2, timeout=2)
    original = fake._call
    def call(operation, args, context):
        if operation in ('commit_context', 'push_context') and not any(
                seen[0] == operation for seen in fake.calls):
            barrier.wait()
        return original(operation, args, context)
    fake._call = call
    assert guard().check(payload(root, 'git push origin HEAD:refs/heads/feature')) == (0, '')
    assert ('push_context', (str(root / 'repo'), 'origin', ['HEAD:refs/heads/feature']), root) in fake.calls


def test_selected_git_directory_push_is_not_read_early(workspace_case):
    root, fake = workspace_case
    assert guard().check(payload(root, 'GIT_DIR=.git git push origin HEAD:refs/heads/feature'))[0] == 0
    push, = [call for call in fake.calls if call[0] == 'push_context']
    assert push[1][0] == str(root / 'repo')
    assert [call[0] for call in fake.calls].index('commit_context') < fake.calls.index(push)


def test_identity_refusal_names_the_fix():
    for kind, actual in (('AUTHOR', {'author': OTHER, 'committer': OWNER}),
                         ('COMMITTER', {'author': OWNER, 'committer': OTHER})):
        code, reason = guard().identity_check(OWNER, actual)
        assert code == 1
        assert reason.startswith(f'GIT_{kind}_IDENT differs from configured identity')
        assert 'wuwei worktree add' in reason
        assert 'git config user.name Builder' in reason
        assert 'git config user.email builder@example.test' in reason
    demo = {'name': 'Demo Owner', 'email': 'demo@example.test'}
    assert "git config user.name 'Demo Owner'" in guard().identity_check(
        demo, {'author': OTHER, 'committer': demo})[1]


@pytest.mark.parametrize('command, expected', [
    ('ls; ls days/x; cat days/x/decisions/D-1.md; grep -n rm config.toml', (0, '')),
    ('W=$(cat .wuwei/executable); $W plan session abc --take-over; $W mcp check', 'unparsed'),
    ('python3 -P -c \'import subprocess;r=subprocess.run(["git","log","-1"]);'
     'print(open("config.toml").read())\'', 'unparsed'),
    ('for r in a b; do git -C $r push origin main; done', 'kept'),
    ('for f in a; do rm wuwei-workspace; done', 'kept'),
])
def test_issue_347_unparsed_and_read_only(workspace_case, command, expected):
    from wuwei.shell import UNPARSED
    root, _ = workspace_case
    result = guard().check({'cwd': str(root), 'tool_name': 'Bash', 'tool_input': {'command': command}})
    if expected == 'kept':
        assert result[0] == 2 and 'commit/push guard could not run' in result[1], result
    else:
        assert result == ((2, UNPARSED) if expected == 'unparsed' else expected)


@pytest.fixture
def item_case(workspace_case):
    """workspace_case with the repository at the item worktree <root>/worktrees/DIV-1."""
    root, fake = workspace_case
    tree = root / 'worktrees/DIV-1'
    tree.mkdir(parents=True)
    fake.results['commit_context'].data['path'] = str(tree)
    fake.results['push_context'].data['updates'][0]['destination'] = 'refs/heads/div-1'
    return root, fake, tree


def item_payload(tree, command):
    return {'cwd': str(tree), 'tool_name': 'Bash', 'tool_input': {'command': command}}


def test_real_values_bare_push(item_case):
    root, fake, tree = item_case
    assert guard().check(item_payload(tree, 'git push')) == (
        1, 'name the remote and the branch: run git push origin HEAD:refs/heads/div-1')
    fake.results['commit_context'].data['path'] = str(root / 'repo')
    code, reason = guard().check(payload(root, 'git push origin'))
    assert code == 1 and 'git push origin HEAD:refs/heads/<branch>' in reason


def test_real_values_fast_check(item_case):
    root, _, tree = item_case
    set_fast_checks(root, {})
    code, reason = guard().check(item_payload(tree, 'git push origin HEAD:refs/heads/div-1'))
    assert code == 1 and '"unit"' in reason and SHA[:12] in reason
    assert 'bin/wuwei build check DIV-1' in reason
    item_case[1].results['commit_context'].data['path'] = str(root / 'repo')
    code, reason = guard().check(payload(root, 'git push origin HEAD:refs/heads/feature'))
    assert code == 1 and 'bin/wuwei fast-checks' in reason


def test_real_values_commit_then_push(item_case):
    root, _, tree = item_case
    code, reason = guard().check(item_payload(tree, 'git commit -m x && git push origin HEAD:refs/heads/div-1'))
    assert code == 1
    steps = [reason.index(text) for text in (
        'commit alone', 'bin/wuwei build check DIV-1', 'git push origin HEAD:refs/heads/div-1')]
    assert steps == sorted(steps)


def test_real_values_default_branch(item_case):
    root, fake, tree = item_case
    fake.results['push_context'].data['updates'][0]['destination'] = 'refs/heads/main'
    code, reason = guard().check(item_payload(tree, 'git push origin HEAD:refs/heads/main'))
    assert code == 1 and 'main' in reason and 'git push origin HEAD:refs/heads/div-1' in reason


def test_real_values_one_reason_through_hook(item_case, monkeypatch, capsys):
    import io
    import json
    import sys
    from types import SimpleNamespace
    from wuwei.commands import hook
    root, _, tree = item_case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    (root / '.wuwei/config.toml').write_text((root / '.wuwei/config.toml').read_text().replace(
        'path = "repo"', 'path = "worktrees/DIV-1"'))
    payload_ = {'hook_event_name': 'PreToolUse', 'session_id': 'fixture', 'cwd': str(tree),
                'transcript_path': str(root / 'transcript.jsonl'), 'tool_name': 'Bash',
                'tool_input': {'command': 'git push'}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload_)))
    assert hook.run(SimpleNamespace(event='PreToolUse')) == 2
    err = capsys.readouterr().err.splitlines()
    assert len(err) == 2 and 'HEAD:refs/heads/div-1' in err[0] and err[1].startswith('posture:')
    assert 'deploy: could not inspect' not in '\n'.join(err)


def through_hook(root, tree, command, monkeypatch, capsys, posture='guarded'):
    """The full PreToolUse hook in process at the item worktree under one posture."""
    import io
    import json
    import sys
    from types import SimpleNamespace
    from wuwei.commands import hook
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    text = (root / '.wuwei/config.toml').read_text().replace('path = "repo"', 'path = "worktrees/DIV-1"')
    text = text.split('[security]')[0] + f'[security]\nposture = "{posture}"\n'
    (root / '.wuwei/config.toml').write_text(text)
    payload_ = {'hook_event_name': 'PreToolUse', 'session_id': 'fixture', 'cwd': str(tree),
                'transcript_path': str(root / 'transcript.jsonl'), 'tool_name': 'Bash',
                'tool_input': {'command': command}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload_)))
    code = hook.run(SimpleNamespace(event='PreToolUse'))
    return code, capsys.readouterr().err


@pytest.mark.parametrize('posture', ['observe', 'guarded', 'strict'])
def test_local_merge_in_item_worktree_passes(item_case, monkeypatch, capsys, posture):
    # #530: a local merge publishes nothing; the push to a protected branch still refuses.
    root, fake, tree = item_case
    assert through_hook(root, tree, 'git merge main', monkeypatch, capsys, posture) == (0, '')
    fake.results['push_context'].data['updates'][0]['destination'] = 'refs/heads/main'
    code, err = through_hook(root, tree, 'git push origin main', monkeypatch, capsys, posture)
    if posture == 'observe':  # publish warns under observe; the native pre-push hook refuses it
        assert code == 0 and 'default branch' in str(warned(root))
    else:
        assert code == 2 and 'default branch' in err


def warned(root):
    import json
    return [json.loads(line)['payload'] for path in root.glob('.wuwei/days/*/events.jsonl')
            for line in path.read_text().splitlines() if json.loads(line)['kind'] == 'guard.would_refuse']


def test_fast_evidence_is_its_own_check(item_case):
    root, _, tree = item_case
    set_fast_checks(root, {})
    repo = {'name': 'example/project', 'fast_checks': ['unit']}
    assert guard().fast_evidence(repo, SHA, str(tree), root) == (
        1, f'fast check "unit" has not passed for HEAD {SHA[:12]}; run bin/wuwei build check DIV-1')
    set_fast_checks(root, {'example/project': {'unit': {'sha': SHA, 'exit': 0}}})
    assert guard().fast_evidence(repo, SHA, str(tree), root) == (0, '')



@pytest.mark.parametrize('pace', ['steady', 'careful', 'fast'])
def test_fast_evidence_passes_with_no_fast_checks(item_case, pace):
    from wuwei import state
    root, _, tree = item_case
    set_fast_checks(root, {})
    state._write_state(lambda data: data.update(pace=pace), root, reserved=False)
    repo = {'name': 'example/project', 'fast_checks': []}
    assert guard().fast_evidence(repo, SHA, str(tree), root) == (0, '')

def with_posture(root, name):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write(f'[security]\nposture = "{name}"\n')


MISSING = f'fast check "unit" has not passed for HEAD {SHA[:12]}; run bin/wuwei build check DIV-1'


@pytest.mark.parametrize('posture', ['observe', 'strict'])
def test_missing_evidence_outside_guarded(item_case, posture):
    # #530: observe returns the reason for the hook to warn; strict refuses as today.
    root, _, tree = item_case
    set_fast_checks(root, {})
    with_posture(root, posture)
    assert guard().check(item_payload(tree, 'git push origin HEAD:refs/heads/div-1')) == (1, MISSING)


def test_missing_evidence_is_a_card_under_guarded(item_case, monkeypatch):
    from types import SimpleNamespace
    from wuwei import integrity, state
    from wuwei.commands import decision
    root, _, tree = item_case
    set_fast_checks(root, {})
    command = 'git push origin HEAD:refs/heads/div-1'
    code, reason = guard().check(item_payload(tree, command))
    assert code == 1 and reason.startswith('publish: ') and 'bin/wuwei build check DIV-1' in reason
    assert 'host terminal' not in reason and 'decision show D-1' in reason
    monkeypatch.setattr(integrity, '_host_confirm', lambda *args, **kwargs: True)
    assert decision.owner_outcome(SimpleNamespace(id='D-1', option='Allow once'), root=root) == (0, 'once')
    code, reason = guard().check(item_payload(tree, f'{command} && git commit --no-verify -m x'))
    assert code == 1 and state.read_state(root)['grants']['D-1']['spent'] is False
    assert guard().check(item_payload(tree, command)) == (0, '')
    assert state.read_state(root)['grants']['D-1']['spent'] is True


@pytest.mark.parametrize('command', ['cd worktrees/DIV-1 && git push origin HEAD:refs/heads/div-1',
                                     'git -C worktrees/DIV-1 push origin HEAD:refs/heads/div-1'])
def test_push_into_recorded_worktree_from_root(item_case, command):
    # #534: the planner pushes an item branch without leaving the workspace root.
    root, fake, tree = item_case
    assert guard().check({'cwd': str(root), 'tool_name': 'Bash',
                          'tool_input': {'command': command}}) == (0, '')
    assert ('push_context', (str(tree), 'origin', ['HEAD:refs/heads/div-1']), root) in fake.calls


@pytest.mark.parametrize('command,step', [
    ('git config core.hooksPath x', 'git config --get'),
    ('GIT_TRACE=1 git commit -m safe', 'remove it from the command')])
def test_refusal_names_the_seat_step_not_the_owner(workspace_case, command, step):
    # #530: the seat has a path, so the reason never sends it to the owner outside the session.
    root, _ = workspace_case
    code, reason = guard().check(payload(root, command))
    assert code in (1, 2) and step in reason, reason
    assert not re.search(r'host terminal|ask the owner|only the owner|by hand', reason), reason


@pytest.mark.parametrize('identity', ['{name = "", email = ""}', '{name = "<name>", email = "<email>"}'])
@pytest.mark.parametrize('command', ['git commit -m safe', 'git push origin HEAD:refs/heads/feature'])
def test_empty_identity_names_the_config_set(workspace_case, command, identity):
    # #605: an empty or malformed repos.N.identity fails with the reason and fix doctor's row
    # shows; the fix names the identity git resolves, read with no new git call.
    root, fake = workspace_case
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('{name = "Builder", email = "builder@example.test"}', identity))
    calls = len(fake.calls)
    reason, fix = guard().unset_identity({'name': '<name>', 'email': ''}, 0, OWNER)
    assert reason == 'repos.0.identity is empty or malformed'
    assert fix == "bin/wuwei config set repos.0.identity '{name = \"Builder\", email = \"builder@example.test\"}'"
    assert guard().check(payload(root, command)) == (2, f'commit/push guard could not run: {reason}; {fix}')
    assert not any(call[0] == 'identity' for call in fake.calls[calls:])
    assert guard().unset_identity(OWNER, 0) is None
    assert guard().unset_identity({'name': '', 'email': ''}, 0, {'name': '<name>', 'email': ''})[1] == (
        "bin/wuwei config set repos.0.identity '{name = \"<name>\", email = \"<email>\"}'")


@pytest.mark.parametrize('built,plain', [
    ('sh -c "gi""t push"', 'git push'), ('g""it push', 'git push'),
    ("eval 'gi''t commit --no-verify -m x'", 'git commit --no-verify -m x'),
    ('sh -c "gi""t commit --no-verify -m x"', 'git commit --no-verify -m x'),
    ('sh -c "gi""t push origin HEAD:refs/heads/feature"', 'git push origin HEAD:refs/heads/feature'),
    ('gi\\\nt commit --no-verify -m x', 'git commit --no-verify -m x'),
])
def test_constructed_command_is_judged_as_plain(workspace_case, built, plain):
    # #671: a name built from quotes, eval, sh -c or a continuation is the command it runs.
    root, _ = workspace_case
    assert guard().check(payload(root, built)) == guard().check(payload(root, plain))
