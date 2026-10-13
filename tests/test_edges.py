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
                       root)
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


@pytest.mark.parametrize('command', ['timeout gh pr merge 5', 'git log | xargs -n'])
def test_unreadable_wrapper_is_unparsed(root, command):
    assert check(root, command) == (2, UNPARSED)


# One table per edge (#849). A row is (command, cwd relative to the workspace, exit, reason
# fragments): the first fragment starts the reason, the others appear in it; an allowed row has
# an empty reason.
def refused(command, *fragments, where='repo'):
    return command, where, 1, fragments


def allowed(command, where='repo'):
    return command, where, 0, ()


def decide(root, command, where, code, fragments, guard='check_bash'):
    got, reason = check(root, command, guard, cwd=root / where)
    assert got == code, (got, reason)
    assert reason.startswith(fragments[0]) if fragments else reason == '', reason
    assert all(fragment in reason for fragment in fragments), reason


ROW = 'command,where,code,fragments'
# Design 4.5: the wrappers that run the rest of the line, each with its own options.
WRAPPERS = ['command {}', 'command -p {}', 'exec {}', 'exec -a name {}', 'timeout 30 {}',
            'timeout -s KILL 30s {}', 'nohup {}', 'nice {}', 'nice -n 5 {}', 'sudo {}',
            'sudo -u bob {}', 'time {}', 'time -p {}', 'xargs {}', 'xargs -n 1 -0 {}',
            'env A=1 command {}', 'command env A=1 timeout 5 {}']


# Host merge: on the floor.
@pytest.mark.parametrize(ROW, [
    *(refused(command, 'merge policy', f'bin/wuwei merge {pr}') for command, pr in [
        ('gh pr merge 7', '<owner/repo>#7'), ('gh pr merge 7 --squash', '<owner/repo>#7'),
        ('GH_REPO=o/r gh pr merge 7', '<owner/repo>#7'), ('env -i gh pr merge 7', '<owner/repo>#7'),
        ("bash -c 'gh pr merge 7'", '<owner/repo>#7'), ('cd x && gh pr merge 7', '<owner/repo>#7'),
        ('/usr/bin/gh pr merge 7', '<owner/repo>#7'), ('gh -R o/r pr merge 7', 'o/r#7'),
        ('gh pr merge https://github.com/o/r/pull/7', 'o/r#7'), ('$(gh pr merge 7)', '<owner/repo>#7'),
        ('gh api -X PUT repos/o/r/pulls/7/merge', 'o/r#7'),
        ('gh api repos/o/r/merges -f base=main -f head=x', '<owner/repo>#<pr>'),
    ]),
    *(refused(wrapper.format('gh pr merge 5'), 'merge policy') for wrapper in WRAPPERS),
    # Review F2, F4, F5: shell grammar, env options and process substitution are seen through.
    *(refused(command, 'merge policy') for command in [
        '{ gh pr merge 7; }', '! gh pr merge 7', 'if true; then gh pr merge 7; fi',
        'while gh pr merge 7; do :; done', 'f() { gh pr merge 7; }; f', 'coproc gh pr merge 7',
        "env -S 'gh pr merge 7'", "env --split-string='gh pr merge 7'", 'env --chdir=/tmp gh pr merge 7',
        'env -C /tmp gh pr merge 7', 'env --unset X gh pr merge 7', 'env -u X gh pr merge 7',
        'env -0 gh pr merge 7', 'env -v gh pr merge 7', 'env -P /usr/bin gh pr merge 7',
        "bash -c -- 'gh pr merge 7'", "bash -o pipefail -c 'gh pr merge 7'", 'timeout 5 -- gh pr merge 7',
        'cat <(gh pr merge 7)', 'diff x >(gh pr merge 7)', 'echo 5 | xargs gh pr merge',
        'env X=1 gh pr merge 7 --squash', 'gh api repos/example/project/pulls/7/merge -X PUT',
        'gh pr merge $PR',
    ]),
    ('gh pr merge "', 'repo', 2, (UNPARSED,)),
    *(allowed(command) for command in [
        'gh pr view 7', 'gh pr checks 7', 'gh api repos/o/r/pulls/7/merge',
        'git commit -m "gh pr merge 7"', 'gh pr comment 7 --body "never gh pr merge 7"',
        "cat > notes.md <<'EOF'\ngh pr merge 7\nEOF", 'python3 -m pytest -q',
        'for x in 1; do echo x; done', 'export X=1',
    ]),
])
def test_merge_edge(root, command, where, code, fragments):
    decide(root, command, where, code, fragments)


# Approve: on the floor; a review body file is read for its event.
@pytest.mark.parametrize(ROW, [
    *(refused(command, 'PR approval', 'bin/wuwei merge') for command in [
        'gh pr review 7 --approve', 'gh pr review -a 7', 'gh api repos/o/r/pulls/7/reviews -f event=APPROVE',
        'gh api repos/o/r/pulls/7/reviews --field=event=APPROVE',
    ]),
    # Review F6: every approval form.
    *(refused(command, 'PR approval') for command in [
        'gh pr review 7 --approve=true', 'gh pr review 7 -ab ok',
        'gh api repos/o/r/pulls/7/reviews --input review.json',
    ]),
    *(allowed(command) for command in [
        'gh pr review 7 --comment -b ok', 'gh pr review 7 --comment -b --approve',
        'gh api repos/o/r/pulls/7/reviews -f event=COMMENT -f body=ok',
        'gh api repos/o/r/pulls/7/reviews --input comment.json',
    ]),
])
def test_approve_edge(root, command, where, code, fragments):
    (root / 'repo/review.json').write_text('{"event": "APPROVE", "body": "ok"}')
    (root / 'repo/comment.json').write_text('{"event": "COMMENT", "body": "ok"}')
    decide(root, command, where, code, fragments)


# Admin and branch protection: on the floor.
@pytest.mark.parametrize(ROW, [
    refused('gh pr merge 7 --admin', 'admin merge', 'bin/wuwei merge'),
    refused('gh pr merge --admin -R o/r 7', 'admin merge', 'bin/wuwei merge'),
    refused('gh api -X PUT repos/o/r/branches/main/protection', 'branch protection'),
    refused('gh api -X POST repos/o/r/rulesets -f name=x', 'branch protection'),
    refused('gh api orgs/o/rulesets/1 -X DELETE', 'branch protection'),
    allowed('gh api repos/o/r/branches/main/protection'), allowed('gh api repos/o/r/rulesets'),
])
def test_admin_edge(root, command, where, code, fragments):
    decide(root, command, where, code, fragments)


# Force push: blocks with enforce on, logged with it off.
@pytest.mark.parametrize(ROW, [
    *(refused(command, 'force-push is refused', 'git push origin HEAD:refs/heads/<branch>') for command in [
        'git push --force', 'git push -f origin x', 'git push -uf origin x',
        'git push --force-with-lease origin x', 'git push origin +x', 'git push --mirror',
        'git -C repo push --force origin x', 'git push origin +HEAD:refs/heads/x',
    ]),
    *(refused(wrapper.format('git push --force origin x'), 'force-push is refused') for wrapper in WRAPPERS),
    refused('git push -f origin div-1', 'force-push is refused', 'git push origin HEAD:refs/heads/div-1',
            where='worktrees/DIV-1'),
    *(allowed(command) for command in [
        'git push origin x', 'git push origin HEAD:x', 'git fetch --force', 'git push -u origin x',
        'git push --delete origin x', 'git push origin :x', 'git commit -m "git push --force"',
    ]),
])
def test_force_push_edge(root, command, where, code, fragments):
    decide(root, command, where, code, fragments)


# The default branch (B6 lead call): blocks with enforce on, logged with it off. #847 F4: WUWEI
# installs no Git hook, so skipping hooks skips nothing of WUWEI's.
@pytest.mark.parametrize(ROW, [
    *(refused(command, 'push to the default branch main is refused', 'bin/wuwei pr raise', '--item DIV-1',
              where='worktrees/DIV-1') for command in [
        'git push origin main', 'git push origin HEAD:main', 'git push upstream HEAD:refs/heads/main',
        'git -C repo push origin main', 'git push --repo origin main',
        'gh api -X PATCH repos/example/project/git/refs/heads/main -f sha=x',
    ]),
    # Review F2: a literal default-branch push in a loop is refused.
    refused('for r in a b; do git -C $r push origin main; done', 'push to the default branch main'),
    refused('git push --no-verify origin HEAD:main', 'push to the default branch'),
    refused('git -c core.hooksPath=/dev/null push origin main', 'push to the default branch'),
    *(allowed(command) for command in [
        'git push --no-verify origin HEAD:refs/heads/a', 'git -c core.hooksPath=/dev/null push origin a',
        'git -ccore.hooksPath=x push origin HEAD:refs/heads/a',
    ]),
    *(allowed(command) for command in [
        'git push origin main-fix', 'git push origin HEAD:refs/heads/div-1', 'git pull origin main',
        'git fetch origin main',
    ]),
])
def test_default_branch_push_edge(root, command, where, code, fragments):
    decide(root, command, where, code, fragments)


def test_a_seat_push_to_a_claimed_pr_branch_is_refused(root):
    # #879 review H2, J2: a claimed PR's branch takes only the gated push of bin/wuwei pr act --push,
    # from any checkout and by any refspec; a push of another branch from the main checkout is allowed.
    state._write_state(lambda data: (data['items']['DIV-1'].update(pr='example/project#9', branch='feature-y'),
                                     data['claimed_prs'].append('example/project#9')), root)
    tree = root / 'worktrees/DIV-1'
    (tree / 'sub').mkdir()
    (root / 'link').symlink_to(tree)
    for command, where in (
            ('git push origin HEAD:refs/heads/feature-y', 'worktrees/DIV-1/sub'),
            ('cd worktrees/DIV-1 && git push origin feature-y', '.'),
            ('git push origin feature-y', 'link'),
            (f'git -C {tree} push origin feature-y', '.'),
            (f'git --git-dir={tree}/.git --work-tree={tree} push', '.'),
            (f'GIT_DIR={tree}/.git git push', '.'),
            (f'GIT_WORK_TREE={tree} git push origin', '.'),
            ('git -C repo push origin feature-y', '.'),
            ('git push origin HEAD:refs/heads/feature-y', 'repo'),
            ('git push origin feature-y:feature-y', 'repo'),
            (f'bash -c "cd {tree}; git push origin feature-y"', '.'),
            ('git push', 'worktrees/DIV-1'),
            # review K2: exported GIT_DIR, short ref forms, every branch, a glob, --git-dir after -C
            (f'export GIT_DIR={tree}/.git; git push origin', '.'),
            (f'export GIT_DIR={tree}/.git && git push', '.'),
            ('git -C repo push origin HEAD:heads/feature-y', '.'),
            ('git -C repo push --all origin', '.'),
            ('git -C repo push --branches origin', '.'),
            ("git -C repo push origin 'refs/heads/*:refs/heads/*'", '.'),
            ('git -C worktrees --git-dir=DIV-1/.git push', '.')):
        decide(root, command, where, 1, ('DIV-1 owns PR example/project#9', 'bin/wuwei pr act example/project#9 --push'))
    for command, where in (('git push origin HEAD:refs/heads/other', 'repo'), ('git status', 'worktrees/DIV-1'),
                           ('export X=1; git push origin other', 'repo'),
                           ('python3 -m pytest -q', 'worktrees/DIV-1')):
        decide(root, command, where, 0, ())


def test_a_seat_push_from_a_raised_pr_worktree_is_refused(root):
    # #903: a WUWEI-raised PR takes the same gated push as a claimed one
    state._write_state(lambda data: (data['items']['DIV-1'].update(pr='example/project#9'),
                                     data['raised_prs'].append('example/project#9')), root)
    for command, where in (('git push origin HEAD', 'worktrees/DIV-1'), ('git push', 'worktrees/DIV-1')):
        decide(root, command, where, 1, ('DIV-1 owns PR example/project#9', 'bin/wuwei pr act example/project#9 --push'))
    decide(root, 'git push origin HEAD:refs/heads/other', 'repo', 0, ())


# Deploy (design 4.7): on the floor; the owner's Yes on the exact command's card lets it run (#816).
@pytest.mark.parametrize(ROW, [
    *(refused(command, 'publish: ', 'Owner step: ', rule) for command, rule in [
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
    ]),
    *(allowed(command) for command in [
        'terraform plan', 'vercel ls', 'git push origin x', 'grep -rn terraform .',
        'echo "terraform apply"', 'ship preview', 'docker build .', 'gh api repos/o/r/issues', 'git merge main',
    ]),
])
def test_deploy_edge(root, command, where, code, fragments):
    decide(root, command, where, code, fragments, 'check_deploy')


@pytest.mark.parametrize('command', [
    'vercel env ls production', 'vc env ls production', 'vercel ls', 'vercel inspect app',
    'gh api "repos/org/repo/deployments?per_page=100"',
    'gh api repos/org/repo/environments',
    'gh api -X GET repos/org/repo/deployments',
    'gh api --method=GET repos/org/repo/environments/production',
    'gh api -i -X GET repos/org/repo/environments/rerun',
    'gh api repos/org/repo/environments/rerun-failed-jobs',
    'gh api -XGET repos/org/repo/deployments/1/statuses',
    'gh api --preview x repos/org/repo/deployments',
    'gh api --preview=x repos/org/repo/environments',
    'gh api repos/org/repo/deployments -H "Accept: application/vnd.github+json"',
    'gh api repos/org/repo/environments --header="Accept: application/vnd.github+json"',
    "env CI=1 sh -c 'vercel env ls production'",
    'vercel env ls production; gh api repos/org/repo/deployments',
])
def test_publish_reads_need_no_card(root, command):
    assert check(root, command, 'check_deploy') == (0, '')
    assert check(root, command) == (0, '')


@pytest.mark.parametrize('path', ['deployments', 'environments/production'])
@pytest.mark.parametrize('options', [
    '-X POST', '--method=PUT', '-XDELETE', '-X HEAD', '-X OPTIONS',
    '-f ref=main', '-F ref=main', '--field=ref=main', '--raw-field=ref=main', '--input=-',
    '-X GET -fref=main', '-X GET -Fref=main', '-X GET --input=-',
    '-X POST --method GET', '-iXDELETE', '-ifref=main', '-iFref=main',
    '--preview x -X POST -f ref=main', '--preview=x -X POST -f ref=main',
    '-H "X-HTTP-Method-Override: POST"', '--header "x-http-method-override: DELETE"',
    '-HX-HTTP-Method-Override:POST', '--header="X-Method-OVERRIDE: PUT"',
])
def test_publish_api_non_reads_still_need_owner(root, path, options):
    code, reason = check(root, f'gh api repos/org/repo/{path} {options}', 'check_deploy')
    assert code == 1 and 'Owner step:' in reason and 'deployment/environment API' in reason


@pytest.mark.parametrize('path', ['deployments', 'environments/production'])
@pytest.mark.parametrize('targets', ['repos/org/repo/{path} extra', 'extra repos/org/repo/{path}'])
@pytest.mark.parametrize('method', ['', '-X POST'])
def test_publish_api_multiple_targets_need_owner(root, path, targets, method):
    command = f'gh api {targets.format(path=path)} {method}'
    code, reason = check(root, command, 'check_deploy')
    assert code == 1 and 'Owner step:' in reason and 'deployment/environment API' in reason


@pytest.mark.parametrize('command', [
    'vercel env add NAME production', 'vc env rm NAME production', 'vercel deploy --prod',
    'vercel env ls production; vercel --prod',
    'gh api repos/org/repo/deployments; gh api -X POST repos/org/repo/deployments',
])
def test_publish_read_does_not_allow_writes(root, command):
    code, reason = check(root, command, 'check_deploy')
    assert code == 1 and 'Owner step:' in reason


def test_publish_read_respects_explicit_deny(root):
    (root / '.wuwei/config.toml').write_text('[deploy]\ndeny = ["vercel env ls"]\n')
    code, reason = check(root, 'vercel env ls production', 'check_deploy')
    assert code == 1 and 'deploy.deny: vercel env ls' in reason


@pytest.mark.parametrize('command', [
    'vercel env ls production', 'gh api "repos/org/repo/deployments?per_page=100"',
])
@pytest.mark.parametrize('enforce', [True, False])
def test_publish_field_reads_through_hook(root, monkeypatch, capsys, command, enforce):
    code, findings = hook(root, monkeypatch, capsys, command, enforce)
    assert code == 0 and findings == []


def test_publish_card_explains_exact_command_binding(root):
    from fakes.owner import answer_card
    command = 'gh workflow run deploy.yml -f ref=abc'
    code, reason = check(root, command, 'check_deploy')
    assert code == 1
    card = json.loads(reason.split('; card: ', 1)[1])
    detail = card['options'][0]['description']
    assert 'Only this exact command text is approved' in detail
    assert 'run it alone' in detail
    answer_card(root, reason)
    for changed in ('gh workflow run deploy.yml --ref main',
                    f'git fetch; {command}; sleep 1; gh run list'):
        assert check(root, changed, 'check_deploy')[0] == 1
    assert check(root, command, 'check_deploy') == (0, '')
    assert check(root, command, 'check_deploy')[0] == 1


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


# A bare gh pr create for an item: blocks with enforce on, logged with it off.
@pytest.mark.parametrize(ROW, [
    *(refused(command, 'pr raise: DIV-1 is a WUWEI item', 'bin/wuwei pr raise example/project', '--item DIV-1',
              where=where) for command, where in [
        ('gh pr create --title t --body b', 'worktrees/DIV-1'),
        ('gh pr create --repo example/project --head div-1 --title t --body b', '.'),
        ('gh -R example/project pr create -H div-1 -t t -b b', '.'),
        ('cd worktrees/DIV-1 && gh pr create -t t -b b', '.'),
    ]),
    allowed('gh pr create -t t -b b'), allowed('gh pr create --repo example/project --head other -t t', '.'),
])
def test_pr_create_edge(root, command, where, code, fragments):
    decide(root, command, where, code, fragments)


def test_pr_raise_allowed_once_the_item_links_a_pr(root):
    state._write_state(lambda data: data['items']['DIV-1'].update(pr='example/project#5'),
                       root)
    assert check(root, 'gh pr create -t t -b b', cwd=root / 'worktrees/DIV-1') == (0, '')


# Outward send (part 16's check_send, moved): on the floor; a read verb is no send.
SEND = 'mcp__acme__send_message'


@pytest.mark.parametrize('tool,allow,code,fragment', [
    (SEND, [], 1, 'outward.allow'),
    (SEND, [SEND], 0, ''),
    ('mcp__acme__send_mail', [SEND], 1, 'outward.allow'),
    ('mcp__acme__get_message', [], 0, ''),
])
def test_outward_send_edge(root, tool, allow, code, fragment):
    from wuwei.guards import edges
    (root / '.wuwei/config.toml').write_text(CONFIG + f'[outward]\nallow = {json.dumps(allow)}\n')
    got, reason = edges.check_send({'cwd': str(root), 'tool_name': tool,
                                    'tool_input': {'to': 'someone', 'text': 'Hello'}})
    assert got == code and fragment in reason and (code or reason == ''), (got, reason)


# guards.enforce off: the floor edges block; force push, the default branch and PR raise log.
@pytest.mark.parametrize('command,where,blocks', [
    ('gh pr merge 7', 'repo', True), ('gh pr review 7 --approve', 'repo', True),
    ('gh pr merge 7 --admin', 'repo', True), ('gh api -X PUT repos/o/r/branches/main/protection', 'repo', True),
    ('terraform apply', 'repo', True), ('git push --force origin x', 'repo', False),
    ('git push origin main', 'repo', False), ('gh pr create -t t -b b', 'worktrees/DIV-1', False),
    # Review F1: the edge decides before the body scan reads a body file it cannot find.
    ('gh pr merge 7 --body-file missing.md', 'repo', True),
    ('gh pr merge 7 --admin --body-file missing.md', 'repo', True),
    ('gh pr review 7 --approve --body-file missing.md', 'repo', True),
    ('gh api repos/o/r/pulls/7/merge -X PUT --input missing.json', 'repo', True),
    ('gh api repos/o/r/pulls/7/reviews --input -', 'repo', True),
    ('gh api repos/o/r/pulls/7/reviews --input missing.json', 'repo', True),
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


def test_doctor_force_push_probe_is_refused(root, monkeypatch, capsys):
    from wuwei.commands.hook import PROBE_SESSION, run
    (root / '.wuwei/config.toml').write_text(CONFIG + '[guards]\nenforce = false\n')
    payload = {'session_id': PROBE_SESSION, 'transcript_path': str(root / 't.jsonl'),
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

