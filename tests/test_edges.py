"""The irreversible edges by exact argv per command segment (#839): one table per edge, each with
refused rows, allowed near misses and a row through the hook with guards.enforce off."""

import io
import json
import shlex
import sys
from types import SimpleNamespace

import pytest

from fakes.vcs import Fake
from wuwei import registry, state
from wuwei.registry import Result
from wuwei.shell import UNPARSED
from wuwei.workspace import ConfigError, load_config


CONFIG = '''
[[repos]]
name = "example/project"
path = "repo"
default_branch = "main"
merge_deploys = false
[environments]
production = "Live"
"release/*" = "Release branches"
[deploy]
workflows = ["deploy.yml", "Production"]
deny = ["ship release", "make publish*"]
'''


@pytest.fixture
def root(tmp_path, monkeypatch):
    """A workspace with repository repo and item DIV-1 recorded at worktrees/DIV-1 on div-1."""
    from fakes.integrity import seed
    root = tmp_path / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    (root / 'repo').mkdir()
    (root / '.wuwei/config.toml').write_text(CONFIG)
    seed(root)
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-10-11T12:00:00Z')
    tree = root / 'worktrees/DIV-1'
    tree.mkdir(parents=True)
    (tree / '.git').write_text('gitdir: elsewhere\n')
    state._write_state(lambda data: data['items'].update({'DIV-1': {'worktree': 'worktrees/DIV-1'}}),
                       root, reserved=False)
    context = Result(0, {'path': str(root / 'repo'), 'common_dir': str(root / 'repo/.git')})
    fake = Fake({'branch': Result(0, {'name': 'div-1'}), 'repo_context': context})
    monkeypatch.setattr(registry, 'load', lambda kind, config: fake)
    return root


def check(root, command, guard='check_bash', cwd=None):
    from wuwei.guards import edges
    return getattr(edges, guard)({'cwd': str(cwd or root / 'repo'), 'tool_name': 'Bash',
                                  'tool_input': {'command': command}})


def hook(root, monkeypatch, capsys, command, enforce, cwd=None, tool='Bash', inputs=None):
    """(exit, guard.would_refuse payloads) of one PreToolUse hook run."""
    from wuwei.commands.hook import run
    (root / '.wuwei/config.toml').write_text(CONFIG + f'[guards]\nenforce = {str(enforce).lower()}\n')
    payload = {'session_id': 'edges', 'transcript_path': str(root / 'transcript.jsonl'),
               'cwd': str(cwd or root / 'repo'), 'hook_event_name': 'PreToolUse', 'tool_name': tool,
               'tool_input': inputs or {'command': command}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    code = run(SimpleNamespace(event='PreToolUse'))
    capsys.readouterr()
    return code, [json.loads(line)['payload'] for path in root.glob('.wuwei/days/*/events.jsonl')
                  for line in path.read_text().splitlines()
                  if json.loads(line)['kind'] == 'guard.would_refuse']


# The segment splitter: (text, [(argv, env, directory relative to the call's cwd)]).
@pytest.mark.parametrize('text,expected', [
    ('git commit -m "gh pr merge 7"', [(['git', 'commit', '-m', 'gh pr merge 7'], {}, '.')]),
    ("cat > notes.md <<'EOF'\ngh pr merge 7\nEOF\ngit status", [(['cat'], {}, '.'), (['git', 'status'], {}, '.')]),
    ('cat <<-EOF | sh\n\tgh pr merge 7\n\tEOF', [(['cat'], {}, '.'), (['sh'], {}, '.')]),
    ('A=1 env -i -u B C=2 gh pr view', [(['gh', 'pr', 'view'], {'A': '1', 'C': '2'}, '.')]),
    ("bash -lc 'cd sub && gh pr view'", [(['cd', 'sub'], {}, '.'), (['gh', 'pr', 'view'], {}, 'sub')]),
    ('cd sub; git status', [(['cd', 'sub'], {}, '.'), (['git', 'status'], {}, 'sub')]),
    ('$(gh pr merge 7)', [(['$'], {}, '.'), (['gh', 'pr', 'merge', '7'], {}, '.')]),
    ('echo "$(gh pr merge 7)"', [(['echo', '$(gh pr merge 7)'], {}, '.')]),
    ('echo hi # gh pr merge 7\ngit status', [(['echo', 'hi'], {}, '.'), (['git', 'status'], {}, '.')]),
    ('gi\\\nt push 2>&1 | tee log', [(['git', 'push', '2'], {}, '.'), (['tee', 'log'], {}, '.')]),
])
def test_segments(root, text, expected):
    from wuwei.guards import edges
    cwd = root / 'repo'
    assert edges.segments(text, cwd) == [(argv, env, (cwd / where).resolve())
                                         for argv, env, where in expected]


def nested(depth):
    text = 'gh pr view'
    for _ in range(depth):
        text = 'sh -c ' + shlex.quote(text)
    return text


@pytest.mark.parametrize('text', ['gh pr merge "7', 'cat <<EOF\ngh pr merge 7', nested(6)])
def test_unsplittable_calls_raise(root, text):
    from wuwei.guards import edges
    with pytest.raises(ValueError):
        edges.segments(text, root)


@pytest.mark.parametrize('enforce', [True, False])
@pytest.mark.parametrize('command', ['gh pr merge "7', 'git push --force "', 'cat <<EOF\ngit push -f'])
def test_unparsed_call_is_logged_once_and_runs(root, monkeypatch, capsys, enforce, command):
    assert check(root, command) == (2, UNPARSED)
    code, logged = hook(root, monkeypatch, capsys, command, enforce)
    assert code == 0
    assert [row['reason'] for row in logged] == [UNPARSED]


@pytest.mark.parametrize('command', [
    'for r in a b; do git -C $r push --force origin main; done',
    'python3 -c "import subprocess; subprocess.run([\'git\', \'push\', \'-f\'])"',
    'bash deploy.sh', 'x=gh; $x pr merge 7', 'echo "$(gh pr merge 7)"',
])
def test_ceilings_are_not_read(root, command):
    # Design 9.1: the code host's protected refs and the credential layout hold these.
    (root / 'repo/deploy.sh').write_text('gh pr merge 7\n')
    assert check(root, command) == check(root, command, 'check_deploy') == (0, '')


def test_outside_every_workspace_is_clean(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    for guard in ('check_bash', 'check_deploy'):
        assert check(tmp_path, 'gh pr merge 7 "', guard, cwd=tmp_path) == (0, '')


# Design 4.5: the wrappers that run the rest of the line, each with its own options.
WRAPPERS = ['command {}', 'command -p {}', 'exec {}', 'exec -a name {}', 'timeout 30 {}',
            'timeout -s KILL 30s {}', 'nohup {}', 'nice {}', 'nice -n 5 {}', 'sudo {}',
            'sudo -u bob {}', 'time {}', 'time -p {}', 'xargs {}', 'xargs -n 1 -0 {}',
            'env A=1 command {}', 'command env A=1 timeout 5 {}']


@pytest.mark.parametrize('wrapper', WRAPPERS)
def test_wrapped_merge_refused(root, wrapper):
    code, reason = check(root, wrapper.format('gh pr merge 5'))
    assert code == 1 and reason.startswith('merge policy'), reason


@pytest.mark.parametrize('wrapper', WRAPPERS)
def test_wrapped_force_push_refused(root, wrapper):
    code, reason = check(root, wrapper.format('git push --force origin x'))
    assert code == 1 and reason.startswith('force-push is refused'), reason


def test_piped_xargs_merge_refused(root):
    assert check(root, 'echo 5 | xargs gh pr merge')[0] == 1


@pytest.mark.parametrize('command', ['timeout gh pr merge 5', 'git log | xargs -n'])
def test_unreadable_wrapper_is_unparsed(root, command):
    assert check(root, command) == (2, UNPARSED)


# Host merge: on the floor.
@pytest.mark.parametrize('command,pr', [
    ('gh pr merge 7', '<owner/repo>#7'), ('gh pr merge 7 --squash', '<owner/repo>#7'),
    ('GH_REPO=o/r gh pr merge 7', '<owner/repo>#7'), ('env -i gh pr merge 7', '<owner/repo>#7'),
    ("bash -c 'gh pr merge 7'", '<owner/repo>#7'), ('cd x && gh pr merge 7', '<owner/repo>#7'),
    ('/usr/bin/gh pr merge 7', '<owner/repo>#7'), ('gh -R o/r pr merge 7', 'o/r#7'),
    ('gh pr merge https://github.com/o/r/pull/7', 'o/r#7'), ('$(gh pr merge 7)', '<owner/repo>#7'),
    ('gh api -X PUT repos/o/r/pulls/7/merge', 'o/r#7'),
    ('gh api repos/o/r/merges -f base=main -f head=x', '<owner/repo>#<pr>'),
])
def test_merge_refused(root, command, pr):
    code, reason = check(root, command)
    assert code == 1 and reason.startswith('merge policy') and f'bin/wuwei merge {pr}' in reason, reason


@pytest.mark.parametrize('command', [
    'gh pr view 7', 'gh pr checks 7', 'gh api repos/o/r/pulls/7/merge',
    'git commit -m "gh pr merge 7"', 'gh pr comment 7 --body "never gh pr merge 7"',
    "cat > notes.md <<'EOF'\ngh pr merge 7\nEOF",
])
def test_merge_allowed(root, command):
    assert check(root, command) == (0, '')


# Approve: on the floor.
@pytest.mark.parametrize('command', [
    'gh pr review 7 --approve', 'gh pr review -a 7', 'gh api repos/o/r/pulls/7/reviews -f event=APPROVE',
    'gh api repos/o/r/pulls/7/reviews --field=event=APPROVE',
])
def test_approve_refused(root, command):
    code, reason = check(root, command)
    assert code == 1 and reason.startswith('PR approval') and 'bin/wuwei merge' in reason, reason


@pytest.mark.parametrize('command', [
    'gh pr review 7 --comment -b ok', 'gh pr review 7 --comment -b --approve',
    'gh api repos/o/r/pulls/7/reviews -f event=COMMENT -f body=ok',
])
def test_approve_allowed(root, command):
    assert check(root, command) == (0, '')


# Admin and branch protection: on the floor.
@pytest.mark.parametrize('command,prefix', [
    ('gh pr merge 7 --admin', 'admin merge'), ('gh pr merge --admin -R o/r 7', 'admin merge'),
    ('gh api -X PUT repos/o/r/branches/main/protection', 'branch protection'),
    ('gh api -X POST repos/o/r/rulesets -f name=x', 'branch protection'),
    ('gh api orgs/o/rulesets/1 -X DELETE', 'branch protection'),
])
def test_admin_refused(root, command, prefix):
    code, reason = check(root, command)
    assert code == 1 and reason.startswith(prefix), reason
    assert prefix != 'admin merge' or 'bin/wuwei merge' in reason


@pytest.mark.parametrize('command', ['gh api repos/o/r/branches/main/protection', 'gh api repos/o/r/rulesets'])
def test_admin_allowed(root, command):
    assert check(root, command) == (0, '')


# Force push: blocks with enforce on, logged with it off.
@pytest.mark.parametrize('command', [
    'git push --force', 'git push -f origin x', 'git push -uf origin x',
    'git push --force-with-lease origin x', 'git push origin +x', 'git push --mirror',
    'git -C repo push --force origin x', 'git push origin +HEAD:refs/heads/x',
])
def test_force_push_refused(root, command):
    code, reason = check(root, command)
    assert code == 1 and reason.startswith('force-push is refused')
    assert 'git push origin HEAD:refs/heads/<branch>' in reason, reason


def test_force_push_names_the_item_branch(root):
    code, reason = check(root, 'git push -f origin div-1', cwd=root / 'worktrees/DIV-1')
    assert code == 1 and 'git push origin HEAD:refs/heads/div-1' in reason, reason


@pytest.mark.parametrize('command', [
    'git push origin x', 'git push origin HEAD:x', 'git fetch --force', 'git push -u origin x',
    'git push --delete origin x', 'git push origin :x', 'git commit -m "git push --force"',
])
def test_force_push_allowed(root, command):
    assert check(root, command) == (0, '')


# The default branch (B6 lead call): blocks with enforce on, logged with it off.
@pytest.mark.parametrize('command', [
    'git push origin main', 'git push origin HEAD:main', 'git push upstream HEAD:refs/heads/main',
    'git -C repo push origin main', 'git push --repo origin main',
    'gh api -X PATCH repos/example/project/git/refs/heads/main -f sha=x',
])
def test_default_branch_push_refused(root, command):
    code, reason = check(root, command, cwd=root / 'worktrees/DIV-1')
    assert code == 1 and reason.startswith('push to the default branch main is refused'), reason
    assert 'bin/wuwei pr raise' in reason and '--item DIV-1' in reason


@pytest.mark.parametrize('command', ['git push origin main-fix', 'git push origin HEAD:refs/heads/div-1',
                                     'git pull origin main', 'git fetch origin main'])
def test_default_branch_push_allowed(root, command):
    assert check(root, command) == (0, '')


# Deploy (design 4.7): on the floor; the owner's Yes on the exact command's card lets it run (#816).
@pytest.mark.parametrize('command,rule', [
    ('ship release --prod', 'deploy.deny: ship release'), ('make publish-prod', 'deploy.deny'),
    ('gh workflow run deploy.yml', 'deploy.workflows'), ('gh workflow run Production', 'deploy.workflows'),
    ('gh -R acme/app workflow run .github/workflows/deploy.yml', 'deploy.workflows'),
    ('gh run rerun 123', 'deploy.workflows'), ('gh release create v1.2.0', 'release create'),
    ('git push origin v1.2.0', 'tag push'), ('git push --tags', 'tag push'),
    ('git push origin HEAD:refs/tags/stable', 'tag push'), ('git push origin production', 'environment'),
    ('git push origin HEAD:release/next', 'environment'), ('terraform apply', 'terraform apply'),
    ("sh -c 'terraform apply -auto-approve'", 'terraform apply'), ('env REGION=x terraform apply', 'terraform'),
    ('kubectl --context prod apply -f a.yml', 'kubectl apply'), ('helm upgrade app chart', 'helm upgrade'),
    ('docker build --push .', 'docker build --push'), ('vercel --prod', 'vercel'),
    ('aws deploy create-deployment --application-name app', 'aws'),
    ('gh api -X POST repos/o/r/deployments', 'deployment/environment API'),
    ('gh api repos/o/r/releases -f tag_name=v1', 'release API'),
    ('gh api repos/o/r/actions/workflows/deploy.yml/dispatches -X POST', 'deploy.workflows'),
])
def test_deploy_refused(root, command, rule):
    code, reason = check(root, command, 'check_deploy')
    assert code == 1 and reason.startswith('publish: ') and 'Owner step: ' in reason, reason
    assert rule in reason


@pytest.mark.parametrize('command', [
    'terraform plan', 'vercel ls', 'git push origin x', 'grep -rn terraform .',
    'echo "terraform apply"', 'ship preview', 'docker build .', 'gh api repos/o/r/issues', 'git merge main',
])
def test_deploy_allowed(root, command):
    assert check(root, command, 'check_deploy') == (0, '')


def test_unmarked_workflow_is_allowed(root):
    (root / '.wuwei/config.toml').write_text('[deploy]\nworkflows = ["deploy.yml"]\n')
    assert check(root, 'gh workflow run ci.yml', 'check_deploy') == (0, '')
    assert check(root, 'gh workflow run deploy.yml', 'check_deploy')[0] == 1


def test_deploy_runs_on_the_owners_yes(root):
    from fakes.owner import answer_card
    command = 'gh release create v1 -R acme/app'
    code, reason = check(root, command, 'check_deploy')
    assert code == 1 and reason.startswith(f'publish: {command}: waits for the owner')
    answer_card(root, reason, 'No')
    assert check(root, command, 'check_deploy')[0] == 1
    answer_card(root, reason)
    assert check(root, command, 'check_deploy') == (0, '')
    assert check(root, command + ' --notes x', 'check_deploy')[0] == 1


@pytest.mark.parametrize('text', ['[deploy]\nworkflows = "deploy.yml"', '[deploy]\ndeny = [12]'])
def test_deploy_unreadable_config_fails_closed(root, text):
    (root / '.wuwei/config.toml').write_text(text)
    with pytest.raises(ConfigError):
        load_config(root)
    assert check(root, 'gh workflow run deploy.yml', 'check_deploy')[0] == 2


# PR raise: blocks with enforce on, logged with it off.
@pytest.mark.parametrize('command,where', [
    ('gh pr create --title t --body b', 'worktrees/DIV-1'),
    ('gh pr create --repo example/project --head div-1 --title t --body b', '.'),
    ('gh -R example/project pr create -H div-1 -t t -b b', '.'),
    ('cd worktrees/DIV-1 && gh pr create -t t -b b', '.'),
])
def test_pr_raise_refused(root, command, where):
    code, reason = check(root, command, cwd=root / where)
    assert code == 1 and reason.startswith('pr raise: DIV-1 is a WUWEI item'), reason
    assert 'bin/wuwei pr raise example/project' in reason and '--item DIV-1' in reason


@pytest.mark.parametrize('command,where', [
    ('gh pr create -t t -b b', 'repo'), ('gh pr create --repo example/project --head other -t t', '.'),
])
def test_pr_raise_allowed(root, command, where):
    assert check(root, command, cwd=root / where) == (0, '')


def test_pr_raise_allowed_once_the_item_links_a_pr(root):
    state._write_state(lambda data: data['items']['DIV-1'].update(pr='example/project#5'),
                       root, reserved=False)
    assert check(root, 'gh pr create -t t -b b', cwd=root / 'worktrees/DIV-1') == (0, '')


# Outward send (part 16's check_send, moved): on the floor.
SEND = 'mcp__acme__send_message'


def test_outward_send_refused_and_allowed(root):
    from wuwei.guards import edges
    call = {'cwd': str(root), 'tool_name': SEND, 'tool_input': {'to': 'someone', 'text': 'Hello'}}
    code, reason = edges.check_send(call)
    assert code == 1 and 'outward.allow' in reason, reason
    (root / '.wuwei/config.toml').write_text(CONFIG + f'[outward]\nallow = ["{SEND}"]\n')
    assert edges.check_send(call) == (0, '')


# guards.enforce off: the floor edges block; force push, the default branch and PR raise log.
@pytest.mark.parametrize('command,where,blocks', [
    ('gh pr merge 7', 'repo', True), ('gh pr review 7 --approve', 'repo', True),
    ('gh pr merge 7 --admin', 'repo', True), ('gh api -X PUT repos/o/r/branches/main/protection', 'repo', True),
    ('terraform apply', 'repo', True), ('git push --force origin x', 'repo', False),
    ('git push origin main', 'repo', False), ('gh pr create -t t -b b', 'worktrees/DIV-1', False),
])
def test_enforce_off(root, monkeypatch, capsys, command, where, blocks):
    code, logged = hook(root, monkeypatch, capsys, command, False, cwd=root / where)
    assert (code, len(logged)) == ((2, 0) if blocks else (0, 1)), logged
    code, logged = hook(root, monkeypatch, capsys, command, True, cwd=root / where)
    assert code == 2


def test_enforce_off_outward_send_blocks(root, monkeypatch, capsys):
    code, _ = hook(root, monkeypatch, capsys, '', False, cwd=root, tool=SEND,
                   inputs={'to': 'someone', 'text': 'Hello'})
    assert code == 2


def test_heartbeat_force_push_probe_is_refused(root, monkeypatch, capsys):
    from wuwei.commands.hook import HEARTBEAT_SESSION, run
    (root / '.wuwei/config.toml').write_text(CONFIG + '[guards]\nenforce = false\n')
    payload = {'session_id': HEARTBEAT_SESSION, 'transcript_path': str(root / 't.jsonl'),
               'cwd': str(root / 'repo'), 'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
               'tool_input': {'command': 'git push --force origin main'}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    assert run(SimpleNamespace(event='PreToolUse')) == 2
    assert 'force-push is refused' in capsys.readouterr().err


def test_hook_adds_no_resolved_line(root, monkeypatch, capsys):
    from wuwei.commands.hook import run
    payload = {'session_id': 'edges', 'transcript_path': str(root / 't.jsonl'), 'cwd': str(root / 'repo'),
               'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
               'tool_input': {'command': 'g""h pr merge 7'}}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload)))
    assert run(SimpleNamespace(event='PreToolUse')) == 2
    out = capsys.readouterr()
    assert 'merge policy' in out.err and 'resolved:' not in out.err + out.out


# Init writes the deny list; config reads the deploy rules.
def test_config_contract(root):
    config = load_config(root)
    assert config['deploy'] == {'workflows': ['deploy.yml', 'Production'],
                                'deny': ['ship release', 'make publish*']}
    assert config['repos'][0]['merge_deploys'] is False


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


def test_init_rejects_home(tmp_path, monkeypatch):
    from wuwei.commands.init import run
    monkeypatch.setenv('HOME', str(tmp_path))
    with pytest.raises(ValueError, match='global'):
        run(SimpleNamespace(path=str(tmp_path)))
    assert not (tmp_path / '.claude').exists()


@pytest.mark.parametrize('pattern', ['* release', 'tools/ship release'])
def test_custom_rules_require_literal_executable(root, pattern):
    path = root / '.wuwei/config.toml'
    path.write_text('[deploy]\ndeny = [' + json.dumps(pattern) + ']\n')
    with pytest.raises(ConfigError, match='literal executable'):
        load_config(root)

