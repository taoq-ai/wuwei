"""#903: raised and claimed PRs share one post-PR path. A PR fix always takes its delta review,
an item with a linked PR is updated by the gated push and never raised again, red checks at the
head the item holds raise a fix whatever its phase, and --complete is leased on the head --run
started from."""

import json

import pytest

from wuwei import derive, state, workspace
from wuwei.registry import Result
from test_close_branches import case  # noqa: F401 (the PR fixture)


@pytest.fixture
def day(tmp_path, monkeypatch):
    from fakes.day import Day
    return Day(tmp_path / 'workspace', monkeypatch)


def red(day, sha):
    day.host.results['checks'] = Result(0, [{'name': 'Unit CI', 'sha': sha, 'state': 'completed',
                                             'conclusion': 'failure', 'url': 'https://example.test/c'}])


def listing(day, sha, checks='red'):
    (day.directory / 'prs.json').write_text(json.dumps({'fetched_at': workspace.now().isoformat(), 'pulls': [
        {'ref': day.ref, 'number': 7, 'state': 'open', 'head': sha, 'checks': checks,
         'mergeable': 'mergeable', 'labels': []}]}))


@pytest.mark.parametrize('first', ['PASS', 'FIX'])
def test_a_raised_pr_fix_takes_its_arch_delta_and_the_gated_push(day, first):
    # The issue's test: raise a PR, receive all PASS verdicts, introduce a CI failure, fix it,
    # complete the architecture review and push: one PR, one required delta review, no raise.
    # FIX: arch asked for a pre-PR round, so its pre-PR delta PASS must not stand in for the review.
    import os
    import subprocess
    from wuwei import commit_push, registry
    day.plan()
    day.approve()
    day.run('plan', 'session', 'planner')
    subprocess.run(['git', '-C', str(day.repo), 'checkout', '-q', '-b', 'feature'], env=dict(os.environ),
                   capture_output=True, check=True)
    day.host.results['pr'].data.update(branch='feature')
    day.build('builder-initial')
    for role in ('arch', 'quality', 'security'):
        day.gate(role, first if role == 'arch' else 'PASS')
    if first == 'FIX':
        day.fix()
        day.gate('arch', 'PASS', round_name='delta')
    assert day.next()['action'] == 'raise'
    day.raise_pr()
    raised = day.head
    assert day.data['items']['A']['phase'] == 'raised'
    red(day, raised)
    action = json.loads(day.run('pr', 'act', day.ref, expected=1))
    assert day.data['items']['A']['phase'] == 'fix'
    day.steps(action)
    assert day.data['items']['A']['phase'] == 'delta' and day.head != raised
    delta = day.next()
    assert (delta['action'], delta.get('roles')) == ('gates', ['arch']), delta
    day.gate('arch', 'PASS', round_name='delta')
    assert day.next() == {'action': 'run', 'command': f'wuwei pr act {day.ref} --push', 'notes': []}
    vcs = registry.load('vcs', None)
    vcs.results['fetch'] = Result(0, {'sha': raised})
    vcs.results['merge_base'] = Result(0, {'sha': raised})
    vcs.results['push_context'] = Result(0, {'head': {'sha': day.head}, 'force': False, 'updates': []})
    vcs.results['push'] = Result(0, {'pushed': True})
    context = commit_push.context  # the scripted day has no git identity
    day.patch.setattr(commit_push, 'context', lambda *args, **kwargs: context(*args, identity=False))
    day.patch.setattr(commit_push, 'push_check', lambda *args: (0, ''))
    assert '"action": "pushed"' in day.run('pr', 'act', day.ref, '--push')
    [push] = [call for call in vcs.calls if call[0] == 'push']
    assert push[1][-1] == raised  # leased on the PR head the worktree contains
    assert day.data['items']['A']['phase'] == 'raised'
    assert len([call for call in day.host.calls if call[0] == 'create_pr']) == 1
    deltas = [row['payload'] for row in day.events if row['kind'] == 'gate.received'
              and row['payload']['round'] == 'delta']
    assert [row['role'] for row in deltas] == ['arch'] * (2 if first == 'FIX' else 1)
    assert not [name for name in day.data['seats'] if name.startswith('shepherd-A')]


@pytest.mark.parametrize('phase', ['gate', 'delta'])
def test_red_checks_on_a_pr_at_gate_raise_a_fix(day, phase):
    # #900's third ask, the field case: the record holds gate, the approved PR's Unit CI is red at
    # the head the item holds; next offers the fix, not the gates. The same at delta.
    from wuwei import dispatch
    day.plan()
    day.approve()
    day.run('plan', 'session', 'planner')
    day.build('builder-initial')
    if phase == 'delta':
        for role in ('arch', 'quality', 'security'):
            day.gate(role, 'FIX' if role == 'quality' else 'PASS')
        day.fix()
    assert day.data['items']['A']['phase'] == phase
    day.host.results['pr'].data.update(head=day.head, branch='feature', mergeable=True)
    day.run('pr', 'claim', day.ref, '--item', 'A')
    assert day.data['items']['A']['phase'] == phase
    red(day, day.head)
    listing(day, day.head)
    config = workspace.load_config(day.root)
    found = [(row['kind'], row['command']) for row in derive.offers(day.data, day.root, config)['launches']
             if row['item'] == 'A']
    assert found == [('fix', f'wuwei pr act {day.ref}')]
    [entry] = [row for row in dispatch.launch_set(day.root)['entries'] if row['item'] == 'A']
    assert (entry['kind'], entry['action'], entry['agent_type']) == ('fix', 'continue', 'wuwei:builder'), entry
    assert 'Unit CI' in entry['prompt'] and day.data['items']['A']['phase'] == 'fix'


def test_red_checks_on_an_older_pr_head_leave_the_gates_to_read_the_new_one(day):
    # the worktree is past the red PR head: that fix is in review; the gates read it first
    day.plan()
    day.approve()
    day.run('plan', 'session', 'planner')
    day.build('builder-initial')
    day.host.results['pr'].data.update(head=day.head, branch='feature', mergeable=True)
    day.run('pr', 'claim', day.ref, '--item', 'A')
    listing(day, 'b' * 40)
    config = workspace.load_config(day.root)
    found = [row['command'] for row in derive.offers(day.data, day.root, config)['launches'] if row['item'] == 'A']
    assert found == ['wuwei dispatch next A']


def test_complete_refuses_when_the_pr_head_moved_since_run(case, monkeypatch, capsys):
    # a teammate pushed while the builder resolved the conflict: --complete pushes nothing
    from wuwei.__main__ import main
    from test_pr_actions import linked, REF
    root, host, vcs, tree = linked(case)
    host.results['pr'].data['mergeable'] = False
    vcs.results['rebase'] = Result(1, reason='conflict')
    vcs.results['fetch'] = Result(0, {'sha': 'b' * 40})
    vcs.results['head'] = Result(0, {'sha': 'a' * 40})
    vcs.results['branch'] = Result(0, {'name': 'feature'})
    monkeypatch.setattr('wuwei.commit_push.context',
                        lambda *args, **kwargs: ({'name': 'acme/widget'}, {'path': str(tree)}, vcs))
    monkeypatch.setattr('wuwei.commit_push.push_check', lambda *args: (0, ''))
    monkeypatch.setattr('wuwei.fast_checks.record', lambda path: 0)
    assert main(['pr', 'act', REF, '--run']) == 1
    capsys.readouterr()
    host.results['pr'].data['head'] = 'c' * 40  # the teammate's push
    vcs.results['head'] = Result(0, {'sha': 'd' * 40})  # the resolved rebase
    vcs.results['merge_base'] = Result(0, {'sha': 'b' * 40})
    vcs.results['push_context'] = Result(0, {'head': {'sha': 'd' * 40}})
    vcs.results['push'] = Result(0, {'pushed': True})
    assert main(['pr', 'act', REF, '--complete']) == 2
    assert 'moved' in capsys.readouterr().out
    assert not any(call[0] == 'push' for call in vcs.calls)
    assert REF not in state.read_state(root).get('pr_action_done', {})



def claimed_red_at_gate(day):
    """The field case: a claimed PR item at gate, Unit CI red at the head it holds."""
    day.plan()
    day.approve()
    day.run('plan', 'session', 'planner')
    day.build('builder-initial')
    day.host.results['pr'].data.update(head=day.head, branch='feature', mergeable=True)
    day.run('pr', 'claim', day.ref, '--item', 'A')
    red(day, day.head)
    listing(day, day.head)


def offered(day):
    config = workspace.load_config(day.root)
    return [(row['kind'], row['command']) for row in derive.offers(day.data, day.root, config)['launches']
            if row['item'] == 'A']


def test_red_at_the_base_too_leaves_the_gates_to_run(day):
    # review F1a: base_red is not the item's to fix; once pr act measured it, the gates run
    claimed_red_at_gate(day)
    base = day.host.results['pr'].data['base_sha']
    day.host.results[('checks', base)] = Result(0, [{'name': 'Unit CI', 'sha': base, 'state': 'completed',
                                                     'conclusion': 'failure', 'url': 'https://example.test/c'}])
    day.run('pr', 'act', day.ref)
    assert day.data['watch']['base_red'][day.ref] == day.head
    assert offered(day) == [('gates', 'wuwei dispatch next A')]
    assert day.data['items']['A']['phase'] == 'gate'


def test_red_while_the_build_is_at_its_checks_takes_the_build_step(day):
    # review F1b: decide's build step stands; pr act could not open a fix from it
    claimed_red_at_gate(day)
    state._write_state(lambda data: data['builds']['A'].update(status='check'), day.root)
    assert offered(day) == [('build', 'wuwei build next A')]


def test_a_late_initial_at_the_fix_head_is_not_reviewed_twice(day):
    # review F2: red before any gate ran; every gate reads the fix head once, arch included
    import shlex
    from wuwei import dispatch
    claimed_red_at_gate(day)
    [entry] = [row for row in dispatch.launch_set(day.root)['entries'] if row['item'] == 'A']
    day.steps(entry)
    action = day.next()
    assert (action['action'], action['roles']) == ('gates', ['arch', 'quality', 'security'])
    for command in action.get('commands', []):
        day.run(*shlex.split(command)[1:])
    for row in day.next()['seats']:
        day.runtime.verdict = 'PASS'
        day.execute(row)
        day.run(*shlex.split(row['receive'])[1:])
    assert day.next() == {'action': 'run', 'command': f'wuwei pr act {day.ref} --push', 'notes': []}
    assert not [key for key in day.data['gate_verdicts'] if key.endswith(':delta')]


def test_a_raised_pr_red_check_fix_is_a_seated_builder_launch(day):
    # a raised PR's red checks resolve to the builder launch, as a claimed PR's do
    from wuwei import dispatch
    day.plan()
    day.approve()
    day.run('plan', 'session', 'planner')
    day.build('builder-initial')
    for role in ('arch', 'quality', 'security'):
        day.gate(role, 'PASS')
    day.raise_pr()
    red(day, day.head)
    listing(day, day.head)
    [entry] = [row for row in dispatch.launch_set(day.root)['entries'] if row['item'] == 'A']
    assert (entry['kind'], entry['action'], entry['agent_type']) == ('fix', 'continue', 'wuwei:builder'), entry
    assert day.data['items']['A']['phase'] == 'fix'


def test_complete_with_no_run_says_how_to_start_over(case, monkeypatch, capsys):
    # review F3: a resolution begun before the run head was recorded is reset, then --run
    from wuwei.__main__ import main
    from test_pr_actions import linked, REF
    root, host, vcs, tree = linked(case)
    host.results['pr'].data['mergeable'] = False
    vcs.results['head'] = Result(0, {'sha': 'd' * 40})
    monkeypatch.setattr('wuwei.commit_push.context',
                        lambda *args, **kwargs: ({'name': 'acme/widget'}, {'path': str(tree)}, vcs))
    assert main(['pr', 'act', REF, '--complete']) == 2
    out = capsys.readouterr().out
    head = host.results['pr'].data['head']
    assert 'git rebase --abort' in out and f'git reset --keep {head}' in out and 'pr act --run' in out
    assert not any(call[0] == 'push' for call in vcs.calls)
