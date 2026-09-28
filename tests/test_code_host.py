"""GitHub responses are replayed offline, including successful error bodies."""

from copy import deepcopy
import importlib
import json
import subprocess

import pytest

from fakes.replay import install_replay, recordings


CASES = [c for c in recordings('code_host') if c['operation'] in
         ('pr', 'checks', 'reviews', 'threads', 'protection')]
WRITES = [c for c in recordings('code_host') if c not in CASES]


def adapter():
    return importlib.import_module('adapters.code_host.github')


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['operation'])
def test_read_recording(case, tmp_path, monkeypatch):
    calls = install_replay(monkeypatch, 'gh', case['steps'])
    result = getattr(adapter(), case['operation'])(*case['args'], root=tmp_path)
    assert (result.exit, result.data, result.reason) == (0, case['data'], '')
    assert len(calls) == len(case['steps'])


@pytest.mark.parametrize('case', CASES, ids=lambda c: c['operation'])
@pytest.mark.parametrize('response', [
    {'stdout': '{"message":"Not Found","documentation_url":"https://docs.github.com"}'},
    {'stdout': '{"data":{},"errors":[{"message":"Denied"}]}'},
    {'stdout': '{}', 'exit': 1}, {'stdout': 'not json'}, {'stdout': '{}'},
    {'stdout': 'null'}, {'stdout': '[]'},
])
def test_read_fails_closed(case, response, tmp_path, monkeypatch, capsys):
    install_replay(monkeypatch, 'gh', [response])
    result = getattr(adapter(), case['operation'])(*case['args'])
    assert result.exit == 2 and result.data is None and result.reason
    assert result.reason in capsys.readouterr().err


@pytest.mark.parametrize('failure', [FileNotFoundError(), subprocess.TimeoutExpired('gh', 30)])
def test_unavailable_tool(failure, monkeypatch, capsys):
    def fail(*args, **kwargs):
        assert 0 < kwargs['timeout'] <= 30
        raise failure
    monkeypatch.setattr(subprocess, 'run', fail)
    result = adapter().pr('acme/widget#7')
    assert result.exit == 2 and result.data is None
    assert result.reason in capsys.readouterr().err


@pytest.mark.parametrize('nested', [False, True])
def test_truncated_threads_fail_closed(nested, tmp_path, monkeypatch):
    case = deepcopy(next(c for c in CASES if c['operation'] == 'threads'))
    body = json.loads(case['steps'][-1]['stdout'])
    connection = body['data']['repository']['pullRequest']['reviewThreads']
    if nested:
        connection = connection['nodes'][0]['comments']
    connection['pageInfo']['hasNextPage'] = True
    case['steps'][-1]['stdout'] = json.dumps(body)
    install_replay(monkeypatch, 'gh', case['steps'])
    result = adapter().threads(*case['args'])
    assert result.exit == 2 and result.data is None


def test_error_on_later_page_discards_all_data(tmp_path, monkeypatch):
    install_replay(monkeypatch, 'gh', [{'stdout': '[[], {"message":"Denied","documentation_url":"url"}]'}])
    result = adapter().reviews('acme/widget#7')
    assert result.exit == 2 and result.data is None


def test_checks_reject_wrong_head(tmp_path, monkeypatch):
    case = deepcopy(next(c for c in CASES if c['operation'] == 'checks'))
    pages = json.loads(case['steps'][0]['stdout'])
    pages[0]['check_runs'][0]['head_sha'] = 'b' * 40
    case['steps'][0]['stdout'] = json.dumps(pages)
    install_replay(monkeypatch, 'gh', case['steps'])
    result = adapter().checks(*case['args'])
    assert result.exit == 2 and result.data is None


@pytest.mark.parametrize('case', WRITES, ids=lambda c: c['operation'])
def test_write_recording(case, tmp_path, monkeypatch):
    calls = install_replay(monkeypatch, 'gh', case['steps'])
    result = getattr(adapter(), case['operation'])(*case['args'], root=tmp_path)
    assert (result.exit, result.data, result.reason) == (0, case['data'], '')
    assert len(calls) == len(case['steps'])


@pytest.mark.parametrize('case', WRITES, ids=lambda c: c['operation'])
@pytest.mark.parametrize('response', [
    {'stdout': '{"message":"Denied","documentation_url":"url"}'},
    {'stdout': '{"errors":[{"message":"Denied"}]}'},
    {'exit': 1, 'stdout': 'success-looking output'},
])
def test_write_failure(case, response, tmp_path, monkeypatch):
    install_replay(monkeypatch, 'gh', [response])
    result = getattr(adapter(), case['operation'])(*case['args'])
    assert result.exit == 2 and result.data is None


@pytest.mark.parametrize('operation,args', [
    ('merge', ['--admin', 'a' * 40]),
    ('merge', ['acme/widget#7', '--admin']),
    ('create_pr', [{'repo': '../widget', 'base':'main','head':'x','title':'t','body':'b'}]),
    ('request_reviewers', ['acme/widget#7', '--admin']),
    ('comment', ['acme/widget#7', 'body', '../reviews']),
    ('revert_pr', ['https://evil.test/acme/widget/pull/7']),
])
def test_invalid_write_input_never_spawns(operation, args, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('invalid input reached subprocess')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    result = getattr(adapter(), operation)(*args)
    assert result.exit == 2 and result.data is None


def test_no_approval_or_override_capability():
    from wuwei import registry
    for name in ('github', 'none'):
        module = importlib.import_module(f'adapters.code_host.{name}')
        assert not any('approve' in name or 'admin' in name for name in dir(module))
    assert not any('approve' in name or 'admin' in name for name in registry.INTERFACES['code_host'])
    source = open(adapter().__file__).read()
    assert '--admin' not in source and '--approve' not in source


def test_revert_returns_new_pr_not_original(tmp_path, monkeypatch):
    case = deepcopy(next(c for c in WRITES if c['operation'] == 'revert_pr'))
    query = 'mutation($id:ID!){revertPullRequest(input:{pullRequestId:$id}){revertPullRequest{number url}}}'
    case['steps'][-1]['input']['query'] = query
    case['steps'][-1]['stdout'] = json.dumps({'data': {'revertPullRequest': {
        'pullRequest': {'number': 7, 'url': 'https://github.com/acme/widget/pull/7'},
        'revertPullRequest': {'number': 8, 'url': 'https://github.com/acme/widget/pull/8'},
    }}})
    install_replay(monkeypatch, 'gh', case['steps'])
    result = adapter().revert_pr('acme/widget#7')
    assert result.exit == 0 and result.data['number'] == 8


def test_api_host_is_pinned_despite_environment(tmp_path, monkeypatch):
    case = deepcopy(CASES[0])
    assert case['steps'][0]['argv'][-2:] == ['--hostname', 'github.com']
    monkeypatch.setenv('GH_HOST', 'elsewhere.example.test')
    install_replay(monkeypatch, 'gh', case['steps'])
    result = adapter().pr(*case['args'])
    assert result.exit == 0 and result.data == case['data']


@pytest.mark.parametrize('response,reason', [
    ({'stdout': '', 'exit': 7}, 'gh exited 7'),
    ({'stdout': '{"message":"secret","documentation_url":"url"}'}, 'GitHub error response'),
])
def test_failure_reason_explains_cause_without_body(response, reason, tmp_path, monkeypatch, capsys):
    install_replay(monkeypatch, 'gh', [response])
    result = adapter().pr('acme/widget#7')
    assert reason in result.reason
    assert reason in capsys.readouterr().err
    assert 'secret' not in result.reason


@pytest.mark.parametrize('args,payload', [
    (['pr', 'review', '7', '--approve'], None),
    (['api', 'repos/acme/widget/pulls/7/reviews', '--method', 'POST', '--input', '-'],
     {'event': 'APPROVE'}),
    (['pr', 'merge', '7', '--admin'], None),
    (['pr', 'merge', 'https://github.com/acme/widget/pull/7', '--squash',
      '--match-head-commit', 'a' * 40, '--admin'], None),
    (['api', 'repos/acme/widget/branches/main/protection', '--method', 'PUT'], None),
    (['api', 'graphql', '--input', '-'], {'query': 'mutation { approve }'}),
    (['api', 'repos/acme/widget/pulls', '--input', '-'], {'title': 'implicit POST'}),
    (['api', 'repos/acme/widget/pulls/7', '--method', 'GET'], None),
    (['api', 'repos/acme/widget/pulls/../reviews', '--method', 'POST', '--input', '-'], {}),
])
def test_run_rejects_unapproved_commands_before_spawn(args, payload, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('unapproved command reached subprocess')
    monkeypatch.setattr(subprocess, 'run', forbidden)
    with pytest.raises(ValueError):
        adapter()._run(args, payload)


def test_deep_json_fails_closed(tmp_path, monkeypatch):
    install_replay(monkeypatch, 'gh', [{'stdout': '[' * 2000 + '0' + ']' * 2000}])
    result = adapter().pr('acme/widget#7')
    assert result.exit == 2 and result.data is None


def test_partial_graphql_discards_success_data(tmp_path, monkeypatch):
    case = deepcopy(next(c for c in CASES if c['operation'] == 'threads'))
    body = json.loads(case['steps'][-1]['stdout'])
    body['errors'] = [{'message': 'partial response'}]
    case['steps'][-1]['stdout'] = json.dumps(body)
    install_replay(monkeypatch, 'gh', case['steps'])
    result = adapter().threads(*case['args'])
    assert result.exit == 2 and result.data is None


def test_real_path_smoke(tmp_path, monkeypatch):
    from fakes.replay import install_stub

    case = next(c for c in WRITES if c['operation'] == 'comment')
    calls = install_stub(tmp_path, monkeypatch, 'gh', case['steps'])
    result = adapter().comment(*case['args'])
    assert result.exit == 0 and result.data == case['data']
    assert len(calls.read_text().splitlines()) == 1  # Stub checks JSON stdin too.

    install_stub(tmp_path, monkeypatch, 'gh', [{'sleep': 10}])
    monkeypatch.setattr(adapter(), 'TIMEOUT', 0.05)
    result = adapter().pr('acme/widget#7')
    assert result.exit == 2 and 'TimeoutExpired' in result.reason

    (tmp_path / 'tools/gh').unlink()
    result = adapter().pr('acme/widget#7')
    assert result.exit == 2 and 'FileNotFoundError' in result.reason
