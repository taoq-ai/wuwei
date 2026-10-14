"""The irreversible edges by exact argv per command segment (#839): one table per edge, each with
refused rows, allowed near misses and a row through the hook with guards.enforce off."""

import io
import json
import shlex
import sys
from fnmatch import fnmatchcase
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


# Irreversible command edges by exact argv.
@pytest.mark.parametrize(ROW, [
    # Host merge: on the floor.
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
    # Admin and branch protection: on the floor.
    refused('gh pr merge 7 --admin', 'admin merge', 'bin/wuwei merge'),
    refused('gh pr merge --admin -R o/r 7', 'admin merge', 'bin/wuwei merge'),
    refused('gh api -X PUT repos/o/r/branches/main/protection', 'branch protection'),
    refused('gh api -X POST repos/o/r/rulesets -f name=x', 'branch protection'),
    refused('gh api orgs/o/rulesets/1 -X DELETE', 'branch protection'),
    allowed('gh api repos/o/r/branches/main/protection'), allowed('gh api repos/o/r/rulesets'),
    # Force push: blocks with enforce on, logged with it off.
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
    # Default branch push: blocks with enforce on, logged with it off.
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
    # A bare gh pr create for an item: blocks with enforce on, logged with it off.
    *(refused(command, 'pr raise: DIV-1 is a WUWEI item', 'bin/wuwei pr raise example/project', '--item DIV-1',
              where=where) for command, where in [
        ('gh pr create --title t --body b', 'worktrees/DIV-1'),
        ('gh pr create --repo example/project --head div-1 --title t --body b', '.'),
        ('gh -R example/project pr create -H div-1 -t t -b b', '.'),
        ('cd worktrees/DIV-1 && gh pr create -t t -b b', '.'),
    ]),
    allowed('gh pr create -t t -b b'), allowed('gh pr create --repo example/project --head other -t t', '.'),
])
def test_irreversible_edge(root, command, where, code, fragments):
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


# Infrastructure keeps exact-command cards; application delivery runs without them.
@pytest.mark.parametrize(ROW, [
    *(refused(command, 'infrastructure: ', 'Owner step: ', rule) for command, rule in [
        ('ship release --prod', 'deploy.deny: ship release'), ('make publish-prod', 'deploy.deny'),
        ('terraform apply', 'terraform apply'),
        ("sh -c 'terraform apply -auto-approve'", 'terraform apply'), ('env REGION=x terraform apply', 'terraform'),
        ('kubectl --context prod apply -f a.yml', 'kubectl apply'), ('helm upgrade app chart', 'helm upgrade'),
        ('aws cloudformation create-stack --stack-name app', 'aws'),
    ]),
    *(allowed(command) for command in [
        'gh workflow run deploy.yml', 'gh workflow run Production',
        'gh -R acme/app workflow run .github/workflows/deploy.yml',
        'gh run rerun 123', 'gh release create v1.2.0', 'git push origin v1.2.0',
        'git push --tags', 'git push origin HEAD:refs/tags/stable', 'git push origin production',
        'git push origin HEAD:release/next', 'docker build --push .', 'vercel --prod',
        'gh api -X POST repos/o/r/deployments', 'gh api repos/o/r/releases -f tag_name=v1',
        'gh api repos/o/r/actions/workflows/deploy.yml/dispatches -X POST',
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
    guard = 'check_deploy' if path == 'deployments' else 'check_bash'
    code, reason = check(root, f'gh api repos/org/repo/{path} {options}', guard)
    if path == 'deployments':
        assert (code, reason) == (0, '')
    else:
        assert code in (1, 2) and 'Owner step:' in reason and reason.startswith('repository settings')


@pytest.mark.parametrize('path', ['deployments', 'environments/production'])
@pytest.mark.parametrize('targets', ['repos/org/repo/{path} extra', 'extra repos/org/repo/{path}'])
@pytest.mark.parametrize('method', ['', '-X POST'])
def test_publish_api_multiple_targets_need_owner(root, path, targets, method):
    command = f'gh api {targets.format(path=path)} {method}'
    code, reason = check(root, command, 'check_deploy' if path == 'deployments' else 'check_bash')
    if path == 'deployments':
        assert (code, reason) == (0, '')
    else:
        assert code == 1 and 'Owner step:' in reason and reason.startswith('repository settings')


@pytest.mark.parametrize('command', [
    'vercel env add NAME production', 'vc env rm NAME production', 'vercel deploy --prod',
    'vercel env ls production; vercel --prod',
    'gh api repos/org/repo/deployments; gh api -X POST repos/org/repo/deployments',
])
def test_publish_read_does_not_allow_writes(root, command):
    code, reason = check(root, command, 'check_deploy')
    if 'env add' in command or 'env rm' in command:
        assert code == 1 and 'Owner step:' in reason
    else:
        assert (code, reason) == (0, '')


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
    command = 'terraform apply -var ref=abc'
    code, reason = check(root, command, 'check_deploy')
    assert code == 1
    card = json.loads(reason.split('; card: ', 1)[1])
    detail = card['options'][0]['description']
    assert 'Only this exact command text is approved' in detail
    assert 'run it alone' in detail
    answer_card(root, reason)
    for changed in ('terraform apply -var ref=main',
                    f'git fetch; {command}; sleep 1; gh run list'):
        assert check(root, changed, 'check_deploy')[0] == 1
    assert check(root, command, 'check_deploy') == (0, '')
    assert check(root, command, 'check_deploy')[0] == 1


def test_unmarked_workflow_is_allowed(root):
    (root / '.wuwei/config.toml').write_text('[deploy]\nworkflows = ["deploy.yml"]\n')
    assert check(root, 'gh workflow run ci.yml', 'check_deploy') == (0, '')
    assert check(root, 'gh workflow run deploy.yml', 'check_deploy') == (0, '')


def test_deploy_runs_on_the_owners_yes(root):
    from fakes.owner import answer_card
    command = 'terraform apply -var app=example'
    code, reason = check(root, command, 'check_deploy')
    assert code == 1 and reason.startswith(f'infrastructure: {command}: waits for the owner')
    answer_card(root, reason, 'No')
    assert check(root, command, 'check_deploy')[0] == 1
    answer_card(root, reason)
    assert check(root, command, 'check_deploy') == (0, '')
    assert check(root, command + ' --notes x', 'check_deploy')[0] == 1


@pytest.mark.parametrize('text', ['[deploy]\ndeny = "ship release"', '[deploy]\ndeny = [12]'])
def test_deploy_unreadable_config_fails_closed(root, text):
    (root / '.wuwei/config.toml').write_text(text)
    with pytest.raises(ConfigError):
        load_config(root)
    assert check(root, 'gh workflow run deploy.yml', 'check_deploy')[0] == 2


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
    ('gh pr merge 7', 'repo', False), ('gh pr review 7 --approve', 'repo', False),
    ('gh pr merge 7 --admin', 'repo', True), ('gh api -X PUT repos/o/r/branches/main/protection', 'repo', True),
    ('terraform apply', 'repo', True), ('git push --force origin x', 'repo', False),
    ('git push origin main', 'repo', False), ('gh pr create -t t -b b', 'worktrees/DIV-1', False),
    # Review F1: the edge decides before the body scan reads a body file it cannot find.
    ('gh pr merge 7 --body-file missing.md', 'repo', False),
    ('gh pr merge 7 --admin --body-file missing.md', 'repo', True),
    ('gh pr review 7 --approve --body-file missing.md', 'repo', False),
    ('gh api repos/o/r/pulls/7/merge -X PUT --input missing.json', 'repo', False),
    ('gh api repos/o/r/pulls/7/reviews --input -', 'repo', False),
    ('gh api repos/o/r/pulls/7/reviews --input missing.json', 'repo', False),
])
def test_enforce_off(root, monkeypatch, capsys, command, where, blocks):
    code, logged = hook(root, monkeypatch, capsys, command, False, cwd=root / where)
    assert (code, len(logged)) == ((2, 0) if blocks else (0, 1)), logged
    code, logged = hook(root, monkeypatch, capsys, command, True, cwd=root / where)
    assert code == 2


def test_enforce_off_outward_send_nudges(root, monkeypatch, capsys):
    code, _ = hook(root, monkeypatch, capsys, '', False, cwd=root, tool=SEND,
                   inputs={'to': 'someone', 'text': 'Hello'})
    assert code == 0


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
    (root / '.wuwei/config.toml').write_text(CONFIG + '[guards]\nenforce = true\n')
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
    assert config['deploy'] == {'deny': ['ship release', 'make publish*']}
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
    settings.write_text(json.dumps({'permissions': {'deny': ['Bash(custom *)',
                                                            'Bash(vercel*)', 'Bash(vc *)'],
                                                   'allow': ['Read']}, 'extra': True}))
    assert run(SimpleNamespace(path=str(project))) == 0
    data = json.loads(settings.read_text())
    assert data['extra'] is True
    assert data['permissions']['allow'] == ['Read']
    deny = data['permissions']['deny']
    assert len(deny) == len(set(deny))
    from wuwei.guards.edges import PERMISSIONS_DENY
    assert set(deny) == {'Bash(custom *)', *PERMISSIONS_DENY}
    assert 'Bash(vercel*)' not in deny and 'Bash(vc *)' not in deny
    assert global_settings.read_text() == '{"owner": true}'
    patterns = [rule[5:-1] for rule in deny if rule.startswith('Bash(')]
    for binary in ('vercel', 'vc'):
        for command in ('alias set target', 'alias rm target', 'domains add example.test', 'env pull', 'pull'):
            assert any(fnmatchcase(f'{binary} {command}', pattern) for pattern in patterns)
        for command in ('--yes', '--prod', 'deploy', '.', './web', '--help'):
            assert not any(fnmatchcase(f'{binary} {command}', pattern) for pattern in patterns)
        assert not any(fnmatchcase(f'{binary} alias ls', pattern) for pattern in patterns)


@pytest.mark.parametrize('legacy,damage', [
    (['Bash(vercel*)', 'Bash(vc *)'], 'broken'),
    (['Bash(vc *)'], 'nonobject'),
    (['Bash(vercel*)', 'Bash(vc *)'], 'symlink_file'),
    (['Bash(vc *)'], 'symlink_dir'),
])
def test_upgrade_replaces_legacy_vercel_denials_only(tmp_path, legacy, damage, capsys):
    from wuwei.commands.init import run
    assert run(SimpleNamespace(path=str(tmp_path))) == 0
    settings = tmp_path / '.claude/settings.json'
    original = {
        'permissions': {
            'allow': ['Read'],
            'deny': ['Bash(custom *)', *legacy, 'Bash(other *)'],
        },
        'extra': {'owner': True},
    }
    settings.write_text(json.dumps(original, indent=2) + '\n')
    assert run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=True)) == 0
    assert 'Would upgrade .claude/settings.json: narrow action denials to infrastructure' in capsys.readouterr().out
    assert json.loads(settings.read_text()) == original
    assert run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=False)) == 0
    migrated = json.loads(settings.read_text())
    assert migrated['extra'] == original['extra']
    assert migrated['permissions']['allow'] == original['permissions']['allow']
    deny = migrated['permissions']['deny']
    assert [rule for rule in deny if rule in ('Bash(custom *)', 'Bash(other *)')] == [
        'Bash(custom *)', 'Bash(other *)']
    assert 'Bash(vercel*)' not in deny and 'Bash(vc *)' not in deny
    for binary in ('vercel', 'vc'):
        for suffix in (' alias set*', ' alias rm*', ' domains add*', ' env add*', ' env rm*'):
            assert deny.count(f'Bash({binary}{suffix})') == 1
        assert f'Bash({binary} deploy*)' not in deny
    after = settings.read_text()
    assert run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=False)) == 0
    assert settings.read_text() == after
    capsys.readouterr()
    if damage == 'broken':
        settings.write_text('{')
    elif damage == 'nonobject':
        settings.write_text('[]')
    else:
        outside = tmp_path / 'outside'
        outside.mkdir()
        (outside / 'settings.json').write_text(after)
        settings.unlink()
        if damage == 'symlink_file':
            settings.symlink_to(outside / 'settings.json')
        else:
            settings.parent.rmdir()
            settings.parent.symlink_to(outside, target_is_directory=True)
    before = settings.read_text()
    pointer = tmp_path / '.wuwei/executable'
    pointer.unlink()
    assert run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=False)) == 0
    assert settings.read_text() == before
    assert pointer.is_file()
    assert '.claude/settings.json migration skipped' in capsys.readouterr().err


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

@pytest.mark.parametrize('command', [
    'vercel', 'vercel --prod', 'vc deploy --prod --yes', 'vercel ./app',
    'vercel promote deployment', 'vercel rollback deployment', 'vercel redeploy deployment',
    'netlify deploy --prod', 'fly deploy', 'docker push org/app',
    'gh release create v1.0', 'git push origin --tags', 'gh workflow run deploy.yml',
    'gh api repos/org/repo/deployments -f ref=main', 'gcloud run deploy app',
    'aws lambda update-function-code --function-name app --zip-file fileb://app.zip',
])
def test_app_delivery_needs_no_card(root, command):
    assert check(root, command, 'check_deploy') == (0, '')


@pytest.mark.parametrize('command', [
    'terraform apply', 'pulumi up', 'pulumi destroy', 'kubectl apply -f resources.yaml',
    'vercel domains add example.test', 'vc env add TOKEN production',
    'vercel project rm app', 'vercel alias set app example.test',
    'aws ec2 run-instances --image-id image', 'aws route53 change-resource-record-sets',
    'gcloud dns record-sets create example.test', 'az group create --name app',
])
def test_infrastructure_stays_on_floor(root, command):
    from wuwei import guards
    from wuwei.guards import edges
    code, reason = check(root, command, 'check_deploy')
    assert code == 1 and reason.startswith('infrastructure:')
    assert guards.floor(edges.check_deploy, reason)


def test_host_denies_only_infrastructure_and_admin():
    from wuwei.guards.edges import PERMISSIONS_DENY
    for command in ('vercel --prod', 'vc deploy', 'fly deploy', 'docker push org/app',
                    'gh pr review 7 --approve', 'gh release create v1'):
        assert not any(fnmatchcase(command, rule[5:-1]) for rule in PERMISSIONS_DENY)
    for command in ('terraform apply', 'vercel domains add example.test', 'gh pr merge 7 --admin'):
        assert any(fnmatchcase(command, rule[5:-1]) for rule in PERMISSIONS_DENY)


def test_upgrade_removes_shipped_app_rules_and_keeps_explicit_enforcement(tmp_path):
    from wuwei.commands.init import run
    assert run(SimpleNamespace(path=str(tmp_path))) == 0
    settings = tmp_path / '.claude/settings.json'
    original = json.loads(settings.read_text())
    original['permissions']['deny'] += ['Bash(vercel --prod*)', 'Bash(docker push*)',
                                        'Bash(gh pr review * --approve*)', 'Bash(custom *)']
    settings.write_text(json.dumps(original))
    config = tmp_path / '.wuwei/config.toml'
    config.write_text(config.read_text().replace('enforce = false', 'enforce = true'))
    assert run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=False)) == 0
    denials = json.loads(settings.read_text())['permissions']['deny']
    assert 'Bash(docker push*)' not in denials
    assert 'Bash(vercel --prod*)' not in denials
    assert 'Bash(gh pr review * --approve*)' not in denials
    assert 'Bash(custom *)' in denials
    assert load_config(tmp_path)['guards']['enforce'] is True
    config.write_text(config.read_text().replace('enforce = true', '# enforce unset'))
    assert run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=False)) == 0
    assert load_config(tmp_path)['guards']['enforce'] is False

@pytest.mark.parametrize('command', ['gh repo edit o/r --visibility public',
    'gh api repos/o/r -X PATCH -f allow_merge_commit=true', 'gh api repos/o/r/rulesets -X POST'])
def test_admin_settings_require_a_card(root, command):
    from fakes.owner import answer_card
    from wuwei.guards import floor, edges
    code, reason = check(root, command)
    assert code == 1 and floor(edges.check_bash, reason) and 'Owner step:' in reason
    answer_card(root, reason)
    assert check(root, command) == (0, '')

@pytest.mark.parametrize('prefix', ['gh pr merge 7', 'gh pr review 7 --approve', 'git push --force origin x'])
@pytest.mark.parametrize('protected', ['gh repo delete o/r --yes', 'gh pr merge 7 --admin',
    'gh api repos/o/r/branches/main/protection -X DELETE'])
def test_nudged_first_segment_cannot_hide_later_admin(root, prefix, protected):
    from wuwei.guards import edges, floor
    code, reason = check(root, prefix + '; ' + protected)
    assert code == 1 and floor(edges.check_bash, reason) and 'Owner step:' in reason

@pytest.mark.parametrize('command', ['gh pr review 7 --approve --body-file review.md',
    'gh pr merge 7 --body-file review.md',
    'gh api repos/o/r/pulls/7/reviews -f event=APPROVE -F body=@review.md'])
@pytest.mark.parametrize('marker', ['canary', 'honeytoken', 'disposition'])
def test_ordinary_actions_still_scan_protected_body_files(root, command, marker):
    from wuwei import security
    from wuwei.guards import edges, floor
    secrets = security.initialize(root / '.wuwei')
    (root / 'repo/review.md').write_text('WUWEI parked A' if marker == 'disposition' else secrets[marker])
    code, reason = check(root, command)
    assert code == 1 and floor(edges.check_bash, reason)


@pytest.mark.parametrize('shape', ['dict', 'list', 'string'])
def test_malformed_send_cannot_hide_canary(root, shape):
    from wuwei import security
    from wuwei.guards import edges, floor
    secrets = security.initialize(root / '.wuwei')
    inputs = {'dict': {'text': secrets['canary'], 'recipients': 'someone'},
              'list': [secrets['canary']], 'string': secrets['canary']}[shape]
    code, reason = edges.check_send({'cwd': str(root), 'tool_name': SEND,
        'tool_input': inputs})
    assert code == 1 and floor(edges.check_send, reason)

@pytest.mark.parametrize('command', ['az webapp deploy --resource-group rg --name app --src-path app.zip',
    'aws deploy create-deployment --application-name app --deployment-group-name prod',
    'aws ecs update-service --cluster app --service app --force-new-deployment'])
def test_cloud_app_delivery_is_not_infrastructure(root, command):
    assert check(root, command, 'check_deploy') == (0, '')


@pytest.mark.parametrize('command', ['vercel domains move example.test other-team',
    'aws ec2 authorize-security-group-ingress --group-id sg-1 --protocol tcp --port 443'])
def test_infrastructure_ownership_and_access_changes_need_cards(root, command):
    code, reason = check(root, command, 'check_deploy')
    assert code == 1 and reason.startswith('infrastructure:')


def test_owner_admin_card_does_not_approve_secret_egress(root):
    from fakes.owner import answer_card
    from wuwei import security
    from wuwei.guards import edges, floor
    secrets = security.initialize(root / '.wuwei')
    body = root / 'repo/review.md'
    body.write_text('Reviewed')
    command = 'gh pr merge 7 --admin --body-file review.md'
    code, reason = check(root, command)
    answer_card(root, reason)
    body.write_text(secrets['canary'])
    code, reason = check(root, command)
    assert code == 1 and reason.startswith('outward: security.') and floor(edges.check_bash, reason)

@pytest.mark.parametrize('target', ['repos/o/r/environments%2fproduction',
    'repos/o/r/environments?name=production'])
def test_environment_api_encoded_target_stays_owner_only(root, target):
    code, reason = check(root, f'gh api {target} -X PUT')
    assert code == 1 and reason.startswith('repository settings') and 'Owner step:' in reason

@pytest.mark.parametrize('command', [
    'aws cloudformation create-stack --stack-name update-function-code --template-body file://stack.yaml',
    'aws cloudformation update-stack --stack-name update-service --force-new-deployment',
])
def test_app_operation_names_in_values_do_not_authorize_infrastructure(root, command):
    code, reason = check(root, command, 'check_deploy')
    assert code == 1 and reason.startswith('infrastructure:')


@pytest.mark.parametrize('command', [
    'netlify env:set TOKEN value', 'ntl sites:delete site',
    'gcloud sql instances patch db', 'aws rds modify-db-instance --db-instance-identifier db',
    'aws s3 rb s3://bucket', 'aws ec2 stop-instances --instance-ids i-1',
    'aws rds reboot-db-instance --db-instance-identifier db', 'fly scale count 0',
    'gcloud compute disks resize disk --size 20GB',
    'gcloud --quiet sql instances delete db', 'aws --no-cli-pager rds delete-db-instance --db-instance-identifier db',
    'aws --output json s3 rb s3://bucket', 'az --only-show-errors group delete -n rg',
    *[f'gcloud {service} deploy app {flag}' for service in ('run', 'functions')
      for flag in ('--allow-unauthenticated', '--service-account=admin@example.test', '--set-secrets=KEY=secret:latest')],
])
def test_review_infrastructure_commands_require_owner_card(root, command):
    from fakes.owner import answer_card
    code, reason = check(root, command, 'check_deploy')
    assert code == 1 and reason.startswith('infrastructure:') and 'Owner step:' in reason
    answer_card(root, reason)
    assert check(root, command, 'check_deploy') == (0, '')


@pytest.mark.parametrize('command', [
    'aws dynamodb get-item --table-name put-events --key k',
    'aws --profile production dynamodb get-item --table-name delete-events --key k',
    'gcloud sql instances describe db --format create',
])
def test_review_cloud_option_values_are_not_operations(root, command):
    assert check(root, command, 'check_deploy') == (0, '')


def test_review_upgrade_keeps_secret_pull_denials(tmp_path):
    from wuwei.commands.init import LEGACY_APP_DENY, run
    rules = {f'Bash({binary}{suffix})' for binary in ('vercel', 'vc')
             for suffix in (' env pull*', ' pull*')}
    assert not rules & LEGACY_APP_DENY
    assert run(SimpleNamespace(path=str(tmp_path))) == 0
    settings = tmp_path / '.claude/settings.json'
    data = json.loads(settings.read_text())
    data['permissions']['deny'] += sorted(rules)
    settings.write_text(json.dumps(data))
    assert run(SimpleNamespace(path=str(tmp_path), upgrade=True, dry_run=False)) == 0
    assert rules <= set(json.loads(settings.read_text())['permissions']['deny'])


REPOSITORY_ADMIN_PATHS = ['collaborators/person', 'hooks', 'hooks/1', 'keys', 'keys/1',
    'actions/secrets/TOKEN', 'actions/variables/NAME', 'actions/permissions',
    'actions/permissions/workflow', 'transfer', 'branches/main/rename',
    'environments', 'environments/production']


@pytest.mark.parametrize('command', [
    *[f'gh api repos/o/r/{path} -X PUT' for path in REPOSITORY_ADMIN_PATHS],
    *[f'gh {family} {verb} NAME -R o/r' for family in ('secret', 'variable')
      for verb in ('set', 'delete')],
    'gh repo deploy-key add key.pub -R o/r', 'gh repo deploy-key delete 1 -R o/r',
])
def test_review_repository_admin_writes_require_card(root, command):
    from fakes.owner import answer_card
    from wuwei.guards import edges, floor
    code, reason = check(root, command)
    assert code == 1 and reason.startswith('repository settings') and floor(edges.check_bash, reason)
    assert 'Owner step:' in reason
    answer_card(root, reason)
    assert check(root, command) == (0, '')


@pytest.mark.parametrize('path', REPOSITORY_ADMIN_PATHS)
def test_review_repository_admin_reads_are_allowed(root, path):
    assert check(root, f'gh api repos/o/r/{path}') == (0, '')


def test_review_admin_body_nudge_still_honors_owner_answer(root):
    from fakes.owner import answer_card
    command = 'gh api repos/o/r -X PATCH --input missing.json'
    code, reason = check(root, command)
    assert code == 2 and 'Owner step:' in reason
    answer_card(root, reason)
    assert check(root, command) == (0, '')


@pytest.mark.parametrize('field', ['raised_prs', 'claimed_prs'])
@pytest.mark.parametrize('command', [
    'gh pr merge 7', 'gh pr merge 7 -R example/project',
    'gh pr merge https://github.com/example/project/pull/7',
    'gh api repos/example/project/pulls/7/merge -X PUT',
    'gh pr merge div-1', 'gh pr merge',
    'GH_REPO=example/project gh pr merge 7',
])
def test_review_owned_raw_merge_stays_on_floor(root, monkeypatch, capsys, field, command):
    ref = 'example/project#7'
    state._write_state(lambda data: (data[field].append(ref),
        data['items']['DIV-1'].update(pr=ref, branch='div-1')), root)
    code, reason = check(root, command)
    assert code == 1 and (f'run bin/wuwei merge {ref}; it merges without a card '
                         'when the gates and CI are green') in reason
    assert hook(root, monkeypatch, capsys, command, False)[0] == 2


@pytest.mark.parametrize('command', ['gh pr merge 8', 'gh pr merge 7 -R other/repo',
                                    'GH_REPO=other/repo gh pr merge 7',
                                    'gh pr review 7 --approve'])
def test_review_unowned_merge_and_approval_remain_nudges(root, monkeypatch, capsys, command):
    state._write_state(lambda data: data['raised_prs'].append('example/project#7'), root)
    assert hook(root, monkeypatch, capsys, command, False)[0] == 0


@pytest.mark.parametrize('command', ['gh pr merge', 'gh pr merge div-1'])
def test_review_raised_merge_resolves_worktree_branch(root, command):
    from wuwei.guards import edges, floor
    ref = 'example/project#7'
    state._write_state(lambda data: (data['raised_prs'].append(ref),
        data['items']['DIV-1'].update(pr=ref)), root)
    code, reason = check(root, command, cwd=root / 'worktrees/DIV-1')
    assert code == 1 and floor(edges.check_bash, reason)
    assert f'run bin/wuwei merge {ref}' in reason


def test_review_environment_card_is_honored_by_the_whole_hook(root, monkeypatch, capsys):
    from fakes.owner import answer_card
    command = 'gh api repos/o/r/environments/production -X PUT'
    code, reason = check(root, command)
    assert code == 1 and 'Owner step:' in reason
    answer_card(root, reason)
    assert hook(root, monkeypatch, capsys, command, False)[0] == 0
