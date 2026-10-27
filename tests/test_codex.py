"""WUWEI on Codex: the same hooks, doors and agents, from Codex's own payload shapes."""

import json
import os
from pathlib import Path
import subprocess
import tomllib

import pytest

from conftest import verdict_text
from wuwei import board, hook, setup, ws

PLUGIN = Path(__file__).resolve().parents[1]
PATCH = '*** Begin Patch\n*** Update File: src/app.py\n@@\n-a\n+b\n*** Add File: .wuwei/ledger/0a1b2c3d.jsonl\n+{}\n*** End Patch\n'


def pre(root, tool, data):
    return hook.handle(root, 'PreToolUse', {'session_id': 's1', 'turn_id': 't1', 'cwd': str(root), 'model': 'gpt',
                                            'permission_mode': 'default', 'hook_event_name': 'PreToolUse',
                                            'tool_name': tool, 'tool_input': data, 'tool_use_id': 'u1'})


def test_the_hook_commands_run_under_either_harness_shell(root):
    hooks = json.loads((PLUGIN / 'hooks' / 'hooks.json').read_text())['hooks']
    command = hooks['SessionStart'][0]['hooks'][0]['command']
    assert 'args' not in hooks['SessionStart'][0]['hooks'][0]
    env = {**os.environ, 'CLAUDE_PLUGIN_ROOT': str(PLUGIN)}
    out = subprocess.run(['sh', '-lc', command], input=json.dumps({'cwd': str(root)}), capture_output=True,
                         text=True, env=env, cwd=root).stdout
    assert json.loads(out)['hookSpecificOutput']['hookEventName'] == 'SessionStart'


def test_an_apply_patch_that_writes_the_ledger_is_refused(root):
    out = pre(root, 'apply_patch', {'command': PATCH})
    assert out['hookSpecificOutput']['permissionDecision'] == 'deny'
    assert pre(root, 'apply_patch', {'command': PATCH.replace('.wuwei/ledger/0a1b2c3d.jsonl', 'src/new.py')}) is None


def test_a_malformed_apply_patch_is_refused_and_recorded_without_crashing_the_hook(root):
    out = pre(root, 'apply_patch', 'not a patch object')['hookSpecificOutput']
    assert out['permissionDecision'] == 'deny' and 'the hook failed' in out['permissionDecisionReason']
    assert ws.rows(root, 'hook.error')


def test_a_spawned_codex_agent_is_a_running_seat(root):
    data = {'agent_type': 'sentinel-quality', 'task_name': 'quality gate', 'message': 'review I-1'}
    pre(root, 'spawn_agent', data)
    assert ws.rows(root, 'seat.started') == []
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'cwd': str(root), 'tool_name': 'spawn_agent',
                                      'tool_input': data, 'tool_response': '{"agent_id": "c1"}'})
    assert [(r['data']['role'], r['data']['agent']) for r in ws.rows(root, 'seat.started')] == [('sentinel-quality', 'c1')]
    assert [s['role'] for s in board.running(root)] == ['sentinel-quality']


@pytest.mark.parametrize('response', [{'agent_id': 7}, {'agent_id': ''}, '{"status": "ok"}', None])
def test_a_codex_spawn_without_a_string_id_records_no_seat(root, response):
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'cwd': str(root), 'tool_name': 'spawn_agent',
                                      'tool_input': {'agent_type': 'sentinel-quality'}, 'tool_response': response})
    assert ws.rows(root, 'seat.started') == [] and board.running(root) == []


def test_a_codex_question_without_a_class_is_sent_back_and_an_answer_is_recorded_unconfirmed(root):
    """No reader for Codex's own transcript yet: its answers count for nothing and say why (hook-transcript)."""
    asked = {'questions': [{'id': 'q1', 'header': 'Go?', 'question': 'Should I continue with the next item?'}]}
    assert pre(root, 'request_user_input', asked)['hookSpecificOutput']['permissionDecision'] == 'deny'
    question = 'one-way: drop the legacy table? Recommended: yes, it has had no reads for 90 days.'
    asked = {'questions': [{'id': 'q1', 'header': 'Drop', 'question': question}], 'isBlocking': True}
    assert pre(root, 'request_user_input', asked) is None
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'cwd': str(root), 'tool_name': 'request_user_input', 'tool_use_id': 'c1',
                                      'transcript_path': str(root / 'rollout.jsonl'), 'tool_input': asked,
                                      'tool_response': {'answers': {'q1': {'answers': ['Yes']}}}})
    assert ws.rows(root, 'prompt') == [] and ws.rows(root, 'answer.unconfirmed')[-1]['data']['answers'] == {question: 'Yes'}


def test_a_codex_gate_verdict_is_unconfirmed_until_a_codex_transcript_reader_exists(root):
    path = root / ws.DIR / 'verdicts' / 'I-1' / 'quality-aaaaaaa.md'
    path.parent.mkdir(parents=True)
    path.write_text(verdict_text())
    hook.handle(root, 'SubagentStop', {'session_id': 's1', 'turn_id': 't1', 'agent_id': 'a1', 'agent_type': 'sentinel-quality',
                                       'cwd': str(root), 'stop_hook_active': False, 'agent_transcript_path': None,
                                       'last_assistant_message': 'Reviewed.\nVerdict file: .wuwei/verdicts/I-1/quality-aaaaaaa.md'})
    assert ws.rows(root, 'attest') == [] and ws.rows(root, 'seat.unconfirmed')[0]['data']['agent'] == 'a1'


def test_init_codex_writes_the_role_agents_and_the_door_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: None)
    setup.init(tmp_path, codex=True)
    setup.init(tmp_path, codex=True)
    role = tomllib.loads((tmp_path / '.codex' / 'agents' / 'sentinel-quality.toml').read_text())
    assert role['name'] == 'sentinel-quality' and 'Quality sentinel charter' in role['developer_instructions']
    assert 'model' not in role  # Codex picks its own models; a Claude model name would not resolve there
    assert len(list((tmp_path / '.codex' / 'agents').glob('*.toml'))) == 8
    rules = (tmp_path / '.codex' / 'rules' / 'wuwei.rules').read_text()
    assert 'pattern = ["git", "push", "--force"], decision = "forbidden"' in rules
    assert 'pattern = ["terraform", "apply"], decision = "prompt"' in rules


def test_doctor_says_when_the_codex_roles_drift_from_the_charters(tmp_path, monkeypatch):
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: None)
    monkeypatch.setattr(setup.gh, 'run', lambda args, timeout=30: 'ok')
    setup.init(tmp_path, codex=True)
    assert ('codex roles', 'ok', 'match the charters') in setup.doctor(tmp_path)
    (tmp_path / '.codex' / 'agents' / 'lead.toml').write_text('name = "lead"\n')
    assert ('codex roles', 'warn', 'stale: lead: run wuwei init --codex') in setup.doctor(tmp_path)


def test_a_codex_goal_met_answer_records_no_goal(root):
    question = 'goal: G-2 met? 0 bugs open past three days.'
    asked = {'questions': [{'id': 'q1', 'header': 'Met', 'question': question}], 'isBlocking': True}
    assert pre(root, 'request_user_input', asked) is None
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'cwd': str(root), 'tool_name': 'request_user_input',
                                      'tool_input': asked, 'tool_response': {'answers': {'q1': {'answers': ['Yes']}}}})
    assert ws.rows(root, 'ruling') == [] and 'not a transcript' in ws.rows(root, 'answer.unconfirmed')[0]['data']['reason']


@pytest.mark.parametrize('identity_key', ['task_name', 'agent_id'])
@pytest.mark.parametrize('encoded', [False, True])
def test_native_dispatch_keeps_identity_role_and_requested_settings(root, identity_key, encoded):
    payload = json.loads((PLUGIN / 'tests/fixtures/payloads/codex/native-spawn-agent-post.json').read_text())
    payload['cwd'] = str(root)
    response = {identity_key: '/root/identity_probe'}
    payload['tool_response'] = json.dumps(response) if encoded else response
    normalized = hook.codex(payload)
    assert normalized['tool_input']['prompt'] == payload['tool_input']['message']
    assert normalized['tool_input']['model'] == 'gpt-6.1-sol'
    assert normalized['tool_input']['effort'] == 'high'
    hook.handle(root, 'PostToolUse', payload)
    seat = ws.rows(root, 'seat.started')[0]['data']
    assert (seat['agent'], seat['role'], seat['item']) == ('/root/identity_probe', 'builder', 'I-1')
    assert (seat['asked'], seat['effort'], seat['model']) == ('gpt-6.1-sol', 'high', 'unmeasured')
    assert board.running(root)[0]['agent'] == '/root/identity_probe'
    assert ws.rows(root, 'attest') == []


@pytest.mark.parametrize('role', [None, '', 'unknown', 7, ['builder']])
def test_native_identity_without_a_valid_role_is_diagnosed_not_inferred(root, role):
    payload = {'session_id': 's1', 'cwd': str(root), 'tool_name': 'spawn_agent',
               'tool_input': {'task_name': 'builder', 'agent_type': role, 'message': 'You are a builder. Item: I-1'},
               'tool_response': {'task_name': '/root/builder'}}
    normalized = hook.codex(payload)
    assert normalized['tool_name'] != 'Agent'
    assert normalized['tool_response']['agentId'] == '/root/builder'
    out = hook.handle(root, 'PostToolUse', payload)
    row = ws.rows(root, 'seat.unconfirmed')[0]['data']
    assert row['agent'] == '/root/builder' and 'role unmeasured' in row['reason']
    assert 'agent_type' in out['hookSpecificOutput']['additionalContext']
    assert ws.rows(root, 'seat.started') == [] and board.running(root) == [] and ws.rows(root, 'attest') == []


@pytest.mark.parametrize('response', [None, {}, [], 7, {'task_name': 7}, {'task_name': ''}, {'task_name': '  '},
                                      {'agent_id': ' '}, {'error': {'agent_id': 'fake'}},
                                      {'error': '{"agent_id": "fake"}'}, '{"task_name":', 'not JSON'])
def test_invalid_native_dispatch_response_is_diagnosed_without_a_seat(root, response):
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'cwd': str(root), 'tool_name': 'spawn_agent',
                                      'tool_input': {'agent_type': 'builder'}, 'tool_response': response})
    assert ws.rows(root, 'hook.error')
    assert ws.rows(root, 'seat.started') == [] and board.running(root) == [] and ws.rows(root, 'attest') == []


def test_namespaced_known_native_role_and_legacy_identity_precedence(root):
    hook.handle(root, 'PostToolUse', {'session_id': 's1', 'cwd': str(root), 'tool_name': 'spawn_agent',
                                      'tool_input': {'agent_type': 'wuwei:builder'},
                                      'tool_response': {'agent_id': 'legacy', 'task_name': '/root/native'}})
    seat = ws.rows(root, 'seat.started')[0]['data']
    assert seat['role'] == 'builder' and seat['agent'] == 'legacy'


@pytest.mark.parametrize('response', [None, {}, {'task_name': ''}])
def test_direct_normalization_never_returns_an_apparently_valid_blank_agent(response):
    with pytest.raises(ValueError, match='Codex spawn_agent response needs'):
        hook.codex({'tool_name': 'spawn_agent', 'tool_input': {'agent_type': 'builder'}, 'tool_response': response})


@pytest.mark.parametrize('surface', ['native', 'native-unconfirmed', 'legacy'])
def test_new_seat_metadata_redacts_credentials_and_canary_without_dropping_message(root, surface):
    credential, canary = 'ghp_' + 'Z' * 36, 'wuwei-canary-review-1259'
    (root / ws.DIR / 'canary').write_text(canary)
    message = f'Item: I-1\nModel reason: credential {credential} canary {canary}'
    payload = {'session_id': 'first', 'cwd': str(root), 'tool_name': 'spawn_agent',
               'tool_input': {'agent_type': 'builder' if surface == 'native' else None,
                              'task_name': canary, 'message': message, 'model': credential, 'reasoning_effort': 'high'},
               'tool_response': {'task_name': '/root/builder'}}
    if surface == 'legacy':
        payload.update(tool_name='Agent', tool_input={'subagent_type': 'builder', 'description': canary,
                       'prompt': message, 'model': credential, 'effort': 'high'}, tool_response={'agentId': 'legacy'})
    else:
        assert hook.codex(payload)['tool_input']['prompt'] == message
    hook.handle(root, 'PostToolUse', payload)
    rows = ws.rows(root, 'seat.unconfirmed' if surface == 'native-unconfirmed' else 'seat.started')
    assert len(rows) == 1
    assert credential not in json.dumps(rows) and canary not in json.dumps(rows)
    assert rows[0]['data']['effort'] == 'high'
    assert ws.rows(root, 'attest') == []


def native_review_spawn(root, session, role='builder'):
    return hook.handle(root, 'PostToolUse', {'session_id': session, 'cwd': str(root), 'tool_name': 'spawn_agent',
                       'tool_input': {'agent_type': role, 'task_name': 'builder', 'message': 'Item: I-1'},
                       'tool_response': {'task_name': '/root/builder'}})


def test_native_unconfirmed_identity_does_not_hide_another_sessions_seat(root):
    native_review_spawn(root, 'first')
    native_review_spawn(root, 'second', role=None)
    assert len(ws.rows(root, 'seat.unconfirmed')) == 1
    assert [s['session'] for s in board.running(root)] == ['first']


def test_native_task_path_can_run_in_a_new_session_after_an_unconfirmed_stop(root):
    native_review_spawn(root, 'first')
    hook.handle(root, 'SubagentStop', {'session_id': 'first', 'agent_id': '/root/builder',
                                      'agent_type': 'builder', 'last_assistant_message': 'Done.'})
    assert board.running(root) == []
    native_review_spawn(root, 'second')
    assert [s['session'] for s in board.running(root)] == ['second']


@pytest.mark.parametrize('agent', ['legacy-id', '/root/builder'])
def test_seat_stops_with_a_session_only_close_that_sessions_identity(root, agent):
    for session in ('first', 'second'):
        ws.record(root, 'seat.started', {'agent': agent, 'session': session, 'role': 'builder'})
    ws.record(root, 'seat.stopped', {'agent': agent, 'session': 'first'})
    assert [s['session'] for s in board.running(root)] == ['second']


@pytest.mark.parametrize('agent, remaining', [('legacy-id', []), ('/root/builder', ['first'])])
def test_sessionless_historical_stops_only_close_legacy_global_identities(root, agent, remaining):
    ws.record(root, 'seat.started', {'agent': agent, 'session': 'first', 'role': 'builder'})
    ws.record(root, 'seat.stopped', {'agent': agent})
    assert [s['session'] for s in board.running(root)] == remaining


def test_seat_metadata_redacts_before_reason_and_description_are_truncated(root):
    credential, canary = 'ghp_' + 'Z' * 36, 'wuwei-canary-review-boundary'
    (root / ws.DIR / 'canary').write_text(canary)
    hook.handle(root, 'PostToolUse', {'session_id': 'first', 'cwd': str(root), 'tool_name': 'spawn_agent',
                'tool_input': {'agent_type': 'builder', 'task_name': 'x' * 110 + canary,
                               'message': 'Model reason: ' + 'x' * 180 + credential},
                'tool_response': {'task_name': '/root/builder'}})
    text = json.dumps(ws.rows(root, 'seat.started'))
    assert 'ghp_' not in text and 'wuwei-can' not in text
