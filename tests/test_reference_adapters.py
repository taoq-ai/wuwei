"""Offline recorded HTTP exchange tests for the reference adapters."""

import importlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request

import pytest


class Reply:
    def __init__(self, payload, status=200):
        self.payload = json.dumps(payload).encode()
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        pass

    def read(self, *unused):
        return self.payload


RECORDINGS = json.loads((Path(__file__).parent / 'fixtures/reference_adapters/recordings.json').read_text())


def replay(monkeypatch, *responses):
    calls = []
    responses = iter(responses)

    def urlopen(request, timeout=None):
        assert isinstance(request, Request)
        assert timeout == 30
        calls.append((request.full_url, dict(request.header_items()),
                      json.loads(request.data) if request.data else None))
        answer = next(responses)
        if isinstance(answer, Exception):
            raise answer
        return Reply(answer)

    monkeypatch.setattr('urllib.request.urlopen', urlopen)
    return calls


def test_http_request_methods_and_empty_body(monkeypatch):
    from adapters import _http
    seen = []

    def urlopen(request, timeout=None):
        seen.append((request.get_method(), request.data, dict(request.header_items())))
        reply = Reply({'ok': True})
        if request.get_method() == 'PUT':
            reply.payload, reply.status = b'', 204
        return reply

    monkeypatch.setattr('urllib.request.urlopen', urlopen)
    assert _http.request('https://example.test/a', 't', None, method='GET') == {'ok': True}
    assert _http.request('https://example.test/a', 't', {'x': 1}, method='PUT',
                         authorization='Basic') == {}
    assert _http.request('https://example.test/a', 't', {'y': 2}) == {'ok': True}
    assert [(method, data) for method, data, _ in seen] == [
        ('GET', None), ('PUT', b'{"x": 1}'), ('POST', b'{"y": 2}')]
    assert seen[1][2]['Authorization'] == 'Basic t' and seen[2][2]['Authorization'] == 'Bearer t'


def test_linear_replay(monkeypatch):
    linear = importlib.import_module('adapters.tracker.linear')
    monkeypatch.setenv('LINEAR_API_KEY', 'private-linear-key')
    calls = replay(monkeypatch, *RECORDINGS['linear'][:2],
                   {'data': {'issue': {'team': {'id': 'team-1'}}}},
                   {'data': {'workflowStates': {'nodes': [{'id': 'state-1', 'name': 'In Review'}],
                                                'pageInfo': {'hasNextPage': False}}}},
                   RECORDINGS['linear'][2], RECORDINGS['linear'][4])
    assert linear.claim('ABC-1').exit == 0
    assert linear.transition('ABC-1', 'In Review').exit == 0
    assert linear.history('ABC-1').data == [{'id': 'change-1'}]
    assert len(calls) == 6
    assert all(url == 'https://api.linear.app/graphql' for url, _, _ in calls)
    assert all('private-linear-key' in headers['Authorization'] for _, headers, _ in calls)
    assert calls[1][2]['variables']['input'] == {'assigneeId': 'user-1'}
    assert calls[4][2]['variables']['input'] == {'stateId': 'state-1'}


def test_linear_failure_is_redacted(monkeypatch):
    linear = importlib.import_module('adapters.tracker.linear')
    monkeypatch.setenv('LINEAR_API_KEY', 'private-linear-key')
    replay(monkeypatch, {'errors': [{'message': 'private-linear-key rejected'}]})
    result = linear.history('ABC-1')
    assert result.exit == 2 and result.data is None
    assert 'private-linear-key' not in result.reason


def test_public_linear_create_draft_reaches_policy_without_http(monkeypatch, tmp_path):
    linear = importlib.import_module('adapters.tracker.linear')
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[owner]\nname = "Pat"\npronouns = "they/them"\n[outbound]\ndefault_tier = "ask"\n')
    calls = replay(monkeypatch)
    result = linear.create({'teamId': 'team-1', 'stateId': 'state-1',
                            'assigneeId': 'user-1', 'projectId': 'project-1',
                            'title': 'New item'}, root=tmp_path)
    assert result.exit == 1
    assert calls == []


def test_public_linear_create_sends_after_policy_clearance(monkeypatch, tmp_path):
    linear = importlib.import_module('adapters.tracker.linear')
    from wuwei import outward
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('LINEAR_API_KEY', 'private-linear-key')
    monkeypatch.setattr(outward, 'check_call', lambda *args, **kwargs: (0, ''))
    calls = replay(monkeypatch, {'data': {'issueCreate': {'success': True, 'issue': {
        'id': 'issue-2', 'identifier': 'ENG-2', 'url': 'https://linear.app/acme/issue/ENG-2'}}}})
    draft = {'teamId': 'team-1', 'title': 'New item'}
    result = linear.create(draft, root=tmp_path)
    assert result.exit == 0
    assert result.data == {'id': 'ENG-2', 'url': 'https://linear.app/acme/issue/ENG-2'}
    assert len(calls) == 1
    assert calls[0][2]['variables']['input'] == draft


def test_slack_replay(monkeypatch):
    slack = importlib.import_module('adapters.chat.slack')
    monkeypatch.setenv('SLACK_BOT_TOKEN', 'private-slack-token')
    calls = replay(monkeypatch, *RECORDINGS['slack'])
    # Exercise the provider functions below the existing outward guard. The guard has
    # separate policy tests and a workspace fixture is not part of these recordings.
    assert slack._send({'channel': 'C123', 'text': 'fixed in abcdef0.', 'thread_ts': '1.0'})['ts'] == '1.2'
    assert slack._send({'channel': 'D123', 'text': 'fixed in abcdef0.'})['ts'] == '2.3'
    assert calls[0][0].endswith('/chat.postMessage')
    assert calls[0][2] == {'channel': 'C123', 'text': 'fixed in abcdef0.', 'thread_ts': '1.0'}
    assert calls[1][2] == {'channel': 'D123', 'text': 'fixed in abcdef0.'}
    assert calls[0][1]['Authorization'] == 'Bearer private-slack-token'


def test_slack_api_base_override(monkeypatch):
    slack = importlib.import_module('adapters.chat.slack')
    monkeypatch.setenv('SLACK_BOT_TOKEN', 'private-slack-token')
    monkeypatch.setenv('SLACK_API_BASE', 'http://127.0.0.1:9/fake')
    calls = replay(monkeypatch, {'ok': True, 'channel': 'C1', 'ts': '1'}, history_page())
    assert slack._send({'channel': 'C1', 'text': 'fixed in abcdef0.'})['ts'] == '1'
    assert slack.history('C1') == []
    assert calls[0][0] == 'http://127.0.0.1:9/fake/chat.postMessage'
    assert calls[1][0].startswith('http://127.0.0.1:9/fake/conversations.history?')


@pytest.mark.parametrize('base', ['http://example.test/api/', 'ftp://example.test/api/'])
def test_slack_api_base_must_be_https_or_loopback(monkeypatch, capsys, base):
    slack = importlib.import_module('adapters.chat.slack')
    monkeypatch.setenv('SLACK_BOT_TOKEN', 'private-slack-token')
    monkeypatch.setenv('SLACK_OWNER_DM_CHANNEL', 'D1')
    monkeypatch.setenv('SLACK_API_BASE', base)
    calls = replay(monkeypatch)
    result = slack.dm.__wrapped__('x')
    assert result.exit == 2 and base not in result.reason and 'example.test' not in result.reason
    assert base not in str(capsys.readouterr())
    assert calls == []


def history_page(*rows, next_cursor=''):
    return {'ok': True, 'messages': list(rows), 'response_metadata': {'next_cursor': next_cursor}}


def rate_limited():
    return HTTPError('https://slack.com/api/conversations.history', 429, 'Too Many Requests',
                     {'Retry-After': '30'}, None)


def test_slack_sent_replay(monkeypatch):
    slack = importlib.import_module('adapters.chat.slack')
    monkeypatch.setenv('SLACK_BOT_TOKEN', 'private-slack-token')
    replay(monkeypatch, history_page(
        {'user': 'U0OWNER', 'text': 'done', 'ts': '3.000000'},
        {'user': 'U0OWNER', 'bot_id': 'B1', 'text': 'draft', 'ts': '2.000000'},
        {'user': 'U9', 'text': 'thanks', 'ts': '1.000000'}), rate_limited())
    assert slack.sent('C1', ['U0OWNER']).data == [{'sender': 'U0OWNER', 'text': 'done'}]
    result = slack.sent('C1', ['U0OWNER'])
    assert result.exit == 2 and 'rate limited' in result.reason and '30' in result.reason
    replay(monkeypatch, HTTPError('https://slack.com/api/conversations.history', 403, 'private', {}, None))
    assert 'HTTP 403: credential has no access' in slack.sent('C1', ['U0OWNER']).reason


def test_greptile_replay(monkeypatch):
    greptile = importlib.import_module('adapters.review_bot.greptile')
    monkeypatch.setenv('GREPTILE_API_KEY', 'private-greptile-key')
    calls = replay(monkeypatch, *RECORDINGS['greptile'])
    assert greptile.score('owner/repo#7').data == 4
    assert greptile.open_findings('owner/repo#7').data == [
        {'id': 'finding-1', 'body': 'Bug', 'addressed': False,
         'isGreptileComment': True}]
    assert [body['params']['name'] for _, _, body in calls] == [
        'get_merge_request', 'get_merge_request', 'list_merge_request_comments']
    assert all(url == 'https://api.greptile.com/mcp' for url, _, _ in calls)


def test_greptile_missing_score_is_unmeasured(monkeypatch):
    greptile = importlib.import_module('adapters.review_bot.greptile')
    monkeypatch.setenv('GREPTILE_API_KEY', 'private-greptile-key')
    replay(monkeypatch, {'jsonrpc': '2.0', 'id': 1, 'result': {'content': [
        {'type': 'text', 'text': '{"mergeRequest":{"codeReviews":[{"status":"COMPLETED"}],"comments":{"greptile":[]}}}'}]}})
    assert greptile.score('owner/repo#7').exit == 2


def test_none_fallback_after_adapter_removed(monkeypatch, tmp_path):
    from wuwei import registry
    monkeypatch.setattr(registry, 'ADAPTERS', tmp_path)
    for kind in ('tracker', 'chat', 'review_bot'):
        directory = tmp_path / kind
        directory.mkdir()
        (directory / 'none.py').write_text('')
        assert registry.known(kind) == ['none']
        with pytest.raises(ValueError):
            registry.validate(kind, {'tracker': 'linear', 'chat': 'slack',
                                     'review_bot': 'greptile'}[kind])


def test_slack_identity_tokens(monkeypatch):
    slack = importlib.import_module('adapters.chat.slack')
    monkeypatch.setenv('SLACK_BOT_TOKEN', 'bot-secret')
    monkeypatch.setenv('SLACK_USER_TOKEN', 'user-secret')
    calls = replay(monkeypatch, {'ok': True, 'channel': 'C1', 'ts': '1'},
                   {'ok': True, 'channel': 'C1', 'ts': '2'})
    assert slack._send({'channel': 'C1', 'text': 'fixed in abcdef0.'}, identity='connector')['ts'] == '1'
    assert slack._send({'channel': 'C1', 'text': 'fixed in abcdef0.'}, identity='custom_app')['ts'] == '2'
    assert calls[0][1]['Authorization'] == 'Bearer user-secret'
    assert calls[1][1]['Authorization'] == 'Bearer bot-secret'


def test_slack_api_error_body_fails_closed(monkeypatch):
    slack = importlib.import_module('adapters.chat.slack')
    monkeypatch.setenv('SLACK_BOT_TOKEN', 'bot-secret')
    replay(monkeypatch, {'ok': False, 'error': 'bot-secret invalid'})
    with pytest.raises(slack.Failure) as failure:
        slack._send({'channel': 'C1', 'text': 'fixed in abcdef0.'})
    assert 'bot-secret' not in str(failure.value)


def test_greptile_error_body_fails_closed(monkeypatch):
    greptile = importlib.import_module('adapters.review_bot.greptile')
    monkeypatch.setenv('GREPTILE_API_KEY', 'private-key')
    replay(monkeypatch, {'jsonrpc': '2.0', 'id': 1,
                         'error': {'message': 'private-key expired'}})
    result = greptile.open_findings('owner/repo#7')
    assert result.exit == 2 and 'private-key' not in result.reason


def test_http_failure_and_timeout_are_unmeasured(monkeypatch):
    linear = importlib.import_module('adapters.tracker.linear')
    monkeypatch.setenv('LINEAR_API_KEY', 'private-key')
    for failure in (HTTPError('https://api.linear.app/graphql', 401, 'private-key', {}, None),
                    TimeoutError('private-key')):
        replay(monkeypatch, failure)
        result = linear.history('ABC-1')
        assert result.exit == 2 and result.data is None
        assert 'private-key' not in result.reason


@pytest.mark.parametrize('code, text', [
    (401, 'HTTP 401: credential rejected'), (403, 'HTTP 403: credential has no access'),
    (404, 'HTTP 404: not found or not visible'), (429, 'HTTP 429: rate limited'),
    (500, 'HTTP 500: provider error'), (503, 'HTTP 503: provider error'), (418, 'HTTP 418')])
def test_http_failure_names_the_status_and_a_hint(monkeypatch, code, text):
    linear = importlib.import_module('adapters.tracker.linear')
    monkeypatch.setenv('LINEAR_API_KEY', 'private-key')
    replay(monkeypatch, HTTPError('https://api.linear.app/graphql', code, 'private-key body', {}, None))
    result = linear.history('ABC-1')
    assert result.exit == 2 and result.reason.startswith(f'linear.history: could not run: {text}')
    assert 'private-key' not in result.reason and '\n' not in result.reason


def test_greptile_stale_review_is_unmeasured(monkeypatch):
    greptile = importlib.import_module('adapters.review_bot.greptile')
    monkeypatch.setenv('GREPTILE_API_KEY', 'private-key')
    replay(monkeypatch, {'jsonrpc': '2.0', 'id': 1, 'result': {'content': [
        {'type': 'text', 'text': json.dumps({'mergeRequest': {
            'reviewAnalysis': {'hasNewCommitsSinceReview': True},
            'codeReviews': [{'status': 'COMPLETED'}],
            'comments': {'greptile': [{'body': 'Confidence Score: 5/5'}]}}})}]}})
    assert greptile.score('owner/repo#7').exit == 2


def test_greptile_truncated_findings_are_unmeasured(monkeypatch):
    greptile = importlib.import_module('adapters.review_bot.greptile')
    monkeypatch.setenv('GREPTILE_API_KEY', 'private-key')
    replay(monkeypatch, RECORDINGS['greptile'][0],
           {'jsonrpc': '2.0', 'id': 1, 'result': {'content': [
               {'type': 'text', 'text': '{"comments":[],"total":1}'}]}})
    assert greptile.open_findings('owner/repo#7').exit == 2


def test_public_slack_post_returns_owner_draft_without_http(monkeypatch, tmp_path):
    slack = importlib.import_module('adapters.chat.slack')
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[owner]\nname = "Pat"\npronouns = "they/them"\n[outbound]\ndefault_tier = "ask"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    calls = replay(monkeypatch)
    result = slack.post('C123', 'Please review this.', None, root=tmp_path)
    assert result.exit == 1 and result.data == 'Please review this.'
    assert calls == []


def test_public_slack_custom_app_uses_bot_identity(monkeypatch, tmp_path):
    slack = importlib.import_module('adapters.chat.slack')
    from wuwei import outward
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[chat]\nidentity = "custom_app"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('SLACK_BOT_TOKEN', 'bot-secret')
    monkeypatch.setenv('SLACK_USER_TOKEN', 'user-secret')
    monkeypatch.setattr(outward, 'check_call', lambda *args, **kwargs: (0, ''))
    calls = replay(monkeypatch, {'ok': True, 'channel': 'C123', 'ts': '1.2'})
    result = slack.post('C123', 'fixed in abcdef0.', None, root=tmp_path)
    assert result.exit == 0
    assert calls[0][1]['Authorization'] == 'Bearer bot-secret'


def test_greptile_accepts_mcp_event_stream(monkeypatch):
    greptile = importlib.import_module('adapters.review_bot.greptile')
    monkeypatch.setenv('GREPTILE_API_KEY', 'private-key')
    seen = []
    result = {'jsonrpc': '2.0', 'id': 1, 'result': {'content': [
        {'type': 'text', 'text': '{"comments":[],"total":0}'}]}}

    def urlopen(request, timeout=None):
        seen.append(dict(request.header_items()))
        answer = Reply(result)
        response = RECORDINGS['greptile'][0] if len(seen) == 1 else result
        answer.payload = ('event: message\ndata: ' + json.dumps(response) + '\n\n').encode()
        answer.headers = {'Content-Type': 'text/event-stream'}
        return answer

    monkeypatch.setattr('urllib.request.urlopen', urlopen)
    assert greptile.open_findings('owner/repo#7').data == []
    assert seen[0]['Accept'] == 'application/json, text/event-stream'


@pytest.mark.parametrize('module,variable,call', [
    ('adapters.tracker.linear', 'LINEAR_API_KEY', lambda adapter: adapter.history('ABC-1')),
    ('adapters.review_bot.greptile', 'GREPTILE_API_KEY',
     lambda adapter: adapter.open_findings('owner/repo#7')),
])
def test_missing_credential_never_calls_network(monkeypatch, module, variable, call):
    monkeypatch.delenv(variable, raising=False)
    requests = replay(monkeypatch)
    result = call(importlib.import_module(module))
    assert result.exit == 2 and result.data is None
    assert variable in result.reason
    assert requests == []


def test_slack_missing_credential_never_calls_network(monkeypatch):
    slack = importlib.import_module('adapters.chat.slack')
    monkeypatch.delenv('SLACK_BOT_TOKEN', raising=False)
    requests = replay(monkeypatch)
    with pytest.raises(slack.Failure, match='SLACK_BOT_TOKEN is missing'):
        slack._send({'channel': 'C1', 'text': 'text'}, identity='custom_app')
    assert requests == []


def test_greptile_empty_findings_require_completed_current_review(monkeypatch):
    greptile = importlib.import_module('adapters.review_bot.greptile')
    monkeypatch.setenv('GREPTILE_API_KEY', 'private-key')
    missing = {'jsonrpc': '2.0', 'id': 1, 'result': {'content': [
        {'type': 'text', 'text': json.dumps({'mergeRequest': {
            'codeReviews': [], 'reviewAnalysis': {'hasNewCommitsSinceReview': False}}})}]}}
    empty = {'jsonrpc': '2.0', 'id': 1, 'result': {'content': [
        {'type': 'text', 'text': '{"comments":[],"total":0}'}]}}
    replay(monkeypatch, missing, empty)
    assert greptile.open_findings('owner/repo#7').exit == 2
    complete = {'jsonrpc': '2.0', 'id': 1, 'result': {'content': [
        {'type': 'text', 'text': json.dumps({'mergeRequest': {
            'codeReviews': [{'status': 'COMPLETED'}],
            'reviewAnalysis': {'hasNewCommitsSinceReview': False}}})}]}}
    replay(monkeypatch, complete, empty)
    assert greptile.open_findings('owner/repo#7').data == []


SLACK_NOW = 1790769600  # WUWEI_NOW below, in epoch seconds


@pytest.fixture
def slack_case(tmp_path, monkeypatch):
    (tmp_path / '.wuwei/memory/notes').mkdir(parents=True)
    (tmp_path / '.wuwei/memory/spine.md').write_text('Memory spine\n')
    (tmp_path / '.wuwei/memory/index.md').write_text('Index\n')
    (tmp_path / '.wuwei/config.toml').write_text(
        '[owner]\nhandles = ["U0OWNER", "pat-gh"]\n[outbound]\nwork_channels = ["C1"]\n'
        '[adapters]\ninbound = "slack"\n')
    for name, value in (('WUWEI_WORKSPACE', str(tmp_path)), ('WUWEI_NOW', '2026-09-30T12:00:00+00:00'),
                        ('HOME', str(tmp_path / 'home')), ('XDG_CONFIG_HOME', str(tmp_path / 'config')),
                        ('SLACK_BOT_TOKEN', 'private-slack-token'), ('SLACK_OWNER_DM_CHANNEL', 'D1')):
        monkeypatch.setenv(name, value)
    monkeypatch.delenv('SLACK_USER_TOKEN', raising=False)
    return tmp_path


def query(call):
    from urllib.parse import parse_qs, urlsplit
    return {key: value[0] for key, value in parse_qs(urlsplit(call[0]).query).items()}


def test_slack_inbound_two_mentions_once(slack_case, monkeypatch):
    from wuwei import inbox, listen
    calls = replay(monkeypatch, *RECORDINGS['slack_history'], *RECORDINGS['slack_history'])
    assert listen.tick(slack_case) == 0
    rows = inbox.read(slack_case)
    assert [row['id'] for row in rows] == ['C1/1790769580.000200', 'C1/1790769590.000300']
    assert '7946' not in rows[0]['text'] and rows[0]['text'].startswith('ping <@U0OWNER|pat>')
    assert listen.tick(slack_case) == 0
    assert inbox.read(slack_case) == rows
    assert [query(call)['oldest'] for call in calls[2:]] == [str(SLACK_NOW - 300)] * 2


def test_slack_inbound_quiet_week_moves_the_cursor(slack_case, monkeypatch):
    from wuwei import listen
    calls = replay(monkeypatch, *RECORDINGS['slack_history'], *[history_page()] * 4)
    assert listen.tick(slack_case) == 0
    week = SLACK_NOW + 7 * 86400
    monkeypatch.setenv('WUWEI_NOW', '2026-10-07T12:00:00+00:00')
    assert listen.tick(slack_case) == 0
    assert listen.cursor(slack_case)['cursors'] == {'slack': str(week)}
    assert listen.tick(slack_case) == 0
    assert [query(call)['oldest'] for call in calls[2:]] == [
        str(SLACK_NOW - 300)] * 2 + [str(week - 300)] * 2


def test_slack_inbound_events(slack_case, monkeypatch):
    slack = importlib.import_module('adapters.inbound.slack')
    calls = replay(monkeypatch, *RECORDINGS['slack_history'])
    result = slack.poll('', root=slack_case)
    assert result.exit == 0
    assert result.data == [
        {'id': 'C1/1790769580.000200', 'source': 'slack', 'channel': 'C1',
         'thread': '1790769000.000100', 'sender': '/U2',
         'text': 'ping <@U0OWNER|pat>, call +44 20 7946 0958', 'ts': '1790769580.000200'},
        {'id': 'C1/1790769590.000300', 'source': 'slack', 'channel': 'C1', 'thread': '',
         'sender': 'T1/U1', 'text': '<@U0OWNER> can you look at this', 'ts': '1790769590.000300'}]
    assert [query(call)['channel'] for call in calls] == ['D1', 'C1']
    for call in calls:
        assert call[0].startswith('https://slack.com/api/conversations.history?')
        assert query(call)['oldest'] == str(SLACK_NOW - 300) and query(call)['limit'] == '100'
        assert call[1]['Authorization'] == 'Bearer private-slack-token'


def test_slack_inbound_dm_only(slack_case, monkeypatch):
    slack = importlib.import_module('adapters.inbound.slack')
    (slack_case / '.wuwei/config.toml').write_text(
        '[owner]\nhandles = ["pat-gh"]\n[adapters]\ninbound = "slack"\n')
    calls = replay(monkeypatch, history_page(
        {'user': 'U0OWNER', 'team': 'T1', 'text': 'approve D-3', 'ts': '1790769590.000100'},
        {'bot_id': 'B1', 'subtype': 'bot_message', 'text': 'Draft D-3', 'ts': '1790769580.000100'}))
    result = slack.poll('', root=slack_case)
    assert [query(call)['channel'] for call in calls] == ['D1']
    assert [(event['id'], event['sender']) for event in result.data] == [('D1/1790769590.000100', 'T1/U0OWNER')]


GOOD = {'user': 'U1', 'text': '<@U0OWNER> hi', 'ts': '1790769590.000100'}


@pytest.mark.parametrize('since,config,responses,reason', [
    ('', None, [rate_limited()], 'rate limited; retry after 30 s'),
    ('', None, [{'ok': False, 'error': 'provider-secret'}], 'invalid history response'),
    ('', None, [history_page(), history_page({'text': 'x', 'ts': '1790769590.000100'})],
     'invalid history message'),
    ('', None, [history_page(), history_page({**GOOD, 'ts': '1'})], 'invalid history message'),
    ('', None, [history_page(), history_page({**GOOD, 'team': 5})], 'invalid history message'),
    ('abc', None, [], 'invalid cursor'),
    ('', None, [history_page(GOOD, next_cursor='n')] * 10, 'history exceeds ten pages'),
    ('', '[owner]\nhandles = ["pat-gh"]\n[outbound]\nexternal_channels = ["C2"]\n', [],
     'owner.handles has no Slack user id'),
])
def test_slack_inbound_fails_closed(slack_case, monkeypatch, since, config, responses, reason):
    slack = importlib.import_module('adapters.inbound.slack')
    if config:
        (slack_case / '.wuwei/config.toml').write_text(config + '[adapters]\ninbound = "slack"\n')
    calls = replay(monkeypatch, *responses)
    result = slack.poll(since, root=slack_case)
    assert result.exit == 2 and result.data is None
    assert result.reason.startswith('slack.poll: could not run: ' + reason)
    assert 'provider-secret' not in result.reason
    assert len(calls) == len(responses)


@pytest.mark.parametrize('missing', [('SLACK_OWNER_DM_CHANNEL',), ('SLACK_BOT_TOKEN', 'SLACK_USER_TOKEN')])
def test_slack_inbound_missing_credentials_never_calls_network(slack_case, monkeypatch, missing):
    slack = importlib.import_module('adapters.inbound.slack')
    for name in missing:
        monkeypatch.delenv(name, raising=False)
    requests = replay(monkeypatch)
    result = slack.poll('', root=slack_case)
    assert result.exit == 2 and result.data is None
    assert missing[0] in result.reason
    assert requests == []
