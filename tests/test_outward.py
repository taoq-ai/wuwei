"""Outward policy tables use local state and in-process hook calls only."""

import io
import json
import sys
from types import SimpleNamespace

import pytest

from wuwei import workspace


@pytest.fixture
def configured(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00Z')
    directory = tmp_path / '.wuwei'
    directory.mkdir()
    (directory / 'config.toml').write_text('[owner]\nname = "Pat Example"\npronouns = "they/them"\n')
    from wuwei import registry
    original_load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, config: (
        SimpleNamespace(resolve=lambda *a, **k: registry.Result(0, {'sha': 'abc1234' + '0' * 33}))
        if kind == 'vcs' else original_load(kind, config)))
    with (directory / 'config.toml').open('a') as stream:
        stream.write('\n[[repos]]\nname = "demo"\npath = "demo"\ndefault_branch = "main"\n')
    with (directory / 'config.toml').open('a') as stream:
        stream.write('\n[outbound]\nwork_channels = ["chat", "C1"]\n')
    from fakes.integrity import seed
    seed(tmp_path)
    return tmp_path, workspace.load_config(tmp_path)


@pytest.mark.parametrize('text,code,reason', [
    ('fixed in abc1234', 0, ''),
    ('I fixed this.', 0, ''),
    ('per Pat, the fix is in', 1, 'owner'),
    ('per PAT EXAMPLE, the fix is in', 1, 'owner'),
    ('per _Pat_, the fix is in', 1, 'owner'),
    ('P\u200bat fixed it', 1, 'owner'),
    ('per \uff30\uff41\uff54, the fix is in', 1, 'owner'),
    ('They fixed it', 1, 'pronoun'),
    ('_They_ fixed it', 1, 'pronoun'),
    ('It is theirs', 1, 'pronoun'),
    ('The theme is ready', 0, ''),
    ('drafts are with the owner', 1, 'internal'),
    ('_drafts_ are with the owner', 1, 'internal'),
    ('the _queue_ is empty', 1, 'internal'),
    ('DRAFTS\nARE WITH THE OWNER', 1, 'internal'),
    ('drafts pending', 1, 'internal'),
    ('pending drafts', 1, 'internal'),
    ('The agent wrote this', 1, 'internal'),
    ('The build queue is empty', 1, 'internal'),
    ('fixed\u2014in abc1234', 1, 'banned'),
    ('Done \U0001f600', 1, 'emoji'),
    ('Done \u2764\ufe0f', 1, 'emoji'),
    ('Done \U0001f1ec\U0001f1e7', 1, 'emoji'),
    ('Done 1\ufe0f\u20e3', 1, 'emoji'),
    ('Done \u00a9', 0, ''),
    ('Done \u25b6', 1, 'emoji'),
    ('', 2, 'text'), ('  ', 2, 'text'), (None, 2, 'text'),
])
def test_lint_table(configured, text, code, reason):
    from wuwei.outward import lint
    result = lint(text, 'chat', configured[1])
    assert result[0] == code
    assert reason in result[1]
    if code:
        assert text is None or not text.strip() or text not in result[1]


@pytest.mark.parametrize('change,text,channel,code', [
    ({'patterns': ['secret\\s+routine']}, 'SECRET routine', 'chat', 1),
    ({'patterns': ['internal_state']}, 'internal_state', 'chat', 1),
    ({'patterns': []}, 'drafts pending', 'chat', 0),
    ({'patterns': ['[']}, 'fixed in abc1234', 'chat', 2),
    ({'banned_characters': ['!']}, 'Ready!', 'chat', 1),
    ({'banned_characters': []}, 'Ready\u2014yes \U0001f600', 'chat', 0),
    ({'max_length': {'chat': 3}}, 'abc', 'chat', 0),
    ({'max_length': {'chat': 3}}, 'abcd', 'chat', 1),
    ({'max_length': {'chat': 3}}, 'abcd', 'tracker', 0),
    ({'max_length': {'chat': 0}}, 'abc', 'chat', 2),
    ({'patterns': [1]}, 'abc', 'chat', 2),
])
def test_configured_lint(configured, change, text, channel, code):
    from wuwei.outward import lint
    config = configured[1]
    config['outward'].update(change)
    assert lint(text, channel, config)[0] == code


def test_missing_owner_fails_closed(configured):
    from wuwei.outward import lint
    config = configured[1]
    config['owner']['name'] = ''
    assert lint('fixed in abc1234', 'chat', config)[0] == 2


def test_rule_defaults_and_configured_tool_patterns(configured):
    root, config = configured
    assert config['outward']['patterns']
    assert config['outward']['banned_characters'] == ['emoji', '\u2014', '\u2015', '\u2e3a', '\u2e3b']
    assert config['outward']['tool_patterns']
    config['outward']['tool_patterns'][0]['channel'] = 'changed'
    assert workspace.load_config(root)['outward']['tool_patterns'][0]['channel'] != 'changed'
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('\n[[outward.tool_patterns]]\npattern = "mcp__custom__send"\nchannel = "customer"\n')
    assert workspace.load_config(root)['outward']['tool_patterns'] == [
        {'pattern': 'mcp__custom__send', 'channel': 'customer'}]


def payload(root, text='fixed in abc1234', tool='mcp__slack__post_message', **fields):
    return {'cwd': str(root), 'tool_name': tool,
            'tool_input': {'text': text, 'channel': 'chat', **fields},
            'hook_event_name': 'PreToolUse', 'session_id': 'test',
            'transcript_path': str(root / 'transcript.jsonl'), 'tool_use_id': 'test-call'}


@pytest.mark.parametrize('text,code', [
    ('fixed in abc1234', 0), (' FIXED IN ABC1234. ', 0),
    ('The cache is thread safe.', 1), ('I disagree with the proposal.', 1),
    ('This is out of scope.', 1), ('fixed in abc1234\nThis is thread safe.', 1),
    ('fixed in abc1234; ship it', 1), ('fixed in abc123', 1),
])
def test_send_or_draft(configured, text, code):
    from wuwei.guards.outward import check_tier as check
    result = check(payload(configured[0], text))
    assert result[0] == code
    if code:
        assert result[1].startswith('outward: draft ') and 'bin/wuwei drafts show ' in result[1]


@pytest.mark.parametrize('text', ['The cache is thread safe.', 'I disagree with the proposal.',
                                  'This is out of scope.', 'thanks <@U09>'])
def test_send_umbrella_lets_team_talk(configured, text):
    # #527: with outbound.default_tier = send, what no narrowing row holds goes out in a work
    # channel; a client channel and sensitive text still ask.
    from wuwei.guards.outward import check_tier as check
    root = configured[0]
    outbound_line(root, 'default_tier = "send"')
    assert check(payload(root, text)) == (0, '')
    outbound_line(root, 'external_channels = ["C2"]')
    assert check(payload(root, 'I will ship it tomorrow', channel='C2'))[0] == 1
    assert check(payload(root, 'Your salary review is in'))[0] == 1


def test_send_umbrella_drops_the_broad_rows(configured):
    from wuwei import outward
    root, config = configured
    assert len(outward.table(config)) == 10
    outbound_line(root, 'default_tier = "send"')
    rows = [row for row, _, _ in outward.table(workspace.load_config(root))]
    assert len(rows) == 7 and not any(row in outward.BROAD_ROWS for row in rows)


def test_no_local_approval_producer():
    from wuwei import outward, state
    from wuwei.guards.outward import GUARDS
    assert all(guard.event == 'PreToolUse' for guard in GUARDS)
    assert not hasattr(state, 'record_draft_answer')
    assert not hasattr(outward, 'draft_digest')


def test_local_approval_cannot_authorize_send(configured):
    import hashlib
    from wuwei import registry
    root, config = configured
    inputs = {'text': 'A technical claim.'}
    digest = hashlib.sha256(json.dumps(
        {'tool_name': 'chat.dm', 'tool_input': inputs},
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    directory = workspace.day_dir(root)
    directory.mkdir(parents=True)
    (directory / 'state.json').write_text(json.dumps({'approved_drafts': {'draft-1': {
        'status': 'approved', 'draft_id': 'draft-1', 'digest': digest,
        'ts': workspace.now().isoformat(),
        'question_id': f'Approve draft draft-1 digest {digest}?'}}}))
    result = registry.load('chat', config).dm(**inputs, root=root)
    assert result.exit == 1
    assert result.reason.startswith('outward: draft ')


@pytest.mark.parametrize('text,code,decision', [
    ('fixed in abc1234', 0, 'send'), ('A technical claim.', 1, 'draft'),
    ('', 1, 'draft'), (None, 2, 'draft'),
])
def test_reusable_classification(configured, text, code, decision):
    from wuwei import outward
    classify = getattr(outward, 'classify', None)
    assert callable(classify)
    assert classify(text, *configured, {'channel': 'chat'}) == (code, decision)


@pytest.mark.parametrize('tool,inputs,code', [
    ('mcp__slack__post_message', {'text': 'fixed in abc1234'}, 1),
    ('mcp__slack__send_message', {'text': 'fixed in abc1234'}, 1),
    ('mcp__linear__create_issue', {'draft': {'title': 'fixed in abc1234'}}, 1),
    ('mcp__slack__slack_post_message', {'text': 'fixed in abc1234', 'channel': 'C1'}, 0),
    ('mcp__slack__chat_postMessage', {'text': 'per Pat, the fix is in'}, 1),
    ('mcp__slack__slack_reply_to_thread', {'text': 'drafts are with the owner'}, 1),
    ('mcp__linear__create_comment', {'body': 'fixed in abc1234', 'issue_id': 'issue-1'}, 1),
    ('mcp__linear__create_comment', {'body': 'Phase: gate.', 'issueId': 'ENG-1', 'category': 'progress'}, 1),
    ('mcp__linear__update_issue', {'description': 'drafts are with the owner'}, 1),
    ('mcp__linear__create_issue', {'draft': {'title': 'fixed in abc1234', 'description': 'They wrote it'}}, 1),
    ('mcp__slack__post_message', {'message': 'drafts are with the owner'}, 1),
    ('mcp__slack__post_message', {'body': 'fixed in abc1234'}, 1),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'body': 'This is thread safe.'}, 1),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'blocks': [{'text': 'per Pat'}]}, 1),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'approved': True}, 1),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'approved_draft_id': 'draft-1'}, 1),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'attachments': []}, 1),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'channel': {'text': 'hidden'}}, 2),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'draft': {'draft': {'text': 'hidden'}}}, 2),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'title': None}, 1),
    ('mcp__slack__post_message', {'text': ['fixed in abc1234']}, 1),
    ('mcp__slack__post_message', {'draft': 'fixed in abc1234'}, 2),
    ('mcp__slack__post_message', {}, 1), ('mcp__slack__post_message', [], 2),
    ('tracker.claim', {'item': 'issue-1'}, 0),
    ('mcp__slack__search', {'query': 'per Pat'}, 0),
    ('other.chat.post', {'text': 'per Pat'}, 0),
    ('Read', {}, 0), ('Bash', {}, 0),
    ('', {}, 2), (None, {}, 2),
])
def test_routing_and_bypass_table(configured, tool, inputs, code):
    from wuwei.guards.outward import check_tier as check
    call = payload(configured[0], tool=tool)
    call['tool_input'] = inputs
    assert check(call)[0] == code


@pytest.mark.parametrize('rules,tool,code', [
    ([{'pattern': 'custom_send', 'channel': 'customer'}], 'custom_send', 1),
    ([{'pattern': 'custom_send', 'channel': 'customer'}], 'prefix_custom_send', 0),
    ([{'pattern': '[', 'channel': 'customer'}], 'custom_send', 2),
    ([{'pattern': '.*', 'channel': 'chat'}, {'pattern': 'custom_send', 'channel': 'other'}], 'custom_send', 2),
])
def test_configured_matching(configured, monkeypatch, rules, tool, code):
    from wuwei.guards.outward import check_tier as check
    root, config = configured
    config['outward']['tool_patterns'] = rules
    monkeypatch.setattr(workspace, 'load_config', lambda root: config)
    assert check(payload(root, 'per Pat, the fix is in', tool=tool))[0] == code


@pytest.mark.parametrize('specific', [False, True])
def test_channel_limits_cannot_be_bypassed(configured, monkeypatch, specific):
    from wuwei.guards.outward import check_lint as check
    root, config = configured
    config['outward']['max_length'] = {'slack': 100, 'C1': 5} if specific else {'slack': 5, 'C1': 100}
    monkeypatch.setattr(workspace, 'load_config', lambda root: config)
    assert check(payload(root, channel='C1'))[0] == 1


@pytest.mark.parametrize('text,invalid,code,warning', [
    ('per Pat, the fix is in', False, 1, False),
    ('The cache is thread safe.', False, 1, False),
    ('fixed in abc1234', True, 2, False),
])
def test_standard_profile(configured, monkeypatch, capsys, text, invalid, code, warning):
    from wuwei.guards.outward import check_lint, check_tier
    root, config = configured
    config['profile'] = 'standard'
    if invalid:
        config['outward']['patterns'] = ['[']
    monkeypatch.setattr(workspace, 'load_config', lambda root: config)
    check = check_tier if text == 'The cache is thread safe.' else check_lint
    assert check(payload(root, text))[0] == code
    output = capsys.readouterr()
    assert ('warning' in output.err) == warning
    assert text not in output.err


@pytest.mark.parametrize('code', [0, 1, 2])
def test_hook_integration(configured, monkeypatch, capsys, code):
    from wuwei.commands.hook import run
    root, _ = configured
    call = payload(root, 'per Pat, the fix is in' if code == 1 else 'fixed in abc1234')
    if code == 2:
        call['tool_input'] = []
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(call)))
    assert run(SimpleNamespace(event='PreToolUse')) == (2 if code else 0)
    output = capsys.readouterr()
    if code:
        assert json.loads(output.out)['hookSpecificOutput']['permissionDecision'] == 'deny'
        assert output.err and 'per Pat' not in output.err
    else:
        assert output.out == output.err == ''


def test_missing_workspace_and_policy(tmp_path, monkeypatch):
    from wuwei.guards.outward import check_tier as check
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert check(payload(tmp_path))[0] == 0
    (tmp_path / '.wuwei').mkdir()
    assert check(payload(tmp_path))[0] == 2
    (tmp_path / '.wuwei/config.toml').write_text('[owner]\nname = [')
    assert check(payload(tmp_path))[0] == 2
    assert check({'tool_name': 'Bash'}) == (0, '')


@pytest.mark.parametrize('tool,code', [
    ('mcp__claude_ai_Slack__slack_send_message', 1),
    ('mcp__slack_123__slack_schedule_message', 1),
    ('mcp__plugin_slack_slack__chat_update', 1),
    ('mcp__claude_ai_Linear__save_issue', 1),
    ('mcp__linear__save_issue', 1),
    ('mcp__plugin_linear_linear__save_comment', 1),
    ('mcp__github__add_issue_comment', 1),
    ('mcp__plugin_github_github__create_pull_request_review_comment', 1),
    ('mcp__unknown__send_message', 2),
    ('mcp__unknown__post_message', 2),
    ('mcp__unknown__reply', 2),
    ('mcp__unknown__schedule_message', 2),
    ('mcp__unknown__create_issue', 1),
    ('mcp__unknown__update_issue', 1),
    ('mcp__unknown__save_issue', 1),
    ('mcp__unknown__comment', 2),
    ('mcp__unknown__chat_write', 2),
    ('mcp__unknown__read', 0),
    ('mcp__unknown__message_user', 2),
    ('mcp__unknown__notify', 2),
    ('mcp__gmail__draft_email', 1),
    ('mcp__unknown__respond_to_event', 2),
    ('mcp__slack__edit_message', 1),
    ('mcp__slack__slack_add_list_record', 2),
    ('mcp__unknown__target_lookup', 0),
    ('mcp__unknown__anything', 0),
])
def test_real_mcp_write_names(configured, tool, code):
    from wuwei.guards.outward import check_tier as check
    result = check(payload(configured[0], 'A technical claim.', tool=tool))
    assert result[0] == code
    if code == 2:
        assert f'bin/wuwei outbound learn --tool {tool}' in result[1]


@pytest.mark.parametrize('tool', ['Skill', 'ToolSearch', 'AskUserQuestion', 'LS', 'Read',
                                  'mcp__unknown__send', 'mcp__slack__post', None])
def test_scope_before_payload_and_policy(tmp_path, monkeypatch, tool):
    from wuwei.guards.outward import check_tier as check
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert check({'cwd': str(tmp_path), 'tool_name': tool, 'tool_input': None}) == (0, '')


@pytest.mark.parametrize('tool', ['Skill', 'ToolSearch', 'AskUserQuestion', 'LS'])
def test_irrelevant_native_tools_ignore_broken_policy(configured, tool):
    from wuwei.guards.outward import check_tier as check
    root, _ = configured
    (root / '.wuwei/config.toml').write_text('broken [')
    assert check({'cwd': str(root), 'tool_name': tool, 'tool_input': None}) == (0, '')


@pytest.mark.parametrize('kind,operation,inputs', [
    ('chat', 'post', {'channel': 'C1', 'text': 'A technical claim.', 'thread': None}),
    ('chat', 'dm', {'text': 'A technical claim.'}),
    ('tracker', 'create', {'draft': {'title': 'A technical claim.'}}),
    ('code_host', 'comment', {'ref': 'org/repo#1', 'text': 'A technical claim.', 'thread': None}),
])
@pytest.mark.parametrize('mode', ['missing', 'mechanical', 'lint', 'broken-policy'])
def test_port_boundary(configured, monkeypatch, kind, operation, inputs, mode):
    from wuwei import registry
    root, config = configured
    adapter = registry.load(kind, config)
    performed = []
    # Real adapter port, fake network/unavailable sink.
    monkeypatch.setattr(registry, 'record_none', lambda *a, **k: performed.append(a) or registry.Result(0))
    if kind == 'code_host':
        monkeypatch.setattr(adapter, '_run', lambda *a, **k: performed.append(a) or {'id': 1, 'html_url': 'https://github.com/org/repo/issues/1#issuecomment-1'})
    if mode == 'lint':
        if kind == 'tracker':
            inputs = {'draft': {'title': 'per Pat, the fix is in'}}
        else:
            inputs = {**inputs, 'text': 'per Pat, the fix is in'}
    if mode == 'mechanical':
        inputs = ({'draft': {'title': 'fixed in abc1234'}} if kind == 'tracker'
                  else {**inputs, 'text': 'fixed in abc1234'})
    if mode == 'broken-policy':
        (root / '.wuwei/config.toml').write_text('broken [')
    result = getattr(adapter, operation)(**inputs, root=root)
    sends = mode == 'mechanical' and operation == 'post'
    expected = 2 if mode == 'broken-policy' else 0 if sends else 1
    assert result.exit == expected, result
    assert bool(performed) == sends


def test_only_mcp_defaults_and_no_textless_operations(configured):
    from wuwei.guards.outward import check_tier as check
    root, config = configured
    assert all(row['pattern'].startswith('mcp__') for row in config['outward']['tool_patterns'])
    for tool in ('tracker.claim', 'tracker.transition'):
        assert check(payload(root, tool=tool))[0] == 0


@pytest.mark.parametrize('text', ['P\u00e1t fixed it', 'P\u034fat fixed it',
    'P\u20ddat fixed it', 'P\u200dat fixed it', '\U0001d413hey fixed it'])
def test_unicode_identity_obfuscation(configured, text):
    from wuwei.outward import lint
    assert lint(text, 'chat', configured[1])[0] == 1


@pytest.mark.parametrize('text', ['<@U12345> fixed it', '@pat-dev fixed it', 'per PAT-DEV, ready'])
def test_owner_handles(configured, text):
    from wuwei.outward import lint
    root, _ = configured
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('[owner]', '[owner]\nhandles = ["U12345", "pat-dev"]'))
    config = workspace.load_config(root)
    assert lint(text, 'chat', config)[0] == 1


def head(result):
    """(code, reason before its #362 next step)."""
    return result[0], result[1].split(';')[0]


@pytest.mark.parametrize('text', ['the agents are ready', 'an agent checked it',
    'sentinel finished', 'two seats are ready', 'a seat finished', 'WUWEI checked it',
    'queued for tomorrow', 'the owner approved', 'Claude checked it', 'CODEX checked it',
    'a subagent checked it', 'subagents checked it', 'steward finished',
    'gate verdict is ready', 'gate verdicts are ready'])
def test_internal_state_defaults(configured, text):
    from wuwei.outward import lint
    assert head(lint(text, 'chat', configured[1])) == (1, 'outward: internal state pattern')


@pytest.mark.parametrize('char,code', [('\u2015', 1), ('\u2e3a', 1), ('\u2e3b', 1),
                                      ('\u2192', 0), ('\u21ff', 0), ('\u00a9', 0), ('\u00ae', 0)])
def test_character_default_corrections(configured, char, code):
    from wuwei.outward import lint
    assert lint('Ready ' + char, 'chat', configured[1])[0] == code


@pytest.mark.parametrize('exits,code', [([], 1), ([1], 1), ([2], 2), ([1, 0], 0), ([0], 0)])
def test_mechanical_sha_must_resolve(configured, monkeypatch, exits, code):
    from wuwei import registry
    from wuwei.guards.outward import check_tier as check
    root, config = configured
    config['repos'] = [{'name': str(i), 'path': f'repo-{i}'} for i in range(len(exits))]
    monkeypatch.setattr(workspace, 'load_config', lambda root: config)
    calls = []
    def resolve(repo, sha, root=None):
        calls.append((repo, sha))
        return registry.Result(exits[len(calls) - 1], {'sha': 'abc1234' + '0' * 33})
    monkeypatch.setattr(registry, 'load', lambda kind, config: SimpleNamespace(resolve=resolve))
    assert check(payload(root))[0] == code
    assert all(str(repo).startswith(str(root)) and sha == 'abc1234' for repo, sha in calls)



@pytest.mark.parametrize('override', [None, '', 'missing'])
def test_ports_require_workspace(tmp_path, monkeypatch, override):
    from wuwei import registry
    monkeypatch.chdir(tmp_path)
    if override is None:
        monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    else:
        monkeypatch.setenv('WUWEI_WORKSPACE', override)
    calls = []

    @registry.outward_operation('chat')
    def post(text, root=None):
        calls.append(text)
        return registry.Result(0)

    result = post('fixed in abc1234', root=tmp_path)
    assert result.exit == 2
    assert result.reason
    assert not calls


@pytest.mark.parametrize('override', ['', 'missing'])
@pytest.mark.parametrize('tool', ['Bash', 'mcp__slack__post_message'])
def test_hook_invalid_workspace_override(configured, monkeypatch, override, tool):
    from wuwei.guards.outward import check_tier as check
    monkeypatch.setenv('WUWEI_WORKSPACE', override)
    code, reason = check(payload(configured[0], tool=tool))
    assert code == 2
    assert reason


@pytest.mark.parametrize('verb', ['get', 'list', 'search', 'read', 'find', 'fetch',
                                  'query', 'describe', 'view', 'lookup'])
def test_unmatched_mcp_read_prefixes(configured, verb):
    from wuwei.guards.outward import check_tier as check
    assert check(payload(configured[0], tool=f'mcp__unknown__{verb}_item')) == (0, '')


@pytest.mark.parametrize('tool,code', [
    ('mcp__slack__slack_search_public', 0),
    ('mcp__slack__slack_read_channel', 0),
    ('mcp__claude_ai_Slack__slack_read_thread', 0),
    ('mcp__plugin_slack_slack__slack_list_user_channels', 0),
    ('mcp__linear__linear_list_issues', 0),
    ('mcp__search__search_items', 0),
    ('mcp__slack__slack_send_message', 1),
    ('mcp__x__notify', 2),
    ('mcp__x__slack_read_thread', 0),
    ('mcp__slack__slack_readwrite', 0),
    ('mcp__x__readwrite', 0),
])
def test_service_prefixed_mcp_reads(configured, tool, code):
    from wuwei.guards.outward import check_tier as check
    assert check(payload(configured[0], 'A technical claim.', tool=tool))[0] == code


@pytest.mark.parametrize('tool,inputs', [
    ('mcp__slack__slack_reply_to_thread',
     {'text': 'fixed in abc1234', 'channel_id': 'C1', 'thread_ts': '1234567890.123456'}),
    ('mcp__linear__create_comment', {'body': 'fixed in abc1234', 'issueId': 'issue-1'}),
    ('mcp__github__add_issue_comment',
     {'body': 'fixed in abc1234', 'owner': 'org', 'repo': 'demo', 'issue_number': 42}),
    ('mcp__github__create_pull_request_review_comment',
     {'body': 'fixed in abc1234', 'owner': 'org', 'repo': 'demo', 'pull_number': 42}),
])
def test_default_tool_payload_metadata(configured, tool, inputs):
    from wuwei.guards.outward import check_tier as check
    call = payload(configured[0], tool=tool)
    call['tool_input'] = inputs
    # Metadata parses, but an unverified chat thread is never eligible.
    assert check(call)[0] == 1


def test_channel_id_limit(configured, monkeypatch):
    from wuwei.guards.outward import check_lint as check
    root, config = configured
    config['outward']['max_length'] = {'C1': 5}
    monkeypatch.setattr(workspace, 'load_config', lambda root: config)
    assert check(payload(root, channel_id='C1'))[0] == 1


@pytest.mark.parametrize('value', [True, 1.5, {}, []])
def test_invalid_numeric_metadata(configured, value):
    from wuwei.guards.outward import check_tier as check
    assert check(payload(configured[0], issue_number=value))[0] == 2


@pytest.mark.parametrize('base', ['\u00a9', '\u00ae', '\u2192', 'A'])
def test_emoji_presentation_selector(configured, base):
    from wuwei.outward import lint
    assert head(lint('Ready ' + base + '\ufe0f', 'chat', configured[1])) == (1, 'outward: emoji is banned')
    assert lint('Ready ' + base, 'chat', configured[1])[0] == 0


def test_owner_addressed_lint_skips_third_person_rules_only(tmp_path, monkeypatch):
    from wuwei import outward, remote
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    (tmp_path / '.wuwei').mkdir()
    path = tmp_path / '.wuwei/config.toml'
    path.write_text('[owner]\nname = ""\n')
    config = workspace.load_config(tmp_path)
    assert outward.lint('Report ready.', 'chat', config)[0] == 2
    assert outward.lint('Report ready.', 'chat', config, to_owner=True) == (0, '')
    path.write_text('[owner]\nname = "Dry Run Operator"\npronouns = "they/them"\n')
    config = workspace.load_config(tmp_path)
    assert outward.lint(remote.CONFIRM, 'chat', config)[0] == 1
    assert outward.lint(remote.CONFIRM, 'chat', config, to_owner=True) == (0, '')
    assert outward.lint('They look done.', 'chat', config, to_owner=True) == (0, '')
    assert outward.lint('wuwei is busy.', 'chat', config, to_owner=True)[0] == 1
    inputs = {'text': remote.CONFIRM, 'channel': 'D1'}
    assert outward.check_lint(inputs, tmp_path, config, {'chat'}, to_owner=True) == (0, '')
    assert outward.check_lint(inputs, tmp_path, config, {'chat'})[0] == 1


def test_shepherd_seat_drafts_what_would_send(configured, monkeypatch):
    from wuwei import outward, registry
    root, config = configured
    assert outward.classify('fixed in abc1234', root, config, {'channel': 'chat'}) == (0, 'send')
    monkeypatch.setenv('WUWEI_SEAT_ROLE', 'shepherd')
    assert outward.classify('fixed in abc1234', root, config, {'channel': 'chat'}) == (1, 'draft')
    calls = []

    @registry.outward_operation('chat')
    def post(channel, text, root=None):
        calls.append(text)
        return registry.Result(0)

    result = post('C1', 'fixed in abc1234', root=root)
    assert result.exit == 1 and result.reason.startswith('outward: draft ')
    assert not calls


@pytest.mark.parametrize('name,hit,miss', [
    ('not-x-but-y', 'It is not just a fix but a rewrite.', 'It is a fix, but small.'),
    ('closer', 'We shipped. Let that sink in.', 'We shipped on Monday.'),
    ('run-up', "Here's the thing: tests fail.", 'Tests fail on main.'),
    ('saying', 'At its core, this is a cache.', 'This is a cache.'),
    ('dash', 'Two options \u2013 A or B.', 'Two options: A or B.'),
    ('dash', 'Two options \u2014 A or B.', 'Two options: A or B.'),
    ('inflation', 'It plays a key role in releases.', 'It runs before releases.'),
    ('sales', 'A stunning new parser.', 'A new parser.'),
    ('stock-word', 'We delve into the logs.', 'We read the logs.'),
    ('bold-label', '- **Speed**: faster', '- Speed: faster'),
    ('chat-leftover', 'Let me know if you want more.', 'The rest is in the record.'),
])
def test_tells_table(name, hit, miss):
    from wuwei import outward
    assert [row[0] for row in outward.TELLS].count(name) == 1
    assert outward.tells(hit) == [name]
    assert outward.tells(miss) == []


def test_tells_never_change_the_lint(configured):
    from wuwei import outward
    _, config = configured
    text = 'This is not just a fix but a rewrite. We delve into it.'
    assert outward.tells(text) == ['not-x-but-y', 'stock-word']
    assert outward.tells('Plain text.') == []
    assert outward.tells('Run `git checkout -- file` on the first underscore-separated word.') == []
    assert outward.tells('Two options -- A or B.') == ['dash']
    assert outward.lint(text, 'C1', config) == (0, '')
    assert head(outward.lint('A fix \u2014 now.', 'C1', config)) == (1, 'outward: banned character')


TELL_TEXT = 'This is not just a fix but a rewrite. We delve into it.'


def ai_tells(root):
    path = workspace.day_dir(root) / 'events.jsonl'
    lines = path.read_text().splitlines() if path.is_file() else []
    return [json.loads(line)['payload'] for line in lines
            if json.loads(line)['kind'] == 'outward.ai_tells']


@pytest.mark.parametrize('channel,is_dm,kind', [
    ('chat', True, 'dm'), ('chat', False, 'review'), ('slack', False, 'review'),
    ('tracker', False, 'tracker'), ('code_host', False, 'pr'), ('docs', False, 'docs'),
    ('customer', False, None),
])
def test_humanize_lint_kinds(configured, capsys, channel, is_dm, kind):
    from wuwei import outward
    root, config = configured
    inputs = {'text': TELL_TEXT, **({'is_dm': True} if is_dm else {})}
    code, reason = outward.humanize_lint(inputs, root, config, {channel})
    assert code == 0
    if kind is None:
        assert reason == '' and ai_tells(root) == []
        return
    assert 'not-x-but-y' in reason and 'stock-word' in reason and 'humanizer' in reason
    assert ai_tells(root) == [{'kind': kind, 'tells': ['not-x-but-y', 'stock-word'], 'draft': False}]
    assert TELL_TEXT not in (workspace.day_dir(root) / 'events.jsonl').read_text()
    assert 'warning:' in capsys.readouterr().err


@pytest.mark.parametrize('change,inputs,code', [
    ({'humanize_strict': True}, {'text': TELL_TEXT}, 1),
    ({'humanize': False}, {'text': TELL_TEXT}, 0),
    ({'humanize_kinds': ['dm']}, {'text': TELL_TEXT}, 0),
    ({}, {'text': 'We use `delve` in code.'}, 0),
    ({}, {'text': 1}, 0),
])
def test_humanize_lint_gates(configured, change, inputs, code):
    from wuwei import outward
    root, config = configured
    config['outward'].update(change)
    result = outward.humanize_lint(inputs, root, config, {'chat'}, draft=True)
    assert result[0] == code
    assert ('not-x-but-y' in result[1]) == (code == 1)
    assert ai_tells(root) == []


def test_check_call_send_humanizes(configured, monkeypatch, capsys):
    from wuwei import outward
    root, config = configured
    monkeypatch.setattr(outward, 'classify', lambda *a, **k: (0, 'send'))
    inputs = {'channel': 'C1', 'text': 'Fixed the parser.'}
    assert outward.check_call(inputs, root, config, {'chat'}) == (0, '')
    assert ai_tells(root) == []
    inputs['text'] = 'We delve into the parser.'
    assert outward.check_call(inputs, root, config, {'chat'}) == (0, '')
    assert ai_tells(root) == [{'kind': 'review', 'tells': ['stock-word'], 'draft': False}]
    config['outward']['humanize_strict'] = True
    code, reason = outward.check_call(inputs, root, config, {'chat'})
    assert code == 1 and 'stock-word' in reason
    config['profile'] = 'standard'
    assert outward.check_call(inputs, root, config, {'chat'}) == (0, '')
    assert 'hook.warning' in (workspace.day_dir(root) / 'events.jsonl').read_text()


def test_hook_lint_humanizes_mcp_writes(configured, monkeypatch, capsys):
    from wuwei.guards.outward import check_lint
    root, config = configured
    monkeypatch.setattr(workspace, 'load_config', lambda root: config)
    call = payload(root, 'We delve into the race.', tool='mcp__linear__create_comment')
    assert check_lint(call)[0] == 0
    assert ai_tells(root) == [{'kind': 'tracker', 'tells': ['stock-word'], 'draft': False}]
    assert check_lint(payload(root, 'Fixed the race.', tool='mcp__linear__create_comment'))[0] == 0
    assert len(ai_tells(root)) == 1
    config['outward']['humanize_strict'] = True
    code, reason = check_lint(call)
    assert code == 1 and 'stock-word' in reason


def test_every_free_text_adapter_write_goes_through_the_port():
    import inspect
    from wuwei import outward, registry, shepherd
    exempt = {('tts', 'speak'): 'local', ('redactor', 'redact'): 'local',
              ('code_host', 'create_pr'): 'shepherd.raise_pr runs outward.lint and outward.humanize_lint',
              # #422: a table of validated counts; telemetry send runs security.outbound itself.
              ('code_host', 'issue'): 'telemetry.validate and security.outbound in wuwei telemetry send'}
    adapter_exempt = {('docs', 'write', 'markdown'):
                      "a file in the item's pull request; docs.page runs outward.humanize_lint"}
    port = 'outward_operation.<locals>.decorate.<locals>.call'
    checked = 0
    for kind, operations in registry.PARAMETERS.items():
        for operation, parameters in operations.items():
            if not set(parameters) & (outward.TEXT_FIELDS | {'draft'}) or (kind, operation) in exempt:
                continue
            for name in registry.known(kind):
                if (kind, operation, name) in adapter_exempt:
                    continue
                module = registry.load(kind, {'adapters': {kind: name}})
                function = getattr(module, operation)
                assert function.__code__.co_qualname == port, (kind, name, operation)
                checked += 1
    assert checked
    assert 'humanize_lint' in inspect.getsource(shepherd.raise_pr)
    from wuwei.commands import telemetry
    assert 'security.outbound' in inspect.getsource(telemetry._send)
    from wuwei import docs
    assert 'humanize_lint' in inspect.getsource(docs.page)


def test_owner_facing_templates_are_plain():
    import ast
    from pathlib import Path
    from wuwei import outward
    cli = Path(__file__).resolve().parents[1] / 'cli/wuwei'
    for name in ('control_plane.py', 'remote.py', 'listen.py', 'report.py', 'decision.py', 'retro.py',
                 'interview.py', 'watch.py', 'commands/decision.py', 'commands/status.py'):
        for node in ast.walk(ast.parse((cli / name).read_text(encoding='utf-8'))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert '\u2014' not in node.value and outward.tells(node.value) == [], (name, node.value)


def docs_inputs(body='Adds a flag.'):
    return {'draft': {'kind': 'page', 'item': 'X', 'title': 'T', 'body': body, 'parent': 'p', 'ref': ''}}


def test_docs_kind_drafts_unless_auto(configured):
    from wuwei import outward
    root, config = configured
    inputs = docs_inputs()
    assert outward.classify('T\nAdds a flag.', root, config, inputs, kind='docs') == (1, 'draft')
    config['docs']['auto'] = ['page']
    assert outward.classify('T\nAdds a flag.', root, config, inputs, kind='docs') == (0, 'send')
    assert outward.classify('T\nA salary change.', root, config, docs_inputs('A salary change.'),
                            kind='docs') == (1, 'draft')
    config['docs']['auto'] = ['report']
    assert outward.classify('T\nAdds a flag.', root, config, inputs, kind='docs') == (1, 'draft')


def test_docs_tool_patterns(configured):
    import re
    root, config = configured
    def channel(tool):
        return next((row['channel'] for row in config['outward']['tool_patterns']
                     if re.fullmatch(row['pattern'], tool, re.IGNORECASE)), None)
    assert channel('mcp__notion__notion-create-pages') == 'docs'
    assert channel('mcp__atlassian__createConfluencePage') == 'docs'
    assert channel('mcp__atlassian__updateConfluencePage') == 'docs'
    assert channel('mcp__atlassian__createJiraIssue') is None
    assert channel('mcp__notion__notion-search') is None


@pytest.mark.parametrize('category,auto,expected', [
    ('progress', None, 'send'), ('pr', None, 'send'), ('close', None, 'send'),
    ('decisions', None, 'draft'), ('verdicts', None, 'draft'), ('items', None, 'draft'),
    ('bugs', None, 'draft'), ('bugs', '["bugs"]', 'send'), (None, None, 'draft'),
])
def test_tracker_auto_policy(configured, category, auto, expected):
    from wuwei import outward
    root, _ = configured
    if auto:
        with (root / '.wuwei/config.toml').open('a') as stream:
            stream.write(f'\n[tracker]\nauto = {auto}\n')
    config = workspace.load_config(root)
    text = '[2026-09-28 item-1] Phase: gate.'
    context = {'item': 'ENG-1', 'text': text, 'category': category}
    code, decision = outward.classify(text, root, config, context, kind='tracker', port=True)
    assert decision == expected and code == (0 if expected == 'send' else 1)
    nested = {'draft': {'title': text, 'item': 'item-1', 'category': category, 'parent': 'ENG-1'}}
    assert outward._text(nested) == ([text], [])
    assert outward.classify(text, root, config, nested, kind='tracker', port=True)[1] == expected


@pytest.mark.parametrize('text', ['[2026-09-28 item-1] Phase: gate, thanks @pat.',
                                  '[2026-09-28 item-1] Phase: gate; salary review.',
                                  '[2026-09-28 item-1] We will fix it by tomorrow.'])
def test_tracker_auto_still_drafts_people_and_sensitive_text(configured, text):
    from wuwei import outward
    root, config = configured
    assert outward.classify(text, root, config, {'item': 'ENG-1', 'text': text,
                                                 'category': 'progress'},
                            kind='tracker', port=True) == (1, 'draft')


@pytest.mark.parametrize('project,board,expected', [
    ('outside/repo', '', 'draft'), ('acme/app', '', 'send'), ('', '', 'send'),
    ('acme/app', 'outside/3', 'draft'),
])
def test_tracker_github_outside_code_host_orgs_drafts(configured, project, board, expected):
    from wuwei import outward
    root, config = configured
    config['adapters']['tracker'] = 'github'
    config['tracker'].update(project=project, board=board)
    config['outbound']['code_host_orgs'] = ['Acme']
    config['repos'][0]['name'] = 'acme/app'
    text = '[2026-09-28 item-1] Phase: gate.'
    assert outward.classify(text, root, config, {'item': 'acme/app#1', 'text': text,
                                                 'category': 'progress'},
                            kind='tracker', port=True)[1] == expected


@pytest.mark.parametrize('name,kind', [
    ('conversations_history', 'read'), ('channels_list', 'read'),
    ('conversations_search_messages', 'read'), ('slack_get_channel_history', 'read'),
    ('getConfluencePage', 'read'), ('get_message', 'read'),
    ('conversations_add_message', 'write'), ('chat_postMessage', 'write'), ('sendEmail', 'write'),
    ('push_files', 'write'), ('mark_all_notifications_read', 'write'),
    ('frobnicate', 'unknown'), ('slack_readwrite', 'unknown'), ('resolve-library-id', 'unknown'),
])
def test_name_words(name, kind):
    # #469: an unmatched MCP tool is a read, a write or unknown by the words of its name.
    from wuwei.guards.outward import READS, WRITES, tool_kind
    server = 'gmail' if name == 'get_message' else 'acme'
    assert tool_kind(f'mcp__{server}__{name}') == kind
    assert 'add' in WRITES and 'history' in READS


# #469: public tool names of common Slack, Linear and GitHub MCP servers (research.md).
RECORDED = {
    'slack': {
        'read': ['conversations_history', 'conversations_replies', 'conversations_search_messages',
                 'channels_list', 'slack_list_channels', 'slack_get_channel_history',
                 'slack_get_thread_replies', 'slack_get_users', 'slack_get_user_profile'],
        'draft': ['conversations_add_message', 'slack_post_message', 'slack_reply_to_thread',
                  'slack_add_reaction'],
        'learn': []},
    'linear': {
        'read': ['list_comments', 'list_cycles', 'get_document', 'list_documents', 'get_issue',
                 'get_issue_git_branch_name', 'list_issues', 'list_issue_statuses',
                 'get_issue_status', 'list_my_issues', 'list_issue_labels', 'list_projects',
                 'get_project', 'list_project_labels', 'list_teams', 'get_team', 'list_users',
                 'get_user', 'search_documentation'],
        'draft': ['create_comment', 'create_issue', 'update_issue'],
        'learn': ['create_project', 'update_project', 'create_issue_label']},
    'github': {
        'read': ['get_me', 'get_issue', 'get_issue_comments', 'list_issues', 'search_issues',
                 'get_pull_request', 'list_pull_requests', 'get_pull_request_files',
                 'get_pull_request_status', 'get_pull_request_comments',
                 'get_pull_request_reviews', 'get_pull_request_diff', 'get_file_contents',
                 'list_commits', 'get_commit', 'list_branches', 'search_code',
                 'search_repositories', 'search_users', 'list_tags', 'get_tag',
                 'list_notifications', 'get_notification_details', 'list_code_scanning_alerts',
                 'get_code_scanning_alert', 'list_secret_scanning_alerts',
                 'get_secret_scanning_alert', 'list_workflows', 'list_workflow_runs',
                 'get_workflow_run', 'get_job_logs'],
        # #492: an issue word resolves to the tracker channel by vocabulary.
        'draft': ['add_issue_comment', 'add_pull_request_review_comment_to_pending_review',
                  'create_issue', 'update_issue', 'assign_copilot_to_issue'],
        'learn': ['create_pull_request', 'update_pull_request',
                 'merge_pull_request', 'update_pull_request_branch', 'create_pull_request_review',
                 'create_pending_pull_request_review', 'submit_pending_pull_request_review',
                 'delete_pending_pull_request_review', 'create_and_submit_pull_request_review',
                 'request_copilot_review', 'create_branch',
                 'create_or_update_file', 'delete_file', 'push_files', 'create_repository',
                 'fork_repository', 'dismiss_notification', 'mark_all_notifications_read',
                 'manage_notification_subscription',
                 'manage_repository_notification_subscription', 'run_workflow',
                 'rerun_workflow_run', 'cancel_workflow_run']},
}


@pytest.mark.parametrize('tool,outcome', [
    (f'mcp__{server}__{name}', outcome) for server, lists in RECORDED.items()
    for outcome, names in lists.items() for name in names])
def test_recorded_server_tools(configured, tool, outcome):
    from wuwei.guards.outward import check_lint, check_tier
    call = payload(configured[0], 'A technical claim.', tool=tool)
    tier, lint = check_tier(call), check_lint(call)
    if outcome == 'read':
        assert tier == lint == (0, '')
    elif outcome == 'draft':
        assert tier[0] == 1 and tier[1].startswith('outward: draft ')
    else:
        assert tier[0] == lint[0] == 2
        assert f'bin/wuwei outbound learn --tool {tool}' in tier[1]
    assert outcome == 'read' or not tier == lint == (0, '')


def set_posture(root, name, outward_area=''):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write(f'\n[security]\nposture = "{name}"\n')
        if outward_area:
            stream.write(f'[security.areas]\noutward = "{outward_area}"\n')


@pytest.mark.parametrize('posture', ['observe', 'guarded', 'strict'])
def test_unmatched_write_names_learn(configured, posture):
    # #492: a write nothing resolves names the connector and the learn command, never config.
    from wuwei.guards.outward import check_lint, check_tier
    root = configured[0]
    set_posture(root, posture)
    for check in (check_tier, check_lint):
        code, reason = check(payload(root, 'A technical claim.', tool='mcp__acme__send_message'))
        assert code == 2 and 'connector acme' in reason
        assert 'bin/wuwei outbound learn --tool mcp__acme__send_message' in reason
        assert 'config set' not in reason


def test_invalid_mcp_name(configured):
    from wuwei.exits import PAYLOAD
    from wuwei.guards.outward import check_tier
    code, reason = check_tier(payload(configured[0], 'A technical claim.', tool="mcp__acme__send'x"))
    assert code == 2 and PAYLOAD in reason and "send'x" not in reason


def run_hook(monkeypatch, call):
    from wuwei.commands.hook import run
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(call)))
    return run(SimpleNamespace(event='PreToolUse'))


def test_why_shows_channel_and_draft(configured, monkeypatch, capsys):
    from wuwei.__main__ import main
    root = configured[0]
    monkeypatch.chdir(root)
    call = payload(root, 'A technical claim.', tool='mcp__slack__conversations_add_message',
                   channel_id='C1')
    assert run_hook(monkeypatch, call) == 2
    capsys.readouterr()
    assert main(['why', 'last', 'refusal']) == 0
    lines = capsys.readouterr().out.splitlines()
    assert any(line.startswith('rule: outward: draft draft-') for line in lines)
    assert any(line.startswith('fix: the owner decides: bin/wuwei drafts show draft-') for line in lines)


def unknown_events(root):
    from wuwei import watch
    return [row for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
            if row['kind'] == 'outward.unknown_tool']


@pytest.mark.parametrize('area,code,recorded', [('', 0, 1), ('off', 0, 0), ('block', 2, 0)])
def test_unknown_tool_recorded_once(configured, monkeypatch, area, code, recorded):
    # #469: under guarded an unknown tool passes with one nudge per tool per day.
    root = configured[0]
    set_posture(root, 'guarded', area)
    call = payload(root, 'A technical claim.', tool='mcp__acme__frobnicate')
    assert run_hook(monkeypatch, call) == code
    assert run_hook(monkeypatch, call) == code
    rows = unknown_events(root)
    assert len(rows) == recorded
    if rows:
        assert rows[0]['payload']['tool'] == 'mcp__acme__frobnicate'
        assert rows[0]['payload']['posture'] == 'guarded'
        assert 'bin/wuwei outbound learn --tool mcp__acme__frobnicate' in rows[0]['payload']['reason']


def test_unknown_tool_outside_workspace(tmp_path, monkeypatch):
    from wuwei.guards.outward import check_lint, check_tier
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    call = payload(tmp_path, 'A technical claim.', tool='mcp__acme__frobnicate')
    assert check_tier(call) == check_lint(call) == (0, '')
    assert not (tmp_path / '.wuwei').exists()


PROBES = ['conversations_search_messages', 'conversations_history', 'channels_list',
          'slack_search_messages', 'slack_get_channel_history']


@pytest.mark.parametrize('posture', ['observe', 'guarded', 'strict'])
@pytest.mark.parametrize('name', [*PROBES, 'conversations_add_message', 'slack_post_message',
                                  'acme frobnicate'])
def test_probe_tools(configured, monkeypatch, capsys, posture, name):
    # #469 acceptance: the owner's seven probes and an unknown name, through the hook.
    root = configured[0]
    set_posture(root, posture)
    server, _, name = name.rpartition(' ')
    tool = f'mcp__{server or "slack"}__{name}'
    call = payload(root, 'A technical claim.', tool=tool, channel_id='C1')
    code = run_hook(monkeypatch, call)
    err = capsys.readouterr().err
    if name in PROBES:
        assert code == 0
    elif server:
        assert code == (2 if posture == 'strict' else 0)
        assert posture != 'strict' or f'bin/wuwei outbound learn --tool {tool}' in err
    else:
        assert code == 2 and 'outward: draft draft-' in err


# #493: a held draft names the rule that forced it.
RULES = [
    # #496: a table decision names its row and the class evidence.
    ('Thanks', {'channel': 'C9'}, {}, 'ask by rule 9 (audience=company) for C9: unknown destination C9, '
     'not in outbound.work_channels, connector default class company'),
    ('Thanks @dev', {'channel': 'C1'}, {}, 'ask by rule 9 (audience=company) for @dev: unknown mention @dev, '
     'not an internal person in outbound.people, connector default class company'),
    ('I will ship it tomorrow', {'channel': 'C1'}, {}, 'ask by rule 7 (topic=commitment) for C1: C1 in '
     'outbound.work_channels as team, outbound.commitment_patterns'),
    ('Thanks', {'channel': 'C1'}, {'WUWEI_SEAT_ROLE': 'shepherd'},
     'headless seat: a headless shepherd seat posts drafts only'),
    ('Can you review my PR?', {'channel': 'C1'}, {},
     'review ping without a code-host link: the review request form with the PR link goes '
     'to shepherd.review_channel'),
    ('Thanks', {'channel': 'C1', 'is_dm': True}, {},
     'approval tier direct message for C1: every direct message drafts'),
    ('Thanks', {'channel': 'C1', 'thread_ts': '1.2'}, {},
     'approval tier thread for C1: chat threads draft until their participants are known'),
]


@pytest.mark.parametrize('text,context,env,rule', RULES)
def test_classify_names_the_rule(configured, monkeypatch, text, context, env, rule):
    from wuwei import outward
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    why = []
    assert outward.classify(text, *configured, {'text': text, **context}, kind='slack', why=why) == (1, 'draft')
    assert why == [rule] and '; ' not in why[0]


def test_classify_send_names_no_rule(configured):
    from wuwei import outward
    why = []
    assert outward.classify('fixed in abc1234', *configured, {'channel': 'C1'}, kind='slack', why=why) == (0, 'send')
    assert why == []


def test_check_tier_appends_the_rule(configured):
    from wuwei import outward
    root, config = configured
    inputs = {'text': 'Thanks', 'channel': 'C9'}
    expected = (1, outward.APPROVAL_REQUIRED + ': ' + RULES[0][3])
    assert outward.check_tier(inputs, root, config, {'slack'}) == expected
    assert outward.check_call(inputs, root, config, {'slack'}) == expected


HELD = r'^outward: draft (draft-[0-9a-f]{32}): ([^;]*); the owner decides: bin/wuwei drafts show \1 --widget$'


def test_guard_stores_and_names_the_draft(configured, monkeypatch):
    import re
    from wuwei import state
    from wuwei.guards.outward import check_tier
    root = configured[0]
    seen = {}
    for text, context, env, rule in RULES[:5]:
        with monkeypatch.context() as patch:
            for key, value in env.items():
                patch.setenv(key, value)
            code, reason = check_tier(payload(root, text, **context))
        match = re.fullmatch(HELD, reason)
        assert code == 1 and match and match[2] == rule, reason
        seen[match[1]] = rule
    assert len(seen) == 5
    rows = state.read_state(root)['drafts']
    for draft_id, rule in seen.items():
        row = rows[draft_id]
        assert (row['status'], row['operation'], row['adapter'], row['tool'], row['channel']) == (
            'pending', 'tool', 'mcp', 'mcp__slack__post_message', 'slack')
        assert row['tier_reason'].endswith(rule)
    assert rows[next(iter(seen))]['destination'] == 'C9'
    again = check_tier(payload(root, RULES[0][0], **RULES[0][1]))
    assert re.fullmatch(HELD, again[1])[1] == next(iter(seen))
    assert len(state.read_state(root)['drafts']) == 5


def test_hook_refusal_names_draft_and_why_reads_it(configured, monkeypatch, capsys):
    from wuwei.__main__ import main
    root = configured[0]
    monkeypatch.chdir(root)
    assert run_hook(monkeypatch, payload(root, 'Thanks', channel='C9')) == 2
    lines = capsys.readouterr().err.splitlines()
    draft_id = lines[0].split()[2].rstrip(':')
    assert lines[:2] == [
        f'outward: draft {draft_id}: {RULES[0][3]}; the owner decides: bin/wuwei drafts show {draft_id} --widget',
        'posture: outward = block (owner-only action; no setting lowers it)']
    assert main(['why', 'last', 'refusal']) == 0
    out = capsys.readouterr().out.splitlines()
    assert f'rule: outward: draft {draft_id}: {RULES[0][3]}' in out
    assert f'fix: the owner decides: bin/wuwei drafts show {draft_id} --widget' in out


# #492: claude.ai connectors put a UUID in the server segment and the brand in the tool name.
UUID = '00000000-0000-4000-8000-000000000001'


def opaque(name, server=UUID):
    return f'mcp__{server}__{name}'


def held_channel(root, reason):
    """The channel of the draft a #493 held reason names; None when the reason holds none."""
    import re
    from wuwei import state
    match = re.fullmatch(HELD, reason)
    return match and state.read_state(root)['drafts'][match[1]]['channel']


@pytest.mark.parametrize('name,channels', [
    ('conversations_add_message', {'slack'}), ('chat_postMessage', {'slack'}),
    ('add_reaction', {'slack'}), ('create_issue', {'tracker'}), ('add_issue_comment', {'tracker'}),
    ('create_draft', {'mail'}), ('label_message', {'mail'}), ('trash_thread', {'mail'}),
    ('append_block', {'docs'}), ('create_page', {'docs'}),
    ('create_issue_label', set()), ('send_message', set()), ('frobnicate_widget', set()),
    ('conversations_search_messages', set()), ('channels_list', set()),
    ('slack_search_public', set()),
    # Scope addition: camelCase, PR comments, Sentry-style writes; resolve-library-id stays out.
    ('addCommentToJiraIssue', {'tracker'}), ('createJiraIssue', {'tracker'}),
    ('getJiraIssue', set()), ('append_block_children', {'docs'}),
    ('add_pull_request_review_comment_to_pending_review', {'code_host'}),
    ('resolve_issue', {'other'}), ('mute_alert', {'other'}), ('update_alert_rule', {'other'}),
    ('resolve-library-id', set()),
])
def test_vocabulary(name, channels):
    from wuwei.guards.outward import resolve
    assert resolve(opaque(name), None) == channels


def events_of(root, kind):
    from wuwei import watch
    return [row for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
            if row['kind'] == kind]


def test_resolve_opaque(configured, monkeypatch, capsys):
    from wuwei.guards.outward import check_tier
    root = configured[0]
    monkeypatch.chdir(root)
    assert run_hook(monkeypatch, payload(root, 'A technical claim.',
                                         tool=opaque('conversations_search_messages'))) == 0
    assert events_of(root, 'hook.refusal') == [] and unknown_events(root) == []
    for name in ('slack_send_message', 'conversations_add_message'):
        code, reason = check_tier(payload(root, 'A technical claim.', tool=opaque(name)))
        assert code == 1 and held_channel(root, reason) == 'slack', reason


def write_config(root, text):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write(text)


def test_alias_resolves_and_reads_still_pass(configured):
    from wuwei.guards.outward import check_lint, check_tier
    root = configured[0]
    write_config(root, f'\n[outward.servers]\n"{UUID}" = "slack"\n')
    code, reason = check_tier(payload(root, 'A technical claim.', tool=opaque('send_message')))
    assert code == 1 and held_channel(root, reason) == 'slack'
    for name in ('conversations_history', 'slack_read_channel'):
        call = payload(root, 'A technical claim.', tool=opaque(name))
        assert check_tier(call) == check_lint(call) == (0, '')
    write_config(root, f'"{UUID.replace("1", "2")}" = "chat"\n')
    with pytest.raises(workspace.ConfigError):
        workspace.load_config(root)


RECORDED_OPAQUE = {
    **{server: {outcome: list(names) for outcome, names in lists.items()}
       for server, lists in RECORDED.items()},
    'mail': {'read': ['get_thread', 'search_threads', 'list_drafts'],
             'draft': ['create_draft', 'update_draft', 'forward', 'label_message', 'trash_thread'],
             'learn': ['send_message']},
}
# Under an opaque server only the brand in the name, the alias or the vocabulary is left.
RECORDED_OPAQUE['linear']['draft'] = ['create_issue', 'update_issue']
RECORDED_OPAQUE['linear']['learn'] += ['create_comment']
RECORDED_OPAQUE['github']['draft'] = ['add_issue_comment', 'create_issue', 'update_issue',
                                      'assign_copilot_to_issue',
                                      'add_pull_request_review_comment_to_pending_review']


@pytest.mark.parametrize('tool,outcome', [
    (opaque(name, f'00000000-0000-4000-8000-00000000000{index}'), outcome)
    for index, lists in enumerate(RECORDED_OPAQUE.values(), 1)
    for outcome, names in lists.items() for name in names])
def test_recorded_opaque_tools(configured, tool, outcome):
    from wuwei.guards.outward import check_lint, check_tier
    call = payload(configured[0], 'A technical claim.', tool=tool)
    tier, lint = check_tier(call), check_lint(call)
    if outcome == 'read':
        assert tier == lint == (0, '')
    elif outcome == 'draft':
        assert tier[0] == 1 and held_channel(configured[0], tier[1]), tier
    else:
        assert tier[0] == lint[0] == 2
        assert f'bin/wuwei outbound learn --tool {tool}' in tier[1]
    assert 'config set' not in tier[1] + lint[1]


@pytest.mark.parametrize('posture', ['observe', 'guarded', 'strict'])
def test_learn_reasons(configured, monkeypatch, capsys, posture):
    from wuwei.guards.outward import check_lint, check_tier
    root = configured[0]
    set_posture(root, posture)
    write = opaque('send_message')
    for check in (check_tier, check_lint):
        code, reason = check(payload(root, 'A technical claim.', tool=write))
        assert code == 2 and UUID in reason and f'bin/wuwei outbound learn --tool {write}' in reason
        assert 'config set' not in reason
    unknown = opaque('frobnicate_widget')
    code = run_hook(monkeypatch, payload(root, 'A technical claim.', tool=unknown))
    err = capsys.readouterr().err
    rows = unknown_events(root)
    reason = err if posture == 'strict' else rows[0]['payload']['reason']
    assert code == (2 if posture == 'strict' else 0)
    assert UUID in reason and f'bin/wuwei outbound learn --tool {unknown}' in reason
    assert 'config set' not in reason
    text = (root / '.wuwei/config.toml').read_text().replace(
        '[outbound]\n', '[outbound]\nlearn = "off"\n')
    (root / '.wuwei/config.toml').write_text(text)
    code, reason = check_tier(payload(root, 'A technical claim.', tool=write))
    assert code == 2 and 'a draft for the owner to send' in reason and 'outbound learn' not in reason


def test_class_modes(configured):
    # #492 scope addition: a Jira comment, a Notion append, a GitHub PR comment and a Sentry
    # resolve through fixture UUID connectors follow their class mode; the owner's mode wins.
    from wuwei.guards.outward import check_lint, check_tier
    root = configured[0]
    sentry, slack = (UUID.replace('1', digit) for digit in '23')
    for name, channel in (('addCommentToJiraIssue', 'tracker'), ('append_block_children', 'docs'),
                          ('add_pull_request_review_comment_to_pending_review', 'code_host')):
        code, reason = check_tier(payload(root, 'A technical claim.', tool=opaque(name)))
        assert code == 1 and held_channel(root, reason) == channel, (name, reason)
    resolve = {**payload(root, tool=opaque('resolve_issue', sentry)), 'tool_input': {'issue_id': 'PROJ-1'}}
    assert check_tier(resolve) == check_lint(resolve) == (0, '')
    assert check_tier(payload(root, 'I disagree with the proposal.', tool=opaque('resolve_issue', sentry)))[0] == 1
    assert check_lint(payload(root, 'per Pat, it is fixed', tool=opaque('resolve_issue', sentry)))[0] == 1
    write_config(root, f'\n[outward.servers]\n"{slack}" = "slack"\n'
                       f'\n[outward.modes]\n"{sentry}" = "draft"\n"{UUID}" = "refuse"\n"{slack}" = "send"\n')
    assert check_tier(resolve)[0] == 1
    code, reason = check_tier(payload(root, 'A technical claim.', tool=opaque('append_block_children')))
    assert code == 1 and 'block by rule 2 ' in reason and 'outward.modes' in reason and 'config set' not in reason
    assert check_tier(payload(root, tool=opaque('get_page'))) == (0, '')
    unknown = payload(root, 'thanks <@U03>', tool=opaque('send_message', slack), channel='C01')
    assert check_tier(unknown) == (0, '')
    with pytest.raises(workspace.ConfigError):
        write_config(root, f'"{UUID.replace("1", "4")}" = "later"\n')
        workspace.load_config(root)


def test_no_config_set_in_reasons():
    # SC-002: no reason the outward guard builds names config set (owner.name stays the
    # owner's own setting in the lint).
    import inspect
    from wuwei.guards import outward as guard
    assert 'config set' not in inspect.getsource(guard)


def test_draft_names_unknown_audience(configured, monkeypatch, capsys):
    # #492 on the #493 card: a held send to an unknown channel or person names it in the
    # rule, and the card names the planner's learn command for that tool unless learn is off.
    import re
    from wuwei.__main__ import main
    root = configured[0]
    monkeypatch.chdir(root)
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('[outbound]\n', '[outbound]\ncompany_domains = ["example.com"]\n'))
    write_config(root, f'\n[outward.servers]\n"{UUID}" = "slack"\n'
                       '\n[outbound.people]\n"slack:U01" = {email = "ada@example.com"}\n'
                       '"slack:U02" = {email = "bo@example.com"}\n')
    tool = opaque('send_message')

    def send_now(reason):
        assert main(['drafts', 'show', re.fullmatch(HELD, reason)[1], '--widget']) == 0
        return json.loads(capsys.readouterr().out)[0]['options'][0]['description']

    code, reason = check_tier_call(root, 'thanks', tool, 'C01')
    assert code == 1 and re.fullmatch(HELD, reason)[2].startswith('ask by rule 9 (audience=company) for C01: unknown destination C01')
    assert f'bin/wuwei outbound learn --tool {tool}' in send_now(reason)
    code, reason = check_tier_call(root, 'thanks <@U03> <@U04>', tool, 'C1')
    assert code == 1 and re.fullmatch(HELD, reason)[2].startswith('ask by rule 9 (audience=company) for @u03: unknown mention @u03')
    assert f'bin/wuwei outbound learn --tool {tool}' in send_now(reason)
    code, reason = check_tier_call(root, 'I think <@U01> <@U02> agree.', tool, 'C1')
    assert code == 1 and 'unknown' not in re.fullmatch(HELD, reason)[2]
    assert 'outbound learn' not in send_now(reason)
    text = (root / '.wuwei/config.toml').read_text().replace('[outbound]\n', '[outbound]\nlearn = "off"\n')
    (root / '.wuwei/config.toml').write_text(text)
    code, reason = check_tier_call(root, 'thanks <@U03> <@U04>', tool, 'C01')
    assert code == 1 and 'outbound learn' not in reason + send_now(reason)


def check_tier_call(root, text, tool, channel):
    from wuwei.guards.outward import check_tier
    return check_tier(payload(root, text, tool=tool, channel=channel))


# #495: a message only the owner receives is never a draft.
def with_owner(root):
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace(
        'work_channels = ["chat", "C1"]\n', 'work_channels = ["chat", "C1"]\nowner_channel = "dm"\n')
        + '\n[outbound.owner]\nmail = "pat@example.test"\n'
        '[outbound.owner.slack]\nuser = "U01"\ndm = "D01"\n')
    return workspace.load_config(root)


def test_owner_config(configured):
    root, config = configured
    assert config['outbound']['owner'] == {'slack': {'user': '', 'dm': ''}, 'mail': '', 'code_host': ''}
    assert config['outbound']['owner_channel'] == 'session'
    config = with_owner(root)
    assert config['outbound']['owner'] == {
        'slack': {'user': 'U01', 'dm': 'D01'}, 'mail': 'pat@example.test', 'code_host': ''}
    assert config['outbound']['owner_channel'] == 'dm'


@pytest.mark.parametrize('context,kind,expected', [
    ({'channel': 'D01'}, 'slack', True), ({'channel': 'U01'}, 'chat', True),
    ({'channel': 'u01'}, 'slack', True), ({'recipient': 'U01'}, 'slack', True),
    ({'recipients': ['U01']}, 'chat', True), ({'recipients': ['U01', 'U02']}, 'slack', False),
    ({'channel': 'D01', 'recipient': 'U02'}, 'slack', False),
    ({'channel': 'D01', 'draft': {'text': 'x'}}, 'slack', False),
    ({}, 'slack', False), ({'channel': 'C1'}, 'slack', False),
    ({'recipients': ['pat@example.test']}, 'mail', True),
    ({'recipients': ['pat@example.test']}, 'slack', False),
    ({'to': 'pat@example.test'}, 'mail', True),
    ({'to': 'pat@example.test', 'cc': ['x@other.test']}, 'mail', False),
    ({'to': 'pat@example.test', 'bcc': 'x@other.test'}, 'mail', False),
    ({'to': 'pat@example.test', 'ccRecipients': [{'emailAddress': {'address': 'x@other.test'}}]}, 'mail', False),
    ({'channel': 'D01'}, 'code_host', False), ({'channel': 'D01'}, 'tracker', False),
    ({'channel': 'D01'}, 'docs', False),
])
def test_owner_only(configured, context, kind, expected):
    from wuwei import outward
    root, config = configured
    assert outward.owner_only(context, config, kind) is False
    assert outward.owner_only(context, with_owner(root), kind) is expected


@pytest.mark.parametrize('user,dm,bad', [('U01', 'C1', 'C1'), ('C1', 'D01', 'C1'),
                                         ('D01', 'U01', 'D01'), ('D01', 'U01', 'U01')])
def test_owner_only_ignores_non_dm_shapes(configured, user, dm, bad):
    from wuwei import outward
    config = with_owner(configured[0])
    config['outbound']['owner']['slack'] = {'user': user, 'dm': dm}
    assert outward.owner_only({'channel': bad}, config, 'slack') is False


@pytest.mark.parametrize('text', ['Your build is green', 'Your salary review is in',
                                  'I will ship it tomorrow'])
@pytest.mark.parametrize('channel', ['D01', 'U01'])
def test_classify_to_owner(configured, monkeypatch, text, channel):
    from wuwei import outward
    root = configured[0]
    config = with_owner(root)
    why = []
    assert outward.classify(text, root, config, {'text': text, 'channel': channel},
                            kind='slack', why=why) == (0, 'send')
    assert why == []
    monkeypatch.setenv('WUWEI_SEAT_ROLE', 'shepherd')
    assert outward.classify(text, root, config, {'text': text, 'channel': channel}, kind='slack') == (1, 'draft')


def test_dm_recipient_rule(configured):
    from wuwei import outward
    root = configured[0]
    config = with_owner(root)
    why = []
    assert outward.classify('Thanks', root, config, {'text': 'Thanks', 'channel': 'U02'},
                            kind='slack', why=why) == (1, 'draft')
    assert why == ["ask by rule 9 (audience=company) for U02: unknown DM recipient U02, not the owner's DM "
                   'or user id in outbound.owner.slack, connector default class company']
    why = []
    assert outward.classify('Thanks', root, config, {'text': 'Thanks', 'is_dm': True},
                            kind='slack', why=why) == (1, 'draft')
    assert why == ['ask by rule 9 (audience=company) for slack: connector default class company']
    why = []  # #496: a DM to an internal person passes the table; the kind rule drafts it.
    config['outbound']['people']['slack:U02'] = {'email': '', 'org': '', 'class': 'team'}
    assert outward.classify('Thanks', root, config, {'text': 'Thanks', 'channel': 'U02'},
                            kind='slack', why=why) == (1, 'draft')
    assert why == ['approval tier direct message for U02: every direct message drafts']


def owner_events(root):
    from wuwei import watch
    path = workspace.day_dir(root) / 'events.jsonl'
    return [row for row in (watch.records(path) if path.exists() else [])
            if row['kind'] == 'outward.to_owner']


def test_to_owner_event_and_lint(configured):
    from wuwei import outward
    root = configured[0]
    config = with_owner(root)
    assert outward.check_tier({'text': 'Your build is green', 'channel': 'D01'}, root, config, {'slack'}) == (0, '')
    assert [row['payload'] for row in owner_events(root)] == [{'channel': 'slack'}]
    assert outward.check_tier({'text': 'fixed in abc1234', 'channel': 'C1'}, root, config, {'slack'}) == (0, '')
    assert outward.check_tier({'text': 'Thanks', 'channel': 'U02'}, root, config, {'slack'})[0] == 1
    assert len(owner_events(root)) == 1
    assert outward.check_lint({'text': 'Pat, your build is green', 'channel': 'D01'}, root, config, {'slack'}) == (0, '')
    assert 'third-person' in outward.check_lint(
        {'text': 'Pat, your build is green', 'channel': 'C1'}, root, config, {'slack'})[1]
    assert outward.check_lint({'text': 'Ready \U0001F600', 'channel': 'D01'}, root, config, {'slack'})[0] == 1


@pytest.mark.parametrize('posture', ['observe', 'guarded', 'strict'])
def test_guard_to_owner_every_posture(configured, posture):
    from wuwei import state
    from wuwei.guards.outward import check_lint, check_tier
    root = configured[0]
    with_owner(root)
    set_posture(root, posture)
    call = payload(root, 'Your build is green', tool=opaque('slack_send_message'), channel='D01')
    assert check_tier(call) == (0, '')
    assert check_lint(call) == (0, '')
    assert len(owner_events(root)) == 1
    assert not state.read_state(root).get('drafts')


def test_guard_to_owner_floor(configured):
    # #495, owner: a self-DM always sends; a strict workspace with the outward area on block,
    # the connector in mode draft or refuse and a sensitive word do not lower it.
    from wuwei import state
    from wuwei.guards.outward import check_lint, check_tier
    root = configured[0]
    with_owner(root)
    set_posture(root, 'strict', 'block')
    write_config(root, f'\n[outward.modes]\n"{UUID}" = "draft"\n')
    path = root / '.wuwei/config.toml'
    for mode, count, held, words in (('draft', 2, 1, 'ask by rule 1 '), ('refuse', 4, 1, 'block by rule 1 ')):
        path.write_text(path.read_text().replace(f'"{UUID}" = "draft"', f'"{UUID}" = "{mode}"'))
        for channel in ('D01', 'U01'):
            call = payload(root, 'Your salary review is in', tool=opaque('slack_send_message'), channel=channel)
            assert check_tier(call) == check_lint(call) == (0, ''), mode
        assert len(owner_events(root)) == count
        code, reason = check_tier(payload(root, 'Thanks', tool=opaque('slack_send_message'), channel='U02'))
        assert code == held and words in reason, (mode, reason)
    assert all(row['destination'] != 'D01' for row in state.read_state(root).get('drafts', {}).values())


def test_guard_owner_mail_with_outside_cc_is_not_owner_only(configured):
    # #501 review F1: an outside cc or bcc means the owner is not the only reader.
    from wuwei.guards.outward import check_tier
    root = configured[0]
    with_owner(root)
    set_posture(root, 'strict', 'block')
    write_config(root, f'\n[outward.modes]\n"{UUID}" = "refuse"\n')
    mail = {'to': 'pat@example.test', 'subject': 'numbers', 'body': 'Our layoffs list'}
    call = payload(root, tool=opaque('send_mail'))
    call['tool_input'] = mail
    assert check_tier(call) == (0, '')
    for extra in ({'cc': ['outsider@evil.test']}, {'bcc': 'outsider@evil.test'}):
        call['tool_input'] = {**mail, **extra}
        code, reason = check_tier(call)
        assert code == 1 and 'block by rule 1 ' in reason and 'outward.modes' in reason, (extra, reason)


# #501: recorded connector tool_input shapes; MESSAGE marks where the message text sits.
PAGE = '00000000111122223333444444444444'
CORPUS = [
    ('slack', {'channel': 'C1', 'text': 'MESSAGE'}, ['C1']),
    ('tracker', {'issue_key': 'DEMO-12', 'comment': 'MESSAGE'}, ['DEMO-12']),
    ('docs', {'pageId': PAGE, 'body': {'storage': {'value': 'MESSAGE', 'representation': 'storage'}}}, [PAGE]),
    ('docs', {'page_id': PAGE, 'children': [{'object': 'block', 'type': 'paragraph', 'paragraph': {
        'rich_text': [{'type': 'text', 'text': {'content': 'MESSAGE'}}]}}]}, [PAGE]),
    ('code_host', {'owner': 'acme', 'repo': 'widgets', 'pull_number': 7, 'body': 'MESSAGE'}, ['widgets', '7']),
    ('other', {'issue_id': 'PROJ-1', 'status': 'resolved'}, ['PROJ-1']),
    ('mail', {'to': 'someone@example.test', 'subject': 'Weekly note', 'body': 'MESSAGE'}, ['someone@example.test']),
]


def shaped(shape, text):
    return json.loads(json.dumps(shape).replace('MESSAGE', text))


def test_text_fields_corpus(configured):
    from wuwei import outward
    root, config = configured
    for channel, shape, destinations in CORPUS:
        texts, found = outward._text(shaped(shape, 'Tests passed'))
        assert found == destinations, shape
        assert ('Tests passed' in texts) == ('MESSAGE' in json.dumps(shape)), shape
        assert not {'block', 'paragraph', 'resolved', 'text', 'acme', PAGE, 'PROJ-1'} & set(texts), texts
        if 'MESSAGE' in json.dumps(shape):
            code, reason = outward.check_tier(shaped(shape, 'Your salary is set'), root, config, {channel},
                                              tool=opaque('write'))
            assert code == 1 and 'outbound.sensitive_keywords' in reason, (shape, reason)


def test_connector_writes_through_the_guard(configured):
    import re
    from wuwei.guards.outward import check_lint, check_tier
    root = configured[0]
    notion = {**payload(root, tool='mcp__notion__append_block_children'),
              'tool_input': shaped(CORPUS[3][1], 'Your salary is set')}
    code, reason = check_tier(notion)
    match = re.fullmatch(HELD, reason)
    assert code == 1 and match, reason
    assert match[2].startswith('ask by rule ') and 'topic=sensitive' in match[2], match[2]
    assert 'outbound.sensitive_keywords' in match[2]
    write_config(root, f'\n[outward.servers]\n"{UUID}" = "tracker"\n\n[outward.modes]\n"{UUID}" = "send"\n')
    jira = {**payload(root, tool=opaque('addCommentToJiraIssue')),
            'tool_input': {'issue_key': 'DEMO-12', 'comment': 'tests passed'}}
    assert check_tier(jira) == check_lint(jira) == (0, '')


def test_text_fields_keep_known_checks():
    from wuwei import outward
    inputs = {'title': 'a', 'draft': {'description': 'b', 'teamId': 't'}, 'channel': 'C1',
              'recipients': ['dev'], 'is_dm': False, 'issue_number': 3, 'thread': None}
    assert outward._text(inputs) == (['b', 'a'], ['C1', 'dev'])
    for bad in ({'is_dm': 'false'}, {'recipients': 'dev'}, {'channel': {'text': 'hidden'}},
                {'issue_number': True}, {'draft': 'x'}, {'draft': {'draft': {}}},
                {'parent': {'page_id': 'p'}}):
        with pytest.raises(ValueError):
            outward._text({'text': 'a', **bad})


def test_textless_write(configured):
    # #501: a write without text has nothing to lint; its mode and destination decide.
    import re
    from wuwei import drafts, outward, state
    from wuwei.guards.outward import check_lint, check_tier
    root, config = configured
    resolve = {**payload(root, tool=opaque('resolve_issue')),
               'tool_input': {'issue_id': 'PROJ-1', 'status': 'resolved'}}
    assert check_tier(resolve) == check_lint(resolve) == (0, '')
    assert outward.check_lint({'issue_id': 'PROJ-1'}, root, config, {'other'}) == (0, '')
    assert outward.check_lint({'text': '', 'channel': 'C1'}, root, config, {'chat'})[0] == 2
    code, reason = outward.check_tier({'text': ' ', 'channel': 'C1'}, root, config, {'chat'})
    assert code == 2 and 'nonempty text required' in reason
    write_config(root, f'\n[outward.modes]\n"{UUID}" = "draft"\n')
    code, reason = check_tier(resolve)
    match = re.fullmatch(HELD, reason)
    assert code == 1 and match, reason
    assert drafts.read(state.read_state(root))[match[1]]['text'] == ''


def test_tool_input_not_an_object(configured):
    from wuwei.guards.outward import check_lint, check_tier
    root = configured[0]
    for check in (check_tier, check_lint):
        for inputs, shape in (([], 'list'), ('x', 'str')):
            call = {**payload(root, tool=opaque('slack_send_message')), 'tool_input': inputs}
            code, reason = check(call)
            assert (code, reason) == (2, f'outward: tool_input is not an object; got {shape}; '
                                         'pass the tool arguments as a JSON object')


# #496: outward control is one owner-configured tier table.
def outbound_line(root, line):
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace('[outbound]\n', f'[outbound]\n{line}\n', 1))


def test_tier_config(configured):
    root, config = configured
    assert config['outbound']['tiers'] == [] and config['outbound']['channel_classes'] == {}
    assert config['outward']['classes'] == {}
    outbound_line(root, 'tiers = [{ person = "U07", tier = "send" }]')
    write_config(root, '\n[outbound.channel_classes]\nC4 = "public"\n'
                       '\n[outbound.people]\n"slack:U07" = { email = "dev@example.test", class = "team" }\n'
                       f'\n[outward.classes]\n"{UUID}" = "company"\n')
    config = workspace.load_config(root)
    assert config['outbound']['tiers'] == [{'tool': '', 'person': 'U07', 'channel': '', 'audience': '',
                                            'topic': '', 'tier': 'send'}]
    assert config['outbound']['channel_classes'] == {'C4': 'public'}
    assert config['outbound']['people']['slack:U07'] == {'email': 'dev@example.test', 'org': '', 'class': 'team'}
    assert config['outward']['classes'] == {UUID: 'company'}


@pytest.mark.parametrize('row,key', [
    ('{ persn = "U07", tier = "send" }', 'outbound.tiers.0.persn'),
    ('{ tool = "(", tier = "ask" }', 'outbound.tiers.0.tool'),
    ('{ tier = "maybe" }', 'outbound.tiers.0.tier'),
    ('{ audience = "boss", tier = "ask" }', 'outbound.tiers.0.audience'),
    ('{ person = "U07" }', 'outbound.tiers.0.tier'),
])
def test_tier_row_validation(configured, row, key):
    # A typo must not widen a row to match everything, so it refuses under every posture.
    root = configured[0]
    set_posture(root, 'guarded')
    outbound_line(root, f'tiers = [{row}]')
    with pytest.raises(workspace.ConfigError, match=key.replace('.', r'\.')):
        workspace.load_config(root)


def test_tier_table(configured):
    import re
    from wuwei import outward
    root, config = configured
    rows = outward.table(config)
    assert [row for row, _, _ in rows] == [dict(row) for row in outward.DEFAULT_TIERS]
    assert {source for _, source, _ in rows} == {'default'} and len(rows) == 10
    assert rows[2][0] == {'audience': 'client', 'topic': 'commitment', 'tier': 'ask'}
    assert not [row for row, _, _ in rows if row['tier'] == 'block']  # owner, 2026-10-04: no default blocks
    outbound_line(root, 'tiers = [{ person = "U07", tier = "send" }]')
    write_config(root, f'\n[outward.modes]\n"{UUID}" = "refuse"\n')
    rows = outward.table(workspace.load_config(root))
    assert rows[0] == ({'tool': f'mcp__{re.escape(UUID)}__.*', 'tier': 'block'}, 'owner', ' (outward.modes)')
    assert rows[1] == ({'person': 'U07', 'tier': 'send'}, 'owner', '')
    assert rows[2] == ({'audience': 'owner', 'tier': 'send'}, 'default', '')
    assert outward.render(rows[1][0]) == '{ person = "U07", tier = "send" }'


def tiers_workspace(root, extra=''):
    with_owner(root)
    outbound_line(root, 'external_channels = ["C2"]')
    write_config(root, f'\n[outward.servers]\n"{UUID}" = "slack"\n' + extra)
    return workspace.load_config(root)


def test_tiers_acceptance(configured):
    import re
    from wuwei import state
    from wuwei.guards.outward import check_tier
    root = configured[0]
    tiers_workspace(root)
    tool = opaque('slack_send_message')
    code, reason = check_tier(payload(root, 'I will ship it tomorrow', tool=tool, channel='C2'))
    assert code == 1 and re.fullmatch(HELD, reason)[2] == (
        'ask by rule 3 (audience=client topic=commitment) for C2: C2 in outbound.external_channels '
        'as client, outbound.commitment_patterns')
    assert len(state.read_state(root).get('drafts', {})) == 1  # a client commitment is a card, not a wall
    code, reason = check_tier(payload(root, 'I will ship it tomorrow', tool=tool, channel='C1'))
    assert code == 1 and re.fullmatch(HELD, reason)[2] == (
        'ask by rule 7 (topic=commitment) for C1: C1 in outbound.work_channels as team, '
        'outbound.commitment_patterns')
    assert check_tier(payload(root, 'Your build is green', tool=tool, channel='D01')) == (0, '')
    # The owner's own row is the only way a client gets a wall.
    outbound_line(root, 'tiers = [{ audience = "client", topic = "commitment", tier = "block" }]')
    assert check_tier(payload(root, 'I will ship it tomorrow', tool=tool, channel='C2')) == (1, (
        'outward: block by rule 1 (audience=client topic=commitment) for C2: C2 in '
        'outbound.external_channels as client, outbound.commitment_patterns; the owner decides: '
        'bin/wuwei outbound tiers'))


def tier_run(root, config, text, channel=None, kind='slack', tool=None, **context):
    from wuwei import outward
    why = []
    inputs = {'text': text, **({'channel': channel} if channel else {}), **context}
    result = outward.classify(text, root, config, inputs, kind=kind, why=why, tool=tool)
    assert all('; ' not in rule for rule in why)
    return result, why


def test_tiers_defaults(configured):
    root = configured[0]
    config = tiers_workspace(root, '\n[outbound.channel_classes]\nC4 = "public"\n')
    assert tier_run(root, config, 'tests passed', 'C4') == (
        (1, 'draft'), ['ask by rule 2 (audience=public) for C4: C4 in outbound.channel_classes as public'])
    result, why = tier_run(root, config, 'I disagree with the proposal.', 'C2')
    assert result == (1, 'draft') and why == [
        'ask by rule 4 (audience=client topic=disagreement) for C2: C2 in outbound.external_channels '
        'as client, outbound.disagreement_patterns']
    assert tier_run(root, config, 'Your salary review is in', 'C2') == (
        (1, 'draft'), ['ask by rule 5 (audience=client) for C2: C2 in outbound.external_channels as client'])
    assert tier_run(root, config, 'tests passed', 'C1') == ((0, 'send'), [])
    result, why = tier_run(root, config, 'thanks <@U09>', 'C1')
    assert result == (1, 'draft') and why == [
        'ask by rule 9 (audience=company) for @u09: unknown mention @u09, not an internal person in '
        'outbound.people, connector default class company']
    from wuwei import outward
    assert outward.classify('', root, config, {'issue_id': 'PROJ-1'}, kind='other') == (0, 'send')
    assert tier_run(root, config, 'I disagree', kind='other') == ((1, 'draft'), [
        'ask by rule 8 (topic=disagreement) for other: connector default class team, '
        'outbound.disagreement_patterns'])


def test_tier_classes(configured):
    root = configured[0]
    config = tiers_workspace(root, '\n[outbound.people]\n"slack:U07" = { class = "client" }\n')
    result, why = tier_run(root, config, 'I will ship it tomorrow', 'C1', is_shared=True)
    assert result == (1, 'draft') and why[0].startswith('ask by rule 3 ') and why[0].endswith(
        '(audience=client topic=commitment) for C1: C1 is shared, connected, external or client, '
        'outbound.commitment_patterns')
    assert tier_run(root, config, 'thanks <@U07>', 'C1') == (
        (1, 'draft'), ['ask by rule 5 (audience=client) for @u07: @u07 in outbound.people as client'])
    assert tier_run(root, config, 'thanks', 'C1', recipient_org='other-org') == (
        (1, 'draft'), ['ask by rule 5 (audience=client) for other-org: recipient_org other-org not in '
                       'outbound.code_host_orgs as client'])
    board = workspace.load_config(root)
    board['adapters']['tracker'] = 'github'
    board['tracker'].update(project='outside/repo', board='')
    from wuwei import outward
    why = []
    text = '[2026-09-28 item-1] Phase: gate.'
    assert outward.classify(text, root, board, {'item': 'ENG-1', 'text': text, 'category': 'progress'},
                            kind='tracker', port=True, why=why) == (1, 'draft')
    assert why == ['ask by rule 5 (audience=client) for board: the board is outside '
                   'outbound.code_host_orgs as client']
    tool = opaque('slack_send_message')
    result, why = tier_run(root, config, 'thanks', 'C9', tool=tool)
    assert result == (1, 'draft') and why[0].startswith('ask by rule 9 (audience=company) for C9: unknown '
                                                         'destination C9, not in outbound.work_channels')
    write_config(root, f'\n[outward.classes]\n"{UUID}" = "team"\n')
    config = workspace.load_config(root)
    assert tier_run(root, config, 'thanks', 'C9', tool=tool) == ((0, 'send'), [])
    assert tier_run(root, config, 'thanks', 'C9')[0] == (1, 'draft')


def test_tiers_mixed_parties(configured):
    root = configured[0]
    config = tiers_workspace(root)
    result, why = tier_run(root, config, 'I will ship it tomorrow', 'C1', channel_id='C2')
    assert result == (1, 'draft') and why[0].startswith('ask by rule 3 (audience=client topic=commitment) for C2')
    result, why = tier_run(root, config, 'Your build is green', 'D01', recipients=['U09'])
    assert result == (1, 'draft') and why[0].startswith('ask by rule 9 (audience=company) for @U09')
    outbound_line(root, 'tiers = [{ person = "U07", tier = "send" }]')
    config = workspace.load_config(root)
    assert tier_run(root, config, 'Can it wait', 'U07') == ((0, 'send'), [])
    result, why = tier_run(root, config, '<@U07> please look at the logs', 'C1')
    assert result == (1, 'draft') and why[0].startswith('approval tier unclassified for C1')


def test_owner_row_person(configured):
    from wuwei import outward
    root = configured[0]
    config = tiers_workspace(root)
    inputs = {'text': 'tests passed <@U07>', 'channel': 'C1'}
    assert outward.check_tier(inputs, root, config, {'slack'}) == (1, (
        f'{outward.APPROVAL_REQUIRED}: ask by rule 9 (audience=company) for @u07: unknown mention @u07, '
        'not an internal person in outbound.people, connector default class company'))
    outbound_line(root, 'tiers = [{ person = "U07", tier = "send" }]')
    config = workspace.load_config(root)
    assert outward.check_tier(inputs, root, config, {'slack'}) == (0, '')
    assert outward.check_tier({'text': 'Can it wait', 'channel': 'U07'}, root, config, {'slack'}) == (0, '')


def test_tier_floor_strict(configured, monkeypatch):
    from wuwei import outward
    root = configured[0]
    tiers_workspace(root)
    outbound_line(root, 'tiers = [{ audience = "client", tier = "send" }]')
    guarded = workspace.load_config(root)
    assert tier_run(root, guarded, 'thanks', 'C2') == ((0, 'send'), [])
    set_posture(root, 'strict')
    config = workspace.load_config(root)
    why, trace = [], []
    assert outward.classify('thanks', root, config, {'text': 'thanks', 'channel': 'C2'}, kind='slack',
                            why=why, trace=trace) == (1, 'draft')
    assert why[0].startswith('ask by rule 6 (audience=client) for C2')
    assert '  rule 1 owner { audience = "client", tier = "send" }: ignored under strict' in trace
    monkeypatch.setenv('WUWEI_SEAT_ROLE', 'shepherd')
    for channel in ('D01', 'C2'):
        assert tier_run(root, guarded, 'thanks', channel)[0] == (1, 'draft')


def test_mode_rows(configured, monkeypatch):
    # #496: the connector mode is the first row; refuse blocks with exit 1 and no draft.
    import re
    from wuwei import state
    from wuwei.guards.outward import check_tier
    root = configured[0]
    tiers_workspace(root, f'\n[outward.modes]\n"{UUID}" = "refuse"\n')
    path = root / '.wuwei/config.toml'
    tool = opaque('slack_send_message')
    monkeypatch.delitem(sys.modules, 'wuwei.drafts', raising=False)
    code, reason = check_tier(payload(root, 'tests passed', tool=tool, channel='C1'))
    assert code == 1 and reason == (f'outward: block by rule 1 (tool=mcp__{re.escape(UUID)}__.*) for C1: C1 in '
                                    'outbound.work_channels as team, outward.modes; the owner decides: '
                                    'bin/wuwei outbound tiers')
    assert 'wuwei.drafts' not in sys.modules and not state.read_state(root).get('drafts')
    path.write_text(path.read_text().replace('= "refuse"', '= "draft"'))
    code, reason = check_tier(payload(root, 'tests passed', tool=tool, channel='C1'))
    assert code == 1 and re.fullmatch(HELD, reason)[2].startswith('ask by rule 1 (tool=mcp__')
    path.write_text(path.read_text().replace('= "draft"', '= "send"'))
    assert check_tier(payload(root, 'I will ship it tomorrow', tool=tool, channel='C1')) == (0, '')
