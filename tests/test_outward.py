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
    ('drafts are with the owner', 0, ''),
    ('_drafts_ are with the owner', 0, ''),
    ('the _queue_ is empty', 0, ''),
    ('DRAFTS\nARE WITH THE OWNER', 0, ''),
    ('drafts pending', 0, ''),
    ('pending drafts', 0, ''),
    ('The agent wrote this', 0, ''),
    ('The build queue is empty', 0, ''),
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
    ({'patterns': [r'\bI-[0-9]+\b']}, 'Notes for I-12', 'chat', 0),  # #533: not lint's
    ({'banned_characters': ['!']}, 'Ready!', 'chat', 1),
    ({'banned_characters': []}, 'Ready\u2014yes \U0001f600', 'chat', 0),
    ({'max_length': {'chat': 3}}, 'abc', 'chat', 0),
    ({'max_length': {'chat': 3}}, 'abcd', 'chat', 1),
    ({'max_length': {'chat': 3}}, 'abcd', 'tracker', 0),
    ({'max_length': {'chat': 0}}, 'abc', 'chat', 2),
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


@pytest.mark.parametrize('tool,inputs,code', [
    ('mcp__slack__post_message', {'text': 'fixed in abc1234'}, 1),
    ('mcp__slack__send_message', {'text': 'fixed in abc1234'}, 1),
    ('mcp__linear__create_issue', {'draft': {'title': 'fixed in abc1234'}}, 1),
    ('mcp__slack__slack_post_message', {'text': 'fixed in abc1234', 'channel': 'C1'}, 1),
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
    from wuwei.guards.edges import check_send as check
    call = payload(configured[0], tool=tool)
    call['tool_input'] = inputs
    assert check(call)[0] == code


def test_configured_matching(configured, monkeypatch):
    # #838: tool_patterns give the lint its channel; they decide no send.
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import check_lint, resolve
    root, config = configured
    config['outward']['tool_patterns'] = [{'pattern': 'mcp__x__custom_send', 'channel': 'customer'}]
    assert resolve('mcp__x__custom_send', config) == {'customer'}
    assert resolve('mcp__x__prefix_custom_send', config) != {'customer'}
    config['outward']['allow'] = ['mcp__x__custom_send']
    config['outward']['tool_patterns'] = [{'pattern': '[', 'channel': 'customer'}]
    monkeypatch.setattr(workspace, 'load_config', lambda root: config)
    call = payload(root, tool='mcp__x__custom_send')
    assert check_send(call)[0] == check_lint(call)[0] == 2


@pytest.mark.parametrize('specific', [False, True])
def test_channel_limits_cannot_be_bypassed(configured, monkeypatch, specific):
    from wuwei.guards.outward import check_lint as check
    root, config = configured
    config['outward']['max_length'] = {'slack': 100, 'C1': 5} if specific else {'slack': 5, 'C1': 100}
    config['outward']['allow'] = ['mcp__slack__post_message']
    monkeypatch.setattr(workspace, 'load_config', lambda root: config)
    assert check(payload(root, channel='C1'))[0] == 1


@pytest.mark.parametrize('text,invalid,code,warning', [
    ('per Pat, the fix is in', False, 1, False),
    ('The cache is thread safe.', False, 1, False),
    ('fixed in abc1234', True, 2, False),
])
def test_standard_profile(configured, monkeypatch, capsys, text, invalid, code, warning):
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import check_lint
    root, config = configured
    config['profile'] = 'standard'
    config['outward']['allow'] = [] if text == 'The cache is thread safe.' else ['mcp__slack__post_message']
    if invalid:
        config['outward']['banned_characters'] = [1]
    monkeypatch.setattr(workspace, 'load_config', lambda root: config)
    check = check_send if text == 'The cache is thread safe.' else check_lint
    assert check(payload(root, text))[0] == code
    output = capsys.readouterr()
    assert ('warning' in output.err) == warning
    assert text not in output.err


@pytest.mark.parametrize('code', [0, 1, 2])
def test_hook_integration(configured, monkeypatch, capsys, code):
    from wuwei.commands.hook import run
    root, _ = configured
    set_enforce(root, 'true')
    if code == 0:
        allow(root, 'mcp__slack__post_message')
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
    from wuwei.guards.edges import check_send as check
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
    ('mcp__unknown__send_message', 1),
    ('mcp__unknown__post_message', 1),
    ('mcp__unknown__reply', 1),
    ('mcp__unknown__schedule_message', 1),
    ('mcp__unknown__create_issue', 1),
    ('mcp__unknown__update_issue', 1),
    ('mcp__unknown__save_issue', 1),
    ('mcp__unknown__comment', 1),
    ('mcp__unknown__chat_write', 1),
    ('mcp__unknown__read', 0),
    ('mcp__unknown__message_user', 1),
    ('mcp__unknown__notify', 1),
    ('mcp__gmail__draft_email', 1),
    ('mcp__unknown__respond_to_event', 1),
    ('mcp__slack__edit_message', 1),
    ('mcp__slack__slack_add_list_record', 1),
    ('mcp__unknown__target_lookup', 0),
    ('mcp__unknown__anything', 0),  # #838 review: unknown names run and log
])
def test_real_mcp_write_names(configured, tool, code):
    from wuwei.guards.edges import check_send as check
    # #838: every write and every unknown name is refused until it is on outward.allow.
    mail = YOUR_MAIL if tool == 'mcp__gmail__draft_email' else None  # mail: the owner's address is unset
    assert check(payload(configured[0], 'A technical claim.', tool=tool)) == (
        refused(tool, mail) if code else (0, ''))


@pytest.mark.parametrize('tool', ['Skill', 'ToolSearch', 'AskUserQuestion', 'LS', 'Read',
                                  'mcp__unknown__send', 'mcp__slack__post', None])
def test_scope_before_payload_and_policy(tmp_path, monkeypatch, tool):
    from wuwei.guards.edges import check_send as check
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    assert check({'cwd': str(tmp_path), 'tool_name': tool, 'tool_input': None}) == (0, '')


@pytest.mark.parametrize('tool', ['Skill', 'ToolSearch', 'AskUserQuestion', 'LS'])
def test_irrelevant_native_tools_ignore_broken_policy(configured, tool):
    from wuwei.guards.edges import check_send as check
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
    sends = mode in ('missing', 'mechanical')  # #838: a duty sends after the lint
    expected = 2 if mode == 'broken-policy' else 0 if sends else 1
    assert result.exit == expected, result
    assert bool(performed) == sends


def test_only_mcp_defaults_and_no_textless_operations(configured):
    from wuwei.guards.edges import check_send as check
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


@pytest.mark.parametrize('char,code', [('\u2015', 1), ('\u2e3a', 1), ('\u2e3b', 1),
                                      ('\u2192', 0), ('\u21ff', 0), ('\u00a9', 0), ('\u00ae', 0)])
def test_character_default_corrections(configured, char, code):
    from wuwei.outward import lint
    assert lint('Ready ' + char, 'chat', configured[1])[0] == code


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
    from wuwei.guards.edges import check_send as check
    monkeypatch.setenv('WUWEI_WORKSPACE', override)
    code, reason = check(payload(configured[0], tool=tool))
    assert code == 2
    assert reason


@pytest.mark.parametrize('verb', ['get', 'list', 'search', 'read', 'find', 'fetch',
                                  'query', 'describe', 'view', 'lookup'])
def test_unmatched_mcp_read_prefixes(configured, verb):
    from wuwei.guards.edges import check_send as check
    assert check(payload(configured[0], tool=f'mcp__unknown__{verb}_item')) == (0, '')


@pytest.mark.parametrize('tool,code', [
    ('mcp__slack__slack_search_public', 0),
    ('mcp__slack__slack_read_channel', 0),
    ('mcp__claude_ai_Slack__slack_read_thread', 0),
    ('mcp__plugin_slack_slack__slack_list_user_channels', 0),
    ('mcp__linear__linear_list_issues', 0),
    ('mcp__search__search_items', 0),
    ('mcp__slack__slack_send_message', 1),
    ('mcp__x__notify', 1),
    ('mcp__x__slack_read_thread', 0),
    ('mcp__slack__slack_readwrite', 0),
    ('mcp__x__readwrite', 0),
])
def test_service_prefixed_mcp_reads(configured, tool, code):
    from wuwei.guards.edges import check_send as check
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
    from wuwei.guards.edges import check_send as check
    call = payload(configured[0], tool=tool)
    call['tool_input'] = inputs
    # Metadata parses, but an unverified chat thread is never eligible.
    assert check(call)[0] == 1


def test_channel_id_limit(configured, monkeypatch):
    from wuwei.guards.outward import check_lint as check
    root, config = configured
    config['outward']['max_length'] = {'C1': 5}
    config['outward']['allow'] = ['mcp__slack__post_message']
    monkeypatch.setattr(workspace, 'load_config', lambda root: config)
    assert check(payload(root, channel_id='C1'))[0] == 1


@pytest.mark.parametrize('value', [True, 1.5, {}, []])
def test_invalid_numeric_metadata(configured, value):
    from wuwei.guards.edges import check_send as check
    assert check(payload(configured[0], issue_number=value))[0] == 2


@pytest.mark.parametrize('base', ['\u00a9', '\u00ae', '\u2192', 'A'])
def test_emoji_presentation_selector(configured, base):
    from wuwei.outward import lint
    assert head(lint('Ready ' + base + '\ufe0f', 'chat', configured[1])) == (1, 'outward: emoji is banned')
    assert lint('Ready ' + base, 'chat', configured[1])[0] == 0


def test_owner_addressed_lint_skips_third_person_rules_only(tmp_path, monkeypatch):
    from wuwei import outward
    owner_line = 'Reply yes within 2 minutes to run it.'
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    (tmp_path / '.wuwei').mkdir()
    path = tmp_path / '.wuwei/config.toml'
    path.write_text('[owner]\nname = ""\n')
    config = workspace.load_config(tmp_path)
    assert outward.lint('Report ready.', 'chat', config)[0] == 2
    assert outward.lint('Report ready.', 'chat', config, to_owner=True) == (0, '')
    path.write_text('[owner]\nname = "Dry Run Operator"\npronouns = "they/them"\n')
    config = workspace.load_config(tmp_path)
    assert outward.lint(owner_line, 'chat', config)[0] == 1
    assert outward.lint(owner_line, 'chat', config, to_owner=True) == (0, '')
    assert outward.lint('They look done.', 'chat', config, to_owner=True) == (0, '')
    config['outward']['patterns'] = [r'\bwuwei\b']  # #533: the owner reads it; the list is for others
    assert outward.lint('wuwei is busy.', 'chat', config, to_owner=True) == (0, '')
    inputs = {'text': owner_line, 'channel': 'D1'}
    assert outward.check_lint(inputs, tmp_path, config, {'chat'}, to_owner=True) == (0, '')
    assert outward.check_lint(inputs, tmp_path, config, {'chat'})[0] == 1


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
    assert ai_tells(root) == [{'kind': kind, 'tells': ['not-x-but-y', 'stock-word'], }]
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
    result = outward.humanize_lint(inputs, root, config, {'chat'})
    assert result[0] == code
    assert ('not-x-but-y' in result[1]) == (code == 1)
    assert ai_tells(root) == []


def test_check_call_send_humanizes(configured, monkeypatch, capsys):
    from wuwei import outward
    root, config = configured
    inputs = {'channel': 'C1', 'text': 'Fixed the parser.'}
    assert outward.check_call(inputs, root, config, {'chat'}) == (0, '')
    assert ai_tells(root) == []
    inputs['text'] = 'We delve into the parser.'
    assert outward.check_call(inputs, root, config, {'chat'}) == (0, '')
    assert ai_tells(root) == [{'kind': 'review', 'tells': ['stock-word'], }]
    config['outward']['humanize_strict'] = True
    code, reason = outward.check_call(inputs, root, config, {'chat'})
    assert code == 1 and 'stock-word' in reason
    config['profile'] = 'standard'
    assert outward.check_call(inputs, root, config, {'chat'}) == (0, '')
    assert 'hook.warning' in (workspace.day_dir(root) / 'events.jsonl').read_text()


def test_hook_lint_humanizes_mcp_writes(configured, monkeypatch, capsys):
    from wuwei.guards.outward import check_lint
    root, config = configured
    config['outward']['allow'] = ['mcp__linear__create_comment']
    monkeypatch.setattr(workspace, 'load_config', lambda root: config)
    call = payload(root, 'We delve into the race.', tool='mcp__linear__create_comment')
    assert check_lint(call)[0] == 0
    assert ai_tells(root) == [{'kind': 'tracker', 'tells': ['stock-word'], }]
    assert check_lint(payload(root, 'Fixed the race.', tool='mcp__linear__create_comment'))[0] == 0
    assert len(ai_tells(root)) == 1
    config['outward']['humanize_strict'] = True
    code, reason = check_lint(call)
    assert code == 1 and 'stock-word' in reason


def test_every_free_text_adapter_write_goes_through_the_port():
    import inspect
    from wuwei import outward, registry, shepherd
    exempt = {('code_host', 'create_pr'): 'shepherd.raise_pr runs outward.lint and outward.humanize_lint',
              # #422: a table of validated counts; telemetry send runs security.outbound itself.
              ('code_host', 'issue'): 'telemetry.validate and security.outbound in wuwei telemetry send'}
    port = 'outward_operation.<locals>.decorate.<locals>.call'
    checked = 0
    for kind, operations in registry.PARAMETERS.items():
        for operation, parameters in operations.items():
            if not set(parameters) & (outward.TEXT_FIELDS | {'draft'}) or (kind, operation) in exempt:
                continue
            for name in registry.known(kind):
                module = registry.load(kind, {'adapters': {kind: name}})
                function = getattr(module, operation)
                assert function.__code__.co_qualname == port, (kind, name, operation)
                checked += 1
    assert checked
    assert 'humanize_lint' in inspect.getsource(shepherd.raise_pr)
    from wuwei.commands import telemetry
    assert 'security.outbound' in inspect.getsource(telemetry._send)


def test_owner_facing_templates_are_plain():
    import ast
    from pathlib import Path
    from wuwei import outward
    cli = Path(__file__).resolve().parents[1] / 'cli/wuwei'
    for name in ('report.py', 'decision.py', 'retro.py',
                 'watch.py', 'commands/status.py'):
        for node in ast.walk(ast.parse((cli / name).read_text(encoding='utf-8'))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert '\u2014' not in node.value and outward.tells(node.value) == [], (name, node.value)


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


def set_enforce(root, value):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write(f'\n[guards]\nenforce = {value}\n')


def test_invalid_mcp_name(configured):
    from wuwei.exits import PAYLOAD
    from wuwei.guards.edges import check_send
    code, reason = check_send(payload(configured[0], 'A technical claim.', tool="mcp__acme__send'x"))
    assert code == 2 and PAYLOAD in reason and "send'x" not in reason


def run_hook(monkeypatch, call):
    from wuwei.commands.hook import run
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps(call)))
    return run(SimpleNamespace(event='PreToolUse'))


PROBES = ['conversations_search_messages', 'conversations_history', 'channels_list',
          'slack_search_messages', 'slack_get_channel_history']


@pytest.mark.parametrize('posture', ['false', 'true'])
@pytest.mark.parametrize('name', [*PROBES, 'conversations_add_message', 'slack_post_message',
                                  'acme frobnicate'])
def test_probe_tools(configured, monkeypatch, capsys, posture, name):
    # #469 acceptance: the owner's seven probes and an unknown name, through the hook.
    root = configured[0]
    set_enforce(root, posture)
    server, _, name = name.rpartition(' ')
    tool = f'mcp__{server or "slack"}__{name}'
    call = payload(root, 'A technical claim.', tool=tool, channel_id='C1')
    code = run_hook(monkeypatch, call)
    err = capsys.readouterr().err
    if name in PROBES or server:  # #838 review: an unknown name runs and logs
        assert code == 0
    elif posture == 'true':
        assert code == 2 and not_allowed(tool) in err
    else:
        assert code == 0


# #492: claude.ai connectors put a UUID in the server segment and the brand in the tool name.
UUID = '00000000-0000-4000-8000-000000000001'


def head(result):
    """(code, reason before its #362 next step)."""
    return result[0], result[1].split(';')[0]


def opaque(name, server=UUID):
    return f'mcp__{server}__{name}'


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
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import resolve
    root = configured[0]
    monkeypatch.chdir(root)
    assert run_hook(monkeypatch, payload(root, 'A technical claim.',
                                         tool=opaque('conversations_search_messages'))) == 0
    assert events_of(root, 'hook.refusal') == []
    for name in ('slack_send_message', 'conversations_add_message'):
        assert resolve(opaque(name), workspace.load_config(root)) == {'slack'}
        assert check_send(payload(root, 'A technical claim.', tool=opaque(name))) == refused(opaque(name))


def write_config(root, text):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write(text)


def test_alias_resolves_and_reads_still_pass(configured):
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import check_lint, resolve
    root = configured[0]
    write_config(root, f'\n[outward.servers]\n"{UUID}" = "slack"\n')
    assert resolve(opaque('send_message'), workspace.load_config(root)) == {'slack'}
    for name in ('conversations_history', 'slack_read_channel'):
        call = payload(root, 'A technical claim.', tool=opaque(name))
        assert check_send(call) == check_lint(call) == (0, '')
    write_config(root, f'"{UUID.replace("1", "2")}" = "chat"\n')
    with pytest.raises(workspace.ConfigError):
        workspace.load_config(root)


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
RECORDED_OPAQUE = {
    **{server: {outcome: list(names) for outcome, names in lists.items()}
       for server, lists in RECORDED.items()},
    'mail': {'read': ['get_thread', 'search_threads', 'list_drafts'],
             'draft': ['create_draft', 'update_draft', 'forward', 'label_message', 'trash_thread'],
             'learn': ['send_message']},
}


# #838: a recorded read passes; every recorded write is refused until it is on outward.allow.
@pytest.mark.parametrize('tool,outcome', [
    *[(f'mcp__{server}__{name}', outcome) for server, lists in RECORDED.items()
      for outcome, names in lists.items() for name in names],
    *[(opaque(name, f'00000000-0000-4000-8000-00000000000{index}'), outcome)
      for index, lists in enumerate(RECORDED_OPAQUE.values(), 1)
      for outcome, names in lists.items() for name in names]])
def test_recorded_tools(configured, tool, outcome):
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import check_lint
    call = payload(configured[0], 'A technical claim.', tool=tool)
    assert check_lint(call) == (0, '')
    mail = YOUR_MAIL if tool.endswith(tuple(RECORDED_OPAQUE['mail']['draft'])) else None
    assert check_send(call) == ((0, '') if outcome == 'read' else refused(tool, mail))


# #495, #838: a message only the owner receives is local.
def with_owner(root):
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text() + '\n[outbound]\nowner_channel = "dm"\n'
                    '[outbound.owner]\nmail = "pat@example.test"\n'
                    '[outbound.owner.slack]\nuser = "U01"\ndm = "D01"\n')
    return workspace.load_config(root)


def test_owner_config(configured):
    root, config = configured
    assert config['outbound']['owner'] == {'slack': {'user': '', 'dm': ''}, 'mail': '', 'code_host': '',
                                           'pages': []}
    assert config['outbound']['owner_channel'] == 'session'
    config = with_owner(root)
    assert config['outbound']['owner'] == {
        'slack': {'user': 'U01', 'dm': 'D01'}, 'mail': 'pat@example.test', 'code_host': '', 'pages': []}
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


def owner_events(root):
    from wuwei import watch
    path = workspace.day_dir(root) / 'events.jsonl'
    return [row for row in (watch.records(path) if path.exists() else [])
            if row['kind'] == 'outward.to_owner']


def test_to_owner_event_and_lint(configured):
    from wuwei import outward
    root = configured[0]
    config = with_owner(root)
    assert outward.check_call({'text': 'Your build is green', 'channel': 'D01'}, root, config, {'slack'}) == (0, '')
    assert [row['payload'] for row in owner_events(root)] == [{'channel': 'slack'}]
    assert outward.check_call({'text': 'fixed in abc1234', 'channel': 'C1'}, root, config, {'slack'}) == (0, '')
    assert len(owner_events(root)) == 1
    assert outward.check_lint({'text': 'Pat, your build is green', 'channel': 'D01'}, root, config, {'slack'}) == (0, '')
    assert 'third-person' in outward.check_lint(
        {'text': 'Pat, your build is green', 'channel': 'C1'}, root, config, {'slack'})[1]
    assert outward.check_lint({'text': 'Ready \U0001F600', 'channel': 'D01'}, root, config, {'slack'})[0] == 1


@pytest.mark.parametrize('posture', ['false', 'true'])
def test_guard_to_owner_either_way(configured, posture):
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import check_lint
    root = configured[0]
    with_owner(root)
    set_enforce(root, posture)
    call = payload(root, 'Your build is green', tool=opaque('slack_send_message'), channel='D01')
    assert check_send(call) == (0, '')
    assert check_lint(call) == (0, '')
    assert len(owner_events(root)) == 1


def test_guard_owner_mail_with_outside_cc_is_not_owner_only(configured):
    # #501 review F1: an outside cc or bcc means the owner is not the only reader.
    from wuwei.guards.edges import check_send
    root = configured[0]
    with_owner(root)
    set_enforce(root, 'true')
    mail = {'to': 'pat@example.test', 'subject': 'numbers', 'body': 'Our layoffs list'}
    call = payload(root, tool=opaque('send_mail'))
    call['tool_input'] = mail
    assert check_send(call) == (0, '')
    for extra in ({'cc': ['outsider@evil.test']}, {'bcc': 'outsider@evil.test'}):
        call['tool_input'] = {**mail, **extra}
        assert check_send(call) == refused(opaque('send_mail')), extra


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


def test_connector_writes_through_the_guard(configured):
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import check_lint
    root = configured[0]
    tool = 'mcp__notion__append_block_children'
    notion = {**payload(root, tool=tool), 'tool_input': shaped(CORPUS[3][1], 'Your salary is set')}
    assert check_send(notion) == refused(tool, PAGES.format(PAGE))
    write_config(root, f'\n[outward.servers]\n"{UUID}" = "tracker"\n')
    allow(root, opaque('addCommentToJiraIssue'))
    jira = {**payload(root, tool=opaque('addCommentToJiraIssue')),
            'tool_input': {'issue_key': 'DEMO-12', 'comment': 'tests passed'}}
    assert check_send(jira) == check_lint(jira) == (0, '')


def test_text_fields_keep_known_checks():
    from wuwei import outward
    inputs = {'title': 'a', 'draft': {'description': 'b', 'teamId': 't'}, 'channel': 'C1',
              'recipients': ['dev'], 'is_dm': False, 'issue_number': 3, 'thread': None}
    assert outward._text(inputs) == (['b', 'a'], ['C1', 'dev'])
    assert outward._text({'parent': {'page_id': 'p'}, 'title': 'a'}) == (['a'], ['p'])  # #838
    for bad in ({'is_dm': 'false'}, {'recipients': 'dev'}, {'channel': {'text': 'hidden'}},
                {'issue_number': True}, {'draft': 'x'}, {'draft': {'draft': {}}}):
        with pytest.raises(ValueError):
            outward._text({'text': 'a', **bad})


def test_textless_write(configured):
    # #501: a write without text has nothing to lint; the allowlist decides it.
    from wuwei import outward
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import check_lint
    root, config = configured
    tool = opaque('resolve_issue')
    resolve = {**payload(root, tool=tool), 'tool_input': {'issue_id': 'PROJ-1', 'status': 'resolved'}}
    assert check_send(resolve) == refused(tool)
    allow(root, tool)
    assert check_send(resolve) == check_lint(resolve) == (0, '')
    assert outward.check_lint({'issue_id': 'PROJ-1'}, root, config, {'other'}) == (0, '')
    assert outward.check_lint({'text': '', 'channel': 'C1'}, root, config, {'chat'})[0] == 2


def test_tool_input_not_an_object(configured):
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import check_lint
    root = configured[0]
    for check in (check_send, check_lint):
        for inputs, shape in (([], 'list'), ('x', 'str')):
            call = {**payload(root, tool=opaque('slack_send_message')), 'tool_input': inputs}
            code, reason = check(call)
            assert (code, reason) == (2, f'outward: tool_input is not an object; got {shape}; '
                                         'pass the tool arguments as a JSON object')


LOCAL_TOOLS = ['mcp__terminal__run_in_terminal', 'mcp__terminal__open_terminal_tab',
               'mcp__terminal__stop_terminal_tab', 'mcp__Claude_Code_iOS_Simulator__control',
               'mcp__Claude_Preview__preview_start', 'mcp__Claude_Browser__preview_start',
               'mcp__computer-use__open_application']


def local_call(root, tool, command='sleep 600'):
    call = payload(root, tool=tool)
    call['tool_input'] = {'command': command}
    return call


@pytest.mark.parametrize('posture', ['false', 'true'])
@pytest.mark.parametrize('tool', LOCAL_TOOLS)
def test_local_tools_pass(configured, posture, tool):
    # #727: a tool that acts only on the owner's machine is never refused by the allowlist.
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import check_lint, resolve
    root = configured[0]
    set_enforce(root, posture)
    call = local_call(root, tool)
    assert check_send(call) == check_lint(call) == (0, '')
    assert resolve(tool, workspace.load_config(root)) == {'local'}


def test_local_shapes_are_exact(configured):
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import resolve
    root, config = configured
    assert check_send(local_call(root, 'mcp__plugin_x_terminal__run_job')) == refused('mcp__plugin_x_terminal__run_job')
    assert resolve('mcp__Claude_Browser__navigate', config) != {'local'}
    assert check_send(local_call(root, 'mcp__terminal__read_terminal')) == (0, '')
    assert resolve('mcp__terminal__read_terminal', config) == set()


def test_local_alias(configured):
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import check_lint, resolve
    root = configured[0]
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('\n[outward.servers]\nacme = "local"\nterminal = "mail"\n')
    call = payload(root, 'A technical claim.', tool='mcp__acme__send_message')
    assert check_send(call) == check_lint(call) == (0, '')
    assert resolve('mcp__terminal__run_in_terminal', workspace.load_config(root)) == {'mail'}


def test_local_keeps_canary_floor(configured):
    from wuwei import security
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import check_lint
    root = configured[0]
    canary = (security.load(root) or security.initialize(root / '.wuwei'))['canary']
    call = local_call(root, 'mcp__terminal__open_terminal_tab', f'echo {canary}')
    code, reason = check_send(call)
    assert code == 1 and reason.startswith('outward: security.')
    assert check_lint(call) == (0, '')


def test_terminal_hook_judges_the_command(configured, monkeypatch, capsys):
    # #727: through the hook the terminal's command meets the Bash guards, as the same Bash call.
    root = configured[0]
    monkeypatch.chdir(root)
    assert run_hook(monkeypatch, local_call(root, 'mcp__terminal__run_in_terminal')) == 0
    day = (workspace.day_dir(root) / 'state.json').relative_to(root)
    write = f"python3 -c 'open(\"{day}\", \"w\")'"
    found = []
    for tool in ('Bash', 'mcp__terminal__run_in_terminal'):
        capsys.readouterr()
        code = run_hook(monkeypatch, local_call(root, tool, write))
        found.append((code, capsys.readouterr().err.splitlines()[:1]))
    assert found[0][0] == 2 and found[0] == found[1]
    assert run_hook(monkeypatch, local_call(root, 'mcp__terminal__run_in_terminal', 3)) == 2


# #838: outward send is an exact tool allowlist; the owner's own surfaces are local.
SEND = 'mcp__slack__slack_send_message'


def not_allowed(tool):
    """The allow line every unlisted-send refusal names."""
    return f"bin/wuwei config set outward.allow '[\"{tool}\"]' --add"


PAGES = "outbound.owner.pages '[\"{}\"]' --add"
YOUR_MAIL = "outbound.owner.mail '\"<your address>\"'"


def refused(tool, surface=None):
    """The exact unlisted-send refusal; surface is the owner's-surface config set argument."""
    first = (f'if it is your own surface, the owner adds it: bin/wuwei config set {surface} '
             '(it asks its Owner step card); else ' if surface else '')
    return (1, f'outward: {tool} may send to other people and is not on outward.allow; {first}the '
               f'owner adds it: {not_allowed(tool)} (it asks its Owner step card), then run the call again')


def allow(root, *tools):
    write_config(root, f'\n[outward]\nallow = {json.dumps(list(tools))}\n')


@pytest.mark.parametrize('enforce', ['false', 'true'])
def test_unlisted_send_is_refused_with_its_line(configured, monkeypatch, capsys, enforce):
    from wuwei.guards.edges import check_send
    root = configured[0]
    set_enforce(root, enforce)
    call = payload(root, 'Thanks', tool=SEND, channel='C1')
    assert check_send(call) == refused(SEND)
    monkeypatch.chdir(root)
    assert run_hook(monkeypatch, call) == (2 if enforce == 'true' else 0)
    out = capsys.readouterr()
    if enforce == 'true':
        assert not_allowed(SEND) in out.err
    else:
        assert 'Nudge:' in out.out and 'owner adds' not in out.out


def _case_listed_send_passes_exactly(configured):
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import check_lint
    root = configured[0]
    allow(root, SEND)
    call = payload(root, 'Thanks', tool=SEND, channel='C1')
    assert check_send(call) == check_lint(call) == (0, '')
    for tool in ('mcp__slack__slack_schedule_message', 'mcp__Slack__slack_send_message'):
        assert check_send(payload(root, 'Thanks', tool=tool, channel='C1')) == refused(tool)
    assert check_send(payload(root, 'Thanks', tool='mcp__x__resolve_library_id', channel='C1')) == (0, '')


def _case_listed_send_keeps_the_lint_and_canary(configured):
    from wuwei import security
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import check_lint
    root = configured[0]
    allow(root, SEND)
    assert 'third-person' in check_lint(payload(root, 'Pat fixed it', tool=SEND, channel='C1'))[1]
    canary = (security.load(root) or security.initialize(root / '.wuwei'))['canary']
    code, reason = check_send(payload(root, f'see {canary}', tool=SEND, channel='C1'))
    assert code == 1 and reason.startswith('outward: security.')


@pytest.mark.parametrize("scenario_fn", [
    _case_listed_send_passes_exactly,
    _case_listed_send_keeps_the_lint_and_canary,
])
def test_listed_send_cases_1104(configured, scenario_fn):
    scenario_fn(configured)


def with_surfaces(root):
    write_config(root, '\n[outbound.owner]\nmail = "pat@example.test"\npages = ["F1", "abc"]\n'
                       '[outbound.owner.slack]\nuser = "U01"\ndm = "D01"\n')
    return workspace.load_config(root)


@pytest.mark.parametrize('tool,inputs', [
    (SEND, {'channel': 'D01', 'text': 'Pat, your build is green'}),
    ('mcp__slack__slack_update_canvas', {'canvas_id': 'F1', 'content': 'Notes'}),
    ('mcp__notion__notion-create-pages', {'parent': {'page_id': 'abc'}, 'title': 'Notes'}),
    ('mcp__notion__notion-update-page', {'page_id': 'abc', 'title': 'Notes'}),
    ('mcp__gmail__send_email', {'to': 'pat@example.test', 'body': 'Notes'}),
])
def test_owner_surfaces_are_local(configured, tool, inputs):
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import check_lint
    root = configured[0]
    with_surfaces(root)
    write_config(root, '\n[outward.servers]\ngmail = "mail"\n')
    call = payload(root, tool=tool)
    call['tool_input'] = inputs
    assert check_send(call) == check_lint(call) == (0, '')
    assert len(owner_events(root)) == 1


@pytest.mark.parametrize('tool,inputs', [
    ('mcp__gmail__send_email', {'to': 'pat@example.test', 'cc': ['x@other.test'], 'body': 'Hi'}),
    (SEND, {'channel': 'D01', 'recipient': 'C9', 'text': 'Hi'}),
    # #838 review F2: a mail draft or reply-all, and any recipient-like key, is never owner-only.
    ('mcp__gmail__send_email', {'to': 'pat@example.test', 'draftId': 'r1', 'body': 'Hi'}),
    ('mcp__gmail__send_email', {'to': 'pat@example.test', 'draft_id': 'r1', 'body': 'Hi'}),
    ('mcp__gmail__send_email', {'to': 'pat@example.test', 'replyAll': True, 'body': 'Hi'}),
    ('mcp__gmail__send_email', {'to': 'pat@example.test', 'reply_all': True, 'body': 'Hi'}),
    (SEND, {'channel': 'D01', 'users': ['U02'], 'text': 'Hi'}),
    (SEND, {'channel': 'D01', 'userIds': ['U02'], 'text': 'Hi'}),
    (SEND, {'channel': 'D01', 'emails': ['x@other.test'], 'text': 'Hi'}),
    (SEND, {'channel': 'D01', 'participants': ['U02'], 'text': 'Hi'}),
    (SEND, {'channel': 'D01', 'members': ['U02'], 'text': 'Hi'}),
    (SEND, {'channel': 'D01', 'invite': {'attendee_emails': ['x@other.test']}, 'text': 'Hi'}),
    ('mcp__notion__notion-update-page', {'page_id': 'abc', 'share': {'person_ids': ['p2']}, 'title': 'Hi'}),
    ('mcp__slack__slack_update_canvas', {'content': 'Notes'}),
    ('mcp__notion__notion-create-pages', {'title': 'Notes'}),
])
def test_not_only_the_owner_is_not_local(configured, tool, inputs):
    from wuwei.guards.edges import check_send
    root = configured[0]
    with_surfaces(root)
    write_config(root, '\n[outward.servers]\ngmail = "mail"\n')
    call = payload(root, tool=tool)
    call['tool_input'] = inputs
    page = inputs.get('page_id')
    assert check_send(call) == refused(tool, page and PAGES.format(page))
    assert not owner_events(root)


def test_owner_unset_resolves_nothing(configured):
    from wuwei.guards.edges import check_send
    root = configured[0]
    assert workspace.load_config(root)['outbound']['owner']['pages'] == []
    assert check_send(payload(root, 'Hi', tool=SEND, channel='D01')) == refused(SEND)


# #838 review F1: a tool that is neither a read nor a write by name, with no channel, runs and logs.
@pytest.mark.parametrize('enforce', ['false', 'true'])
@pytest.mark.parametrize('tool', ['mcp__Claude_Browser__computer', 'mcp__claude-in-chrome__navigate'])
def test_unknown_tool_runs_and_logs(configured, monkeypatch, capsys, enforce, tool):
    from wuwei.guards.edges import check_send
    from wuwei.guards.outward import check_lint
    root = configured[0]
    set_enforce(root, enforce)
    call = payload(root, tool=tool)
    call['tool_input'] = {'url': 'https://example.test'}
    assert check_send(call) == (0, '')
    code, reason = check_lint(call)
    assert code == 1 and not_allowed(tool) in reason and 'neither a read nor a write' in reason
    monkeypatch.chdir(root)
    assert run_hook(monkeypatch, call) == 0
    [event] = events_of(root, 'guard.would_refuse')
    assert event['payload']['guard'] == 'outward' and not_allowed(tool) in event['payload']['reason']


# #838 review F3: an owner disposition marker never leaves through the guard or a port.
def test_owner_marker_refused_without_a_canary(configured):
    from wuwei import outward
    from wuwei.guards.edges import check_send
    root, config = configured
    allow(root, SEND)
    assert check_send(payload(root, 'WUWEI parked x', tool=SEND, channel='C1')) == (1, outward.OWNER_MARKERS)
    assert outward.check_call({'text': 'WUWEI parked x', 'channel': 'C1'}, root, config, {'slack'}) == (
        1, outward.OWNER_MARKERS)


# #838 review: the own-surface line only for a canvas or page id; never a channel, DM, user or address.


@pytest.mark.parametrize('tool,inputs,surface', [
    (SEND, {'channel': 'C1', 'text': 'Hi'}, None),
    (SEND, {'channel': 'D01', 'text': 'Hi'}, None),
    (SEND, {'channel': 'U02', 'text': 'Hi'}, None),
    (SEND, {'channel': 'F123', 'text': 'Hi'}, PAGES.format('F123')),
    ('mcp__slack__slack_update_canvas', {'canvas_id': 'F9', 'content': 'Hi'}, PAGES.format('F9')),
    ('mcp__slack__slack_update_canvas', {'canvas_id': "F9'; rm -rf x", 'content': 'Hi'}, PAGES.format('<id>')),
    ('mcp__slack__slack_update_canvas', {'content': 'Hi'}, None),
    ('mcp__notion__notion-update-page', {'page_id': 'abc', 'title': 'Hi'}, PAGES.format('abc')),
    ('mcp__notion__notion-create-pages', {'parent': {'page_id': 'abc'}, 'title': 'Hi'}, PAGES.format('abc')),
    ('mcp__gmail__send_email', {'to': 'pat@example.test', 'body': 'Hi'}, YOUR_MAIL),
])
def test_refusal_offers_a_canvas_or_page_first(configured, tool, inputs, surface):
    from wuwei.guards.edges import check_send
    root = configured[0]
    write_config(root, '\n[outward.servers]\ngmail = "mail"\n')
    call = payload(root, tool=tool)
    call['tool_input'] = inputs
    assert check_send(call) == refused(tool, surface)


def test_refusal_never_offers_a_set_mail_address(configured):
    from wuwei.guards.edges import check_send
    root = configured[0]
    with_owner(root)
    write_config(root, '\n[outward.servers]\ngmail = "mail"\n')
    call = payload(root, tool='mcp__gmail__send_email')
    call['tool_input'] = {'to': 'x@other.test', 'body': 'Hi'}
    assert check_send(call) == refused('mcp__gmail__send_email')


def test_share_is_a_write():
    from wuwei.guards.outward import tool_kind
    assert tool_kind('mcp__drive__share_file') == 'write'


def test_refusal_on_another_channel_names_no_surface(configured):
    from wuwei.guards.edges import check_send
    tool = 'mcp__linear__save_issue'
    result = check_send(payload(configured[0], 'Hi', tool=tool, channel='C1'))
    assert result == refused(tool) and 'outbound.owner' not in result[1]

@pytest.mark.parametrize('server,allowed', [
    ('22222222-2222-4222-8222-222222222222', True),
    ('11111111-1111-4111-8111-111111111111', True),
    ('named-server', False), ('not-a-uuid', False),
])
def test_uuid_allow_survives_account_switch(configured, server, allowed):
    from wuwei.guards.edges import check_send
    with (configured[0] / '.wuwei/config.toml').open('a') as stream:
        stream.write('\n[outward]\nallow=["mcp__11111111-1111-4111-8111-111111111111__slack_send_message"]\n')
    payload = {'cwd': str(configured[0]), 'tool_name': f'mcp__{server}__slack_send_message',
               'tool_input': {'channel': 'C123', 'text': 'Hello'}}
    assert check_send(payload)[0] == (0 if allowed else 1)
    payload['tool_name'] = f'mcp__{server}__slack_delete_message'
    assert check_send(payload)[0] == 1
