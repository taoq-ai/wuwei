"""Deployment decisions run in process; no real git, gh, or cloud tool."""

import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from fakes.code_host import Fake
from wuwei import registry
from wuwei.guards import discover
from wuwei.registry import Result
from wuwei.workspace import ConfigError, load_config


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('''
profile = "strict"
[[repos]]
name = "acme/app"
path = "."
default_branch = "main"
merge_deploys = false
[environments]
production = "Live"
"release/*" = "Release branches"
[deploy]
workflows = ["deploy.yml", "Production"]
deny = ["ship release", "make publish*"]
''')
    return tmp_path


def check(root, command):
    guards = [g for g in discover() if g.check.__module__ == 'wuwei.guards.deploy']
    assert len(guards) == 1, 'deployment guard must be installed'
    guard, = guards
    assert (guard.event, guard.matcher) == ('PreToolUse', 'Bash')
    return guard.check({'cwd': str(root), 'tool_name': 'Bash',
                        'tool_input': {'command': command}})


@pytest.mark.parametrize('profile', ['strict', 'standard'])
@pytest.mark.parametrize('command,code,reason', [
    ('terraform plan', 0, ''),
    ('python3 -m pytest -q', 0, ''),
    ('grep -rn terraform .', 0, ''),
    (r"$'\x74\x6f\x66\x75' apply", 2, 'ANSI-C'),
    ('$DEPLOY apply', 2, 'nonliteral'),
    ("'to'fu apply", 1, 'tofu apply'),
    (r'to\fu apply', 1, 'tofu apply'),
    ('git status', 0, ''),
    ('gh workflow run test.yml', 2, 'workflow'),
    ('gh pr view 42', 0, ''),
    ('gh --version', 0, ''),
    ('gh --help', 0, ''),
    ('gh -h', 0, ''),
    ('gh help', 0, ''),
    ('gh version', 0, ''),
    ('docker ps', 0, ''),
    ('echo hello', 0, ''),
    ("sh -c 'terraform apply -auto-approve'", 1, 'terraform apply'),
    ('terraform -chdir=infra destroy', 1, 'terraform destroy'),
    ('kubectl --context prod apply -f app.yml', 1, 'kubectl apply'),
    ('kubectl create deployment app --image=app', 1, 'kubectl create'),
    ('kubectl replace -f app.yml', 1, 'kubectl replace'),
    ('kubectl rollout restart deployment/app', 1, 'kubectl rollout'),
    ('helm --namespace prod upgrade app chart', 1, 'helm upgrade'),
    ('helm install app chart', 1, 'helm install'),
    ('pulumi up', 1, 'pulumi up'),
    ('tofu apply', 1, 'tofu apply'),
    ('tofu destroy', 1, 'tofu destroy'),
    ('pulumi update', 1, 'pulumi update'),
    ('podman push app:latest', 1, 'podman push'),
    ('fly launch', 1, 'fly launch'),
    ('flyctl launch', 1, 'flyctl launch'),
    ('vc', 1, 'vc'),
    ('vc --prod', 1, 'vc'),
    ('ntl deploy --prod', 1, 'ntl deploy'),
    ('az webapp up', 1, 'az'),
    ('aws apprunner start-deployment --service-arn app', 1, 'aws'),
    ('gcloud run up', 1, 'gcloud'),
    ('kubectl set image deployment/app app=app:v2', 1, 'kubectl set image'),
    ('kubectl patch deployment app -p data', 1, 'kubectl patch'),
    ('helm rollback app 1', 1, 'helm rollback'),
    ('vercel', 1, 'vercel'),
    ('vercel --prod', 1, 'vercel'),
    ('vercel deploy', 1, 'vercel'),
    ('vercel ls', 0, ''),
    ('netlify deploy --prod', 1, 'netlify deploy'),
    ('fly deploy', 1, 'fly deploy'),
    ('gcloud run deploy app', 1, 'gcloud'),
    ('aws deploy create-deployment --application-name app', 1, 'aws'),
    ('aws cloudformation update-stack --stack-name app', 1, 'aws'),
    ('aws lambda update-function-code --function-name app', 1, 'aws'),
    ('aws ecs update-service --cluster prod --service app', 1, 'aws'),
    ('az webapp deployment source config-zip --src app.zip', 1, 'az'),
    ('az deployment group create --resource-group prod', 1, 'az'),
    ('gcloud projects list', 0, ''),
    ('aws s3 ls', 0, ''),
    ('az account show', 0, ''),
    ('docker --context prod push app:latest', 1, 'docker push'),
    ('gh release create v1.2.0', 1, 'release'),
    ('git push --tags', 1, 'tag'),
    ('git push origin v1.2.0', 1, 'tag'),
    ('git push origin refs/tags/stable', 1, 'tag'),
    ('git push origin HEAD:refs/tags/stable', 1, 'tag'),
    ('git push origin tag stable', 1, 'tag'),
    ('git push --follow-tags origin main', 1, 'tag'),
    ('git push --mirror origin', 1, 'tag'),
    ('git push origin production', 1, 'environment'),
    ('git push origin HEAD:release/next', 1, 'environment'),
    ('git push origin +HEAD:refs/heads/production', 1, 'environment'),
    ('git push origin HEAD:refs/heads/topic', 0, ''),
    ('git push origin stable', 0, ''),
    ('git push -u origin feat', 0, ''),
    ('git push', 2, 'destination'),
    ('git push --all', 2, 'destination'),
    ('git -C repo push origin production', 1, 'environment'),
    ('git -c push.followTags=true push origin HEAD:refs/heads/topic', 2, 'override'),
    ('GIT_DIR=elsewhere git push origin HEAD:refs/heads/topic', 2, 'override'),
    ('git merge topic', 2, 'branch'),
    ('gh workflow run deploy.yml', 1, 'workflow'),
    ('gh -R acme/app workflow run .github/workflows/deploy.yml', 1, 'workflow'),
    ('gh workflow run --ref main deploy.yml', 1, 'workflow'),
    ('gh workflow rerun deploy.yml', 1, 'workflow'),
    ('gh run rerun 123', 2, 'workflow'),
    ('gh workflow run 123', 2, 'workflow'),
    ('gh workflow run', 2, 'workflow'),
    ('gh api repos/acme/app/deployments', 1, 'API'),
    ('gh api --method GET repos/acme/app/environments/prod', 1, 'API'),
    ('gh api https://api.github.com/repos/acme/app/%64eployments', 1, 'API'),
    ('gh api repos/acme/app/actions/workflows/deploy.yml/dispatches -X POST', 1, 'workflow'),
    ('gh api repos/acme/app/actions/runs/123/rerun -X POST', 2, 'workflow'),
    ('gh api repos/acme/app/releases -f tag_name=v1', 1, 'release'),
    ('gh api repos/acme/app/git/refs -f ref=refs/tags/v1', 1, 'tag'),
    ('gh api repos/acme/app/merges -f base=production', 1, 'environment'),
    ('gh api repos/acme/app/issues', 0, ''),
    ('ship release --prod', 1, 'deploy.deny'),
    ('make publish-prod', 1, 'deploy.deny'),
    ('ship preview', 0, ''),
    ('terraform "$ACTION"', 2, 'literal'),
    ('terraform ap*', 2, 'literal'),
    ('python -c \'import os; os.system("terraform apply")\'', 0, ''),
    ('python -c \'import os; os.system("gh release create v1")\'', 2, 'git/gh mention'),
    ('node -e "run(\'gh release create v1\')"', 2, 'git/gh mention'),
    ('perl -e "system(\'git push --tags\')"', 2, 'git/gh mention'),
    ('echo terraform apply | sh', 2, ''),
    ('xargs terraform', 2, ''),
    ('terraform apply "', 2, 'plain command'),
    ('gh secret-alias', 2, ''),
    ('git ship', 2, ''),
    ('./push.sh', 2, 'opaque'), ('sh push.sh', 2, 'opaque'),
    ('bash push.sh', 2, 'opaque'),
    ('./run.sh', 0, ''), ('sh run.sh', 0, ''), ('bash run.sh', 0, ''),
])
def test_decisions(workspace, profile, command, code, reason):
    (workspace / 'push.sh').write_text('terraform apply\n')
    (workspace / 'run.sh').write_text('echo ok\n')
    path = workspace / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('"strict"', json.dumps(profile)))
    actual, message = check(workspace, command)
    assert actual == code, message
    assert reason in message
    assert not code or message


@pytest.mark.parametrize('wrapper', [
    'sh -c {quoted}', 'bash -lc {quoted}', 'zsh -c {quoted}',
    'env REGION=prod {command}', 'command {command}', 'exec {command}',
    '({command})', 'true && {command}', 'echo ok; {command}',
    'sudo -n {command}', 'timeout 30 {command}',
])
def test_wrapped_deploy(workspace, wrapper):
    command = 'terraform apply -auto-approve'
    code, message = check(workspace, wrapper.format(command=command, quoted=repr(command)))
    assert code == 1, message
    assert 'terraform apply' in message


@pytest.mark.parametrize('result,code,reason', [
    (Result(0, {'repo': 'acme/app', 'base': 'production'}), 1, 'environment'),
    (Result(0, {'repo': 'acme/app', 'base': 'release/next'}), 1, 'environment'),
    (Result(0, {'repo': 'acme/app', 'base': 'main'}), 0, ''),
    (Result(2, {'base': 'main'}, 'unavailable'), 2, 'unavailable'),
    (Result(1, {'base': 'main'}, 'findings'), 2, 'findings'),
    (Result(0, {}), 2, ''),
])
@pytest.mark.parametrize('command', ['gh pr merge 42 -R acme/app',
                                     'gh pr merge https://github.com/acme/app/pull/42',
                                     'gh api repos/acme/app/pulls/42/merge -X PUT'])
def test_merge_port(workspace, monkeypatch, result, code, reason, command):
    fake = Fake({'pr': result})
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake if kind == 'code_host' else None)
    actual, message = check(workspace, command)
    assert actual == code, message
    assert reason in message
    assert len(fake.calls) == 1
    assert fake.calls[0][0] == 'pr'
    assert fake.calls[0][1][0] in ('acme/app#42', 'https://github.com/acme/app/pull/42')


def test_merge_deploys(workspace, monkeypatch):
    path = workspace / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('merge_deploys = false', 'merge_deploys = true'))
    fake = Fake({'pr': Result(0, {'repo': 'acme/app', 'base': 'main'})})
    monkeypatch.setattr(registry, 'load', lambda *args: fake)
    assert check(workspace, 'gh pr merge 42 -R acme/app')[0] == 1


def test_port_exception(workspace, monkeypatch):
    def broken(*args):
        raise OSError('offline')
    monkeypatch.setattr(registry, 'load', broken)
    code, reason = check(workspace, 'gh pr merge 42 -R acme/app')
    assert code == 2 and 'offline' in reason


def test_config_contract(workspace):
    config = load_config(workspace)
    assert config['deploy'] == {'workflows': ['deploy.yml', 'Production'],
                                'deny': ['ship release', 'make publish*']}
    assert config['repos'][0]['merge_deploys'] is False


@pytest.mark.parametrize('text', ['[deploy]\nworkflows = "deploy.yml"',
                                 '[deploy]\ndeny = [12]',
                                 '[deploy]\ndeny = [""]',
                                 '[deploy]\nworkflows = [" "]'])
def test_invalid_config(workspace, text):
    (workspace / '.wuwei/config.toml').write_text(text)
    with pytest.raises(ConfigError):
        load_config(workspace)
    assert check(workspace, 'gh workflow run deploy.yml')[0] == 2


def test_unreadable_config(workspace):
    (workspace / '.wuwei/config.toml').unlink()
    code, message = check(workspace, 'git push origin HEAD:refs/heads/topic')
    assert code == 2 and message


def test_hook_denial(workspace, monkeypatch, capsys):
    from wuwei.commands.hook import run
    payload = {'session_id': 'test', 'transcript_path': 'transcript.jsonl',
               'cwd': str(workspace), 'hook_event_name': 'PreToolUse',
               'tool_name': 'Bash', 'tool_input': {'command': 'terraform apply'}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    assert run(SimpleNamespace(event='PreToolUse')) == 2
    out = capsys.readouterr()
    assert 'terraform apply' in out.err
    assert json.loads(out.out)['hookSpecificOutput']['permissionDecision'] == 'deny'


def test_init_permissions(tmp_path, monkeypatch):
    from wuwei.commands.init import run
    home = tmp_path / 'owner'
    (home / '.claude').mkdir(parents=True)
    global_settings = home / '.claude/settings.json'
    global_settings.write_text('{"owner": true}')
    monkeypatch.setenv('HOME', str(home))
    project = tmp_path / 'project'
    (project / '.claude').mkdir(parents=True)
    settings = project / '.claude/settings.json'
    settings.write_text(json.dumps({'permissions': {'deny': ['Bash(custom *)'],
                                                   'allow': ['Read']}, 'extra': True}))
    assert run(SimpleNamespace(path=str(project))) == 0
    data = json.loads(settings.read_text())
    assert data['extra'] is True
    assert data['permissions']['allow'] == ['Read']
    deny = data['permissions']['deny']
    assert len(deny) == len(set(deny))
    assert set(deny) == {'Bash(custom *)', *(
        f'Bash({command})' for command in (
            'terraform apply*', 'tofu apply*', 'kubectl apply*', 'helm install*',
            'helm upgrade*', 'pulumi up*', 'vercel*', 'vc *', 'netlify deploy*',
            'ntl deploy*', 'fly deploy*', 'flyctl deploy*', 'docker push*',
            'podman push*', 'gh release create*', 'git push --tags*',
            'git push * --tags*', 'gh pr review --approve*',
            'gh pr review * --approve*', 'gh pr review * -a*',
            'gh pr merge * --admin*'))}
    assert global_settings.read_text() == '{"owner": true}'


def test_init_creates_local_settings(tmp_path):
    from wuwei.commands.init import run
    assert run(SimpleNamespace(path=str(tmp_path))) == 0
    data = json.loads((tmp_path / '.claude/settings.json').read_text())
    assert data['permissions']['deny']


@pytest.mark.parametrize('content', ['broken', '[]', '{"permissions": []}',
                                     '{"permissions": {"deny": "no"}}',
                                     '{"permissions": {"deny": [7]}}'])
def test_init_rejects_invalid_settings(tmp_path, content):
    from wuwei.commands.init import run
    (tmp_path / '.claude').mkdir()
    settings = tmp_path / '.claude/settings.json'
    settings.write_text(content)
    try:
        result = run(SimpleNamespace(path=str(tmp_path)))
    except (ValueError, OSError):
        result = 2 # CLI dispatch translates these to exit 2.
    assert result == 2
    assert not (tmp_path / '.wuwei').exists()
    assert settings.read_text() == content


@pytest.mark.parametrize('kind', ['directory', 'file'])
def test_init_rejects_settings_symlinks(tmp_path, kind):
    from wuwei.commands.init import run
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    settings = elsewhere / 'settings.json'
    settings.write_text('{}')
    project = tmp_path / 'project'
    project.mkdir()
    if kind == 'directory':
        (project / '.claude').symlink_to(elsewhere, target_is_directory=True)
    else:
        (project / '.claude').mkdir()
        (project / '.claude/settings.json').symlink_to(settings)
    try:
        result = run(SimpleNamespace(path=str(project)))
    except (ValueError, OSError):
        result = 2
    assert result == 2
    assert not (project / '.wuwei').exists()
    assert settings.read_text() == '{}'


def test_init_settings_write_failure_is_retryable(tmp_path, monkeypatch):
    from wuwei.commands import init
    from wuwei import workspace as workspace_module
    def fail(*args, **kwargs):
        raise OSError('settings unavailable')
    with monkeypatch.context() as patch:
        patch.setattr(workspace_module, 'atomic_write', fail)
        try:
            result = init.run(SimpleNamespace(path=str(tmp_path)))
        except OSError:
            result = 2
        assert result == 2
        assert not (tmp_path / '.wuwei').exists()
    assert init.run(SimpleNamespace(path=str(tmp_path))) == 0


@pytest.mark.parametrize('command', [
    'git push --repo origin HEAD:refs/heads/production HEAD:refs/heads/topic',
    'git push origin HEAD:refs/heads/topic --receive-pack=custom-command',
    'vercel ./app --prod',
    'vercel promote previous-deployment',
    'gh api repos/acme/app/releases -X GET --method POST -f tag_name=v1',
    'gh pr -R acme/app merge 42',
    'gh workflow -R acme/app run deploy.yml',
    'gh release -R acme/app create v1.2.0',
    'GH_HOST=enterprise.example gh pr merge 42 -R acme/app',
    'gh api --hostname enterprise.example repos/acme/app/pulls/42/merge -X PUT',
    'gh api https://enterprise.example/api/v3/repos/acme/app/pulls/42/merge -X PUT',
    'gh pr merge 42 -R acme/app --repo acme/different',
    'ship "$ACTION"',
    'ship releas*',
    'xargs ship',
    "sh -c 'ship \"$ACTION\"'",
    'echo ship release | sh',
])
def test_review_bypasses(workspace, monkeypatch, command):
    base = 'production' if command == 'gh pr -R acme/app merge 42' else 'main'
    fake = Fake({'pr': Result(0, {'repo': 'acme/app', 'base': base})})
    monkeypatch.setattr(registry, 'load', lambda *args: fake)
    code, reason = check(workspace, command)
    assert code in (1, 2), reason


def test_all_repo_options_use_last_value(workspace, monkeypatch):
    fake = Fake({'pr': Result(0, {'repo': 'acme/different', 'base': 'production'})})
    monkeypatch.setattr(registry, 'load', lambda *args: fake)
    assert check(workspace, 'gh pr merge 42 -R acme/app --repo acme/different')[0] == 1
    assert fake.calls[0][1] == ('acme/different#42',)


def test_init_rejects_home(tmp_path, monkeypatch):
    from wuwei.commands.init import run
    monkeypatch.setenv('HOME', str(tmp_path))
    with pytest.raises(ValueError, match='global'):
        run(SimpleNamespace(path=str(tmp_path)))
    assert not (tmp_path / '.claude').exists()


@pytest.mark.parametrize('pattern', ['* release', 'tools/ship release'])
def test_custom_rules_require_literal_executable(workspace, pattern):
    path = workspace / '.wuwei/config.toml'
    path.write_text('[deploy]\ndeny = [' + json.dumps(pattern) + ']\n')
    with pytest.raises(ConfigError, match='literal executable'):
        load_config(workspace)


@pytest.mark.parametrize('command', ['git status', 'pytest', 'terraform apply', 'git "'])
def test_outside_workspace_is_clean(tmp_path, monkeypatch, command):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert check(tmp_path, command) == (0, '')


@pytest.mark.parametrize('command', [
    'python3 -m pytest -q', 'node -v', 'python3 --version',
    'for file in *.py; do echo "$file"; done',
])
def test_irrelevant_commands_skip_parsing(workspace, monkeypatch, command):
    from wuwei.guards import deploy
    def unexpected(*args, **kwargs):
        pytest.fail('irrelevant command reached shell parser')
    monkeypatch.setattr(deploy, 'normalize', unexpected)
    assert check(workspace, command) == (0, '')


@pytest.mark.parametrize('command', [
    'grep -rn terraform .', 'ls docker', 'echo "fly me"', 'pytest -k docker',
    'cat Dockerfile | grep aws', 'az.txt', 'echo ship release',
    'python -c \'import os; os.system("ship release")\'',
    'node -e \'run("ship release")\'',
    'python3 -m pytest -k terraform',
])
def test_deploy_names_in_data_are_clean(workspace, command):
    assert check(workspace, command) == (0, '')


@pytest.mark.parametrize('tool', ['docker', 'podman'])
@pytest.mark.parametrize('verb', ['build', 'buildx build'])
@pytest.mark.parametrize('option,code', [
    ('--push', 1), ('--output=type=registry', 1),
    ('--output type=registry,name=app', 1), ('-o type=registry', 1),
    ('--load', 0), ('--output=type=local,dest=out', 0), ('', 0),
])
def test_container_build_publication(workspace, tool, verb, option, code):
    actual, reason = check(workspace, f'{tool} {verb} {option} .')
    assert actual == code, reason


def test_custom_wrapper_rule_preserves_normalization(workspace):
    path = workspace / '.wuwei/config.toml'
    path.write_text('[deploy]\ndeny = ["sh publish", "env publish"]\n')
    assert check(workspace, "sh -c 'terraform apply'")[0] == 1
    assert check(workspace, 'env REGION=prod terraform apply')[0] == 1


@pytest.mark.parametrize('option', ['--body', '-b', '--subject', '-t', '--body-file', '-F'])
def test_repo_flag_in_option_value_is_data(workspace, monkeypatch, option):
    fake = Fake({'pr': Result(0, {'repo': 'acme/danger', 'base': 'production'})})
    monkeypatch.setattr(registry, 'load', lambda *args: fake)
    assert check(workspace, f'gh pr merge 42 -R acme/danger {option} -Racme/app --auto')[0] == 1
    assert fake.calls[0][1] == ('acme/danger#42',)


def test_rebase_flag_does_not_swallow_repository_option(workspace, monkeypatch):
    fake = Fake({'pr': Result(0, {'repo': 'acme/danger', 'base': 'production'})})
    monkeypatch.setattr(registry, 'load', lambda *args: fake)
    assert check(workspace, 'gh pr merge 42 -r -R acme/app --repo acme/danger')[0] == 1
    assert fake.calls[0][1] == ('acme/danger#42',)


def test_custom_rules_preserve_builtin_opaque_mentions(workspace):
    assert check(workspace, 'git-push origin refs/tags/v1')[0] == 2


@pytest.mark.parametrize('marked,target', [
    (['deploy.yml'], 'Production'),
    (['Production'], 'other.yml'),
    (['123'], 'other.yml'),
])
def test_workflow_aliases_fail_closed(workspace, marked, target):
    (workspace / '.wuwei/config.toml').write_text(
        '[deploy]\nworkflows = ' + json.dumps(marked) + '\n')
    code, reason = check(workspace, 'gh workflow run ' + target)
    assert code == 2 and 'workflow' in reason


def test_distinct_workflow_filenames_are_clean(workspace):
    (workspace / '.wuwei/config.toml').write_text('[deploy]\nworkflows = ["deploy.yml"]\n')
    assert check(workspace, 'gh workflow run test.yml') == (0, '')
