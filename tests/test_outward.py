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
        assert 'deliver as a draft for the owner to send' in result[1]


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
    assert 'deliver as a draft for the owner to send' in result.reason


@pytest.mark.parametrize('text,code,decision', [
    ('fixed in abc1234', 0, 'send'), ('A technical claim.', 1, 'draft'),
    ('', 2, 'draft'), (None, 2, 'draft'),
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
    ('mcp__linear__update_issue', {'description': 'drafts are with the owner'}, 1),
    ('mcp__linear__create_issue', {'draft': {'title': 'fixed in abc1234', 'description': 'They wrote it'}}, 1),
    ('mcp__slack__post_message', {'message': 'drafts are with the owner'}, 1),
    ('mcp__slack__post_message', {'body': 'fixed in abc1234'}, 1),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'body': 'This is thread safe.'}, 1),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'blocks': [{'text': 'per Pat'}]}, 2),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'approved': True}, 2),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'approved_draft_id': 'draft-1'}, 2),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'attachments': []}, 2),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'channel': {'text': 'hidden'}}, 2),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'draft': {'draft': {'text': 'hidden'}}}, 2),
    ('mcp__slack__post_message', {'text': 'fixed in abc1234', 'title': None}, 2),
    ('mcp__slack__post_message', {'text': ['fixed in abc1234']}, 2),
    ('mcp__slack__post_message', {'draft': 'fixed in abc1234'}, 2),
    ('mcp__slack__post_message', {}, 2), ('mcp__slack__post_message', [], 2),
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
        call['tool_input'] = {'blocks': []}
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
    ('mcp__unknown__create_issue', 2),
    ('mcp__unknown__update_issue', 2),
    ('mcp__unknown__save_issue', 2),
    ('mcp__unknown__comment', 2),
    ('mcp__unknown__chat_write', 2),
    ('mcp__unknown__read', 0),
    ('mcp__unknown__message_user', 2),
    ('mcp__unknown__notify', 2),
    ('mcp__gmail__draft_email', 2),
    ('mcp__unknown__respond_to_event', 2),
    ('mcp__slack__edit_message', 2),
    ('mcp__slack__slack_add_list_record', 2),
    ('mcp__unknown__target_lookup', 2),
    ('mcp__unknown__anything', 2),
])
def test_real_mcp_write_names(configured, tool, code):
    from wuwei.guards.outward import check_tier as check
    result = check(payload(configured[0], 'A technical claim.', tool=tool))
    assert result[0] == code
    if code == 2:
        assert 'configure' in result[1]


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
    ('mcp__x__slack_read_thread', 2),
    ('mcp__slack__slack_readwrite', 2),
    ('mcp__x__readwrite', 2),
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
    assert result.exit == 1 and 'stored draft' in result.reason
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
    ({}, {'text': 1}, 2),
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
