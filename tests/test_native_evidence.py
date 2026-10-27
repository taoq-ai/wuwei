import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shlex
import sys

import pytest

from conftest import verdict_text
from test_guards import TRANSCRIPT_WRITES
from wuwei import guards, hook, ws

FIXTURE = json.loads((Path(__file__).parent / "fixtures/native-evidence.json").read_text())

@pytest.fixture
def native(root, monkeypatch):
    folder = root / '.codex/sessions'
    folder.mkdir(parents=True)
    monkeypatch.setattr(ws, 'SESSIONS', folder, raising=False)
    parent = [copy.deepcopy(FIXTURE[k]) for k in ('parent_meta', 'spawn', 'spawn_output')]
    parent[1]['payload']['arguments'] = json.dumps(FIXTURE['spawn_arguments'])
    child = [copy.deepcopy(FIXTURE[k]) for k in ('child_meta', 'child_report', 'child_completion')]
    parent_path, child_path = folder / 'parent.jsonl', folder / 'child.jsonl'
    def save():
        for path, rows in ((parent_path, parent), (child_path, child)):
            path.write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
    monkeypatch.setattr(hook.time, 'sleep', lambda _: None)
    save()
    payload = {'session_id': 'id-1', 'agent_id': 'id-2', 'agent_type': 'builder', 'transcript_path': str(parent_path),
               'agent_transcript_path': str(child_path), 'cwd': str(root), 'last_assistant_message': child[2]['payload']['last_agent_message'], 'hook_event_name': 'SubagentStop'}
    return payload, parent, child, save


def test_genuine_native_builder_stop_uses_its_canonical_task_path(root, native):
    payload, parent, child, save = native
    hook.handle(root, 'SubagentStop', payload)
    assert ws.rows(root, 'seat.stopped')[-1]['data']['agent'] == '/root/codex_transcript_probe'
    assert not ws.rows(root, 'seat.unconfirmed')


@pytest.mark.parametrize('bad', ['parent', 'role', 'path', 'call', 'inherited', 'completion', 'earlier', 'outer', 'duplicate'])
def test_native_seat_proof_rejects_unmatched_and_replayed_records(root, native, bad):
    payload, parent, child, save = native
    if bad == 'parent': child[0]['payload']['parent_thread_id'] = 'other'
    if bad == 'role': child[0]['payload']['agent_role'] = 'sentinel-security'
    if bad == 'path': child[0]['payload']['agent_path'] = '/root/other'
    if bad == 'call': parent[2]['payload']['call_id'] = 'other'
    if bad == 'inherited': child[1]['ordinal'], child[2]['ordinal'] = 10, 11
    if bad == 'completion': child[2]['payload']['last_agent_message'] = 'other'
    if bad == 'earlier': payload['last_assistant_message'] = 'previous report'
    if bad == 'outer': child[2]['type'] = 'response_item'
    if bad == 'duplicate': parent.insert(2, copy.deepcopy(parent[1]))
    save()
    assert hook._report(root, payload, payload['last_assistant_message']) is None
    assert not ws.rows(root, 'seat.stopped')


def test_native_reader_rejects_symlink_escape_and_partial_json(root, native):
    payload, parent, child, save = native
    path = Path(payload['agent_transcript_path'])
    outside = root / 'outside.jsonl'
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    assert hook.transcript_rows(path, '') is None
    path.unlink()
    path.write_text('{')
    assert hook.transcript_rows(path, '') is None


def test_native_stop_callback_is_completion_when_task_complete_is_written_after_the_hook(root, native):
    payload, parent, child, save = native
    child.pop()
    save()
    assert hook._report(root, payload, payload['last_assistant_message']) == payload['last_assistant_message']


def test_native_notification_uses_the_exact_frame_and_canonical_or_hashed_identity(root, native):
    payload, parent, child, save = native
    parent.append(copy.deepcopy(FIXTURE['parent_delivery']))
    save()
    agent = child[0]['payload']['agent_path']
    for identity in (agent, hashlib.sha256(agent.encode()).hexdigest()):
        assert hook._native_told(payload['transcript_path'], identity, payload['last_assistant_message'], '2000-01-01T00:00:00+00:00')
    parent[-1]['payload']['content'][0]['text'] = 'quoted ' + parent[-1]['payload']['content'][0]['text']
    save()
    assert not hook._native_told(payload['transcript_path'], agent, payload['last_assistant_message'], '2000-01-01T00:00:00+00:00')


def test_native_nonmessage_state_rows_do_not_break_report_proof(root, native):
    payload, parent, child, save = native
    child.insert(2, {'ordinal': 183, 'type': 'world_state', 'payload': {'state': {}}})
    save()
    assert hook._native_report(payload, payload['last_assistant_message'])



@pytest.mark.parametrize('kind', ['world_state', 'turn_context'])
def test_native_rows_without_payload_type_still_reach_the_real_stop(root, native, kind):
    payload, parent, child, save = native
    child.insert(1, {'ordinal': 181, 'type': kind, 'payload': {'model': 'gpt-child', 'effort': 'high'}})
    save()
    hook.handle(root, 'SubagentStop', payload)
    assert ws.rows(root, 'seat.stopped')[-1]['data']['agent'] == child[0]['payload']['agent_path']
    assert not ws.rows(root, 'hook.error')


@pytest.mark.parametrize('bad', ['missing-meta', 'later-meta', 'duplicate-ordinal', 'negative-ordinal', 'bool-ordinal',
                                'bad-boundary', 'same-uuid', 'wrong-stop-uuid', 'unknown-role', 'bad-task-path', 'parent-inherited'])
def test_invalid_native_identity_never_attests(root, native, bad):
    payload, parent, child, save = native
    if bad == 'missing-meta': child.pop(0)
    if bad == 'later-meta': child.append({**copy.deepcopy(child[0]), 'ordinal': 200})
    if bad == 'duplicate-ordinal': child[2]['ordinal'] = child[1]['ordinal']
    if bad == 'negative-ordinal': child[1]['ordinal'] = -1
    if bad == 'bool-ordinal': child[1]['ordinal'] = True
    if bad == 'bad-boundary': child[0]['payload']['subagent_history_start_ordinal'] = '45'
    if bad == 'same-uuid': child[0]['payload']['id'] = parent[0]['payload']['id']; payload['agent_id'] = parent[0]['payload']['id']
    if bad == 'wrong-stop-uuid': payload['agent_id'] = 'other-native-id'
    if bad == 'unknown-role': payload['agent_type'] = child[0]['payload']['agent_role'] = 'unknown'
    if bad == 'bad-task-path':
        child[0]['payload']['agent_path'] = '/root/../other'
        parent[1]['payload']['arguments'] = json.dumps({'agent_type': 'builder', 'task_name': '../other'})
        parent[2]['payload']['output'] = json.dumps({'task_name': '/root/../other'})
    if bad == 'parent-inherited': parent[0]['payload']['subagent_history_start_ordinal'] = 100
    save()
    hook.handle(root, 'SubagentStop', payload)
    assert not ws.rows(root, 'attest') and not ws.rows(root, 'seat.stopped')
    assert ws.rows(root, 'seat.unconfirmed') and not ws.rows(root, 'hook.error')


@pytest.mark.parametrize('contents', ['', '{', 'null', '[]', '{}', '\xff'])
def test_unreadable_native_record_stays_unconfirmed(root, native, contents):
    payload, parent, child, save = native
    Path(payload['agent_transcript_path']).write_bytes(contents.encode('latin1'))
    hook.handle(root, 'SubagentStop', payload)
    assert not ws.rows(root, 'seat.stopped') and not ws.rows(root, 'hook.error')
    assert ws.rows(root, 'seat.unconfirmed')


def test_the_native_root_uses_the_account_not_environment(tmp_path):
    env = {**os.environ, 'HOME': str(tmp_path), 'USERPROFILE': str(tmp_path), 'CODEX_HOME': str(tmp_path),
           'PYTHONPATH': str(Path(ws.__file__).parents[1])}
    ran = subprocess.run([sys.executable, '-c', 'from wuwei import ws; print(ws.SESSIONS)'], env=env,
                         capture_output=True, text=True, timeout=60)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.strip().endswith(os.path.join('.codex', 'sessions')) and str(tmp_path) not in ran.stdout


NATIVE_PATHS = ['~/.codex/sessions/s.jsonl', '/root/.codex/sessions/s.jsonl', '$HOME/.codex/sessions/s.jsonl',
                '"$HOME"/.codex/sessions/s.jsonl', '~//.codex//sessions//s.jsonl', '~/./.codex/./sessions/s.jsonl',
                '~/x/../.codex/sessions/s.jsonl', '~/.codex/x/../sessions/s.jsonl', '~/.c*/sessions/s.jsonl',
                '~/.codex/sess*/s.jsonl', '~/.codex/ses[s]ions/s.jsonl', '~/.codex/{sessions,x}/s.jsonl',
                '~/.{codex,x}/sessions/s.jsonl', '~/.codex/sessions', '~/.codex',
                r'C:\Users\u\.codex\sessions\s.jsonl', r'C:\Users\u\.CODEX\SESSIONS\s.jsonl',
                r'C:\Users\u\.codex.\sessions \s.jsonl:stream']


@pytest.mark.parametrize('path', NATIVE_PATHS)
@pytest.mark.parametrize('write', TRANSCRIPT_WRITES)
def test_native_transcripts_inherit_all_existing_shell_writers(root, path, write):
    target = '"' + path.replace('\\', '/') + '"' if path.startswith('C:') else path
    command = write.format(p=target)
    if path.startswith('C:') and write.startswith('python3'):
        command = 'python3 -c ' + shlex.quote(f"open({path!r}, 'a').write('x')")
    if path.startswith('C:') and write.startswith('bash -c'):
        command = 'bash -c ' + shlex.quote('echo x >> ' + target)
    result = guards.bash(root, command, str(root), 's1')
    assert result and result['decision'] == 'deny' and 'transcripts' in result['reason']


@pytest.mark.parametrize('tool,key', [('Write','file_path'), ('Edit','file_path'), ('MultiEdit','file_path'),
                                     ('NotebookEdit','notebook_path'), ('Edit','file_paths')])
@pytest.mark.parametrize('path', NATIVE_PATHS)
def test_native_transcripts_inherit_all_existing_edit_guards(root, tool, key, path):
    result = guards.pre_tool(root, {'tool_name': tool, 'tool_input': {key: [path] if key == 'file_paths' else path}})
    assert result and result['decision'] == 'deny'


@pytest.mark.parametrize('prefix', ['cd /root/.codex/sessions && ', 'pushd /root/.codex/sessions && ',
                                    'env -C /root/.codex/sessions ', 'env --chdir=/root/.codex/sessions ',
                                    'sudo -D /root/.codex/sessions '])
def test_native_directory_wrappers_stay_guarded(root, prefix):
    assert guards.bash(root, prefix + 'printf x > file', str(root), 's1')['decision'] == 'deny'


@pytest.mark.parametrize('command', ['cat ~/.codex/sessions/s.jsonl', 'python3 - < ~/.codex/sessions/s.jsonl',
                                   'cd ~/.codex/sessions && grep x s.jsonl', 'echo x > ~/.codex/settings.toml',
                                   'echo x > ~/.codex%2Fsessions/s.jsonl'])
def test_native_intended_reads_and_literal_percent_names_pass(root, command):
    assert guards.bash(root, command, str(root), 's1') is None


def report(native, text, role=None):
    payload, parent, child, save = native
    if role:
        payload['agent_type'] = child[0]['payload']['agent_role'] = role
        parent[1]['payload']['arguments'] = json.dumps({**FIXTURE['spawn_arguments'], 'agent_type': role})
    payload['last_assistant_message'] = child[-1]['payload']['last_agent_message'] = text
    child[-2]['payload']['content'][0]['text'] = text
    save()
    return payload


def test_native_gate_attestation_uses_child_own_settings_not_parent(root, native):
    payload, parent, child, save = native
    path = root / '.wuwei/verdicts/I-1/quality.md'
    path.parent.mkdir(parents=True); path.write_text(verdict_text())
    report(native, 'Verdict file: .wuwei/verdicts/I-1/quality.md', 'sentinel-quality')
    child.insert(1, {'type':'turn_context', 'ordinal': 40, 'payload':{'model':'inherited-parent', 'effort':'low'}})
    child.insert(2, {'type':'turn_context', 'ordinal': 181, 'payload':{'model':'gpt-child', 'effort':'high'}})
    save()
    hook.handle(root, 'PostToolUse', {'session_id':'id-1', 'tool_name':'spawn_agent', 'model':'parent-model',
        'tool_input':{'agent_type':'sentinel-quality', 'task_name':'codex_transcript_probe', 'message':'Item: I-1',
                      'model':'requested-model', 'reasoning_effort':'low'}, 'tool_response':json.dumps({'task_name':'/root/codex_transcript_probe'})})
    hook.handle(root, 'SubagentStop', {**payload, 'model':'stop-model'})
    [attested] = ws.rows(root, 'attest')
    assert attested['data']['recorded_model'] == 'gpt-child'
    assert attested['data']['recorded_effort'] == 'high'
    assert attested['data']['model'] == 'unmeasured'
    assert ws.rows(root, 'seat.stopped')[-1]['data']['recorded_model'] == 'gpt-child'
    assert ws.rows(root, 'seat.started')[-1]['data']['turn_model'] == 'parent-model'


def test_native_child_settings_are_redacted_before_recording(root, native):
    payload, parent, child, save = native
    canary = 'wuwei-canary-native-secret'
    (root/'.wuwei/canary').write_text(canary)
    child.insert(1, {'type':'turn_context', 'ordinal':181, 'payload':{'model':'ghp_'+'x'*36, 'effort':canary}})
    save(); hook.handle(root, 'SubagentStop', payload)
    row = json.dumps(ws.rows(root, 'seat.stopped'))
    assert canary not in row and 'ghp_' not in row
    assert '***' in row


def test_ordinary_native_owner_text_does_not_confirm_a_ruling(root, native):
    payload, parent, child, save = native
    parent.append({'ordinal':100, 'type':'response_item', 'payload':{'type':'message','role':'user',
                  'content':[{'type':'input_text','text':'Yes, approved'}]}})
    save(); hook.handle(root, 'Stop', {k:v for k,v in payload.items() if not k.startswith('agent_')})
    assert not ws.rows(root, 'ruling') and not ws.rows(root, 'plan.approved')


def test_native_report_versions_use_collision_free_names_and_latest_valid_delivery(root, native):
    payload = report(native, 'FIRST')
    hook.handle(root, 'SubagentStop', payload)
    report(native, 'SECOND'); hook.handle(root, 'SubagentStop', payload)
    report(native, 'FIRST'); hook.handle(root, 'SubagentStop', payload)
    pending = root/'.wuwei/reports/pending'
    files = list(pending.glob('*.md'))
    assert len(files) == 3
    assert all(hashlib.sha256(b'/root/codex_transcript_probe').hexdigest() in p.name for p in files)
    out = hook.handle(root, 'Stop', {'session_id':'id-1', 'transcript_path':payload['transcript_path']})
    assert out['decision'] == 'block' and '\nFIRST' in out['reason'] and '\nSECOND' not in out['reason']
    assert hook.handle(root, 'Stop', {'session_id':'id-1', 'transcript_path':payload['transcript_path']}) is None

@pytest.mark.parametrize('bad', ['author', 'recipient', 'frame', 'body', 'time'])
def test_native_notification_mismatch_still_delivers_report(root, native, bad):
    payload = report(native, 'NATIVE FINAL')
    hook.handle(root, 'SubagentStop', payload)
    pending = next((root/'.wuwei/reports/pending').glob('*.md'))
    os.utime(pending, (1_000_000_000, 1_000_000_000))
    _, parent, _, save = native
    row = copy.deepcopy(FIXTURE['parent_delivery'])
    row['payload']['content'][0]['text'] = 'Message Type: FINAL_ANSWER\nTask name: /root\nSender: /root/codex_transcript_probe\nPayload:\nNATIVE FINAL'
    if bad == 'author': row['payload']['author'] = '/root/other'
    if bad == 'recipient': row['payload']['recipient'] = '/root/other'
    if bad == 'frame': row['payload']['content'][0]['text'] = 'quoted '+row['payload']['content'][0]['text']
    if bad == 'body': row['payload']['content'][0]['text'] += ' different'
    if bad == 'time': row['timestamp'] = '1990-01-01T00:00:00+00:00'
    parent.append(row); save()
    out = hook.handle(root, 'Stop', {'session_id':'id-1','transcript_path':payload['transcript_path']})
    assert out['decision'] == 'block' and '\nNATIVE FINAL' in out['reason']


@pytest.mark.parametrize('event', ['Stop','PreToolUse'])
def test_genuine_native_notification_gives_only_a_pointer_and_never_blocks_stop(root, native, event):
    payload = report(native, 'NATIVE FINAL')
    hook.handle(root, 'SubagentStop', payload)
    pending = next((root/'.wuwei/reports/pending').glob('*.md'))
    os.utime(pending, (1_000_000_000, 1_000_000_000))
    _, parent, _, save = native
    row = copy.deepcopy(FIXTURE['parent_delivery'])
    row['payload']['content'][0]['text'] = 'Message Type: FINAL_ANSWER\nTask name: /root\nSender: /root/codex_transcript_probe\nPayload:\nNATIVE FINAL'
    parent.append(row); save()
    out = hook.deliver(root, event, {'session_id':'id-1','transcript_path':payload['transcript_path']}, None, [])
    if event == 'Stop': assert out is None
    else:
        note = out['hookSpecificOutput']['additionalContext']
        assert 'report already notified' in note and '\nNATIVE FINAL' not in note


def test_native_report_concurrent_delivery_has_one_claim(root, native):
    from concurrent.futures import ThreadPoolExecutor
    payload = report(native, 'ONE CLAIM')
    hook.handle(root, 'SubagentStop', payload)
    planner = {'session_id':'id-1', 'transcript_path':payload['transcript_path']}
    with ThreadPoolExecutor(max_workers=4) as pool:
        found = list(pool.map(lambda _:hook.deliver(root, 'PreToolUse', planner, None, []),range(4)))
    assert sum(bool(o and 'ONE CLAIM' in str(o)) for o in found) == 1


@pytest.mark.parametrize('change', ['no-boundary','duplicate-path-call','later-final','missing-settings','future-settings'])
def test_native_boundary_identity_and_settings_edges(root, native, change):
    payload, parent, child, save = native
    if change == 'no-boundary': child[0]['payload'].pop('subagent_history_start_ordinal')
    if change == 'duplicate-path-call':
        for row in copy.deepcopy(parent[1:]):
            row['ordinal'] += 100; row['payload']['call_id'] = 'different-call'; parent.append(row)
    if change == 'later-final':
        child.append({**copy.deepcopy(child[1]), 'ordinal':200})
        child[-1]['payload']['content'][0]['text'] = 'LATER FINAL'
    if change == 'missing-settings':
        child.insert(1, {'ordinal':181, 'type':'turn_context', 'payload':{'model':{}, 'effort':[]}})
    if change == 'future-settings':
        child.append({'ordinal':200,'type':'turn_context','payload':{'model':'future','effort':'high'}})
    save(); hook.handle(root, 'SubagentStop', payload)
    if change in ('missing-settings','future-settings'):
        row = ws.rows(root, 'seat.stopped')[-1]['data']
        assert row['recorded_model'] == row['recorded_effort'] == 'unmeasured'
    else:
        assert not ws.rows(root, 'seat.stopped') and not ws.rows(root, 'attest')
