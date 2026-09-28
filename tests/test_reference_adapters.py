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


def test_linear_replay(monkeypatch):
    linear = importlib.import_module('adapters.tracker.linear')
    monkeypatch.setenv('LINEAR_API_KEY', 'private-linear-key')
    calls = replay(monkeypatch, *RECORDINGS['linear'][:3], RECORDINGS['linear'][4])
    assert linear.claim('ABC-1').exit == 0
    assert linear.transition('ABC-1', 'state-1').exit == 0
    assert linear.history('ABC-1').data == [{'id': 'change-1'}]
    assert len(calls) == 4
    assert all(url == 'https://api.linear.app/graphql' for url, _, _ in calls)
    assert all('private-linear-key' in headers['Authorization'] for _, headers, _ in calls)
    assert calls[1][2]['variables']['input'] == {'assigneeId': 'user-1'}
    assert calls[2][2]['variables']['input'] == {'stateId': 'state-1'}


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
    (tmp_path / '.wuwei/config.toml').write_text('[owner]\nname = "Pat"\npronouns = "they/them"\n')
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
    monkeypatch.setattr(outward, 'check_call', lambda *args: (0, ''))
    calls = replay(monkeypatch, RECORDINGS['linear'][3])
    draft = {'teamId': 'team-1', 'title': 'New item'}
    result = linear.create(draft, root=tmp_path)
    assert result.exit == 0
    assert result.data == {'id': 'issue-2'}
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
    (tmp_path / '.wuwei/config.toml').write_text('[owner]\nname = "Pat"\npronouns = "they/them"\n')
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
    monkeypatch.setattr(outward, 'check_call', lambda *args: (0, ''))
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
