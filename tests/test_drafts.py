"""Owner draft queue uses real port wrappers and fake external boundaries."""

import json
from types import SimpleNamespace

import pytest

from wuwei import integrity, registry, state, workspace
from wuwei.__main__ import main

REAL_CONFIRM = integrity._host_confirm


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(integrity, '_host_confirm', lambda value, **kwargs: True)
    private = tmp_path / '.wuwei'
    private.mkdir()
    (private / 'config.toml').write_text(
        '[owner]\nname = "Pat Example"\npronouns = "they/them"\n'
        '[outbound]\nwork_channels = ["C1"]\n'
        '[voice.sources]\nexternal = ["C2"]\n')
    return tmp_path


@pytest.fixture
def sink(monkeypatch):
    calls = []
    monkeypatch.setattr(registry, 'record_none',
                        lambda *args, **kwargs: calls.append((args, kwargs)) or registry.Result(0))
    return calls


def queued(root, text='I can deliver this tomorrow.', **kwargs):
    adapter = registry.load('chat', workspace.load_config(root))
    result = adapter.post('C2', text, kwargs.get('thread'), root=root)
    assert result.exit == 1
    rows = state.read_state(root)['drafts']
    row = list(rows.values())[-1]
    assert row['id'] in result.reason
    return row


def test_approve_tier_is_stored_and_listed_without_send(root, sink, capsys):
    row = queued(root, thread='123.456')
    assert sink == []
    assert row['status'] == 'pending'
    assert row['channel'] == 'chat'
    assert row['destination'] == 'C2'
    assert row['inputs'] == {'channel': 'C2', 'text': row['text'], 'thread': '123.456'}
    assert row['created'] == workspace.now().isoformat()
    assert row['tier_reason'] and row['audience'] == 'external'
    assert row['item'] is None
    assert main(['drafts']) == 0
    out = capsys.readouterr().out
    assert row['id'] in out and row['text'] in out and 'C2' in out
    events = (workspace.day_dir(root) / 'events.jsonl').read_text()
    assert row['text'] not in events
    assert json.loads(events.splitlines()[-1])['kind'] == 'draft.created'


def test_queue_retains_adapter_operation_and_item(root, sink):
    state._write_state(lambda data: data['items'].update(A={'pr': 'org/repo#7'}),
                       root, reserved=False)
    config = workspace.load_config(root)
    config['adapters']['code_host'] = 'none'
    adapter = registry.load('code_host', config)
    result = adapter.comment('org/repo#7', 'I can deliver this tomorrow.', 'comment-1', root=root)
    assert result.exit == 1 and sink == []
    row, = state.read_state(root)['drafts'].values()
    assert row['operation'] == 'comment'
    assert row['destination'] == 'org/repo#7' and row['item'] == 'A'


@pytest.mark.parametrize('broken', ['policy', 'security', 'empty'])
def test_invalid_call_does_not_create_draft(root, sink, broken):
    from wuwei import security
    adapter = registry.load('chat', workspace.load_config(root))
    text = 'I can deliver this tomorrow.'
    if broken == 'policy':
        (root / '.wuwei/config.toml').write_text('broken [')
    elif broken == 'security':
        text = security.initialize(root / '.wuwei')['canary']
    else:
        text = ''
    result = adapter.post('C2', text, None, root=root)
    assert result.exit == (1 if broken == 'security' else 2)
    assert result.reason and sink == []
    assert not state.read_state(root).get('drafts')


def test_generic_writers_cannot_forge_drafts(root, capsys):
    state._write_state(lambda data: None, root, reserved=False)
    for key in ('drafts', 'drafts.fake.status'):
        assert main(['state', 'set', key, '"sent"']) == 1
        assert 'wuwei drafts' in capsys.readouterr().err
    for kind in ('draft.created', 'draft.sending', 'draft.sent', 'draft.failed', 'draft.dropped'):
        assert main(['event', kind, '{}']) == 1
        assert 'wuwei drafts' in capsys.readouterr().err
    assert not state.read_state(root).get('drafts')


@pytest.fixture
def port(root, monkeypatch):
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text() + '\n[adapters]\nchat = "slack"\n')
    adapter = registry.load('chat', workspace.load_config(root))
    original = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: adapter if kind == 'chat'
                        else original(kind, config))
    calls = []
    monkeypatch.setattr(adapter, '_send', lambda payload, *args: calls.append(payload.copy())
                        or {'channel': payload['channel'], 'ts': '123.456'})
    return adapter, calls


def edit_to(monkeypatch, text):
    original = registry.load

    def edit(path, command, root=None):
        path.write_text(text)
        return registry.Result(0)
    monkeypatch.setattr(registry, 'load', lambda kind, config: SimpleNamespace(edit=edit)
                        if kind == 'editor' else original(kind, config))


def test_owner_approval_sends_original_once(root, port):
    row = queued(root, thread='1.2')
    assert main(['drafts', 'approve', row['id']]) == 0
    assert port[1] == [{'channel': 'C2', 'text': row['text'], 'thread_ts': '1.2'}]
    stored = state.read_state(root)['drafts'][row['id']]
    assert stored['status'] == 'sent' and stored['final_text'] == row['text']
    assert stored['edit_size'] == 0 and stored['sent_unedited'] is True
    assert stored['decided'] == workspace.now().isoformat()
    assert main(['drafts', 'approve', row['id']]) == 1
    assert len(port[1]) == 1
    # An owner decision never authorizes another seat call with the same text.
    queued(root)
    assert len(port[1]) == 1


def test_approve_without_terminal_is_owner_action(root, port, monkeypatch, capsys):
    import builtins
    row = queued(root)
    monkeypatch.setattr(integrity, '_host_confirm', REAL_CONFIRM)
    real_open = builtins.open

    def fake_open(name, *args, **kwargs):
        if name == '/dev/tty':
            raise OSError(6, 'Device not configured')
        return real_open(name, *args, **kwargs)
    monkeypatch.setattr(builtins, 'open', fake_open)
    capsys.readouterr()
    assert main(['drafts', 'approve', row['id']]) == 2
    assert 'this is an owner action: run it in a host terminal' in capsys.readouterr().err
    assert port[1] == []
    assert state.read_state(root)['drafts'][row['id']]['status'] == 'pending'


def test_approve_declined_digest_sends_nothing(root, port, monkeypatch, capsys):
    row = queued(root)
    monkeypatch.setattr(integrity, '_host_confirm', lambda value, **kwargs: False)
    capsys.readouterr()
    assert main(['drafts', 'approve', row['id']]) == 1
    assert 'drafts: owner confirmation declined' in capsys.readouterr().err
    assert port[1] == []
    assert state.read_state(root)['drafts'][row['id']]['status'] == 'pending'


def test_approve_digest_covers_id_and_final_text(root, port, monkeypatch):
    from hashlib import sha256
    row = queued(root)
    final = 'I can deliver this today.'
    edit_to(monkeypatch, final)
    seen = []
    monkeypatch.setattr(integrity, '_host_confirm',
                        lambda value, **kwargs: seen.append((value, kwargs['prompt'])) or True)
    assert main(['drafts', 'approve', row['id'], '--edit']) == 0
    (digest, prompt), = seen
    assert digest == sha256((row['id'] + '\n' + final).encode()).hexdigest()
    assert row['destination'] in prompt and final in prompt and 'type:' not in prompt


def test_editor_trailing_newline_counts_as_unedited(root, port, monkeypatch):
    row = queued(root)
    edit_to(monkeypatch, row['text'] + '\n')
    assert main(['drafts', 'approve', row['id'], '--edit']) == 0
    stored = state.read_state(root)['drafts'][row['id']]
    assert stored['sent_unedited'] is True
    assert stored['edit_size'] == 0
    assert stored['final_text'] == row['text']
    assert port[1][0]['text'] == row['text']


def test_owner_edit_records_before_after_and_lints(root, port, monkeypatch):
    row = queued(root, 'I can deliver this tomorrow.')
    final = 'I can deliver this today.'
    edit_to(monkeypatch, final)
    assert main(['drafts', 'approve', row['id'], '--edit']) == 0
    assert port[1][0]['text'] == final
    stored = state.read_state(root)['drafts'][row['id']]
    assert stored['text'] == row['text'] and stored['final_text'] == final
    assert stored['edit_size'] > 0 and stored['sent_unedited'] is False
    events = (workspace.day_dir(root) / 'events.jsonl').read_text()
    assert row['text'] not in events and final not in events


@pytest.mark.parametrize('failure,code', [('outward', 1), ('voice', 1), ('security', 1),
                                         ('editor', 2), ('adapter-change', 2)])
def test_presend_failures_leave_pending(root, port, monkeypatch, failure, code):
    row = queued(root)
    args = ['drafts', 'approve', row['id']]
    if failure == 'outward':
        edit_to(monkeypatch, 'Pat wrote this.')
        args += ['--edit']
    elif failure == 'voice':
        memory = root / '.wuwei/memory'
        memory.mkdir()
        (memory / 'voice.md').write_text('## external\n- never: tomorrow\n')
    elif failure == 'security':
        from wuwei import security
        marker = security.initialize(root / '.wuwei')['canary']
        edit_to(monkeypatch, marker)
        args += ['--edit']
    elif failure == 'editor':
        original = registry.load
        monkeypatch.setattr(registry, 'load', lambda kind, config: SimpleNamespace(
            edit=lambda *a, **k: registry.Result(2, reason='editor missing'))
            if kind == 'editor' else original(kind, config))
        args += ['--edit']
    else:
        path = root / '.wuwei/config.toml'
        path.write_text(path.read_text().replace('chat = "slack"', 'chat = "none"'))
    assert main(args) == code
    assert state.read_state(root)['drafts'][row['id']]['status'] == 'pending'
    assert port[1] == []


def test_drop_closes_without_sending(root, port):
    row = queued(root)
    assert main(['drafts', 'drop', row['id']]) == 0
    assert state.read_state(root)['drafts'][row['id']]['status'] == 'dropped'
    assert main(['drafts', 'approve', row['id']]) == 1
    assert main(['drafts', 'drop', row['id']]) == 1
    assert port[1] == []


@pytest.mark.parametrize('failure', ['error', 'invalid-result', 'interrupted'])
def test_uncertain_send_is_not_retried(root, port, monkeypatch, failure):
    row = queued(root)
    attempts = []

    def send(*args):
        attempts.append(1)
        if failure == 'error':
            raise TimeoutError('private provider text')
        if failure == 'interrupted':
            raise KeyboardInterrupt()
        return registry.Result(7)
    monkeypatch.setattr(port[0], '_send', send)
    assert main(['drafts', 'approve', row['id']]) == 2
    assert state.read_state(root)['drafts'][row['id']]['status'] in ('sending', 'failed')
    assert main(['drafts', 'approve', row['id']]) == 1
    assert attempts == [1]


def test_concurrent_approval_claims_before_transport(root, port, monkeypatch):
    from wuwei import drafts
    row = queued(root)
    attempts = []

    def send(payload, *args):
        attempts.append(payload)
        result = drafts.approve(root, row['id'])
        assert result.exit == 1
        return {'channel': 'C2', 'ts': '1.2'}
    monkeypatch.setattr(port[0], '_send', send)
    assert main(['drafts', 'approve', row['id']]) == 0
    assert len(attempts) == 1


@pytest.mark.parametrize('script,code', [
    ('bin/wuwei drafts approve draft-test', 1),
    ('python3 -P -m wuwei drafts approve draft-test --edit', 1),
    ('bin/wuwei drafts drop draft-test', 1),
    ('env X=1 bin/wuwei drafts approve draft-test', 1),
    ('sh -c "bin/wuwei drafts approve draft-test"', 1),
    ('bin/wuwei drafts approve "$ID"', 1),
    ('for x in a; do bin/wuwei drafts approve "$x"; done', 2),
    ('bin/wuwei drafts', 0),
    ('python3 -m pytest -q', 0),
    ('for x in a; do echo "$x"; done', 0),
    ('export X=1', 0),
])
def test_seat_cannot_decide_drafts(root, script, code):
    from wuwei.guards.protect_state import check_bash
    state._write_state(lambda data: data['seats'].update(builder={
        'id': 'builder', 'role': 'builder', 'item': 'A', 'status': 'running'}),
        root, reserved=False)
    result = check_bash({'cwd': str(root), 'tool_name': 'Bash',
                        'session_id': 'builder', 'tool_input': {'command': script}})
    assert result[0] == code
    if code:
        assert result[1]


def test_draft_guard_outside_workspace_is_clean(tmp_path, monkeypatch):
    from wuwei.guards.protect_state import check_bash
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert check_bash({'cwd': str(tmp_path), 'tool_name': 'Bash', 'tool_input': {
        'command': 'for x in a; do bin/wuwei drafts approve "$x"; done'}}) == (0, '')


def test_voice_metrics_use_successful_sends_per_audience(root, port, monkeypatch):
    from wuwei import metrics
    assert metrics.collect(root)['voice_drafts'] == 'unmeasured'
    first = queued(root, 'I can deliver this tomorrow.')
    assert main(['drafts', 'approve', first['id']]) == 0
    second = queued(root, 'I can deliver this tomorrow.')
    edit_to(monkeypatch, 'I can deliver this today.')
    assert main(['drafts', 'approve', second['id'], '--edit']) == 0
    dropped = queued(root)
    assert main(['drafts', 'drop', dropped['id']]) == 0
    queued(root)
    result = metrics.collect(root)['voice_drafts']
    size = state.read_state(root)['drafts'][second['id']]['edit_size']
    assert result == {'external': {'sent': 2, 'share_sent_unedited': .5,
                                   'edit_sizes': [size]}}


def test_cockpit_lists_pending_drafts_read_only(root, port):
    from wuwei.commands.dashboard import cockpit_snapshot
    row = queued(root)
    dropped = queued(root)
    assert main(['drafts', 'drop', dropped['id']]) == 0
    directory = workspace.day_dir(root)
    before = [(directory / name).read_bytes() for name in ('state.json', 'events.jsonl')]
    result = cockpit_snapshot(directory)['drafts']
    assert len(result) == 1 and result[0]['id'] == row['id']
    assert result[0]['text'] == row['text']
    assert result[0]['approve_command'] == f"bin/wuwei drafts approve {row['id']}"
    assert before == [(directory / name).read_bytes() for name in ('state.json', 'events.jsonl')]


@pytest.mark.parametrize('bad', [None, [], {'bad': {}}, {'bad': {'status': 'sent'}}])
def test_malformed_drafts_fail_closed(root, bad):
    from wuwei import metrics
    from wuwei.commands.dashboard import cockpit_snapshot
    state._write_state(lambda data: data.update(drafts=bad), root, reserved=False)
    assert main(['drafts']) == 2
    with pytest.raises(ValueError):
        metrics.collect(root)
    with pytest.raises(ValueError):
        cockpit_snapshot(workspace.day_dir(root))


@pytest.mark.parametrize('script', [
    "bin/w'uw'ei dra'fts' approve draft-test",
    "bin/wuw\\ei dra\\fts drop draft-test",
])
def test_quoted_host_action_cannot_bypass_guard(root, script):
    from wuwei.guards.protect_state import check_bash
    assert check_bash({'cwd': str(root), 'tool_name': 'Bash',
                       'tool_input': {'command': script}})[0] == 1


def test_multifield_edit_preserves_destination(root, monkeypatch):
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text() + '\n[adapters]\ntracker = "linear"\n')
    adapter = registry.load('tracker', workspace.load_config(root))
    original = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: adapter if kind == 'tracker'
                        else original(kind, config))
    calls = []
    monkeypatch.setattr(adapter, '_query', lambda *a, **k: calls.append((a, k)))
    result = adapter.create({'title': 'A proposal', 'description': 'More detail',
                             'teamId': 'team-id'}, root=root)
    assert result.exit == 1
    row, = state.read_state(root)['drafts'].values()
    assert row['destination'] == 'team-id'
    edit_to(monkeypatch, json.dumps({'draft.title': 'New proposal',
                                   'draft.description': 'New detail', 'draft.team': 'elsewhere'}))
    assert main(['drafts', 'approve', row['id'], '--edit']) == 2
    assert state.read_state(root)['drafts'][row['id']]['status'] == 'pending'
    assert calls == []


@pytest.mark.parametrize('script', [
    'python3 -P -mwuwei drafts approve draft-test',
    'python3 -P -mwu\\wei drafts drop draft-test',
])
def test_attached_module_cannot_bypass_owner_guard(root, script):
    from wuwei.guards.protect_state import check_bash
    assert check_bash({'cwd': str(root), 'tool_name': 'Bash',
                       'tool_input': {'command': script}})[0] == 1


def test_dm_approval_uses_destination_voice_profile(root, port, monkeypatch):
    monkeypatch.setenv('SLACK_OWNER_DM_CHANNEL', 'D123')
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('external = ["C2"]', 'external = ["C2", "D123"]'))
    memory = root / '.wuwei/memory'
    memory.mkdir()
    (memory / 'voice.md').write_text('## external\n- never: tomorrow\n')
    assert port[0].dm('I can deliver this tomorrow.', root=root).exit == 1
    row, = state.read_state(root)['drafts'].values()
    assert row['audience'] == 'external'
    assert main(['drafts', 'approve', row['id']]) == 1
    assert port[1] == []
    assert state.read_state(root)['drafts'][row['id']]['status'] == 'pending'


@pytest.mark.parametrize('script,code', [
    ('python3 -Pmwuwei drafts approve draft-test', 1),
    ('python3 -PBmwuwei drafts drop draft-test', 1),
    ('python3 -P -m wuwei.__main__ drafts approve draft-test', 2),
    ('python3 -P cli/wuwei/__main__.py drafts approve draft-test', 2),
    ('python3 -c "from wuwei import drafts; drafts.approve(1,2)"', 2),
    ('python3 cli/wuwei/__main__.py drafts approve draft-test', 2),
    ('python3 -c "from wuwei import mcp; mcp.decide()"', 2),
])
def test_python_entrypoint_forms_cannot_bypass_guard(root, script, code):
    from wuwei.guards.protect_state import check_bash
    assert check_bash({'cwd': str(root), 'tool_name': 'Bash',
                       'tool_input': {'command': script}})[0] == code


def test_draft_style_finding_is_recorded_and_never_blocks(root, port, monkeypatch):
    from wuwei import drafts
    row = queued(root, 'I can deliver this tomorrow. This is not just a fix but a rewrite. We delve into it.')
    assert row['style'] == ['not-x-but-y', 'stock-word']
    data = state.read_state(root)
    data['drafts'][row['id']].pop('style')
    assert drafts.read(data)[row['id']]['status'] == 'pending'
    edit_to(monkeypatch, 'I can deliver this \u2014 tomorrow.')
    assert main(['drafts', 'approve', row['id'], '--edit']) == 1
    assert port[1] == []


TELLS = 'I can deliver this tomorrow. This is not just a fix but a rewrite. We delve into it.'


def outward_config(root, text):
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text() + f'\n[outward]\n{text}\n')


def ai_tells(root):
    path = workspace.day_dir(root) / 'events.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()] if path.is_file() else []
    return [row['payload'] for row in rows if row['kind'] == 'outward.ai_tells']


def test_humanize_warns_and_records_on_draft(root, sink, capsys):
    row = queued(root, TELLS)
    assert row['style'] == ['not-x-but-y', 'stock-word']
    assert ai_tells(root) == [{'kind': 'review', 'tells': ['not-x-but-y', 'stock-word'], 'draft': True}]
    assert 'warning: outward: ai tells' in capsys.readouterr().err


def test_humanize_strict_refuses_draft(root, sink):
    outward_config(root, 'humanize_strict = true')
    adapter = registry.load('chat', workspace.load_config(root))
    result = adapter.post('C2', TELLS, None, root=root)
    assert result.exit == 1
    assert 'not-x-but-y' in result.reason and 'stock-word' in result.reason
    assert 'humanizer' in result.reason
    assert not state.read_state(root).get('drafts')
    path = workspace.day_dir(root) / 'events.jsonl'
    assert not path.is_file() or 'draft.created' not in path.read_text()
    assert ai_tells(root) == [] and sink == []


def test_humanize_off_drafts_as_before(root, sink, capsys):
    outward_config(root, 'humanize = false\nhumanize_strict = true')
    row = queued(root, TELLS)
    assert row['style'] == ['not-x-but-y', 'stock-word']
    assert ai_tells(root) == []
    assert 'warning: outward: ai tells' not in capsys.readouterr().err


def test_humanize_kinds_select_dm(root, sink):
    outward_config(root, 'humanize_kinds = ["dm"]')
    queued(root, TELLS)
    assert ai_tells(root) == []
    adapter = registry.load('chat', workspace.load_config(root))
    assert adapter.dm(TELLS, root=root).exit == 1
    assert [row['kind'] for row in ai_tells(root)] == ['dm']


def test_approve_shows_humanize_findings(root, port, monkeypatch, capsys):
    row = queued(root, TELLS)
    assert main(['drafts']) == 0
    assert 'not-x-but-y' in capsys.readouterr().out
    prompts = []
    monkeypatch.setattr(integrity, '_host_confirm',
                        lambda value, **kwargs: prompts.append(kwargs['prompt']) or True)
    assert main(['drafts', 'approve', row['id']]) == 0
    assert len(port[1]) == 1
    prompt, = prompts
    assert row['destination'] in prompt and TELLS in prompt and 'not-x-but-y, stock-word' in prompt


def test_approve_strict_refuses_edited_tells(root, port, monkeypatch, capsys):
    row = queued(root)
    outward_config(root, 'humanize_strict = true')
    edit_to(monkeypatch, 'I can deliver this tomorrow. We delve into it.')
    assert main(['drafts', 'approve', row['id'], '--edit']) == 1
    output = capsys.readouterr()
    assert 'stock-word' in output.out + output.err
    assert port[1] == []
