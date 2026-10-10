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
        '[outbound]\ndefault_tier = "ask"\nwork_channels = ["C1"]\n'
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


def test_port_draft_reason_names_rule_and_card(root, sink):
    adapter = registry.load('chat', workspace.load_config(root))
    result = adapter.post('C2', 'I can deliver this tomorrow.', None, root=root)
    row = list(state.read_state(root)['drafts'].values())[-1]
    assert result.reason == (
        f"outward: draft {row['id']}: ask by rule 7 (topic=commitment) for C2: unknown destination C2, "
        'not in outbound.work_channels, connector default class company, outbound.commitment_patterns; '
        f"the owner decides: bin/wuwei drafts show {row['id']} --widget")


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


def strict(root):
    """The host confirmation runs under strict only (#493)."""
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text() + '[security]\nposture = "strict"\n')


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
    strict(root)
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
    strict(root)
    row = queued(root)
    monkeypatch.setattr(integrity, '_host_confirm', lambda value, **kwargs: False)
    capsys.readouterr()
    assert main(['drafts', 'approve', row['id']]) == 1
    assert 'drafts: owner confirmation declined' in capsys.readouterr().err
    assert port[1] == []
    assert state.read_state(root)['drafts'][row['id']]['status'] == 'pending'


def test_approve_digest_covers_id_and_final_text(root, port, monkeypatch):
    from hashlib import sha256
    strict(root)
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


def test_approve_outside_strict_needs_no_prompt(root, port, monkeypatch):
    from hashlib import sha256
    row = queued(root)
    monkeypatch.setattr(integrity, '_host_confirm', lambda *a, **k: pytest.fail('prompted'))
    assert main(['drafts', 'approve', row['id']]) == 0
    assert len(port[1]) == 1
    stored = state.read_state(root)['drafts'][row['id']]
    assert stored['answer'] == 'Send now'
    assert stored['text_sha256'] == sha256(row['text'].encode()).hexdigest()


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


def test_edit_outside_strict_still_asks_the_owner(root, port, monkeypatch):
    # #493 verify: an editor text never comes from a card, so --edit is confirmed like --file.
    row = queued(root)
    edit_to(monkeypatch, 'attacker text')
    prompts = []
    monkeypatch.setattr(integrity, '_host_confirm', lambda value, **kwargs: prompts.append(value) or False)
    assert main(['drafts', 'approve', row['id'], '--edit']) == 1
    assert len(prompts) == 1 and port[1] == []
    assert state.read_state(root)['drafts'][row['id']]['status'] == 'pending'
    monkeypatch.setattr(integrity, '_host_confirm', lambda value, **kwargs: prompts.append(value) or True)
    assert main(['drafts', 'approve', row['id'], '--edit']) == 0
    assert len(prompts) == 2 and port[1][0]['text'] == 'attacker text'


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
    assert result[0]['approve_command'] == f"{workspace.owner_cli(root)} drafts approve {row['id']}"
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
    strict(root)
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


DOCS_DRAFT = {'kind': 'page', 'item': 'X', 'title': 'X: Add a flag', 'body': 'Adds a flag.',
              'parent': 'https://www.notion.so/Docs-00000000111122223333444444444444', 'ref': ''}


def docs_queued(root, monkeypatch):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('[docs]\nsystem = "notion"\n')
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: pytest.fail('network'))
    adapter = registry.load('docs', workspace.load_config(root))
    result = adapter.write(DOCS_DRAFT, root=root)
    assert result.exit == 1 and result.reason.startswith('outward: draft ')
    row, = state.read_state(root)['drafts'].values()
    return row


def test_docs_write_is_queued(root, monkeypatch):
    row = docs_queued(root, monkeypatch)
    assert (row['channel'], row['operation'], row['adapter']) == ('docs', 'write', 'notion')
    assert row['item'] == 'X' and row['destination'] == DOCS_DRAFT['parent']
    assert row['status'] == 'pending' and row['inputs'] == {'draft': DOCS_DRAFT}
    from wuwei import drafts
    assert drafts.read(state.read_state(root))


def test_approving_a_docs_draft_records_the_write(root, monkeypatch):
    from test_docs_port import NOTION, replay
    state._write_state(lambda data: data['items'].update(
        X={'docs': {'value': 'new', 'reason': ''}}), root, reserved=False)
    row = docs_queued(root, monkeypatch)
    monkeypatch.setenv('NOTION_TOKEN', 'private-notion-token')
    calls = replay(monkeypatch, NOTION['create'])
    assert main(['drafts', 'approve', row['id']]) == 0
    assert [call[0] for call in calls] == ['POST']
    written = [json.loads(line)['payload'] for line in
               (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()
               if json.loads(line)['kind'] == 'docs.written']
    assert len(written) == 1 and written[0]['draft'] == row['id']
    assert written[0]['page'] == NOTION['create']['url']
    assert state.read_state(root)['items']['X']['docs']['value'] == NOTION['create']['url']


def fake_tracker(monkeypatch, root, created=None):
    """A tracker module behind the real outward wrapper, recording sends."""
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text() + '\n[adapters]\ntracker = "linear"\n')
    sent = []

    def create(draft, *, root=None):
        sent.append(('create', draft))
        return registry.Result(0, created)

    def comment(item, text, category, *, root=None):
        sent.append(('comment', item, text, category))
        return registry.Result(0, {'id': 'comment-1'})
    for function in (create, comment):
        function.__module__ = 'adapters.tracker.linear'
    module = SimpleNamespace(create=registry.outward_operation('tracker')(create),
                             comment=registry.outward_operation('tracker')(comment))
    original = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: module if kind == 'tracker'
                        else original(kind, config))
    return module, sent


def test_tracker_comment_drafts_and_approves_through_comment(root, monkeypatch, capsys):
    module, sent = fake_tracker(monkeypatch, root)
    text = '[2026-09-29 item-1] Decision D-1: ship it. Outcome: yes.'
    result = module.comment('ENG-1', text, 'decisions', root=root)
    assert result.exit == 1 and sent == []
    row, = state.read_state(root)['drafts'].values()
    assert (row['channel'], row['operation'], row['text']) == ('tracker', 'comment', text)
    capsys.readouterr()
    assert main(['drafts', 'approve', row['id']]) == 0
    assert sent == [('comment', 'ENG-1', text, 'decisions')]
    assert capsys.readouterr().out.strip() == f"drafts: {row['id']} sent"


def test_approved_ticket_creation_is_recorded(root, monkeypatch, capsys):
    module, sent = fake_tracker(monkeypatch, root, {'id': 'ENG-9', 'url': 'https://example.test/ENG-9'})
    draft = {'title': 'Add export', 'description': 'Track: build', 'item': 'item-1',
             'category': 'items'}
    assert module.create(draft, root=root).exit == 1
    row, = state.read_state(root)['drafts'].values()
    capsys.readouterr()
    assert main(['drafts', 'approve', row['id']]) == 0
    # #741: the owner sees the id the tracker opened, ready to copy
    assert capsys.readouterr().out.strip() == (
        f"drafts: {row['id']} sent; ticket ENG-9 https://example.test/ENG-9")
    data = state.read_state(root)
    assert data['tickets'] == {'item-1': {'id': 'ENG-9', 'source': 'create'}}
    assert data['tracker_log'] == {'create:items:item-1:add export': {
        'outcome': 'written', 'ticket': 'ENG-9'}}
    events = [json.loads(line) for line in
              (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines()]
    created = [event['payload'] for event in events if event['kind'] == 'tracker.created']
    assert len(created) == 1 and created[0].items() >= {
        'class': 'items', 'subject': 'item-1', 'ticket': 'ENG-9', 'parent': None}.items()


def held(root, text='Thanks', channel='C9', tool='mcp__slack__post_message', **fields):
    """A Slack MCP call the outward guard holds (#493); returns its exit, reason and row."""
    from wuwei.guards.outward import check_tier
    code, reason = check_tier({'cwd': str(root), 'tool_name': tool, 'session_id': 'test',
                               'tool_input': {'text': text, 'channel': channel, **fields}})
    rows = state.read_state(root).get('drafts', {})
    return code, reason, next((row for row in rows.values() if row['id'] in reason), None)


def card(capsys, draft_id):
    assert main(['drafts', 'show', draft_id, '--widget']) == 0
    widget, = json.loads(capsys.readouterr().out)
    return widget


def test_card_drop_names_the_workspace(root):
    from wuwei import drafts
    row = {'id': 'draft-test', 'tier_reason': 'approval tier', 'adapter': 'mcp', 'destination': 'C1', 'text': 'Hi'}
    widget = drafts.widget(row, workspace.load_config(root), root)
    options = {option['label']: option['description'] for option in widget['options']}
    assert f"{workspace.owner_cli(root)} drafts drop draft-test" in options['Drop']


def test_card_for_a_held_tool_call(root, capsys):
    path = root / '.wuwei/config.toml'  # learn off: the card names no outbound learn (#492).
    path.write_text(path.read_text().replace('[outbound]\ndefault_tier = "ask"\n', '[outbound]\ndefault_tier = "ask"\nlearn = "off"\n'))
    _, _, row = held(root)
    widget = card(capsys, row['id'])
    assert widget['header'] == 'Draft' and widget['record'] == f"{workspace.owner_cli(root)} drafts approve {row['id']}"
    question = widget['question']
    assert row['id'] in question and 'C9' in question and 'mcp__slack__post_message' in question
    assert 'ask by rule 9 (audience=company) for C9: unknown destination C9, not in outbound.work_channels' in question and 'Thanks' in question
    labels = [option['label'] for option in widget['options']]
    assert labels == ['Send now (Recommended)', 'Send with an edit', 'Keep as draft', 'Always ask for this channel']
    text = {option['label']: option['description'] for option in widget['options']}
    assert f"{workspace.owner_cli(root)} drafts approve {row['id']} --file" in text['Send with an edit']
    assert f"{workspace.owner_cli(root)} drafts drop {row['id']}" in text['Keep as draft']
    assert 'outbound learn' not in text['Send now (Recommended)']
    assert main(['drafts', 'show', row['id']]) == 0
    assert json.loads(capsys.readouterr().out)['id'] == row['id']


def test_card_for_a_port_draft(root, sink, capsys):
    row = queued(root)
    widget = card(capsys, row['id'])
    assert 'ask by rule 7 (topic=commitment) for C2' in widget['question'] and 'C2' in widget['question']
    assert widget['options'][0]['label'] == 'Send now (Recommended)'


def test_strict_recommends_keep_for_a_tier_rule(root, sink, capsys):
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text() + '[security]\nposture = "strict"\n')
    row = queued(root)
    assert card(capsys, row['id'])['options'][0]['label'] == 'Keep as draft (Recommended)'
    _, _, row = held(root)
    assert card(capsys, row['id'])['options'][0]['label'] == 'Send now (Recommended)'


def test_card_names_outbound_learn_when_on(root, capsys, monkeypatch):
    _, _, row = held(root)
    load = workspace.load_config

    def learning(start=None):
        config = load(start)
        config['outbound']['learn'] = 'card'
        return config
    monkeypatch.setattr(workspace, 'load_config', learning)
    send = card(capsys, row['id'])['options'][0]['description']
    assert 'bin/wuwei outbound learn' in send and 'C9' in send


def test_card_offers_owner_identity_for_unknown_dm(root, capsys, monkeypatch):
    # #495: a DM held because the owner's identity is unknown offers to learn it on the card.
    tool = 'mcp__00000000-0000-4000-8000-000000000001__slack_send_message'
    _, reason, row = held(root, channel='U01', tool=tool)
    assert 'unknown DM recipient U01' in reason
    load = workspace.load_config

    def learning(start=None):
        config = load(start)
        config['outbound']['learn'] = 'card'
        return config
    monkeypatch.setattr(workspace, 'load_config', learning)
    send = card(capsys, row['id'])['options'][0]['description']
    assert f'bin/wuwei outbound learn --tool {tool} --owner <file>' in send


def test_show_unknown_or_decided_draft_exits_one(root, capsys):
    assert main(['drafts', 'show', 'draft-' + '0' * 32, '--widget']) == 1
    assert 'unknown draft ID' in capsys.readouterr().err
    _, _, row = held(root)
    assert main(['drafts', 'drop', row['id']]) == 0
    capsys.readouterr()
    assert main(['drafts', 'show', row['id']]) == 1
    assert 'draft is dropped' in capsys.readouterr().err


def test_approve_with_a_file(root, port, capsys):
    row = queued(root)
    reply = root / 'reply.txt'
    reply.write_text('I can deliver this today.')
    assert main(['drafts', 'approve', row['id'], '--file', str(reply)]) == 0
    assert port[1][0]['text'] == 'I can deliver this today.'
    stored = state.read_state(root)['drafts'][row['id']]
    assert stored['answer'] == 'Send with an edit' and stored['edit_size'] > 0
    assert stored['sent_unedited'] is False


def test_approve_file_is_linted_and_newline_is_unedited(root, port, capsys):
    row = queued(root)
    reply = root / 'reply.txt'
    reply.write_text('I can deliver this\u2014today.')
    assert main(['drafts', 'approve', row['id'], '--file', str(reply)]) == 1
    assert state.read_state(root)['drafts'][row['id']]['status'] == 'pending' and port[1] == []
    reply.write_text(row['text'] + '\n')
    assert main(['drafts', 'approve', row['id'], '--file', str(reply)]) == 0
    stored = state.read_state(root)['drafts'][row['id']]
    assert stored['sent_unedited'] is True and port[1][0]['text'] == row['text']
    with pytest.raises(SystemExit) as exit:
        main(['drafts', 'approve', row['id'], '--file', str(reply), '--edit'])
    assert exit.value.code == 2


def events_of(root, kind):
    return [{key: row['payload'][key] for key in ('id', 'tool')} for row in
            map(json.loads, (workspace.day_dir(root) / 'events.jsonl').read_text().splitlines())
            if row['kind'] == kind]


def test_approved_tool_draft_passes_its_call_once(root, capsys, monkeypatch):
    from datetime import timedelta
    from hashlib import sha256
    from wuwei.guards.outward import check_tier
    monkeypatch.setattr(integrity, '_host_confirm', lambda *a, **k: pytest.fail('prompted'))
    _, _, row = held(root)
    assert main(['drafts', 'approve', row['id']]) == 0
    assert 'repeat the same call to C9 within 3600 seconds' in capsys.readouterr().out
    stored = state.read_state(root)['drafts'][row['id']]
    assert stored['status'] == 'approved' and stored['answer'] == 'Send now'
    assert stored['text_sha256'] == sha256(b'Thanks').hexdigest()
    assert stored['decided'] == workspace.now().isoformat()
    assert stored['expires'] == (workspace.now() + timedelta(seconds=3600)).isoformat()
    assert events_of(root, 'draft.approved') == [{'id': row['id'], 'tool': 'mcp__slack__post_message'}]
    call = {'cwd': str(root), 'tool_name': 'mcp__slack__post_message', 'session_id': 'test',
            'tool_input': {'text': 'Thanks', 'channel': 'C9'}}
    assert check_tier(call) == (0, '')
    assert events_of(root, 'draft.sent') == [{'id': row['id'], 'tool': 'mcp__slack__post_message'}]
    assert state.read_state(root)['drafts'][row['id']]['status'] == 'sent'
    code, reason, again = held(root)
    assert code == 1 and again['id'] != row['id']


@pytest.mark.parametrize('change', ['tool', 'channel', 'text', 'expired'])
def test_allowance_matches_tool_destination_text_and_time(root, monkeypatch, change):
    _, _, row = held(root)
    assert main(['drafts', 'approve', row['id']]) == 0
    call = {'text': 'Thanks', 'channel': 'C9', 'tool': 'mcp__slack__post_message'}
    if change == 'expired':
        monkeypatch.setenv('WUWEI_NOW', '2026-09-29T13:00:01Z')
    else:
        call[change] = {'tool': 'mcp__slack__send_message', 'channel': 'C8', 'text': 'Thanks!'}[change]
    code, _, other = held(root, **call)
    assert code == 1 and other['id'] != row['id']
    assert state.read_state(root)['drafts'][row['id']]['status'] == 'approved'


def test_draft_ttl_is_configured_in_seconds(root, capsys):
    from datetime import timedelta
    outward_config(root, 'draft_ttl = 120')
    _, _, row = held(root)
    assert main(['drafts', 'approve', row['id']]) == 0
    expires = state.read_state(root)['drafts'][row['id']]['expires']
    assert expires == (workspace.now() + timedelta(seconds=120)).isoformat()
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('draft_ttl = 120', 'draft_ttl = 30'))
    with pytest.raises(workspace.ConfigError, match='draft_ttl'):
        workspace.load_config(root)


def test_approved_port_draft_passes_any_tool_once(root, sink, capsys):
    from wuwei.guards.outward import check_tier
    row = queued(root)
    assert main(['drafts', 'approve', row['id']]) == 0
    stored = state.read_state(root)['drafts'][row['id']]
    assert stored['status'] == 'approved' and 'tool' not in stored and sink == []
    call = {'cwd': str(root), 'tool_name': 'mcp__slack__post_message', 'session_id': 'test',
            'tool_input': {'text': row['text'], 'channel': 'C2'}}
    assert check_tier(call) == (0, '')
    assert check_tier(call)[0] == 1


def test_allowance_cannot_be_forged_or_carry_a_canary(root, monkeypatch, capsys):
    from wuwei import security
    assert main(['event', 'draft.approved', '{}']) == 1
    marker = security.initialize(root / '.wuwei')['canary']
    with monkeypatch.context() as patch:
        patch.setattr(security, 'outbound', lambda *a, **k: (0, ''))
        _, _, row = held(root, f'Thanks {marker}')
        assert main(['drafts', 'approve', row['id']]) == 0
    code, reason, _ = held(root, f'Thanks {marker}')
    assert code == 1 and 'security' in reason
    assert state.read_state(root)['drafts'][row['id']]['status'] == 'approved'


def test_strict_recommends_keep_for_a_client_row(root, capsys):
    # #496: a draft a tier row held for a known audience keeps; an unknown audience is learnable.
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('[outbound]\ndefault_tier = "ask"\n', '[outbound]\ndefault_tier = "ask"\nexternal_channels = ["C2"]\n')
                    + '[security]\nposture = "strict"\n')
    _, reason, row = held(root, channel='C2')
    assert 'ask by rule 5 (audience=client) for C2' in reason
    assert card(capsys, row['id'])['options'][0]['label'] == 'Keep as draft (Recommended)'


def test_card_adds_a_tier_row(root, capsys):
    # #496 review F2: the owner adds a row from the card, never by typing config.
    _, reason, row = held(root, text='Thanks @u07', channel='C1')
    assert 'ask by rule 9 (audience=company) for @u07' in reason
    options = {option['label']: option['description'] for option in card(capsys, row['id'])['options']}
    assert list(options) == ['Send now (Recommended)', 'Send with an edit', 'Keep as draft',
                             'Always send to this person']
    assert f"{workspace.owner_cli(root)} drafts approve {row['id']} --always" in options['Always send to this person']
    assert f"{workspace.owner_cli(root)} drafts drop {row['id']}" in options['Keep as draft']
    assert held(root, text='@u07 thanks', channel='C1')[0] == 1
    assert main(['drafts', 'approve', row['id'], '--always']) == 0
    config = workspace.load_config(root)
    assert [{key: value for key, value in tier.items() if value} for tier in config['outbound']['tiers']] == [
        {'person': 'u07', 'tier': 'send'}]
    code, reason, _ = held(root, text='@u07 thanks', channel='C1')
    assert code == 0, reason
    capsys.readouterr()
    _, _, row = held(root)  # C9: an unknown destination.
    options = {option['label']: option['description'] for option in card(capsys, row['id'])['options']}
    assert 'Always ask for this channel' in options and 'Always send to this person' not in options
    assert main(['drafts', 'approve', row['id'], '--always']) == 0
    assert [tier['channel'] for tier in workspace.load_config(root)['outbound']['tiers']] == ['', 'C9']
    capsys.readouterr()
    _, _, row = held(root, text='I will ship it tomorrow @u08', channel='C1')  # A topic row: no Always.
    labels = [option['label'] for option in card(capsys, row['id'])['options']]
    assert not any(label.startswith('Always') for label in labels)
    assert main(['drafts', 'approve', row['id'], '--always']) == 1
    assert 'no Always option' in capsys.readouterr().err


def test_card_always_sends_in_the_channel_threads(root, capsys):
    # #526: a thread held because its participants are not learned offers a channel thread row.
    _, reason, row = held(root, channel='C1', thread_ts='1.2')
    assert 'for C1/1.2: participants of thread 1.2 not learned' in reason
    options = {option['label']: option['description'] for option in card(capsys, row['id'])['options']}
    assert "Always send in this channel's threads" in options
    assert 'later thread replies in C1 go out without a card' in options["Always send in this channel's threads"]
    assert main(['drafts', 'approve', row['id'], '--always']) == 0
    assert [{key: value for key, value in tier.items() if value}
            for tier in workspace.load_config(root)['outbound']['tiers']] == [
        {'channel': 'C1', 'topic': 'thread', 'tier': 'send'}]
    code, reason, _ = held(root, channel='C1', thread_ts='9.9')
    assert code == 0, reason
