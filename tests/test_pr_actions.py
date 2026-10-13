"""PR actions use recorded host evidence and fake ports."""

import json

import pytest
from types import SimpleNamespace

from wuwei import pr_actions, registry, state, workspace
from wuwei.__main__ import main
from wuwei.registry import Result
from test_close_branches import case, own, REF


def linked(case):
    root, host, vcs = case
    own(root)
    tree = root / 'repo'
    tree.mkdir()
    def update(data):
        data['items']['A'] = {**state.ITEM_DEFAULTS, 'phase': 'planned',
                              'worktree': str(tree), 'pr': REF}
        data['approved_items'] = ['A']
    state._write_state(update, root)
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
        'agent_id': 'old-builder', 'action': {'action': 'done'}}), root)


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
    monkeypatch.setattr('wuwei.commit_push.context',
                        lambda *args, **kwargs: ({'name': 'acme/widget'}, {'path': str(tree)}, vcs))
    monkeypatch.setattr('wuwei.commit_push.push_check', lambda *args: (0, ''))
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


def test_red_ci_at_the_round_cap_parks_for_the_owners_resume(case, capsys):
    # #844: at the cap red checks open no round; the item parks in code and the owner decides on
    # plan resume's Owner step card, never a refusal with no owner path.
    root, host, _, tree = linked(case)
    completed_build(root, tree)
    state._write_state(lambda data: data['builds']['A'].update(fix_rounds=2), root)
    host.results['checks'] = Result(0, [{'name': 'tests', 'sha': 'a' * 40,
        'state': 'completed', 'conclusion': 'failure', 'url': 'https://example.test/check'}])
    assert main(['pr', 'act', REF]) == 1
    assert 'bin/wuwei plan resume A' in capsys.readouterr().out
    item = state.read_state(root)['items']['A']
    assert item['phase'] == 'parked' and item['disposition']['reason'].startswith('round cap 2 reached')


def test_red_ci_at_the_round_cap_after_the_owners_resume_opens_one_round(case, capsys):
    # #904: the owner's resume grants one round past the cap; opening it spends the grant.
    root, host, _, tree = linked(case)
    completed_build(root, tree)
    state._write_state(lambda data: data['builds']['A'].update(fix_rounds=2), root)
    state.append_event('plan.resumed', {'item': 'A'}, root)
    host.results['checks'] = Result(0, [{'name': 'tests', 'sha': 'a' * 40,
        'state': 'completed', 'conclusion': 'failure', 'url': 'https://example.test/check'}])
    assert main(['pr', 'act', REF]) == 1
    action = json.loads(capsys.readouterr().out)
    assert action['action'] in ('launch', 'continue') and 'tests' in action['prompt']
    assert state.read_state(root)['items']['A']['phase'] == 'fix'
    from wuwei import dispatch
    assert not dispatch._resumed(root, 'A')


def test_unanswered_thread_needs_composed_reply(case, capsys):
    root, host, _, _ = linked(case)
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
            'body': 'Please explain', 'created_at': workspace.now().isoformat()}]}]
    assert main(['pr', 'act', REF]) == 1
    action = json.loads(capsys.readouterr().out)
    assert action['action'] == 'reply' and action['question'] == 'Please explain'


def test_review_fix_request_opens_fix_round(case, capsys):
    root, host, _, tree = linked(case)
    completed_build(root, tree)
    host.results['reviews'] = Result(0, [{'id': 5, 'author': 'reviewer', 'is_bot': False,
        'state': 'changes_requested', 'sha': 'a' * 40, 'body': 'Please fix the parser',
        'submitted_at': workspace.now().isoformat()}])
    assert main(['pr', 'act', REF]) == 1  # #906: no keyword opens a round; the seat classifies
    assert json.loads(capsys.readouterr().out)['action'] == 'reply'
    assert main(['pr', 'act', REF, '--thread', '5', '--fix', 'the item promised the parser']) == 1
    action = json.loads(capsys.readouterr().out)
    assert 'Please fix the parser' in action['prompt'] and 'the item promised the parser' in action['prompt']
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
    assert main(['pr', 'act', REF, '--thread', 'T17', '--fix', 'a defect in the promised parser']) == 1
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
    from wuwei.commands import status
    assert '1 shipped' in line and status.WORDS[phase] not in line


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


SCOPE = 'This is out of scope; add a new API instead'
WHY = 'a new API is not in the approved promise'
ASKED = ['pr', 'act', REF, '--thread', 'T17', '--scope', WHY]


def scope_thread(host, body=SCOPE):
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
            'body': body, 'created_at': workspace.now().isoformat()}]}]


def test_scope_change_asks_the_owner_step_card_only_when_the_seat_says_so(case, capsys):
    # Part 14, #906: a scope change is the owner's decision, asked only on the seat's explicit --scope.
    root, host, _, _ = linked(case)
    scope_thread(host)
    assert main(['pr', 'act', REF]) == 1
    out, err = capsys.readouterr()
    assert json.loads(out)['action'] == 'reply' and 'Owner step' not in err
    assert main(ASKED) == 1
    err = capsys.readouterr().err
    assert f"Owner step: bin/wuwei pr act {REF} --thread T17 --scope '{WHY}' (" in err
    assert f'The shepherd asks a scope decision on {REF} (T17): \\"{SCOPE}\\"' in err
    assert 'The planner replies that the thread is deferred to you.' in err
    assert not list((workspace.day_dir(root) / 'decisions').glob('D-*.md'))
    assert main(ASKED) == 1  # asked again until the owner answers
    assert f'Owner step: bin/wuwei pr act {REF} --thread T17 --scope' in capsys.readouterr().err
    assert main([*ASKED[:-1], ' ']) == 2  # a classification names its reason
    assert 'need the reason against the item promise' in capsys.readouterr().out


@pytest.mark.parametrize('reply', ['No', 'Yes'])
def test_answered_scope_card_routes_by_answer(case, capsys, reply):
    from fakes import owner
    root, host, _, tree = linked(case)
    if reply == 'Yes':
        completed_build(root, tree)
    scope_thread(host)
    assert main(ASKED) == 1
    owner.answer_card(root, capsys.readouterr().err, reply=reply)
    assert main(ASKED) == 1
    action = json.loads(capsys.readouterr().out.splitlines()[-1])
    if reply == 'No':
        assert (action['action'], action['option']) == ('reply', 'defer')
    else:
        assert SCOPE in action['prompt'] and WHY in action['prompt']
        rounds = state.read_state(root)['builds']['A']['fix_rounds']
        assert main(ASKED) == 1  # F6: the Yes opened its round; a replay asks the owner again
        assert 'Owner step' in capsys.readouterr().err
        assert state.read_state(root)['builds']['A']['fix_rounds'] == rounds


def test_a_bot_p1_thread_is_answered_or_fixed_by_its_id(case, monkeypatch, capsys):
    # #906 F4: an open P1 bot thread is owed; the seat can reply to it or open a fix round for it.
    root, host, _, tree = linked(case)
    completed_build(root, tree)
    host.results['threads'].data['threads'] = [{'id': 'B1', 'resolved': False, 'outdated': False, 'comments': [{
        'id': 8, 'author': 'review-bot', 'is_bot': True, 'body': '**P1** the loop never ends',
        'created_at': workspace.now().isoformat()}]}]
    assert main(['pr', 'act', REF]) == 1
    action = json.loads(capsys.readouterr().out)
    assert (action['surface'], action['thread'], action['owed']) == ('bot-p1', 'B1', ['bot-p1:B1'])
    sent = []
    monkeypatch.setattr('wuwei.obligations.reply', lambda *args: sent.append(args) or 0)
    assert main(['pr', 'act', REF, '--thread', 'B1', '--reply', 'The loop ends at the cap.']) == 2  # D3
    assert 'use --fix' in capsys.readouterr().out and sent == []
    assert main(['pr', 'act', REF, '--thread', 'B1', '--fix', 'the item promised a bounded loop']) == 1
    assert '**P1** the loop never ends' in json.loads(capsys.readouterr().out)['prompt']
    assert state.read_state(root)['items']['A']['phase'] == 'fix'


def thread(number, body, name=None):
    return {'id': name or f'T{number}', 'resolved': False, 'outdated': False, 'comments': [{
        'id': number, 'author': 'reviewer', 'is_bot': False, 'body': body,
        'created_at': workspace.now().isoformat()}]}


@pytest.mark.parametrize('question', ['Could you explain this change?', 'Is this in scope?',
                                      'Why not a queue instead?'])
def test_an_explicit_reply_posts_whatever_words_the_question_holds(case, monkeypatch, capsys, question):
    # #906: the reply is honoured first; "change", "scope" and "instead" open no round and no card.
    root, host, _, tree = linked(case)
    completed_build(root, tree)
    host.results['threads'].data['threads'] = [thread(3, question)]
    sent = []
    monkeypatch.setattr('wuwei.obligations.reply', lambda *args: sent.append(args) or 0)
    assert main(['pr', 'act', REF]) == 1
    out, err = capsys.readouterr()
    assert json.loads(out)['action'] == 'reply' and 'Owner step' not in err
    assert main(['pr', 'act', REF, '--thread', 'T3', '--reply', 'It removes a race.']) == 0
    assert [call[:4] for call in sent] == [(REF, 'thread', 3, 'It removes a race.')]
    assert state.read_state(root)['items']['A']['phase'] == 'raised'
    assert 'Owner step' not in capsys.readouterr().err


def test_each_thread_is_answered_by_its_id_and_a_newer_comment_takes_no_reply(case, monkeypatch, capsys):
    # #906: multiple threads, and new activity while the seat composes a reply: the reply goes to the
    # thread it names, never to the comment that now sorts first.
    root, host, _, _ = linked(case)
    host.results['threads'].data['threads'] = [thread(3, 'Why a lock?'), thread(4, 'Why a retry?')]
    assert main(['pr', 'act', REF]) == 1
    action = json.loads(capsys.readouterr().out)
    assert (action['thread'], action['owed']) == ('T3', ['thread:T3', 'thread:T4'])
    host.results['threads'].data['comments'] = [{'id': 9, 'author': 'reviewer', 'is_bot': False,
                                                 'body': 'Also, any docs?', 'created_at': workspace.now().isoformat()}]
    sent = []
    monkeypatch.setattr('wuwei.obligations.reply', lambda *args: sent.append(args) or 0)
    assert main(['pr', 'act', REF, '--thread', 'T4', '--reply', 'The host drops calls.']) == 0
    assert sent[0][:4] == (REF, 'thread', 4, 'The host drops calls.')
    assert main(['pr', 'act', REF, '--thread', 'T9', '--reply', 'x']) == 2
    assert 'T9 is not owed a reply' in capsys.readouterr().out


def test_no_reply_owed_records_the_shepherd_duty_from_the_ledger(case, capsys):
    # #906: completion comes from a fresh read with nothing owed, once, stamped with the read's start.
    from wuwei import derive
    root, host, _, _ = linked(case)
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({'fetched_at': None, 'pulls': [
        {'ref': REF, 'state': 'open', 'checks': 'pending', 'activity_at': '2026-09-28T11:00:00Z'}]}))
    config = workspace.load_config(root)
    shepherd = lambda: [row for row in derive.duties(root, config) if row['duty'] == 'shepherd']
    host.results['threads'].data['threads'] = [thread(3, 'Why a lock?')]
    assert main(['pr', 'state', REF]) == 1
    assert shepherd()  # a reply is still owed
    host.results['threads'].data['threads'] = []
    assert main(['pr', 'state', REF]) == 0
    assert main(['pr', 'state', REF]) == 0
    assert shepherd() == []
    done = [row['payload'] for row in map(json.loads, (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines())
            if row['kind'] == 'duty.done']
    assert [(row['item'], row['duty'], row['as_of']) for row in done] == [('A', 'shepherd', workspace.now().isoformat())]


def explained(case):
    root, host, _, _ = linked(case)
    host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
        'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
            'body': 'Please explain', 'created_at': workspace.now().isoformat()}]}]
    return root, host


def test_reply_posts_through_obligations(case, monkeypatch):
    # #838: pr act --reply posts through obligations.reply and the code-host port; no tier, no draft.
    root, host = explained(case)
    sent = []
    monkeypatch.setattr('wuwei.obligations.reply', lambda *args: sent.append(args) or 0)
    assert main(['pr', 'act', REF]) == 1
    assert sent == []
    assert main(['pr', 'act', REF, '--reply', 'The change removes a race.']) == 0
    assert sent[0][:4] == (REF, 'thread', 3, 'The change removes a race.')


def test_reply_the_lint_refuses_exits_one(case, monkeypatch, capsys):
    root, host = explained(case)
    (root / '.wuwei/config.toml').write_text('[owner]\nname = "Pat Example"\nhandles=["builder"]\n'
                                             '[spec]\nengine = "none"\n')
    monkeypatch.setattr(host, 'comment', registry.outward_operation('code_host')(
        lambda ref, text, thread, root=None: pytest.fail('posted')))
    assert main(['pr', 'act', REF, '--reply', 'Pat asked for this race fix.']) == 1
    assert 'third-person owner reference' in capsys.readouterr().out
    assert not state.read_state(root).get('reply_acks')


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
    monkeypatch.setattr('wuwei.commit_push.context',
                        lambda *args, **kwargs: ({'name': 'acme/widget'}, {'path': str(tree)}, vcs))
    assert main(['pr', 'act', REF, '--run']) == 1
    assert 'conflict' in capsys.readouterr().out
    assert REF not in state.read_state(root).get('pr_action_done', {})


def run_started(root, host):
    """#903: --run recorded the PR head it started from; --complete is leased on it."""
    pr_actions.evaluate(root, [REF])
    state._write_state(lambda data: data['watch']['actions'][REF].update(
        run_head=host.results['pr'].data['head']), root)


def test_conflict_can_complete_after_manual_resolution(case, monkeypatch):
    root, host, vcs, tree = linked(case)
    host.results['pr'].data['mergeable'] = False
    run_started(root, host)
    vcs.results['head'] = Result(0, {'sha': 'b' * 40})
    vcs.results['branch'] = Result(0, {'name': 'feature'})
    vcs.results['push'] = Result(0, {'pushed': True})
    vcs.results['merge_base'] = Result(0, {'sha': 'b' * 40})
    vcs.results['push_context'] = Result(0, {'head': {'sha': 'b' * 40}})
    monkeypatch.setattr('wuwei.fast_checks.record', lambda path: 0)
    monkeypatch.setattr('wuwei.commit_push.context',
                        lambda *args, **kwargs: ({'name': 'acme/widget'}, {'path': str(tree)}, vcs))
    monkeypatch.setattr('wuwei.commit_push.push_check', lambda *args: (0, ''))
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
    run_started(root, host)
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
        'acme/widget': {'test': {'sha': 'b' * 40, 'exit': 0}}}), root)
    assert main(['pr', 'act', REF, '--complete']) == 0
    assert any(call[0] == 'push' for call in vcs.calls)


def test_unreadable_base_never_starts_rebase(case, monkeypatch, capsys):
    root, host, vcs, tree = linked(case)
    host.results['pr'].data['mergeable'] = False
    vcs.results['head'] = Result(0, {'sha': 'a' * 40})
    vcs.results['branch'] = Result(0, {'name': 'feature'})
    vcs.results['fetch'] = Result(2, reason='timeout')
    monkeypatch.setattr('wuwei.commit_push.context',
                        lambda *args, **kwargs: ({'name': 'acme/widget'}, {'path': str(tree)}, vcs))
    assert main(['pr', 'act', REF, '--run']) == 2
    assert 'timeout' in capsys.readouterr().out
    assert not any(call[0] == 'rebase' for call in vcs.calls)


def test_fix_round_returns_to_delta_gate(case):
    from wuwei.commands import build
    root, host, vcs, tree = linked(case)
    vcs.results['status'] = Result(0, [])  # #871 L2: the fix round left a clean tree
    completed_build(root, tree)
    action = build.open_fix('A', 'tests failed', root=root)
    assert action['action'] == 'continue'
    record = state.read_state(root)['builds']['A']
    state._write_state(lambda data: data['builds']['A'].update(status='check'),
                       root)
    from test_build_next import measured
    measured(root, 'A')
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
                       root)
    assert build.open_fix('A', 'review failure', root=root)['action'] == 'launch'
    assert state.read_state(root)['items']['A']['phase'] == 'fix'


def test_new_codex_fix_launch_uses_feedback_brief(case, monkeypatch):
    from wuwei.commands import build
    root, _, _, tree = linked(case)
    completed_build(root, tree)
    def change(data):
        data['builds']['A'].update(runtime='codex', status='ready')
        data['builds']['A'].pop('agent_id')
    state._write_state(change, root)
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
    state._write_state(change, root)
    action = build.open_fix('A', 'tests failed', root=root)
    assert action['action'] == 'continue'
    assert action['feedback'] == 'tests failed'


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
    state._write_state(update, root)
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
    assert main(['pr', 'state', REF]) == 1
    assert json.loads(capsys.readouterr().out)[0]['state'] == 'threads_unanswered'


@pytest.mark.parametrize('listing', [[], [{'path': 'HOUSE', 'branch': 'feature', 'head': 'a' * 40}]])
@pytest.mark.parametrize('change', ['ci_red', 'conflicted', 'review_fix'])
def test_fix_without_a_worktree_returns_the_adopt_command(case, capsys, listing, change):
    # #901: one re-entry command, which adopts the branch's worktree or checks the branch out
    command = 'bin/wuwei build reconcile A --repo acme/widget --branch feature'
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
    assert main(['pr', 'act', REF, *(['--thread', '5', '--fix', 'promised'] if change == 'review_fix' else [])]) == 1
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
    assert state.read_state(root)['items']['A']['phase'] == 'implement'  # #879 G1: its gates run next


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


def test_adopted_fix_round_needs_no_ticket(case, capsys):
    root, host, _, _ = adopted(case, 'fast_checks = ["python -m pytest -q"]\n', worktree=True,
                               extra='[adapters]\ntracker = "linear"\n')
    host.results['checks'] = Result(0, RED)
    assert main(['pr', 'act', REF]) == 1
    assert json.loads(capsys.readouterr().out)['action'] == 'launch'


def test_latest_finds_the_last_comment_of_a_bot_thread():
    measured = {'reviews': [], 'threads': {'comments': [], 'threads': [{'id': 'T1', 'comments': [
        {'id': 1, 'body': 'first'}, {'id': 2, 'body': '**P1** last'}]}]}}
    thread, latest = pr_actions._latest(measured, 'bot-p1', 'T1')
    assert thread['id'] == 'T1' and latest['body'] == '**P1** last'


def test_observed_merge_removes_the_item_scratch(case, monkeypatch):
    """#647: the item's scratch directory goes with the confirmed merge; others stay."""
    root, host, _, _ = linked(case)
    keys = ('escaped_defects', 'review_rework', 'owner_intervention', 'lead_time')
    monkeypatch.setattr('wuwei.metrics.collect', lambda root: {
        **dict.fromkeys(keys, 0), 'baseline': dict.fromkeys(keys, 0), 'quality_by_band': 'unmeasured'})
    for name in ('A/builder/x', 'B/builder/y'):
        (root / workspace.SCRATCH / name).parent.mkdir(parents=True)
        (root / workspace.SCRATCH / name).write_text('x')
    host.results['pr'].data.update(state='closed', merged=True)
    assert main(['pr', 'state']) == 0
    assert state.read_state(root)['items']['A']['phase'] == 'merged'
    assert not (root / workspace.SCRATCH / 'A').exists()
    assert (root / workspace.SCRATCH / 'B/builder/y').is_file()


def draft(case, flag=None):
    # #726: a linked draft PR whose ready call flips the fixture.
    root, host, _, _ = linked(case)
    host.results['pr'].data['draft'] = True
    calls = []
    def ready(ref, root=None):
        calls.append(ref)
        host.results['pr'].data['draft'] = False
        return Result(0, {'ready': True})
    host.ready = ready
    if flag is not None:
        state._write_state(lambda data: data['items']['A'].update(owner_merge={
            'value': flag, 'by': 'owner', 'at': '2026-09-28T08:00:00+00:00'}), root)
    return root, host, calls


@pytest.mark.parametrize('flag,args,readied', [
    (False, [], True), (True, [], False), (None, [], False), (True, ['--ready'], True)])
def test_act_marks_a_draft_ready(case, capsys, flag, args, readied):
    root, host, calls = draft(case, flag)
    assert main(['pr', 'act', REF, *args]) == 0
    assert calls == ([REF] if readied else [])
    if readied:
        assert json.loads(capsys.readouterr().out.splitlines()[-1]) == {'action': 'ready', 'pr': REF}


def test_act_never_readies_a_closed_draft(case):
    root, host, calls = draft(case, False)
    host.results['pr'].data['state'] = 'closed'
    main(['pr', 'act', REF, '--ready'])
    assert calls == []


def test_ready_on_a_ready_pr_never_merges(case, capsys):
    root, host, calls = draft(case)
    host.results['pr'].data['draft'] = False
    host.results['reviews'] = Result(0, [{'id': 11, 'author': 'reviewer', 'state': 'approved', 'body': '',
        'sha': 'a' * 40, 'submitted_at': '2026-09-28T11:00:00Z', 'is_bot': False}])
    assert main(['pr', 'act', REF, '--ready']) == 0
    assert capsys.readouterr().out.splitlines()[-1] == f'{REF}: already ready for review'
    assert calls == [] and not any(call[0] == 'merge' for call in host.calls)
    with pytest.raises(SystemExit) as exit:
        main(['pr', 'act', REF, '--ready', '--run'])
    assert exit.value.code == 2


@pytest.mark.parametrize('failure', ['offline', 'still_draft'])
def test_ready_that_does_not_take_fails_closed(case, capsys, failure):
    root, host, calls = draft(case)
    host.ready = (lambda ref, root=None: Result(2, None, 'offline')) if failure == 'offline' else (
        lambda ref, root=None: Result(0, {'ready': True}))
    assert main(['pr', 'act', REF, '--ready']) == 2
    assert f'{REF}: PR action unmeasured:' in capsys.readouterr().out


def test_malformed_owner_merge_never_readies(case):
    root, host, calls = draft(case)
    state._write_state(lambda data: data['items']['A'].update(owner_merge={'value': 'no'}), root)
    assert main(['pr', 'act', REF]) == 2
    assert calls == []


def test_state_rows_carry_draft(case):
    root, host, calls = draft(case)
    assert pr_actions.evaluate(root, [REF])[1][0]['draft'] is True
    host.results['pr'].data['draft'] = False
    assert pr_actions.evaluate(root, [REF])[1][0]['draft'] is False


def check(name, conclusion, status='completed', sha='a' * 40):
    return {'name': name, 'sha': sha, 'state': status, 'conclusion': conclusion}


def test_fake_checks_answer_per_commit(case):
    """#728: the fake has no checks at the base unless a test sets them."""
    root, host, _ = case
    host.results['checks'] = Result(0, [check('tests', 'failure')])
    assert host.checks(REF, 'b' * 40).data == []
    rows = [check('tests', 'failure', sha='b' * 40)]
    host.results[('checks', 'b' * 40)] = Result(0, rows)
    assert host.checks(REF, 'b' * 40).data == rows
    assert host.checks(REF, 'a' * 40).data == [check('tests', 'failure')]
    assert [c for c in host.calls if c[0] == 'checks'] == [
        ('checks', (REF, 'b' * 40), None)] * 2 + [('checks', (REF, 'a' * 40), None)]


def red_at_base(host, *rows):
    host.results[('checks', 'b' * 40)] = Result(0, [check(*row, sha='b' * 40) for row in rows])


def pr_row(capsys):
    row, = json.loads(capsys.readouterr().out)
    return row


def test_check_red_at_base_too_is_base_red(case, capsys):
    """#728: a check red at the base commit too is not the PR's; no fix round is asked."""
    root, host, _, tree = linked(case)
    completed_build(root, tree)
    host.results['checks'] = Result(0, [check('audit', 'failure')])
    red_at_base(host, ('audit', 'failure'))
    builds = state.read_state(root)['builds']['A']
    assert main(['pr', 'state', REF]) == 0
    row = pr_row(capsys)
    assert (row['state'], row['reason'], row['action'], row['deadline'], row['exit']) == (
        'base_red', f'base_red: audit fails at {"b" * 40} too', '', None, 0)
    assert REF not in state.read_state(root)['watch']['actions']
    assert main(['pr', 'act', REF]) == 0
    assert capsys.readouterr().out == ''
    data = state.read_state(root)
    assert data['items']['A']['phase'] == 'raised' and data['builds']['A'] == builds


def test_base_red_drops_the_ci_red_episode(case, capsys):
    root, host, _, _ = linked(case)
    host.results['checks'] = Result(0, [check('audit', 'failure')])
    assert main(['pr', 'state', REF]) == 1
    assert pr_row(capsys)['state'] == 'ci_red'
    assert state.read_state(root)['watch']['actions'][REF]['state'] == 'ci_red'
    red_at_base(host, ('audit', 'failure'))
    assert main(['pr', 'state', REF]) == 0
    assert pr_row(capsys)['state'] == 'base_red'
    assert REF not in state.read_state(root)['watch']['actions']


@pytest.mark.parametrize('head, base', [
    ([('audit', 'failure')], [('audit', 'success')]),
    ([('audit', 'failure')], []),
    ([('audit', 'failure')], [('audit', None, 'in_progress')]),
    ([('audit', 'failure'), ('lint', 'failure')], [('audit', 'failure'), ('lint', 'success')]),
])
def test_a_check_of_the_prs_own_stays_ci_red(case, capsys, head, base):
    root, host, _, _ = linked(case)
    host.results['checks'] = Result(0, [check(*row) for row in head])
    red_at_base(host, *base)
    assert main(['pr', 'state', REF]) == 1
    row = pr_row(capsys)
    assert (row['state'], row['action']) == ('ci_red', 'start a fix round') and 'reason' not in row


def test_a_green_pr_does_not_read_the_base(case, capsys):
    root, host, _, _ = linked(case)
    main(['pr', 'state', REF])
    assert pr_row(capsys)['state'] == 'waiting'
    assert ('checks', (REF, 'b' * 40), None) not in host.calls


@pytest.mark.parametrize('damage', ['timeout', 'other sha', 'error body', 'no base'])
def test_unreadable_base_is_unmeasured(case, capsys, damage):
    root, host, _, _ = linked(case)
    host.results['checks'] = Result(0, [check('audit', 'failure')])
    if damage == 'timeout':
        host.results[('checks', 'b' * 40)] = Result(2, None, 'timeout')
    elif damage == 'other sha':
        host.results[('checks', 'b' * 40)] = Result(0, [check('audit', 'failure', sha='c' * 40)])
    elif damage == 'error body':
        host.results[('checks', 'b' * 40)] = Result(0, {'message': 'Not Found'})
    else:
        host.results['pr'].data['base_sha'] = None
    assert main(['pr', 'state', REF]) == 2
    row = pr_row(capsys)
    assert row['exit'] == 2 and row['reason'].startswith('PR state unmeasured:')


def test_pr_act_names_the_refused_replys_bucket(case, monkeypatch, capsys):
    # #953 field case through pr act: zero headers and a full quota produce a short hold.
    import importlib
    from fakes.replay import NOW, hms, install_clock, install_replay, limits
    root, _, vcs, _ = linked(case)
    github = importlib.import_module('adapters.code_host.github')
    monkeypatch.setattr(registry, 'load', lambda kind, config: {'code_host': github, 'vcs': vcs}[kind])
    monkeypatch.setenv('WUWEI_RATE_LIMIT_WAIT', '0')
    install_clock(monkeypatch)
    pr = ['api', 'repos/acme/widget/pulls/7', '-H', 'Cache-Control: no-cache', '--include', '--hostname', 'github.com']
    head = ('HTTP/2.0 403 Forbidden\r\nX-Ratelimit-Limit: 5000\r\nX-Ratelimit-Remaining: 0\r\n'
            'X-Ratelimit-Reset: 1791809746\r\nX-Ratelimit-Resource: core\r\n\r\n{"message":"API rate limit exceeded"}')
    calls = install_replay(monkeypatch, 'gh', [
        {'argv': pr, 'exit': 1, 'stdout': head, 'stderr': 'gh: API rate limit exceeded for user ID 1. (HTTP 403)'},
        {'argv': ['api', 'rate_limit', '--hostname', 'github.com'], 'stdout': limits(5000, 5000, NOW + 3600)}])
    assert main(['pr', 'act', REF]) == 2
    out = capsys.readouterr().out
    assert f'GitHub rate limit until {hms(NOW + 60)} UTC' in out
    assert 'headers say 0 of 5000 core calls left' in out
    assert 'rate_limit shows 5000 of 5000 core calls left' in out
    assert 'token: gh keyring' in out and len(calls) == 2


@pytest.mark.parametrize('how', ['act', 'launch', 'thread'])
def test_one_pr_action_collects_one_evidence_bundle(case, how):
    # #907: evaluate reads the PR, its reviews, discussion and checks once; launch and act act on
    # that read and never collect the bundle again.
    root, host, _, tree = linked(case)
    completed_build(root, tree)
    if how == 'thread':
        host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
            'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
                'body': 'Please fix the parser', 'created_at': workspace.now().isoformat()}]}]
    else:
        host.results['checks'] = Result(0, [{'name': 'tests', 'sha': 'a' * 40,
            'state': 'completed', 'conclusion': 'failure', 'url': 'https://example.test/check'}])
    host.calls.clear()
    if how == 'launch':
        assert pr_actions.launch(root, REF)['action'] in ('launch', 'continue')
    else:
        assert main(['pr', 'act', REF, *(['--thread', 'T17', '--fix', 'promised'] if how == 'thread' else [])]) == 1
    assert state.read_state(root)['items']['A']['phase'] == 'fix'
    reads = [call[0] for call in host.calls]
    assert [reads.count(name) for name in ('pr', 'reviews', 'threads')] == [1, 1, 1], reads
