"""Day-close refusals through in-process ports and the real hook dispatcher."""

import importlib
import io
import json
from datetime import timedelta
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from fakes.code_host import Fake as Host
from fakes.vcs import Fake as VCS
from wuwei import obligations, registry, state, watch, workspace
from wuwei.__main__ import main
from wuwei.registry import Result

REF = 'acme/widget#7'
DAY = '2026-09-28'
CHARTER = '.wuwei/charters/builder.md'
CHANGELOG = '.wuwei/memory/CHANGELOG.md'


def module(name):
    assert (Path(__file__).resolve().parents[1] / 'cli/wuwei' / (name + '.py')).exists(), name + ' missing'
    return importlib.import_module('wuwei.' + name.replace('/', '.'))


@pytest.fixture
def case(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/.git').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[owner]\nhandles=["builder"]\n[spec]\nengine = "none"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', DAY + 'T12:00:00+00:00')
    state.write_state(lambda data: None, tmp_path)
    directory = workspace.day_dir(tmp_path)
    (directory / 'retro').mkdir()
    (directory / 'decisions').mkdir()
    (directory / 'retro' / (DAY + '.md')).write_text('## Applied\nnone\n## Proposed\nnone\n')
    from wuwei.guards.verdict import check_retro
    assert check_retro({'cwd': str(tmp_path), 'agent_id': 'planner-note', 'agent_type': 'planner',
                        'last_assistant_message': 'Blocked: none\nGap: none\nChange: none\n'})[0] == 0
    host, vcs = Host(), VCS()
    host.results['pr'].data['merged'] = False
    host.results['reviews'] = Result(0, [])
    host.results['threads'] = Result(0, {'comments': [], 'threads': []})
    host.results['checks'] = Result(0, [])
    vcs.results['changes_on'] = Result(0, ['charters/builder.md', 'memory/CHANGELOG.md'])
    (tmp_path / CHANGELOG).parent.mkdir(parents=True)
    (tmp_path / CHANGELOG).write_text('- (2026-09-01) Keep tests.\n')
    # HEAD contains the committed charter and changelog.
    vcs.results['read_tree'] = Result(0, {'charters/builder.md': '- (2026-09-01) Keep tests.\n',
        'memory/CHANGELOG.md': '- ' + DAY + ' builder changed\n- (2026-09-01) Keep tests.\n'})
    vcs.results['workspace_changes'] = Result(0, [])
    runtime = SimpleNamespace(dispatch=lambda *args, **kwargs: Result(0, {'agent_type': 'wuwei:steward'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config: {'code_host': host, 'vcs': vcs,
                                                               'runtime': runtime}[kind])
    return tmp_path, host, vcs


def capture(root, role='sentinel-arch', agent='sentinel-note'):
    from wuwei.guards.verdict import check_retro
    return check_retro({'cwd': str(root), 'agent_id': agent, 'agent_type': role,
                        'last_assistant_message': 'Blocked: none\nGap: none\nChange: none\n'})


def test_source_p7_shortfall_then_parity(case):
    root, _, _ = case
    (workspace.day_dir(root) / 'decisions/gate-a.md').write_text('Change: improve tests\n')
    closing = module('closing')
    code, reason = closing.retro(root)
    assert code == 1 and '1 verdict' in reason and '0 sentinel' in reason
    assert capture(root)[0] == 0
    assert closing.retro(root)[0] == 0


@pytest.mark.parametrize('change,expected,fragment', [
    ('clean', 0, ''), ('missing', 1, 'does not exist'),
    ('applied', 1, 'Applied'), ('proposed', 1, 'Proposed'),
    ('no_notes', 1, 'empty'), ('bad_notes', 2, 'unmeasured'),
    ('uncommitted', 1, 'no commit'), ('no_changelog', 1, 'dated'),
    ('uncommitted_changelog', 1, 'changelog'), ('landed', 0, ''),
    ('none_bypass', 1, 'no commit'), ('read_error', 2, 'unmeasured'),
    ('malformed_paths', 2, 'unmeasured'), ('empty_applied', 1, 'Applied'),
])
def test_retro_table(case, change, expected, fragment):
    root, _, vcs = case
    directory = workspace.day_dir(root)
    path = directory / 'retro' / (DAY + '.md')
    if change == 'missing':
        path.unlink()
    elif change in ('applied', 'proposed'):
        path.write_text(path.read_text().replace('## ' + change.title(), '## Absent'))
    elif change == 'empty_applied':
        path.write_text('## Applied\n\n## Proposed\nnone\n')
    elif change in ('no_notes', 'bad_notes'):
        event_path = directory / 'events.jsonl'
        event_path.chmod(0o644)
        event_path.write_text('' if change == 'no_notes' else '{broken\n')
    elif change != 'clean':
        path.write_text('## Applied\n' + ('none\n' if change == 'none_bypass' else '') +
                        '- `' + CHARTER + '`\n## Proposed\nnone\n')
        if change in ('uncommitted', 'none_bypass'):
            vcs.results['changes_on'] = Result(0, [])
        elif change == 'no_changelog':
            vcs.results['read_tree'].data['memory/CHANGELOG.md'] = '- 2026-09-27 prior change\n'
        elif change == 'uncommitted_changelog':
            vcs.results['changes_on'] = Result(0, ['charters/builder.md'])
        elif change == 'read_error':
            vcs.results['changes_on'] = Result(2, None, 'timeout')
        elif change == 'malformed_paths':
            vcs.results['changes_on'] = Result(0, {'error': 'no history'})
    code, reason = module('closing').retro(root)
    assert code == expected, reason
    assert fragment in reason


def test_duplicate_capture_cannot_hide_shortfall(case):
    root, _, _ = case
    for name in ('a', 'b'):
        (workspace.day_dir(root) / 'decisions' / ('gate-' + name + '.md')).write_text('**Change:** x\n')
    capture(root)
    capture(root)
    assert module('closing').retro(root)[0] == 1


def test_pending_charter_proposal_blocks_retro(case):
    root, _, _ = case
    directory = workspace.day_dir(root)
    (directory / 'proposals').mkdir()
    (directory / 'proposals/one.json').write_text(json.dumps({
        'target': CHARTER, 'action': 'add', 'text': '- Check tests.',
        'reason': 'gap', 'evidence': '.wuwei/days/' + DAY + '/retro/note.json'}))
    code, reason = module('closing').retro(root)
    assert code == 1 and 'promote' in reason


def test_landed_charter_omitted_from_retro_blocks(case):
    root, _, _ = case
    directory = workspace.day_dir(root)
    (directory / 'proposals').mkdir()
    (directory / 'proposals/one.landed').write_text(json.dumps({'target': CHARTER}))
    code, reason = module('closing').retro(root)
    assert code == 1 and 'Applied' in reason


def test_rejected_charter_proposal_without_landing_blocks(case):
    root, _, _ = case
    directory = workspace.day_dir(root)
    (directory / 'proposals').mkdir()
    (directory / 'proposals/one.rejected').write_text(json.dumps({'target': CHARTER}))
    code, reason = module('closing').retro(root)
    assert code == 1 and 'rejected' in reason


def test_close_without_amendments_needs_no_git_repository(case, monkeypatch):
    root, host, _ = case
    vcs = importlib.import_module('adapters.vcs.git')
    runtime = SimpleNamespace(dispatch=lambda *args, **kwargs: Result(0, {'agent_type': 'wuwei:steward'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config: {'code_host': host, 'vcs': vcs,
                                                               'runtime': runtime}[kind])
    monkeypatch.chdir(root)
    assert not (root / '.git').exists()
    assert main(['close']) == 0


def own(root):
    state._write_state(lambda data: data.update(raised_prs=[REF]), root, reserved=False)
    state._write_state(lambda data: data.update(planner_session_id='planner'), root, reserved=False)


def advance(monkeypatch, seconds):
    monkeypatch.setenv('WUWEI_NOW', (workspace.now() + timedelta(seconds=seconds)).isoformat())


def action(case):
    root, host, _ = case
    host.results['pr'].data['mergeable'] = False
    from wuwei import pr_actions
    assert pr_actions.evaluate(root)[0] == 1


def disposition(case, kind='parked', text=None):
    from test_decision import VALID
    root, host, _ = case
    if text is None:
        text = VALID.replace('Reversibility: two-way', 'Reversibility: one-way').replace(
            'Decided-by: seat', 'Decided-by: owner')
    (workspace.day_dir(root) / 'decisions/D-1.md').write_text(text)
    host.results['threads'].data['comments'] = [{
        'id': 10, 'author': 'builder', 'is_bot': False,
        'body': f'WUWEI {kind} {REF} D-1 {DAY} ' + obligations._fingerprint(text), 'created_at': DAY + 'T12:00:00Z'}]
    return module('pr_actions').record_disposition(root, REF, kind, 'D-1', 10)


@pytest.mark.parametrize('change', ['seat_route', 'seat_decider', 'seat_outcome'])
def test_disposition_requires_owner_routed_decision(case, change):
    from test_decision import VALID
    root, _, _ = case
    own(root)
    text = VALID.replace('Reversibility: two-way', 'Reversibility: one-way').replace(
        'Decided-by: seat', 'Decided-by: owner')
    if change == 'seat_route':
        text = text.replace('Reversibility: one-way', 'Reversibility: two-way')
    elif change == 'seat_decider':
        text = text.replace('Decided-by: owner', 'Decided-by: seat')
    else:
        state._write_state(lambda data: data.update(decision_outcomes={'D-1': {}}),
                           root, reserved=False)
    with pytest.raises(ValueError, match='owner-routed'):
        disposition(case, text=text)
    assert not state.read_state(root).get('pr_dispositions')


def test_disposition_accepts_owner_answered_decision(case, monkeypatch):
    from test_decision import VALID
    root, host, _ = case
    own(root)
    monkeypatch.chdir(root)
    path = workspace.day_dir(root) / 'decisions/D-1.md'
    path.write_text(VALID.replace('Reversibility: two-way', 'Reversibility: one-way').replace(
        'Decided-by: seat', 'Decided-by: owner'))
    assert main(['decision', 'route', 'D-1']) == 0
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    assert main(['decision', 'outcome', 'D-1', 'B']) == 0
    host.results['threads'].data['comments'] = [{
        'id': 10, 'author': 'builder', 'is_bot': False,
        'body': f'WUWEI parked {REF} D-1 {DAY} ' + obligations._fingerprint(path.read_text()),
        'created_at': DAY + 'T12:00:00Z'}]
    assert module('pr_actions').record_disposition(root, REF, 'parked', 'D-1', 10) == 0
    assert state.read_state(root)['pr_dispositions'][REF]['decision'] == 'D-1'


@pytest.mark.parametrize('kind', ['parked', 'carried'])
@pytest.mark.parametrize('tool', ['comment', 'api', 'Write', 'Edit'])
def test_native_tools_cannot_produce_disposition_markers(case, monkeypatch, capsys, kind, tool):
    root, _, _ = case
    marker = f'WUWEI {kind} {REF} D-1 {DAY} ' + 'a' * 64
    if tool in ('comment', 'api'):
        command = (f"gh pr comment 7 -R acme/widget --body '{marker}'" if tool == 'comment'
                   else f"gh api repos/acme/widget/issues/7/comments -f body='{marker}'")
        name, inputs = 'Bash', {'command': command}
    else:
        name, inputs = tool, {'file_path': str(root / 'body.txt'),
                              'content' if tool == 'Write' else 'new_string': marker}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps({**payload(root),
        'hook_event_name': 'PreToolUse', 'tool_name': name, 'tool_input': inputs})))
    assert main(['hook', 'PreToolUse']) == 2
    refusal = json.loads(capsys.readouterr().out)['hookSpecificOutput']
    assert refusal['permissionDecision'] == 'deny'
    assert 'owner disposition' in refusal['permissionDecisionReason']


@pytest.mark.parametrize('seconds,expected', [(1799, 0), (1800, 0), (1801, 1)])
def test_explicit_action_deadline(case, monkeypatch, seconds, expected):
    root, _, _ = case
    own(root)
    action(case)
    assert watch.poll(root) == 0
    saved = state.read_state(root)['watch']
    assert 'actions' in saved, 'watch action producer missing'
    deadline = saved['actions'][REF]['deadline']
    advance(monkeypatch, seconds)
    watch.poll(root)
    assert state.read_state(root)['watch']['actions'][REF]['deadline'] == deadline
    code, reason = module('pr_actions').check(root)
    assert code == expected, reason
    if expected:
        assert REF in reason and 'conflicted' in reason and 'rebase' in reason


@pytest.mark.parametrize('poll', [False, True])
def test_waiting_pr_without_action_does_not_block_turn_end(case, monkeypatch, poll):
    root, _, _ = case
    own(root)
    if poll:
        assert watch.poll(root) == 0
    advance(monkeypatch, 1801)
    stop = module('guards/stop')
    assert stop.check(payload(root)) == (0, '')
    assert stop.check(payload(root, stop_hook_active=True)) == (0, '')
    assert module('pr_actions').check(root, closing=True)[0] == 1
    assert not watch.saved(root).get('actions')


@pytest.mark.parametrize('flag', [True, 'unused'])
def test_only_recorded_close_request_triggers_day_close(case, flag):
    root, _, _ = case
    own(root)
    watch.poll(root)
    assert module('guards/stop').check(payload(root, day_close=flag)) == (0, '')
    state._write_state(lambda data: data.update(close_requested=True), root, reserved=False)
    assert module('guards/stop').check(payload(root, day_close=False))[0] == 1


def test_watch_never_inherits_yesterdays_actions(case, monkeypatch):
    root, _, _ = case
    own(root)
    action(case)
    assert watch.poll(root) == 0
    prior = watch.saved(root)['actions'][REF]['deadline']
    advance(monkeypatch, 86400)
    own(root)
    assert watch.poll(root) == 0
    assert watch.saved(root)['actions'][REF]['deadline'] > prior
    assert module('guards/stop').check(payload(root)) == (0, '')


@pytest.mark.parametrize('change,expected', [
    ('open', 1), ('closed', 1), ('merged', 0), ('parked', 0), ('carried', 0),
    ('missing_action', 1), ('failed_read', 2), ('malformed_action', 2),
])
def test_pr_close_table(case, change, expected):
    root, host, _ = case
    own(root)
    watch.poll(root)
    if change in ('closed', 'merged'):
        host.results['pr'].data.update(state='closed', merged=change == 'merged')
    elif change in ('parked', 'carried'):
        assert disposition(case, change) == 0
    elif change == 'missing_action':
        state._write_state(lambda data: data['watch'].pop('actions', None), root, reserved=False)
    elif change == 'malformed_action':
        state._write_state(lambda data: data['watch'].update(actions=[]), root, reserved=False)
    elif change == 'failed_read':
        host.results['pr'] = Result(2, None, 'timeout')
    code, reason = module('pr_actions').check(root, closing=True)
    assert code == expected, reason


@pytest.mark.parametrize('change', ['author', 'bot', 'body', 'decision', 'day', 'removed'])
def test_local_disposition_never_proves_owner_action(case, change):
    root, host, _ = case
    own(root)
    watch.poll(root)
    assert disposition(case) == 0
    comment = host.results['threads'].data['comments'][0]
    if change == 'author':
        comment['author'] = 'seat'
    elif change == 'bot':
        comment['is_bot'] = True
    elif change == 'body':
        comment['body'] = 'I did not park it'
    elif change == 'day':
        comment['body'] = comment['body'].replace(DAY, '2026-09-27')
    elif change == 'decision':
        (workspace.day_dir(root) / 'decisions/D-1.md').write_text('Decided-by: owner\n')
    else:
        host.results['threads'].data['comments'] = []
    code, reason = module('pr_actions').check(root, closing=True)
    assert code == 2, reason


def test_carried_does_not_waive_overdue_action(case, monkeypatch):
    root, _, _ = case
    own(root)
    action(case)
    watch.poll(root)
    assert disposition(case, 'carried') == 0
    advance(monkeypatch, 1801)
    assert module('pr_actions').check(root)[0] == 1


def test_failed_poll_does_not_reset_deadline(case, monkeypatch):
    root, host, _ = case
    own(root)
    action(case)
    watch.poll(root)
    assert 'actions' in state.read_state(root)['watch'], 'watch action producer missing'
    before = state.read_state(root)['watch']['actions']
    advance(monkeypatch, 1801)
    host.results['pr'] = Result(2, None, 'unavailable')
    assert watch.poll(root) == 2
    assert state.read_state(root)['watch']['actions'] == before


def payload(root, **extra):
    return {'cwd': str(root), 'session_id': 'planner', 'transcript_path': 'unused',
            'hook_event_name': 'Stop', 'stop_hook_active': False, **extra}


@pytest.mark.parametrize('change,expected', [
    ('clean', 0), ('owed_thread', 1), ('visibility', 1), ('retro', 1),
    ('error', 2), ('active_retry', 0), ('unknown_session', 0), ('no_planner', 0),
    ('malformed_state', 2), ('bad_retry', 2),
])
def test_stop_table(case, monkeypatch, change, expected):
    root, host, _ = case
    own(root)
    watch.poll(root)
    hook_payload = payload(root)
    if change == 'clean':
        host.results['pr'].data.update(state='closed', merged=True)
    elif change in ('owed_thread', 'visibility', 'retro', 'error'):
        state._write_state(lambda data: data.update(close_requested=True), root, reserved=False)
        if change == 'owed_thread':
            host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
                'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
                    'body': 'Please fix', 'created_at': DAY + 'T10:00:00Z'}]}]
        elif change == 'retro':
            host.results['pr'].data.update(state='closed', merged=True)
            (workspace.day_dir(root) / 'retro' / (DAY + '.md')).unlink()
        elif change == 'error':
            host.results['pr'] = Result(2, None, 'timeout')
    elif change == 'active_retry':
        action(case)
        advance(monkeypatch, 1801)
        hook_payload['stop_hook_active'] = True
    elif change == 'unknown_session':
        hook_payload['session_id'] = 'other'
        advance(monkeypatch, 1801)
    elif change == 'no_planner':
        state._write_state(lambda data: data.pop('planner_session_id'), root, reserved=False)
    elif change == 'malformed_state':
        path = workspace.day_dir(root) / 'state.json'
        path.chmod(0o644)
        path.write_text('{bad')
    elif change == 'bad_retry':
        hook_payload['stop_hook_active'] = 'true'
    code, reason = module('guards/stop').check(hook_payload)
    assert code == expected, reason
    if change == 'owed_thread':
        assert REF in reason and 'T17' in reason


@pytest.mark.parametrize('location', ['outside', 'repo', 'worktree', 'target'])
def test_stop_scope(case, tmp_path, monkeypatch, location):
    root, _, _ = case
    own(root)
    action(case)
    watch.poll(root)
    advance(monkeypatch, 1801)
    other = root.parent / ('outside-' + root.name)
    other.mkdir()
    p = payload(other)
    if location == 'repo':
        config = root / '.wuwei/config.toml'
        config.write_text(config.read_text() + '\n[[repos]]\nname="acme/widget"\npath="' +
                          str(other) + '"\ndefault_branch="main"\n')
    elif location == 'worktree':
        # Use the native WUWEI anchor consumed by the existing scope helper.
        gitdir = other / '.git'
        gitdir.mkdir()
        (gitdir / 'wuwei-workspace').write_text(str(root) + '\n')
    elif location == 'target':
        p['tool_input'] = {'path': str(root)}
    code, reason = module('guards/stop').check(p)
    assert code == (0 if location == 'outside' else 1), reason


def test_close_command_and_hook_retry(case, monkeypatch, capsys):
    root, host, _ = case
    own(root)
    watch.poll(root)
    monkeypatch.chdir(root)
    assert module('commands/close')
    assert main(['close']) == 1
    assert state.read_state(root)['close_requested'] is True
    capsys.readouterr()
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload(root, stop_hook_active=False))))
    assert main(['hook', 'Stop']) == 2
    block = json.loads(capsys.readouterr().out)
    assert block['decision'] == 'block' and REF in block['reason']
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload(root, stop_hook_active=True))))
    assert main(['hook', 'Stop']) == 0
    assert capsys.readouterr().out == ''
    host.results['pr'].data.update(state='closed', merged=True)
    assert main(['close']) == 0


def test_close_outside_workspace(case, monkeypatch):
    root, _, _ = case
    monkeypatch.chdir(root.parent)
    assert module('commands/close')
    assert main(['close']) == 0
    assert 'close_requested' not in state.read_state(root)


@pytest.mark.parametrize('key', ['close_requested', 'pr_dispositions', 'watch.actions'])
def test_guard_state_only_dedicated_writer(case, key):
    assert main(['state', 'set', key, '{}']) == 1


@pytest.mark.parametrize('kind', ['day.close_requested', 'pr.disposition'])
def test_guard_events_only_dedicated_writer(case, kind):
    assert main(['event', kind]) == 1


def test_disable_stop_guard_mutation(case, monkeypatch, capsys):
    from wuwei.commands import hook
    root, _, _ = case
    own(root)
    action(case)
    watch.poll(root)
    advance(monkeypatch, 1801)
    def refusal():
        monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload(root))))
        assert main(['hook', 'Stop']) == 2
        assert REF in json.loads(capsys.readouterr().out)['reason']
    refusal()
    discover = hook.discover
    monkeypatch.setattr(hook, 'discover', lambda: [g for g in discover()
                         if g.check.__module__ != 'wuwei.guards.stop'])
    with pytest.raises(AssertionError):
        refusal()


def test_close_does_not_manufacture_empty_ownership(case, monkeypatch):
    root, _, _ = case
    monkeypatch.chdir(root)
    (workspace.day_dir(root) / 'state.json').unlink()
    assert main(['close']) == 0  # #362: a state answer, and still nothing written
    assert not (workspace.day_dir(root) / 'state.json').exists()


def test_disposition_comment_cannot_be_rebound_to_changed_decision(case):
    root, _, _ = case
    own(root)
    watch.poll(root)
    assert disposition(case) == 0
    path = workspace.day_dir(root) / 'decisions/D-1.md'
    path.write_text(path.read_text().replace('Regression returns.', 'An entirely different risk.'))
    with pytest.raises(ValueError, match='owner-authored'):
        module('pr_actions').record_disposition(root, REF, 'parked', 'D-1', 10)


@pytest.mark.parametrize('kind', ['parked', 'carried'])
@pytest.mark.parametrize('profile', ['strict', 'standard'])
def test_agents_cannot_send_owner_disposition_markers(case, kind, profile):
    from wuwei import outward
    root, _, _ = case
    config = workspace.load_config(root)
    config['profile'] = profile
    config['outbound']['code_host_orgs'] = ['acme']
    code, reason = outward.check_call({'ref': REF, 'text':
        f'WUWEI {kind} {REF} D-1 {DAY} ' + 'a' * 64}, root, config, {'code_host'})
    assert code in (1, 2) and 'draft' in reason


def test_planner_handoff_does_not_exempt_original_session(case, monkeypatch):
    root, _, _ = case
    own(root)
    action(case)
    watch.poll(root)
    assert main(['plan', 'session', 'planner']) == 0
    assert main(['plan', 'session', 'replacement', '--take-over']) == 0
    advance(monkeypatch, 1801)
    stop = module('guards/stop')
    assert stop.check(payload(root))[0] == 1
    assert stop.check(payload(root, session_id='replacement'))[0] == 1


def test_missing_state_cannot_erase_recorded_planner(case):
    root, _, _ = case
    own(root)
    assert main(['plan', 'session', 'planner']) == 0
    (workspace.day_dir(root) / 'state.json').unlink()
    code, reason = module('guards/stop').check(payload(root))
    assert code == 2 and 'state missing' in reason


def test_poll_does_not_read_prior_day_when_snapshot_already_saved(case):
    root, _, _ = case
    own(root)
    assert watch.poll(root) == 0
    previous = root / '.wuwei/days/2026-09-27'
    previous.mkdir()
    (previous / 'state.json').write_text('{broken')
    assert watch.poll(root) == 0


@pytest.mark.parametrize('command', ['python3 -m pytest -q', 'for x in a; do echo "$x"; done', 'export X=1'])
def test_stop_registration_does_not_parse_bash(case, command, monkeypatch):
    from wuwei.guards.stop import GUARDS
    assert all(guard.event == 'Stop' and guard.matcher is None for guard in GUARDS)
    from wuwei.commands import hook
    root, _, _ = case
    # Only the new registration is under test; existing unrelated guards have their own tables.
    monkeypatch.setattr(hook, 'discover', lambda: GUARDS)
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps({**payload(root),
        'hook_event_name': 'PreToolUse', 'tool_name': 'Bash',
        'tool_input': {'command': command}, 'tool_use_id': 'call'})))
    assert main(['hook', 'PreToolUse']) == 0


def approved(root, **item):
    state._write_state(lambda data: data.update(items={'A': item}, approved_items=['A']),
                       root, reserved=False)


def seat_disposition(root, monkeypatch, outcome='parked A', recorded=True):
    from test_decision import VALID
    path = workspace.day_dir(root) / 'decisions/D-1.md'
    path.write_text(VALID.replace('Outcome: pending', 'Outcome: ' + outcome))
    monkeypatch.chdir(root)
    if recorded:
        assert main(['decision', 'route', 'D-1']) == 0
    return path


@pytest.mark.parametrize('mode,expected', [
    ('open', 1), ('blocked', 1), ('phase_only', 1), ('done_only', 1),
    ('merged', 1), ('parked', 0), ('carried', 0), ('unrecorded', 1),
    ('other_item', 1), ('invalid_decision', 2), ('missing_decision', 2),
])
def test_close_approved_item_table(case, monkeypatch, capsys, mode, expected):
    root, _, _ = case
    approved(root)
    if mode in ('blocked', 'phase_only', 'done_only', 'merged'):
        data = state.read_state(root)
        data['items']['A'].update(
            status='done' if mode == 'done_only' else 'blocked',
            phase={'phase_only': 'parked', 'merged': 'merged'}.get(mode, 'planned'))
        if mode == 'phase_only':
            data['items']['A']['resume_phase'] = 'planned'
        workspace.atomic_write(workspace.day_dir(root) / 'state.json', json.dumps(data))
    elif mode not in ('open',):
        path = seat_disposition(root, monkeypatch,
            outcome='carried A' if mode == 'carried' else 'parked B' if mode == 'other_item' else 'parked A',
            recorded=mode != 'unrecorded')
        if mode == 'invalid_decision':
            path.write_text('Outcome: parked A\n')
        elif mode == 'missing_decision':
            path.unlink()
    monkeypatch.chdir(root)
    assert main(['close']) == expected
    if expected:
        assert 'A' in capsys.readouterr().out


@pytest.mark.parametrize('retry', [False, True])
@pytest.mark.parametrize('mode,expected', [
    ('pending', 1), ('forged_outcome', 1), ('forged_route', 1),
    ('malformed', 2), ('symlink', 2), ('missing', 2), ('seat', 0),
    ('answered', 0), ('legacy_answered', 0), ('seat_ledger', 1),
])
def test_close_owner_decision_table(case, monkeypatch, retry, mode, expected):
    from test_decision import VALID
    root, _, _ = case
    monkeypatch.chdir(root)
    path = workspace.day_dir(root) / 'decisions/D-1.md'
    owner_text = VALID.replace('Reversibility: two-way', 'Reversibility: one-way').replace(
        'Decided-by: seat', 'Decided-by: owner')
    path.write_text(VALID if mode == 'seat' else owner_text)
    assert main(['decision', 'route', 'D-1']) == 0
    if mode == 'forged_outcome':
        path.write_text(owner_text.replace('Outcome: pending', 'Outcome: approved'))
    elif mode == 'forged_route':
        path.write_text(VALID.replace('Outcome: pending', 'Outcome: approved'))
    elif mode == 'malformed':
        path.write_text('bad')
    elif mode in ('symlink', 'missing'):
        path.unlink()
        if mode == 'symlink':
            target = root / 'decision.md'
            target.write_text(owner_text)
            path.symlink_to(target)
    elif mode == 'answered':
        monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
        assert main(['decision', 'outcome', 'D-1', 'A']) == 0
    elif mode in ('legacy_answered', 'seat_ledger'):
        record = {'option': 'A', 'decided_by': 'owner' if mode == 'legacy_answered' else 'seat'}
        state._write_state(lambda data: data.setdefault('decision_outcomes', {}).update({'D-1': record}),
                           root, reserved=False)
    state._write_state(lambda data: data.update(close_requested=True,
                       planner_session_id='planner'), root, reserved=False)
    code, reason = module('guards/stop').check(payload(root, stop_hook_active=retry))
    assert code == (0 if retry else expected), reason
    if code:
        assert 'D-1' in reason
    if mode == 'answered':
        from wuwei import report
        assert '- D-1: A' in report.build(root)
        assert 'D-1' not in reason
        assert 'D-1' not in module('closing').unresolved(root, [])[1]


@pytest.mark.parametrize('mode,expected', [
    ('unpushed', 0), ('pushed', 1), ('unlinked', 1), ('raised', 0), ('claimed', 0),
    ('read_error', 2), ('error_body', 2), ('branch_error', 2),
])
def test_close_pushed_branch_table(case, monkeypatch, mode, expected):
    root, host, vcs = case
    approved(root, worktree='repo')
    seat_disposition(root, monkeypatch)
    vcs.results['branch'] = Result(0, {'name': 'feature-A'})
    vcs.results['pushed_branches'] = Result(0, [] if mode == 'unpushed' else ['feature-A'])
    if mode in ('raised', 'claimed'):
        state._write_state(lambda data: (data['items']['A'].update(pr=REF),
            data[mode + '_prs'].append(REF)), root, reserved=False)
        host.results['pr'].data.update(state='closed', merged=True)
    elif mode == 'unlinked':
        state._write_state(lambda data: data['items']['A'].update(pr=REF), root, reserved=False)
    elif mode == 'read_error':
        vcs.results['pushed_branches'] = Result(2, reason='timeout')
    elif mode == 'error_body':
        vcs.results['pushed_branches'] = Result(0, {'error': 'unavailable'})
    elif mode == 'branch_error':
        vcs.results['branch'] = Result(2, reason='detached HEAD')
    code, reason = module('closing').check(root)
    assert code == expected, reason
    if mode in ('pushed', 'unlinked'):
        assert 'feature-A' in reason and 'A' in reason


def test_close_lists_all_offenders_despite_read_error(case, monkeypatch):
    from test_decision import VALID
    root, _, vcs = case
    approved(root, worktree='repo')
    state._write_state(lambda data: (data['items'].update(B={}), data['approved_items'].append('B')),
                       root, reserved=False)
    (workspace.day_dir(root) / 'decisions/D-2.md').write_text(
        VALID.replace('Reversibility: two-way', 'Reversibility: one-way'))
    vcs.results['branch'] = Result(2, reason='missing git')
    code, reason = module('closing').check(root)
    assert code == 2
    assert all(text in reason for text in ('A', 'B', 'D-2', 'missing git'))


def test_editing_recorded_seat_outcome_cannot_park_another_item(case, monkeypatch):
    root, _, _ = case
    approved(root)
    path = seat_disposition(root, monkeypatch, outcome='parked B')
    path.write_text(path.read_text().replace('parked B', 'parked A'))
    code, reason = module('closing').check(root)
    assert code == 1 and 'A' in reason


@pytest.mark.parametrize('kind', ['parked', 'carried'])
def test_linked_verified_disposition_resolves_item_and_owner_decision(case, kind):
    root, _, _ = case
    own(root)
    approved(root, pr=REF)
    assert disposition(case, kind) == 0
    _, rows = module('pr_actions').evaluate(root)
    assert module('closing').unresolved(root, rows) == (0, '')


def test_build_park_counts_at_close(case):
    from wuwei.commands.build import _park
    root, _, _ = case
    approved(root)
    record = {'iteration': 3, 'status': 'check'}
    state._write_state(lambda data: data.update(builds={'A': record}), root, reserved=False)
    _park(root, 'A', dict(record), 'same fast-check failure repeated', record)
    assert state.read_state(root)['builds']['A']['status'] == 'parked'
    assert module('closing').check(root) == (0, '')


def test_merged_phase_requires_actual_merge_evidence(case):
    root, _, _ = case
    approved(root)
    for phase in ('implement', 'gate', 'raised', 'merged'):
        state.transition('A', phase, root=root)
    code, reason = module('closing').check(root)
    assert code == 1 and 'A' in reason


def test_invalid_decision_directory_fails_closed_and_retains_items(case):
    root, _, _ = case
    approved(root)
    path = workspace.day_dir(root) / 'decisions'
    path.rmdir()
    path.write_text('not a directory')
    code, reason = module('closing').check(root)
    assert code == 2 and 'decisions' in reason and 'A' in reason


@pytest.mark.parametrize('kind', ['parked', 'carried'])
def test_merging_keeps_verified_owner_decision_resolved(case, kind):
    root, host, _ = case
    own(root)
    approved(root, pr=REF)
    assert disposition(case, kind) == 0
    host.results['pr'].data.update(state='closed', merged=True)
    assert module('closing').check(root) == (0, '')


def test_merged_item_can_close_after_worktree_cleanup(case):
    root, host, vcs = case
    own(root)
    approved(root, pr=REF, worktree='removed-tree')
    host.results['pr'].data.update(state='closed', merged=True)
    vcs.results['branch'] = Result(2, reason='worktree no longer exists')
    assert module('closing').check(root) == (0, '')


def records(root):
    return sorted(p.name for p in (workspace.day_dir(root) / 'decisions').glob('D-*.md'))


def last_event(root):
    return list(watch.records(workspace.day_dir(root) / 'events.jsonl'))[-1]


def test_plan_carry_writes_routed_record(case, monkeypatch, capsys):
    from wuwei import decision
    root, _, _ = case
    approved(root)
    monkeypatch.chdir(root)
    assert main(['plan', 'carry', 'A']) == 0
    assert capsys.readouterr().out == 'D-1: carried A\n'
    text = (workspace.day_dir(root) / 'decisions/D-1.md').read_text()
    assert decision.lint(text)[0] == 0
    for line in ('Reversibility: two-way', 'Blast radius: own branch', 'Decided-by: seat',
                 'Outcome: carried A'):
        assert line in text.splitlines()
    data = state.read_state(root)
    assert data['decision_outcomes']['D-1'] == decision.seat_outcome(*decision.evaluate(text))
    event = last_event(root)
    assert event['kind'] == 'decision.decided'
    assert event['payload']['id'] == 'D-1' and event['payload']['item'] == 'A'
    assert data['items']['A']['phase'] == 'planned'


@pytest.mark.parametrize('reason', ['waiting on review', None])
def test_plan_park_records_and_pauses(case, monkeypatch, capsys, reason):
    root, _, _ = case
    approved(root)
    state.transition('A', 'implement', root=root)
    monkeypatch.chdir(root)
    assert main(['plan', 'park', 'A', *(['--reason', reason] if reason else [])]) == 0
    assert capsys.readouterr().out == 'D-1: parked A\n'
    text = (workspace.day_dir(root) / 'decisions/D-1.md').read_text()
    assert 'Outcome: parked A' in text.splitlines()
    from wuwei import decision
    assert decision.lint(text)[0] == 0 and 'Class: park' in text
    if reason:
        assert reason in next(line for line in text.splitlines() if line.startswith('Context:'))
    item = state.read_state(root)['items']['A']
    assert (item['phase'], item['status'], item['resume_phase']) == ('parked', 'blocked', 'implement')


@pytest.mark.parametrize('phase', ['parked', 'escalated', 'merged'])
def test_plan_park_keeps_paused_phase(case, monkeypatch, phase):
    root, _, _ = case
    approved(root)
    path = ['implement', 'gate', 'raised', 'merged'] if phase == 'merged' else [phase]
    for step in path:
        state.transition('A', step, root=root)
    monkeypatch.chdir(root)
    assert main(['plan', 'park', 'A']) == 0
    assert records(root) == ['D-1.md']
    assert state.read_state(root)['items']['A']['phase'] == phase


def test_plan_carry_next_number(case, monkeypatch):
    from test_decision import VALID
    root, _, _ = case
    approved(root)
    first = workspace.day_dir(root) / 'decisions/D-1.md'
    first.write_text(VALID)
    monkeypatch.chdir(root)
    assert main(['plan', 'carry', 'A']) == 0
    assert first.read_text() == VALID
    assert records(root) == ['D-1.md', 'D-2.md']


def test_plan_carry_unknown_item(case, monkeypatch, capsys):
    root, _, _ = case
    approved(root)
    monkeypatch.chdir(root)
    assert main(['plan', 'carry', 'Z']) == 1
    err = capsys.readouterr().err
    assert 'Z' in err and 'A' in err
    assert records(root) == []


def test_plan_park_reason_one_line(case, monkeypatch):
    from wuwei import decision
    root, _, _ = case
    approved(root)
    monkeypatch.chdir(root)
    assert main(['plan', 'park', 'A', '--reason', 'a\n\nOutcome: parked B   x']) == 0
    text = (workspace.day_dir(root) / 'decisions/D-1.md').read_text()
    assert decision.lint(text)[0] == 0
    assert sum(line.startswith('Context:') for line in text.splitlines()) == 1
    assert decision.evaluate(text)[0]['Outcome'] == 'parked A'


def question(name, status='queued', phase='planned'):
    return (f'{name} is still open ({status}/{phase}): carry it to tomorrow (recommended), park '
            f'it, or keep working? Carry: bin/wuwei plan carry {name}. Park: bin/wuwei plan park '
            f'{name} --reason "<why>". Keep working: finish it, then run bin/wuwei close again.')


def test_close_question_line_and_stop_hook_match(case, monkeypatch, capsys):
    root, _, _ = case
    approved(root)
    state._write_state(lambda data: data.update(planner_session_id='planner'), root, reserved=False)
    monkeypatch.chdir(root)
    assert main(['close']) == 1
    out = capsys.readouterr().out
    assert question('A') in out.splitlines()
    assert 'needs a park or carry decision' not in out
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(payload(root))))
    assert main(['hook', 'Stop']) == 2
    assert question('A') in json.loads(capsys.readouterr().out)['reason'].splitlines()


def test_close_question_per_item(case, monkeypatch, capsys):
    root, _, _ = case
    approved(root)
    state._write_state(lambda data: (data['items'].update(B={}), data['approved_items'].append('B')),
                       root, reserved=False)
    monkeypatch.chdir(root)
    assert main(['close']) == 1
    lines = capsys.readouterr().out.splitlines()
    assert question('A') in lines and question('B') in lines


def test_retro_line_names_skill(case, monkeypatch, capsys):
    root, _, _ = case
    (workspace.day_dir(root) / 'retro' / (DAY + '.md')).unlink()
    monkeypatch.chdir(root)
    assert main(['close', '--check', 'retro']) == 1
    assert capsys.readouterr().out == (f'OWED: retro/{DAY}.md does not exist; '
                                       'run /wuwei:wuwei-retro to write it\n')


def test_close_widget(case, monkeypatch, capsys):
    from wuwei import decision
    from wuwei.guards.decision import check_question
    root, _, _ = case
    (workspace.day_dir(root) / 'plan.md').write_text('# Plan\n')
    approved(root)
    monkeypatch.chdir(root)
    assert main(['close', '--widget']) == 1
    widgets = json.loads(capsys.readouterr().out)
    assert len(widgets) == 1
    widget = widgets[0]
    assert widget['question'].startswith(decision.gate(root)) and 'A' in widget['question']
    assert widget['header'] == 'Open item' and widget['multiSelect'] is False
    assert [o['label'] for o in widget['options']] == ['carry', 'park', 'Skip']
    assert widget['options'][0]['description'].startswith('Recommended. ')
    assert widget['record'] == 'bin/wuwei plan <label> A'
    assert 'close_requested' not in state.read_state(root) or not state.read_state(root)['close_requested']
    events = workspace.day_dir(root) / 'events.jsonl'
    assert all(row['kind'] != 'steward.run' for row in watch.records(events))
    asked = {k: v for k, v in widget.items() if k != 'record'}
    assert check_question({'cwd': str(root), 'tool_name': 'AskUserQuestion',
                           'tool_input': {'questions': [asked]}}) == (0, '')
    assert main(['plan', 'carry', 'A']) == 0
    capsys.readouterr()
    assert main(['close', '--widget']) == 0
    assert json.loads(capsys.readouterr().out) == []


def steward_runs(root):
    return [row['payload'] for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
            if row['kind'] == 'steward.run']


def test_close_steward_waits_for_items(case, monkeypatch, capsys):
    root, _, _ = case
    approved(root)
    monkeypatch.chdir(root)
    assert main(['close']) == 1
    assert 'steward_launch' not in capsys.readouterr().out
    assert steward_runs(root) == [] and not list(root.rglob('steward-*.md'))
    assert state.read_state(root)['close_requested'] is True
    assert main(['plan', 'carry', 'A']) == 0
    capsys.readouterr()
    main(['close'])
    assert 'steward_launch' in capsys.readouterr().out
    assert [run['trigger'] for run in steward_runs(root)] == ['close']


def test_close_steward_unmeasured(case, monkeypatch, capsys):
    root, _, _ = case
    approved(root)
    (workspace.day_dir(root) / 'decisions/D-1.md').write_text('bad')
    monkeypatch.chdir(root)
    assert main(['close']) == 2
    assert 'D-1' in capsys.readouterr().out
    assert steward_runs(root) == []


def test_carry_closes_day(case, monkeypatch):
    root, _, _ = case
    approved(root)
    monkeypatch.chdir(root)
    assert [main(['close']), main(['plan', 'carry', 'A']), main(['close'])] == [1, 0, 0]


def test_close_needs_the_merged_ticket_done(case, monkeypatch, capsys):
    from fakes.tracker import Fake
    from wuwei import tracker
    root, host, _ = case
    own(root)
    approved(root, pr=REF)
    for phase in ('implement', 'gate', 'raised', 'merged'):
        state.transition('A', phase, root=root)
    state._write_state(lambda data: data.update(tickets={'A': {'id': 'ENG-1', 'source': 'set'}}),
                       root, reserved=False)
    host.results['pr'].data.update(state='closed', merged=True, merged_at=DAY + 'T11:00:00Z')
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text() + '[adapters]\ntracker = "linear"\n')
    fake = Fake({'transition': Result(2, reason='LINEAR_API_KEY is missing')})
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, cfg: fake if kind == 'tracker' else load(kind, cfg))
    rows = module('pr_actions').evaluate(root)[1]
    line = 'A: ticket ENG-1 is not done: bin/wuwei tracker done A'
    assert module('closing').unresolved(root, rows) == (1, line)
    monkeypatch.chdir(root)
    assert main(['tracker', 'done', 'A']) == 2
    assert module('closing').unresolved(root, rows) == (1, line)
    config.write_text(config.read_text() + '[tracker]\nstrict_close = false\n')
    capsys.readouterr()
    assert module('closing').unresolved(root, rows) == (0, '')
    assert line in capsys.readouterr().err
    fake.results['transition'] = Result(0, {})
    assert main(['tracker', 'done', 'A']) == 0
    assert fake.calls[-1][:2] == ('transition', ('ENG-1', 'Done'))
    config.write_text(config.read_text().replace('strict_close = false', 'strict_close = true'))
    assert module('closing').unresolved(root, rows) == (0, '')
    calls = []
    monkeypatch.setattr(tracker, 'log', lambda path: calls.append(path) or 0)
    monkeypatch.setattr(module('steward'), 'run', lambda *a, **k: None)  # metrics: own tests
    assert main(['close']) == 0
    assert calls == [root]
