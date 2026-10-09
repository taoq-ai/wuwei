"""PR actions use recorded host evidence and fake ports."""

import json

import pytest
from types import SimpleNamespace

import pytest

from wuwei import drafts, pr_actions, registry, state, workspace
from wuwei.__main__ import main
from wuwei.registry import Result
from test_stop import case, own, REF


def linked(case):
    root, host, vcs = case
    own(root)
    tree = root / 'repo'
    tree.mkdir()
    def update(data):
        data['items']['A'] = {**state.ITEM_DEFAULTS, 'phase': 'planned',
                              'worktree': str(tree), 'pr': REF}
        data['approved_items'] = ['A']
    state._write_state(update, root, reserved=False)
    for phase in ('implement', 'gate', 'raised'):
        state.transition('A', phase, root)
    return root, host, vcs, tree


def completed_build(root, tree):
    brief = workspace.day_dir(root) / 'briefs/builder.md'
    brief.parent.mkdir(exist_ok=True)
    brief.write_text('Fix the item.\n')
    state._write_state(lambda data: data.setdefault('builds', {}).update(A={
        'brief': str(brief.relative_to(root)), 'worktree': str(tree),
        'runtime': 'claude', 'repo': 'acme/widget', 'commands': ['test'],
        'iteration': 1, 'repeats': 0, 'signature': None, 'status': 'done',
        'agent_id': 'old-builder', 'action': {'action': 'done'}}), root, reserved=False)


def test_conflict_step_and_done(case, monkeypatch, capsys):
    root, host, vcs, tree = linked(case)
    host.results['pr'].data['mergeable'] = False
    assert main(['pr', 'act', REF]) == 1
    step = json.loads(capsys.readouterr().out)
    assert step['action'] == 'rebase' and step['worktree'] == str(tree)
    assert step['item'] == 'A'
    vcs.results['rebase'] = Result(0, {'rebased': True})
    vcs.results['fetch'] = Result(0, {'sha': 'b' * 40})
    vcs.results['merge_base'] = Result(0, {'sha': 'b' * 40})
    vcs.results['push'] = Result(0, {'pushed': True})
    heads = iter(('a' * 40, 'b' * 40))
    monkeypatch.setattr(vcs, 'head', lambda *args, **kwargs: Result(0, {'sha': next(heads)}))
    vcs.results['branch'] = Result(0, {'name': 'feature'})
    monkeypatch.setattr('wuwei.fast_checks.record', lambda path: 0)
    monkeypatch.setattr('wuwei.guards.commit_push.context',
                        lambda *args, **kwargs: ({'name': 'acme/widget'}, {'path': str(tree)}, vcs))
    monkeypatch.setattr('wuwei.guards.commit_push.push_check', lambda *args: (0, ''))
    vcs.results['push_context'] = Result(0, {'head': {'sha': 'b' * 40},
        'updates': [{'source': 'b' * 40, 'destination': 'refs/heads/feature'}],
        'force': False, 'remote': 'origin'})
    assert main(['pr', 'act', REF, '--run']) == 0
    assert state.read_state(root)['pr_action_done'][REF]['head'] == 'b' * 40
    assert any(call[0] == 'rebase' for call in vcs.calls)
    assert any(call[0] == 'push' and call[1][-1] == 'a' * 40 for call in vcs.calls)
    assert pr_actions.evaluate(root, [REF])[1][0]['exit'] == 0


def test_red_ci_opens_fix_round(case, capsys):
    root, host, _, tree = linked(case)
    completed_build(root, tree)
    host.results['checks'] = Result(0, [{'name': 'tests', 'sha': 'a' * 40,
        'state': 'completed', 'conclusion': 'failure', 'url': 'https://example.test/check'}])
    assert main(['pr', 'act', REF]) == 1
    action = json.loads(capsys.readouterr().out)
    assert action['action'] in ('launch', 'continue')
    assert 'tests' in action['prompt']
    assert state.read_state(root)['items']['A']['phase'] == 'fix'


def test_unanswered_thread_needs_composed_reply(case, capsys):
    root, host, _, _ = linked(case)
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
            'body': 'Please explain', 'created_at': workspace.now().isoformat()}]}]
    assert main(['pr', 'act', REF]) == 1
    action = json.loads(capsys.readouterr().out)
    assert action['action'] == 'reply' and action['question'] == 'Please explain'
    assert not drafts.read(state.read_state(root))


def test_review_fix_request_opens_fix_round(case, capsys):
    root, host, _, tree = linked(case)
    completed_build(root, tree)
    host.results['reviews'] = Result(0, [{'id': 5, 'author': 'reviewer', 'is_bot': False,
        'state': 'changes_requested', 'sha': 'a' * 40, 'body': 'Please fix the parser',
        'submitted_at': workspace.now().isoformat()}])
    assert main(['pr', 'act', REF]) == 1
    action = json.loads(capsys.readouterr().out)
    assert 'Please fix the parser' in action['prompt']
    assert state.read_state(root)['items']['A']['phase'] == 'fix'


def test_review_question_needs_composed_reply(case, capsys):
    root, host, _, _ = linked(case)
    host.results['reviews'] = Result(0, [{'id': 5, 'author': 'reviewer', 'is_bot': False,
        'state': 'changes_requested', 'sha': 'a' * 40, 'body': 'Why is this needed?',
        'submitted_at': workspace.now().isoformat()}])
    assert main(['pr', 'act', REF]) == 1
    action = json.loads(capsys.readouterr().out)
    assert action['action'] == 'reply' and action['surface'] == 'review'


def test_thread_fix_request_opens_fix_round(case, capsys):
    root, host, _, tree = linked(case)
    completed_build(root, tree)
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
            'body': 'Please fix the parser', 'created_at': workspace.now().isoformat()}]}]
    assert main(['pr', 'act', REF]) == 1
    assert 'Please fix the parser' in json.loads(capsys.readouterr().out)['prompt']


@pytest.mark.parametrize('phase', ['raised', 'fix', 'delta'])
def test_observed_merge_moves_raised_to_merged(case, monkeypatch, capsys, phase):
    root, host, _, _ = linked(case)
    for step in ('fix', 'delta')[:('raised', 'fix', 'delta').index(phase)]:
        state.transition('A', step, root)
    keys = ('escaped_defects', 'review_rework', 'owner_intervention', 'lead_time')
    monkeypatch.setattr('wuwei.metrics.collect', lambda root: {
        **dict.fromkeys(keys, 0), 'baseline': dict.fromkeys(keys, 0), 'quality_by_band': 'unmeasured'})
    host.results['pr'].data.update(state='closed', merged=True)
    assert main(['pr', 'state']) == 0
    assert state.read_state(root)['items']['A']['phase'] == 'merged'
    lines = (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()
    event = [json.loads(line) for line in lines if json.loads(line)['kind'] == 'pr.action'][-1]
    assert event['payload']['phase_changes'] == {'A': 'merged'}
    capsys.readouterr()
    monkeypatch.chdir(root)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    assert main(['report']) == 0
    merged = capsys.readouterr().out.split('## Merged\n', 1)[1].split('\n\n', 1)[0]
    assert merged == f'- A ({REF})'
    assert main(['status', '--line']) == 0
    line = capsys.readouterr().out
    assert 'merged 1/' in line and phase not in line


@pytest.mark.parametrize('phase', ['delta', 'parked'])
def test_unmerged_or_paused_items_keep_their_phase(case, capsys, phase):
    root, host, _, _ = linked(case)
    state.transition('A', 'fix' if phase == 'delta' else phase, root)
    if phase == 'delta':
        state.transition('A', 'delta', root)
    else:
        host.results['pr'].data.update(state='closed', merged=True)
    assert main(['pr', 'state']) != 2
    assert state.read_state(root)['items']['A']['phase'] == phase


def test_scope_disagreement_creates_decision(case, capsys):
    root, host, _, _ = linked(case)
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
            'body': 'This is out of scope; add a new API instead',
            'created_at': workspace.now().isoformat()}]}]
    assert main(['pr', 'act', REF]) == 1
    action = json.loads(capsys.readouterr().out)
    assert action['action'] == 'owner_decision'
    from wuwei import decision
    assert decision.lint((root / action['decision']).read_text())[0] == 0
    assert main(['pr', 'act', REF]) == 1
    assert json.loads(capsys.readouterr().out.splitlines()[-1])['decision'] == action['decision']


def test_pr_act_decision_is_routed_and_nudges(case, monkeypatch, capsys):
    root, host, _, _ = linked(case)
    monkeypatch.chdir(root)
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
            'body': 'This is out of scope; add a new API instead',
            'created_at': workspace.now().isoformat()}]}]
    assert main(['pr', 'act', REF]) == 1
    identifier = json.loads(capsys.readouterr().out)['decision'].rsplit('/', 1)[-1].removesuffix('.md')
    assert identifier in state.read_state(root)['decision_routes']
    lines = (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()
    assert any(json.loads(line)['kind'] == 'decision.routed' for line in lines)

    def pending():
        assert main(['nudges', '--json']) == 0
        return [row for row in json.loads(capsys.readouterr().out)
                if row['source'] == 'decision.pending' and identifier in row['reason']]
    assert [(row['tier'], row['lane']) for row in pending()] == [('nudge', 'Decisions')]
    assert main(['status', '--line']) == 0
    assert 'nudges 0' not in capsys.readouterr().out
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    assert main(['decision', 'outcome', identifier, 'defer']) == 0
    capsys.readouterr()
    assert pending() == []


@pytest.mark.parametrize('option', ['defer', 'change'])
def test_answered_scope_decision_routes_by_option(case, monkeypatch, capsys, option):
    root, host, _, tree = linked(case)
    if option == 'change':
        completed_build(root, tree)
    body = 'This is out of scope; add a new API instead'
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
            'body': body, 'created_at': workspace.now().isoformat()}]}]
    assert main(['pr', 'act', REF]) == 1
    path = json.loads(capsys.readouterr().out)['decision']
    identifier = path.rsplit('/', 1)[-1].removesuffix('.md')
    assert main(['decision', 'route', identifier]) == 0
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    assert main(['decision', 'outcome', identifier, option]) == 0
    capsys.readouterr()
    assert main(['pr', 'act', REF]) == 1
    action = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert action.get('action') != 'owner_decision'
    if option == 'defer':
        assert action['action'] == 'reply'
        assert action['decision'] == path and action['option'] == 'defer'
    else:
        assert body in action['prompt']


def test_allowed_tier_sends_thread_reply(case, monkeypatch):
    root, host, _, _ = linked(case)
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
            'body': 'Please explain', 'created_at': workspace.now().isoformat()}]}]
    monkeypatch.setattr('wuwei.outward.classify', lambda *args, **kwargs: (0, 'send'))
    sent = []
    monkeypatch.setattr('wuwei.obligations.reply', lambda *args: sent.append(args) or 0)
    assert main(['pr', 'act', REF]) == 1
    assert sent == []
    assert main(['pr', 'act', REF, '--reply', 'The change removes a race.']) == 0
    assert sent[0][:3] == (REF, 'thread', 3)
    assert sent[0][3] == 'The change removes a race.'


def test_unmeasured_outward_tier_keeps_draft_and_exits_two(case, monkeypatch, capsys):
    root, host, _, _ = linked(case)
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
            'body': 'Please explain', 'created_at': workspace.now().isoformat()}]}]
    monkeypatch.setattr('wuwei.outward.classify', lambda *args, **kwargs: (2, 'draft'))
    assert main(['pr', 'act', REF, '--reply', 'The change removes a race.']) == 2
    assert [row['status'] for row in drafts.read(state.read_state(root)).values()] == ['pending']
    assert 'unmeasured' in capsys.readouterr().out



def test_blocked_reply_prints_the_row_and_creates_no_draft(case, monkeypatch, capsys):
    # #496: a reply the tier table blocks exits 1 with the row named, and no draft.
    root, host, _, _ = linked(case)
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
            'body': 'Please explain', 'created_at': workspace.now().isoformat()}]}]
    fragment = 'block by rule 3 (audience=client topic=commitment) for X: X is client'
    monkeypatch.setattr('wuwei.outward.classify',
                        lambda *args, why=None, **kwargs: why.append(fragment) or (1, 'block'))
    assert main(['pr', 'act', REF, '--reply', 'I will ship it tomorrow.']) == 1
    assert capsys.readouterr().err.strip() == f'outward: {fragment}; the owner decides: bin/wuwei outbound tiers'
    assert drafts.read(state.read_state(root)) == {}

def test_draft_is_stable_and_not_duplicated(case, capsys):
    root, host, _, _ = linked(case)
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
            'body': 'Please explain', 'created_at': workspace.now().isoformat()}]}]
    assert main(['pr', 'act', REF, '--reply', 'The change removes a race.']) == 1
    capsys.readouterr()
    assert main(['pr', 'act', REF, '--reply', 'The change removes a race.']) == 1
    assert len(drafts.read(state.read_state(root))) == 1


def test_reply_draft_reaches_owner_queue(case, capsys):
    root, host, _, _ = linked(case)
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
            'body': 'Please explain', 'created_at': workspace.now().isoformat()}]}]
    text = 'The change removes a race.'
    assert main(['pr', 'act', REF, '--reply', text]) == 1
    action = json.loads(capsys.readouterr().out)
    assert action['action'] == 'draft_reply' and action['draft'].startswith('draft-')
    assert main(['drafts']) == 0
    row, = json.loads(capsys.readouterr().out)
    assert row['id'] == action['draft'] and row['status'] == 'pending'
    assert (row['channel'], row['operation'], row['destination']) == ('code_host', 'comment', REF)
    assert row['inputs'] == {'ref': REF, 'text': text, 'thread': 3} and row['item'] == 'A'
    assert 'pr_reply_drafts' not in state.read_state(root)


@pytest.mark.parametrize('strict', [True, False])
def test_reply_draft_is_humanized(case, capsys, strict):
    root, host, _, _ = linked(case)
    if strict:
        with (root / '.wuwei/config.toml').open('a') as stream:
            stream.write('\n[outward]\nhumanize_strict = true\n')
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
            'body': 'Please explain', 'created_at': workspace.now().isoformat()}]}]
    assert main(['pr', 'act', REF, '--reply', 'We delve into the race.']) == 1
    output = capsys.readouterr()
    assert 'stock-word' in (output.out if strict else output.err)
    rows = drafts.read(state.read_state(root))
    events = [json.loads(line) for line in
              (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()]
    found = [row['payload'] for row in events if row['kind'] == 'outward.ai_tells']
    if strict:
        assert rows == {} and found == []
    else:
        assert len(rows) == 1
        assert found == [{'kind': 'pr', 'tells': ['stock-word'], 'draft': True}]


def test_repeated_act_keeps_first_unanswered_thread(case, capsys):
    root, host, _, _ = linked(case)
    host.results['threads'].data['threads'] = [
        {'id': name, 'resolved': False, 'outdated': False,
         'comments': [{'id': number, 'author': 'reviewer', 'is_bot': False,
                       'body': 'Please explain', 'created_at': workspace.now().isoformat()}]}
        for name, number in (('T17', 3), ('T18', 4))]
    assert main(['pr', 'act', REF]) == 1
    assert json.loads(capsys.readouterr().out)['thread'] == 'T17'
    assert main(['pr', 'act', REF]) == 1
    assert json.loads(capsys.readouterr().out)['thread'] == 'T17'


def test_rebase_port_failure_does_not_record_done(case, monkeypatch, capsys):
    root, host, vcs, tree = linked(case)
    host.results['pr'].data['mergeable'] = False
    vcs.results['rebase'] = Result(1, reason='conflict')
    vcs.results['fetch'] = Result(0, {'sha': 'b' * 40})
    vcs.results['head'] = Result(0, {'sha': 'a' * 40})
    vcs.results['branch'] = Result(0, {'name': 'feature'})
    monkeypatch.setattr('wuwei.guards.commit_push.context',
                        lambda *args, **kwargs: ({'name': 'acme/widget'}, {'path': str(tree)}, vcs))
    assert main(['pr', 'act', REF, '--run']) == 1
    assert 'conflict' in capsys.readouterr().out
    assert REF not in state.read_state(root).get('pr_action_done', {})


def test_conflict_can_complete_after_manual_resolution(case, monkeypatch):
    root, host, vcs, tree = linked(case)
    host.results['pr'].data['mergeable'] = False
    vcs.results['head'] = Result(0, {'sha': 'b' * 40})
    vcs.results['branch'] = Result(0, {'name': 'feature'})
    vcs.results['push'] = Result(0, {'pushed': True})
    vcs.results['merge_base'] = Result(0, {'sha': 'b' * 40})
    vcs.results['push_context'] = Result(0, {'head': {'sha': 'b' * 40}})
    monkeypatch.setattr('wuwei.fast_checks.record', lambda path: 0)
    monkeypatch.setattr('wuwei.guards.commit_push.context',
                        lambda *args, **kwargs: ({'name': 'acme/widget'}, {'path': str(tree)}, vcs))
    monkeypatch.setattr('wuwei.guards.commit_push.push_check', lambda *args: (0, ''))
    assert main(['pr', 'act', REF, '--complete']) == 0
    assert state.read_state(root)['pr_action_done'][REF]['head'] == 'b' * 40
    assert not any(call[0] == 'rebase' for call in vcs.calls)


def test_conflict_complete_push_is_checked_with_identity(case, monkeypatch):
    # No stubbed context or push_check: the real push guard checks identity and evidence.
    root, host, vcs, tree = linked(case)
    (root / '.wuwei/config.toml').write_text(
        '[owner]\nhandles=["builder"]\n[[repos]]\nname = "acme/widget"\npath = "repo"\n'
        'default_branch = "main"\nfast_checks = ["test"]\n'
        'identity = {name = "Builder", email = "builder@example.test"}\n')
    host.results['pr'].data['mergeable'] = False
    owner = {'name': 'Builder', 'email': 'builder@example.test'}
    head = {'sha': 'b' * 40, 'author': owner, 'committer': owner}
    repository = {'path': str(tree / '.git'), 'common_dir': str(tree / '.git')}
    vcs.results.update(
        repo_context=Result(0, repository),
        commit_context=Result(0, {**repository, 'author': owner, 'committer': owner}),
        head=Result(0, head), branch=Result(0, {'name': 'feature'}),
        merge_base=Result(0, {'sha': 'b' * 40}), push=Result(0, {'pushed': True}),
        push_commits=Result(0, {'commits': [head]}),
        push_context=Result(0, {'head': head, 'remote': 'origin', 'force': False,
                                'updates': [{'source': 'b' * 40, 'destination': 'refs/heads/feature'}]}))
    monkeypatch.setattr('wuwei.fast_checks.record', lambda path: 0)
    state._write_state(lambda data: data.update(fast_checks={
        'acme/widget': {'test': {'sha': 'b' * 40, 'exit': 0}}}), root, reserved=False)
    assert main(['pr', 'act', REF, '--complete']) == 0
    assert any(call[0] == 'push' for call in vcs.calls)


def test_unreadable_base_never_starts_rebase(case, monkeypatch, capsys):
    root, host, vcs, tree = linked(case)
    host.results['pr'].data['mergeable'] = False
    vcs.results['head'] = Result(0, {'sha': 'a' * 40})
    vcs.results['branch'] = Result(0, {'name': 'feature'})
    vcs.results['fetch'] = Result(2, reason='timeout')
    monkeypatch.setattr('wuwei.guards.commit_push.context',
                        lambda *args, **kwargs: ({'name': 'acme/widget'}, {'path': str(tree)}, vcs))
    assert main(['pr', 'act', REF, '--run']) == 2
    assert 'timeout' in capsys.readouterr().out
    assert not any(call[0] == 'rebase' for call in vcs.calls)


def test_fix_round_returns_to_delta_gate(case):
    from wuwei.commands import build
    root, host, _, tree = linked(case)
    completed_build(root, tree)
    action = build.open_fix('A', 'tests failed', root=root)
    assert action['action'] == 'continue'
    record = state.read_state(root)['builds']['A']
    state._write_state(lambda data: data['builds']['A'].update(status='check'),
                       root, reserved=False)
    assert build.complete_checks('A', [Result(0)], root=root) == 0
    assert state.read_state(root)['items']['A']['phase'] == 'delta'


def test_new_review_cycle_allows_another_fix_round(case):
    from wuwei.commands import build
    root, _, _, tree = linked(case)
    completed_build(root, tree)
    build.open_fix('A', 'first review', root=root)
    state.transition('A', 'delta', root)
    state.transition('A', 'raised', root)
    assert build.open_fix('A', 'second review', root=root)['action'] == 'continue'


def test_ready_claimed_build_can_become_fix_round(case):
    from wuwei.commands import build
    root, _, _, tree = linked(case)
    completed_build(root, tree)
    state._write_state(lambda data: (data['builds']['A'].update(status='ready'),
                                     data['builds']['A'].pop('agent_id')),
                       root, reserved=False)
    assert build.open_fix('A', 'review failure', root=root)['action'] == 'launch'
    assert state.read_state(root)['items']['A']['phase'] == 'fix'


def test_new_codex_fix_launch_uses_feedback_brief(case, monkeypatch):
    from wuwei.commands import build
    root, _, _, tree = linked(case)
    completed_build(root, tree)
    def change(data):
        data['builds']['A'].update(runtime='codex', status='ready')
        data['builds']['A'].pop('agent_id')
    state._write_state(change, root, reserved=False)
    def write(role, item, name, body, **kwargs):
        path = workspace.day_dir(root) / 'briefs' / (name + '.md')
        path.write_text(body)
        return str(path.relative_to(root))
    monkeypatch.setattr('wuwei.brief.write', write)
    action = build.open_fix('A', 'tests failed', root=root)
    assert action['action'] == 'launch'
    assert 'tests failed' in (root / action['brief']).read_text()


def test_existing_codex_job_gets_fix_feedback(case):
    from wuwei.commands import build
    root, _, _, tree = linked(case)
    completed_build(root, tree)
    def change(data):
        data['builds']['A'].update(runtime='codex', job={'id': 'prior'})
        data['builds']['A'].pop('agent_id')
    state._write_state(change, root, reserved=False)
    action = build.open_fix('A', 'tests failed', root=root)
    assert action['action'] == 'continue'
    assert action['feedback'] == 'tests failed'


def watched(root, **changes):
    from test_stop import own
    own(root)
    now = workspace.now()
    record = {'measured_at': now.isoformat(), 'prs': {REF: {}}, 'actions': {REF: {
        'state': 'approved', 'action': pr_actions.ACTIONS['approved'][0],
        'created_at': now.isoformat(), 'deadline': now.replace(hour=13).isoformat()}}}
    record.update(changes)
    state._write_state(lambda data: data.update(watch=record), root, reserved=False)


def test_stop_trusts_fresh_clean_watch_record(case, monkeypatch):
    root, _, _ = case
    watched(root)
    monkeypatch.setattr(pr_actions, 'evaluate', lambda *args: (_ for _ in ()).throw(AssertionError('live read')))
    assert pr_actions.check(root) == (0, '')


@pytest.mark.parametrize('change', [
    {'measured_at': None}, {'measured_at': '2026-09-28T11:55:59+00:00'},
    {'measured_at': '2026-09-28T12:00:01+00:00'}, {'prs': {}},
    {'actions': {REF: {'deadline': '2026-09-28T11:59:59+00:00'}}},
    'no_prs', 'closing',
])
def test_stop_reads_live_unless_watch_proves_clean(case, monkeypatch, change):
    root, _, _ = case
    if change == 'no_prs':
        state._write_state(lambda data: data.update(watch={'measured_at': workspace.now().isoformat(),
                                                             'prs': {}}), root, reserved=False)
    else:
        watched(root, **({} if change == 'closing' else change))
    called = []
    monkeypatch.setattr(pr_actions, 'evaluate', lambda *args: called.append(1) or (0, []))
    pr_actions.check(root, closing=change == 'closing')
    assert called == [1]


def adopted(case, fast_checks='', worktree=False, extra=''):
    """An item linked to the owned PR the way pr claim leaves it: raised, no build (#510)."""
    root, host, vcs = case
    own(root)
    with (root / '.wuwei/config.toml').open('a') as config:
        config.write(extra + '[[repos]]\nname = "acme/widget"\npath = "repo"\ndefault_branch = "main"\n'
                     + fast_checks)
    tree = root / 'repo'
    tree.mkdir()
    def update(data):
        data['items']['A'] = {**state.ITEM_DEFAULTS, 'phase': 'planned', 'pr': REF, 'goal': 'G-1',
                              **({'worktree': str(tree)} if worktree else {})}
        data['approved_items'] = ['A']
        data['gate_approved'] = True
    state._write_state(update, root, reserved=False)
    state.transition('A', 'raised', root)
    vcs.results['worktrees'] = Result(0, [])
    for name, value in (('status', []), ('head', {'sha': 'a' * 40}), ('merge_base', {'sha': 'b' * 40}),
                        ('branches', []), ('diff_stat', [])):
        vcs.results[name] = Result(0, value)
    return root, host, vcs, tree


RED = [{'name': 'tests', 'sha': 'a' * 40, 'state': 'completed', 'conclusion': 'failure',
        'url': 'https://example.test/check'}]


def test_pr_act_shepherds_without_a_worktree(case, monkeypatch, capsys):
    root, host, _, _ = adopted(case)
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
            'body': 'Please explain', 'created_at': workspace.now().isoformat()}]}]
    assert main(['pr', 'act', REF]) == 1
    assert json.loads(capsys.readouterr().out)['action'] == 'reply'
    assert main(['pr', 'act', REF, '--reply', 'It keeps the option stable.']) == 1
    assert json.loads(capsys.readouterr().out)['action'] == 'draft_reply'
    assert main(['pr', 'state', REF]) == 1
    assert json.loads(capsys.readouterr().out)[0]['state'] == 'threads_unanswered'


@pytest.mark.parametrize('listing,command', [
    ([], 'bin/wuwei worktree add A --branch feature --repo acme/widget'),
    ([{'path': 'HOUSE', 'branch': 'feature', 'head': 'a' * 40}], 'bin/wuwei worktree adopt HOUSE --item A'),
])
@pytest.mark.parametrize('change', ['ci_red', 'conflicted', 'review_fix'])
def test_fix_without_a_worktree_returns_the_adopt_command(case, capsys, listing, command, change):
    root, host, vcs, _ = adopted(case)
    vcs.results['worktrees'] = Result(0, listing)
    if change == 'ci_red':
        host.results['checks'] = Result(0, RED)
    elif change == 'conflicted':
        host.results['pr'].data['mergeable'] = False
    else:
        host.results['reviews'] = Result(0, [{'id': 5, 'author': 'reviewer', 'is_bot': False,
            'state': 'changes_requested', 'sha': 'a' * 40, 'body': 'Please fix the parser',
            'submitted_at': workspace.now().isoformat()}])
    assert main(['pr', 'act', REF]) == 1
    action = json.loads(capsys.readouterr().out)
    assert {key: action[key] for key in ('action', 'item', 'command', 'then')} == {
        'action': 'adopt', 'item': 'A', 'command': command, 'then': f'bin/wuwei pr act {REF}'}
    assert 'checkout' in action['why']


def test_adopted_fix_round_writes_the_builder_brief(case, capsys):
    root, host, _, tree = adopted(case, 'fast_checks = ["python -m pytest -q"]\n', worktree=True)
    host.results['checks'] = Result(0, RED)
    assert main(['pr', 'act', REF]) == 1
    action = json.loads(capsys.readouterr().out)
    assert action['action'] == 'launch' and action['worktree'] == str(tree)
    events = [json.loads(line) for line in (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()]
    brief = next(e['payload'] for e in events if e['kind'] == 'brief written')
    assert brief['name'] == 'A-adopted-fix' and brief['worktree'] == str(tree)
    assert 'tests: failure' in (root / brief['path']).read_text()
    assert state.read_state(root)['items']['A']['phase'] == 'raised'


def test_adopted_fix_round_without_fast_checks_names_them(case, capsys):
    root, host, _, _ = adopted(case, worktree=True)
    host.results['checks'] = Result(0, RED)
    # #600: no fast checks is a state, not a wall: the fix round launches and its brief names it
    assert main(['pr', 'act', REF]) == 1
    assert json.loads(capsys.readouterr().out)['action'] == 'launch'
    brief = (workspace.day_dir(root) / 'briefs/A-adopted-fix.md').read_text()
    assert 'Fast checks: none configured' in brief and 'checks: none configured" in the PR body' in brief
    with (root / '.wuwei/config.toml').open('a') as config:
        config.write('fast_checks = ["python -m pytest -q"]\n')
    assert main(['pr', 'act', REF]) == 1
    assert json.loads(capsys.readouterr().out)['action'] == 'launch'


def test_adopted_fix_round_needs_the_ticket(case, capsys):
    root, host, _, _ = adopted(case, 'fast_checks = ["python -m pytest -q"]\n', worktree=True,
                               extra='[adapters]\ntracker = "linear"\n')
    host.results['checks'] = Result(0, RED)
    assert main(['pr', 'act', REF]) == 1
    assert 'ticket' in capsys.readouterr().out


def test_latest_finds_the_last_comment_of_a_bot_thread():
    measured = {'reviews': [], 'threads': {'comments': [], 'threads': [{'id': 'T1', 'comments': [
        {'id': 1, 'body': 'first'}, {'id': 2, 'body': '**P1** last'}]}]}}
    thread, latest = pr_actions._latest(measured, 'bot-p1', 'T1')
    assert thread['id'] == 'T1' and latest['body'] == '**P1** last'
