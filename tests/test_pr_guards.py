"""PR guard policy and bypass tables use in-process ports only."""

import importlib
import json
import os
from pathlib import Path

import pytest

from fakes.vcs import Fake
from wuwei import registry, workspace
from wuwei.registry import Result

SHA = 'a' * 40
OLD = 'b' * 40


def guard():
    path = Path(__file__).resolve().parents[1] / 'cli/wuwei/guards/pr.py'
    assert path.exists(), 'PR guard is missing'
    return importlib.import_module('wuwei.guards.pr')


def evidence(sha=SHA, verdict='PASS'):
    return (f'Head: {sha}\nVerdict: {verdict}\nProbes: tested\n'
            'AUTH: PASS\nSimplicity: checked\nDesign: checked\n'
            'Blocked: none\nGap: none\nChange: none\n')


@pytest.fixture
def case(tmp_path, monkeypatch):
    for key in os.environ:
        if key.startswith(('GIT_', 'GH_')):
            monkeypatch.delenv(key)
    root = tmp_path / 'workspace'
    repo = root / 'repo'
    repo.mkdir(parents=True)
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text('''
[[repos]]
name = "example/project"
path = "repo"
default_branch = "main"
''')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00Z')
    decisions = workspace.day_dir(root) / 'decisions'
    decisions.mkdir(parents=True)
    for gate in ('arch', 'quality', 'security'):
        (decisions / f'gate-9-{gate}.md').write_text(evidence())
    fake = Fake({'head': Result(0, {'sha': SHA}), 'resolve': Result(0, {'sha': SHA}),
                 'commit_context': Result(0, {'path': str(repo), 'common_dir': str(repo / '.git')})})
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake)
    return root, fake, decisions


def payload(root, command, cwd=None):
    return {'cwd': str(cwd or root / 'repo'), 'tool_name': 'Bash',
            'tool_input': {'command': command}}


@pytest.mark.parametrize('command,code,hint', [
    ('gh pr create --reviewer alice', 0, ''),
    ('gh pr create --reviewer=alice,bob', 0, ''),
    ('gh pr create -ralice', 0, ''),
    ('gh pr create -r alice --title Example --body Text', 0, ''),
    ('gh pr create', 1, 'reviewer'),
    ('gh pr create --reviewer ""', 1, 'reviewer'),
    ('gh pr create --reviewer ,', 1, 'reviewer'),
    ('gh pr create --title "--reviewer alice"', 1, 'reviewer'),
    ('gh pr create --reviewer', 2, 'value'),
    ('gh pr create --reviewer alice --head other', 2, 'HEAD'),
    ('gh pr create -R other/project -r alice', 2, 'repository'),
    ('GH_REPO=other/project gh pr create -r alice', 2, 'environment'),
    ('GIT_DIR=other gh pr create -r alice', 2, 'environment'),
])
def test_create_options(case, command, code, hint):
    root, fake, _ = case
    result = guard().check(payload(root, command))
    assert result[0] == code, result
    assert hint in result[1]
    if code == 0:
        assert ('head', (str(root / 'repo'),), root) in fake.calls


@pytest.mark.parametrize('kind,code,hint', [
    ('missing', 1, 'security'), ('stale', 1, 'security'),
    ('fix', 1, 'security'), ('short', 0, ''),
    ('duplicate', 2, 'security'), ('comment', 2, 'security'),
    ('fenced', 2, 'security'), ('blocking', 2, 'security'),
    ('unreadable', 2, 'security'), ('other-item', 1, 'security'),
])
def test_verdict_evidence(case, kind, code, hint):
    root, _, decisions = case
    path = decisions / 'gate-9-security.md'
    if kind == 'missing':
        path.unlink()
        (workspace.day_dir(root) / 'state.json').write_text(json.dumps({
            'gates': {gate: {'sha': SHA, 'verdict': 'PASS'}
                      for gate in ('arch', 'quality', 'security')}}))
    elif kind == 'stale':
        path.write_text(evidence(OLD))
    elif kind == 'fix':
        path.write_text(evidence(verdict='FIX'))
    elif kind == 'short':
        path.write_text(evidence(SHA[:7]))
    elif kind == 'duplicate':
        path.write_text(evidence() + f'Head: {OLD}\n')
    elif kind == 'comment':
        path.write_text('<!--\n' + evidence() + '-->')
    elif kind == 'fenced':
        path.write_text('```\n' + evidence() + '```')
    elif kind == 'blocking':
        path.write_text(evidence() + '- P1 cli/example.py:1 blocks: yes; fails when changed\n')
    elif kind == 'unreadable':
        path.write_bytes(b'\xff')
    elif kind == 'other-item':
        path.rename(decisions / 'gate-10-security.md')
    result = guard().check(payload(root, 'gh pr create -r alice'))
    assert result[0] == code, result
    assert hint in result[1]


@pytest.mark.parametrize('operation,result', [
    ('head', Result(2, {'sha': SHA}, 'offline')),
    ('head', Result(0, {})), ('head', Result(0, {'sha': 'bad'})),
    ('resolve', Result(2, {'sha': SHA}, 'ambiguous')),
])
def test_port_errors(case, operation, result):
    root, fake, decisions = case
    fake.results[operation] = result
    (decisions / 'gate-9-security.md').write_text(evidence(SHA[:7]))
    code, reason = guard().check(payload(root, 'gh pr create -r alice'))
    assert code == 2 and reason


@pytest.mark.parametrize('profile', ['strict', 'standard'])
@pytest.mark.parametrize('command,code,hint', [
    ('gh pr merge 9', 1, 'merge.auto is off'),
    ('gh pr merge 9 --admin', 1, 'admin'),
    ('gh pr review 9 --approve', 1, 'approv'),
    ('gh pr review 9 -a', 1, 'approv'),
    ('gh pr review 9 --comment --body Fine', 0, ''),
    ('gh pr view 9', 0, ''),
    ('gh api repos/o/r/pulls/9/merge -X PUT', 1, 'merge policy'),
    ('gh api -XPUT /repos/o/r/pulls/9/merge', 1, 'merge policy'),
    ('gh api repos/o/r/pulls/9/merge', 0, ''),
    ('gh api repos/o/r/pulls/9/reviews -f event=APPROVE', 1, 'approv'),
    ('gh api repos/o/r/pulls/9/reviews --raw-field=event=APPROVE', 1, 'approv'),
    ('gh api repos/o/r/pulls/9/reviews -Fevent=APPROVE', 1, 'approv'),
    ('gh api repos/o/r/pulls/9/reviews/1/events -f event=APPROVE', 1, 'approv'),
    ('gh api repos/o/r/pulls/9/reviews -f event=COMMENT', 0, ''),
    ('gh api repos/o/r/pulls/9/reviews --input body.json', 2, 'opaque'),
    ('gh api repos/o/r/pulls/9/reviews -F event=@event.txt', 2, 'opaque'),
    ('gh api repos/o/r/branches/main/protection -X DELETE', 1, 'protection'),
    ('gh api repos/o/r/branches/main/protection/required_status_checks -F strict=true', 1, 'protection'),
    ('gh api repos/o/r/branches/main/protection', 0, ''),
    ('gh api repos/o/r/rulesets/1 -X DELETE', 1, 'protection'),
    ('gh api repos/o/r/pulls -f title=Example', 2, 'create'),
    ('gh api graphql -f query="mutation { approve }"', 2, 'opaque'),
])
def test_policy_actions(case, profile, command, code, hint):
    root, _, _ = case
    config = root / '.wuwei/config.toml'
    config.write_text(f'profile = "{profile}"\n' + config.read_text())
    result = guard().check(payload(root, command))
    assert result[0] == code, result
    assert hint in result[1]


@pytest.mark.parametrize('command,code', [
    ('sh -c "gh pr merge 9"', 1), ('bash -lc "gh pr review -a"', 1),
    ('zsh -c "gh pr merge 9"', 1), ('(gh pr merge 9)', 1),
    ('env X=1 command gh pr review -a', 1), ('exec gh pr merge 9', 1),
    ('/usr/bin/gh pr merge 9', 1), ('g"h" pr merge 9', 1),
    ('echo 9 | xargs gh pr merge', 2),
    ('python3 -c "import os; os.system(\'gh pr merge 9\')"', 2),
    ('node -e "require(\'child_process\').execSync(\'gh pr merge 9\')"', 2),
    ('perl -e "system(\'gh pr merge 9\')"', 2),
    ('gh pr merge $PR', 2), ('gh pr merge $(cat pr)', 2),
    ('for i in 9; do gh pr merge $i; done', 2),
    ('gh pr merge "', 2),
    ('gh pr create -r alice && gh pr review -a', 2),
    ('python3 -m pytest -q', 0), ('for i in 1; do echo ok; done', 0),
    ('export X=1', 0), ('git status', 0),
    ('./push.sh', 2), ('sh push.sh', 2), ('bash push.sh', 2),
    ('./run.sh', 0), ('sh run.sh', 0), ('bash run.sh', 0),
])
def test_bypasses_and_relevance(case, command, code):
    root, _, _ = case
    (root / 'repo/push.sh').write_text('gh pr merge 9 --admin\n')
    (root / 'repo/run.sh').write_text('echo ok\n')
    result = guard().check(payload(root, command))
    assert result[0] == code, result


@pytest.mark.parametrize('command', ['python3 -m pytest -q', 'export X=1', 'for x in 1; do echo x; done'])
def test_irrelevant_never_normalized(case, monkeypatch, command):
    from wuwei import shell
    def fail(raw):
        pytest.fail('irrelevant command reached normalizer')
    monkeypatch.setattr(shell, 'normalize', fail)
    assert guard().check(payload(case[0], command)) == (0, '')


@pytest.mark.parametrize('override', [True, False])
def test_unrelated_project_passes(case, tmp_path, monkeypatch, override):
    root, fake, _ = case
    outside = tmp_path / 'unrelated'
    outside.mkdir()
    if not override:
        monkeypatch.delenv('WUWEI_WORKSPACE')
    for command in ('gh pr merge 9', 'gh pr review --approve', 'gh pr merge "'):
        assert guard().check(payload(root, command, outside)) == (0, '')
    assert not fake.calls


def test_outside_workspace_does_not_read_scripts(case, tmp_path, monkeypatch):
    from wuwei import shell

    def fail(*args):
        pytest.fail('out-of-scope command reached script reader')

    monkeypatch.setattr(shell, 'script_text', fail)
    assert guard().check(payload(case[0], './push.sh', tmp_path)) == (0, '')


@pytest.mark.parametrize('command', ['python3 -m pytest -q', 'export X=1', 'for x in 1; do echo x; done'])
def test_irrelevant_commands_do_not_require_config(case, command):
    root, _, _ = case
    (root / '.wuwei/config.toml').unlink()
    assert guard().check(payload(root, command)) == (0, '')


@pytest.mark.parametrize('wrapper', ['cd {repo} && gh pr merge 9',
                                    'sh -c "cd {repo}; gh pr merge 9"',
                                    'pushd {repo}; gh pr review -a'])
def test_target_workspace_from_outside(case, tmp_path, monkeypatch, wrapper):
    root, _, _ = case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    result = guard().check(payload(root, wrapper.format(repo=root / 'repo'), tmp_path))
    assert result[0] == 1, result


def test_configured_external_repo_and_worktree(case, tmp_path):
    root, _, _ = case
    external = tmp_path / 'external'
    external.mkdir()
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('path = "repo"', 'path = "../external"'))
    assert guard().check(payload(root, 'gh pr merge 9', external))[0] == 1
    worktree = tmp_path / 'worktree'
    worktree.mkdir()
    (worktree / '.git').write_text('gitdir: unused-by-core')
    assert guard().check(payload(root, 'gh pr merge 9', worktree))[0] == 1


@pytest.mark.parametrize('command,repo,pr', [
    ('gh pr merge 9', None, '9'),
    ('gh -R o/r pr merge 9', 'o/r', '9'),
    ('gh pr --repo=o/r merge 9', 'o/r', '9'),
    ('gh pr merge 9 --repo o/r', 'o/r', '9'),
    ('gh pr merge 9 --repo old/repo -R o/r', 'o/r', '9'),
    ('gh pr merge 9 -R old/repo --repo o/r', 'o/r', '9'),
    ('gh -R old/repo pr merge 9 --repo o/r', 'o/r', '9'),
    ('gh pr --repo old/repo merge 9 -Ro/r', 'o/r', '9'),
    ('gh api repos/o/r/pulls/9/merge -X PUT', 'o/r', '9'),
    ('gh api repos/o/r/merges -f base=main -f head=topic', 'o/r', None),
])
def test_merge_policy_single_call_and_admin_never_delegates(case, monkeypatch, command, repo, pr):
    root, _, _ = case
    calls = []
    def policy(repo, pr, cwd, root, config):
        calls.append((repo, pr, cwd, root, config))
        return 1, 'required checks not green'
    monkeypatch.setattr(guard(), 'merge_check', policy)
    assert guard().check(payload(root, command)) == (1, 'required checks not green')
    assert calls == [(repo, pr, root / 'repo', root, workspace.load_config(root))]
    calls.clear()
    assert guard().check(payload(root, 'gh pr merge 9 --admin'))[0] == 1
    assert calls == []


def test_registration_mutation(case, monkeypatch):
    from wuwei.guards import discover
    def enforced():
        return any(record.check(payload(case[0], 'gh pr review -a'))[0] == 1
                   for record in discover() if record.check.__module__ == guard().__name__)
    assert enforced()
    monkeypatch.setattr(guard(), 'GUARDS', [])
    with pytest.raises(AssertionError):
        assert enforced()


@pytest.mark.parametrize('command', [
    'git commit -m changed && gh pr create -r alice',
    'git checkout other && gh pr create -r alice',
    'echo forged > evidence.md; gh pr create -r alice',
    'gh pr create -r alice > evidence.md',
    'gh pr create -r alice; gh api repos/o/r/git/refs/heads/topic -X PATCH',
    'gh pr create -r alice; gh pr create -r bob',
])
def test_create_compound_cannot_change_measured_inputs(case, command):
    result = guard().check(payload(case[0], command))
    assert result[0] == 2, result
    assert 'separat' in result[1]


@pytest.mark.parametrize('command,code', [
    ('gh api /repos/o/r/branches/main/%70rotection -XDELETE', 1),
    ('gh api repos/o/r/pulls/9/merge --method=PUT', 1),
    ('gh api repos/o/r/pulls/9/reviews -f event=COMMENT -f event=APPROVE', 1),
    ('gh api repos/o/r/pulls/9/reviews -X POST', 2),
    ('gh api repos/o/r/pulls/9/reviews -X GET -f event=APPROVE', 0),
    ('gh pr review -abFine', 2),
    ('gh --repo o/r pr merge 9 --admin', 1),
    ('gh pr create --reviewer --title Example', 2),
    ('sh -c "gh pr create -r alice"', 0),
    ('(cd repo && gh pr create -r alice)', 2),
])
def test_additional_normalized_forms(case, command, code):
    assert guard().check(payload(case[0], command))[0] == code


def test_vcs_resolution_cannot_return_malformed_success(case):
    root, fake, decisions = case
    fake.results['resolve'] = Result(0, {'sha': 'not-a-sha'})
    (decisions / 'gate-9-security.md').write_text(evidence(SHA[:7]))
    assert guard().check(payload(root, 'gh pr create -r alice'))[0] == 2


def test_in_scope_cwd_still_checks_target_outside(case, tmp_path):
    root, _, _ = case
    assert guard().check(payload(root, f'sh -c "cd {tmp_path}; gh pr merge 9"'))[0] == 1


def test_hook_routes_guard(case, monkeypatch, capsys):
    import io
    import sys
    from wuwei.commands.hook import run
    from wuwei.guards import Guard
    import wuwei.guards
    data = payload(case[0], 'gh pr review --approve')
    data.update(session_id='test', transcript_path='transcript.jsonl',
                hook_event_name='PreToolUse', tool_use_id='test-tool')
    monkeypatch.setattr(wuwei.guards, 'discover', lambda: [Guard('PreToolUse', 'Bash', guard().check)])
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(data)))
    from argparse import Namespace
    assert run(Namespace(event='PreToolUse')) == 2
    output = json.loads(capsys.readouterr().out)['hookSpecificOutput']
    assert output['permissionDecision'] == 'deny'
    assert 'approv' in output['permissionDecisionReason']


def test_authentication_environment_is_not_repository_selection(case, monkeypatch):
    monkeypatch.setenv('GH_TOKEN', 'test-token')
    assert guard().check(payload(case[0], 'gh pr create -r alice'))[0] == 0


@pytest.mark.parametrize('command,code', [
    ('gh api repos/o/r/pulls/9/merge -X GET --method PUT', 1),
    ('gh api repos/o/r/pulls/9/reviews -X GET --method POST -f event=APPROVE', 1),
    ('gh api repos/o/r/branches/main/protection -X GET --method DELETE', 1),
    ('gh api repos/o/r/pulls/9/merge --method PUT -X GET', 0),
    ('gh api repos/o/r/pulls/9/merge -X PUT -X GET', 0),
    ('gh api repos/o/r/pulls/9/merge --method GET --method PUT', 1),
])
def test_api_method_flags_use_last_value(case, command, code):
    assert guard().check(payload(case[0], command))[0] == code


@pytest.mark.parametrize('variable', ['GIT_DIR', 'GIT_WORK_TREE'])
def test_environment_target_activates_scope(case, tmp_path, monkeypatch, variable):
    root, _, _ = case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    command = f'{variable}={root / "repo"} gh pr merge 9'
    assert guard().check(payload(root, command, tmp_path))[0] == 1


@pytest.mark.parametrize('endpoint', [
    'https://host.test/api/v3/repos/o/r/pulls/9/merge',
    '/repos/o/r/pulls/9/../9/merge',
])
def test_api_endpoint_path_normalization(case, endpoint):
    assert guard().check(payload(case[0], f'gh api {endpoint} -X PUT'))[0] == 1


@pytest.mark.parametrize('command', [
    'gh pr --repo o/r review --approve',
    'gh pr -R o/r merge --admin',
    'gh pr --repo=o/r merge 9',
])
def test_repository_option_between_subcommands(case, command):
    assert guard().check(payload(case[0], command))[0] == 1


@pytest.mark.parametrize('template', [
    'cd {repo}; python3 -c "import os; os.system(\'gh pr merge 9\')"',
    'sh -c "cd {repo}; gh pr merge $PR"',
])
def test_uninspectable_directory_target_fails_closed(case, tmp_path, monkeypatch, template):
    root, _, _ = case
    monkeypatch.delenv('WUWEI_WORKSPACE')
    assert guard().check(payload(root, template.format(repo=root / 'repo'), tmp_path))[0] == 2


def test_org_ruleset_write_is_protection_change(case):
    assert guard().check(payload(case[0], 'gh api orgs/o/rulesets/1 -X DELETE'))[0] == 1


def test_configured_home_relative_repo(case, tmp_path, monkeypatch):
    root, _, _ = case
    monkeypatch.setenv('HOME', str(tmp_path))
    repo = tmp_path / 'external'
    repo.mkdir()
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('path = "repo"', 'path = "~/external"'))
    assert guard().check(payload(root, 'gh pr merge 9', repo))[0] == 1


def test_enterprise_graphql_is_opaque(case):
    command = 'gh api https://host.test/api/graphql -f "query=mutation { approve }"'
    assert guard().check(payload(case[0], command))[0] == 2


def test_security_evidence_obeys_existing_lint(case):
    root, _, decisions = case
    (decisions / 'gate-9-security.md').write_text(evidence().replace('AUTH: PASS\n', ''))
    assert guard().check(payload(root, 'gh pr create -r alice'))[0] == 2


def test_inherited_repository_target_is_in_scope(case, tmp_path, monkeypatch):
    root, _, _ = case
    monkeypatch.setenv('GIT_DIR', str(root / 'repo'))
    assert guard().check(payload(root, 'gh pr merge 9', tmp_path))[0] == 1


@pytest.mark.parametrize('command,code', [
    ('gh alias set lgtm "pr review --approve"', 1),
    ('gh lgtm 9', 2),
    ("gh alias set --shell m 'gh pr merge 9 --admin'", 1),
    ('gh m', 2),
    ('gh alias import aliases.yml', 1),
    ('gh alias delete m', 1),
    ('gh --repo o/r lgtm 9', 2),
    ('gh alias list', 0),
    ('gh issue list', 0),
    ('gh repo view', 0),
])
def test_aliases_cannot_bypass_policy(case, command, code):
    assert guard().check(payload(case[0], command))[0] == code


@pytest.mark.parametrize('command,code', [
    ('gh pr view $PR', 0),
    ('cd /tmp && gh pr view $PR', 0),
    ('pushd /tmp; gh pr view $PR', 0),
    ('sh -c \'cd /tmp && gh pr view $PR\'', 0),
    ('cd /tmp; gh pr view "', 0),
    ('gh pr view "', 0),
    ('sh -c "cd {repo}; gh pr view $PR', 2),
    ('cd $TARGET && gh pr view $PR', 2),
    ('pushd "$TARGET"; gh pr view $PR', 2),
    ('cd {repo} && gh pr view $PR', 2),
    ('cd {root}; cd repo; gh pr view $PR', 2),
    ('sh -c \'cd {repo}; gh pr view $PR\'', 2),
])
@pytest.mark.parametrize('override', [True, False])
def test_parse_failure_scope_uses_directory_targets(case, tmp_path, monkeypatch, command, code, override):
    root, _, _ = case
    if not override:
        monkeypatch.delenv('WUWEI_WORKSPACE')
    command = command.format(root=root, repo=root / 'repo')
    assert guard().check(payload(root, command, tmp_path))[0] == code


@pytest.mark.parametrize('command,code', [
    ('gh api repos/o/r/merges -X POST', 1),
    ('gh api repos/o/r/merges -f base=main -f head=topic', 1),
    ('gh api repos/example/project/git/refs/heads/main -X PATCH', 1),
    ('gh api repos/example/project/git/refs/heads/main -X POST', 1),
    ('gh api repos/example/project/git/refs/heads/main -f sha=abc', 1),
    ('gh api repos/example/project/git/refs/heads/release/live -X PATCH', 1),
    ('gh api repos/example/project/git/refs/heads/topic -X PATCH', 0),
    ('gh api repos/example/project/git/refs/heads/main', 0),
    ('gh api repos/unknown/project/git/refs/heads/topic -X PATCH', 2),
])
def test_branch_merge_and_ref_api_policy(case, command, code):
    root, _, _ = case
    config = root / '.wuwei/config.toml'
    config.write_text('[environments]\n"release/*" = "production"\n' + config.read_text())
    assert guard().check(payload(root, command))[0] == code


@pytest.mark.parametrize('inherited', [False, True])
@pytest.mark.parametrize('variable,code', [
    ('GIT_EDITOR', 0), ('GIT_PAGER', 0), ('GIT_TRACE', 0), ('GIT_TERMINAL_PROMPT', 0),
    ('GH_TOKEN', 0), ('PATH', 0), ('HOME', 0), ('XDG_CONFIG_HOME', 0),
    ('GIT_DIR', 2), ('GIT_WORK_TREE', 2), ('GIT_COMMON_DIR', 2),
    ('GIT_INDEX_FILE', 2), ('GIT_NAMESPACE', 2), ('GIT_CONFIG', 2),
    ('GIT_CONFIG_COUNT', 2), ('GIT_CONFIG_GLOBAL', 2),
    ('GH_REPO', 2), ('GH_HOST', 2), ('GH_CONFIG_DIR', 2),
])
def test_create_environment_only_rejects_repository_selection(case, monkeypatch, inherited, variable, code):
    command = 'gh pr create -r alice'
    if inherited:
        monkeypatch.setenv(variable, 'value')
    else:
        command = f'{variable}=value {command}'
    assert guard().check(payload(case[0], command))[0] == code


@pytest.mark.parametrize('command', [
    'gh --version', 'gh --help', 'gh -h', 'gh help', 'gh version',
])
def test_global_information_flags(case, command):
    assert guard().check(payload(case[0], command)) == (0, '')


@pytest.mark.parametrize('endpoint,code', [
    ('//repos/o/r/pulls/9/merge', 1),
    ('repos/o/r/pulls/9/merge?key=value', 1),
    ('repos/o/r/pulls/9/merge#fragment', 1),
    ('repos/example/project/git/refs/heads/main?key=value', 1),
    ('REPOS/o/r/PULLS/9/MERGE', 1),
    ('https://host.test/API/V3/REPOS/o/r/PULLS/9/MERGE', 1),
    ('REPOS/o/r/MERGES', 1),
    ('REPOS/o/r/BRANCHES/main/PROTECTION', 1),
    ('ORGS/o/RULESETS/1', 1),
    ('REPOS/o/r/PULLS/9/REVIEWS', 2),
    ('REPOS/o/r/PULLS', 2),
    ('REPOS/example/project/GIT/REFS/HEADS/main', 1),
    ('REPOS/example/project/GIT/REFS/HEADS/MAIN', 0),
    ('GRAPHQL', 2),
])
def test_api_endpoint_parsing_matches_gh(case, endpoint, code):
    assert guard().check(payload(case[0], f'gh api "{endpoint}" -X POST'))[0] == code
