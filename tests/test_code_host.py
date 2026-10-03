"""GitHub responses are replayed offline, including successful error bodies."""

from copy import deepcopy
import importlib
import json
import subprocess

import pytest

from fakes.replay import install_replay, recordings


CASES = [c for c in recordings('code_host') if c['operation'] in
         ('pr', 'checks', 'reviews', 'threads', 'protection', 'merged_prs', 'default_branch',
          'viewer_login')]
WRITES = [c for c in recordings('code_host') if c not in CASES]


def adapter():
    return importlib.import_module('adapters.code_host.github')


def transport(name):
    # Skip outward policy only, preserving the adapter's result/error wrapper.
    operation = getattr(adapter(), name)
    return operation.__wrapped__ if name == 'comment' else operation


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
    # These recordings exercise transport encoding; outward port policy has its own tests.
    result = transport(case['operation'])(*case['args'], root=tmp_path)
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
    result = transport(case['operation'])(*case['args'])
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
    result = transport(operation)(*args)
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
    result = transport('comment')(*case['args'])
    assert result.exit == 0 and result.data == case['data']
    assert len(calls.read_text().splitlines()) == 1  # Stub checks JSON stdin too.

    install_stub(tmp_path, monkeypatch, 'gh', [{'sleep': 10}])
    monkeypatch.setattr(adapter(), 'TIMEOUT', 0.05)
    result = adapter().pr('acme/widget#7')
    assert result.exit == 2 and 'TimeoutExpired' in result.reason

    (tmp_path / 'tools/gh').unlink()
    result = adapter().pr('acme/widget#7')
    assert result.exit == 2 and 'FileNotFoundError' in result.reason


@pytest.mark.parametrize('actor,expected', [
    ({'login': 'robot', '__typename': 'Bot'}, 0),
    ({'login': 'robot'}, 2), (None, 2),
    ({'login': 'robot', '__typename': 'Unknown'}, 2),
])
def test_thread_actor_type_is_explicit(actor, expected, monkeypatch):
    case = deepcopy(next(c for c in CASES if c['operation'] == 'threads'))
    body = json.loads(case['steps'][-1]['stdout'])
    comment = body['data']['repository']['pullRequest']['reviewThreads']['nodes'][0]['comments']['nodes'][0]
    comment['author'] = actor
    case['steps'][-1]['stdout'] = json.dumps(body)
    install_replay(monkeypatch, 'gh', case['steps'])
    result = adapter().threads(*case['args'])
    assert result.exit == expected
    if expected == 0:
        assert result.data['threads'][0]['comments'][0]['is_bot'] is True


@pytest.mark.parametrize('field', ['requested_reviewers', 'requested_teams'])
def test_pr_missing_reviewer_evidence_is_unreadable(field, monkeypatch):
    case = deepcopy(next(c for c in CASES if c['operation'] == 'pr'))
    body = json.loads(case['steps'][0]['stdout'])
    del body[field]
    case['steps'][0]['stdout'] = json.dumps(body)
    install_replay(monkeypatch, 'gh', case['steps'])
    assert adapter().pr(*case['args']).exit == 2


@pytest.mark.parametrize('merged', [True, False, None, 'true'])
def test_pr_exposes_verified_merge_bit(monkeypatch, merged):
    case = deepcopy(next(c for c in CASES if c['operation'] == 'pr'))
    raw = json.loads(case['steps'][0]['stdout'])
    raw['merged'] = merged
    raw['merge_commit_sha'] = 'a' * 40 if merged is True else None
    case['steps'][0]['stdout'] = json.dumps(raw)
    install_replay(monkeypatch, 'gh', case['steps'])
    result = adapter().pr(*case['args'])
    if type(merged) is bool:
        assert result.exit == 0 and result.data.get('merged') is merged
    else:
        assert result.exit == 2


SCOPE_TOKEN = 'opaque-scope-token'


def scope_run(monkeypatch, stdout='', exit=0):
    seen = []
    def run(argv, **kwargs):
        seen.append((argv, kwargs.get('env')))
        return subprocess.CompletedProcess(argv, exit, stdout, 'error ' + SCOPE_TOKEN)
    monkeypatch.setattr(subprocess, 'run', run)
    return seen


@pytest.mark.parametrize('variable', ['GH_TOKEN', 'GITHUB_TOKEN'])
def test_token_scopes_measures_only_that_token(variable, monkeypatch):
    monkeypatch.setenv(variable, SCOPE_TOKEN)
    other = 'GITHUB_TOKEN' if variable == 'GH_TOKEN' else 'GH_TOKEN'
    monkeypatch.setenv(other, 'other-token')
    seen = scope_run(monkeypatch, 'HTTP/2.0 200 OK\nX-Oauth-Scopes: repo, read:org\n\n{"login": "x"}')
    result = adapter().token_scopes(variable)
    assert (result.exit, result.data) == (0, {'scopes': ['repo', 'read:org']})
    [(argv, env)] = seen
    assert argv == ['gh', 'api', '--include', 'user', '--hostname', 'github.com']
    assert env['GH_TOKEN'] == SCOPE_TOKEN and 'GITHUB_TOKEN' not in env


@pytest.mark.parametrize('stdout,exit,variable', [
    ('HTTP/2.0 200 OK\n\n{"X-OAuth-Scopes": "repo"}', 0, 'GH_TOKEN'),
    ('HTTP/2.0 200 OK\nX-OAuth-Scopes: \n\n{}', 0, 'GH_TOKEN'),
    ('HTTP/2.0 401\nX-OAuth-Scopes: repo\n\n{}', 1, 'GH_TOKEN'),
    ('HTTP/2.0 200 OK\nX-OAuth-Scopes: repo\n\n{}', 0, 'LINEAR_API_KEY'),
    ('HTTP/2.0 200 OK\nX-OAuth-Scopes: repo\n\n{}', 0, 'GITHUB_TOKEN'),
])
def test_token_scopes_unmeasured(stdout, exit, variable, monkeypatch, capsys):
    monkeypatch.setenv('GH_TOKEN', SCOPE_TOKEN)
    monkeypatch.setenv('LINEAR_API_KEY', SCOPE_TOKEN)
    scope_run(monkeypatch, stdout, exit)
    result = adapter().token_scopes(variable)
    assert result.exit == 2 and result.data is None
    assert SCOPE_TOKEN not in result.reason + str(capsys.readouterr())


def test_run_rejects_user_scope_read_with_payload(monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: pytest.fail('spawned'))
    with pytest.raises(ValueError):
        adapter()._run(['api', '--include', 'user'], {'x': 1}, json_output=False)
    with pytest.raises(ValueError):
        adapter()._run(['api', '--include', 'user'])


def test_protection_requires_deletion_setting(monkeypatch):
    case = deepcopy(next(c for c in CASES if c['operation'] == 'protection'))
    body = json.loads(case['steps'][0]['stdout'])
    del body['allow_deletions']
    case['steps'][0]['stdout'] = json.dumps(body)
    install_replay(monkeypatch, 'gh', case['steps'])
    assert adapter().protection(*case['args']).exit == 2


def test_unreadable_protection_is_not_absent(monkeypatch):
    # A repository the token cannot see 404s on the rulesets read too, so it stays unmeasured.
    calls = install_replay(monkeypatch, 'gh', [{'exit': 1, 'stderr': 'gh: Not Found (HTTP 404)'},
                                               {'exit': 1, 'stderr': 'gh: Not Found (HTTP 404)'}])
    result = adapter().protection('acme/widget', 'main')
    assert result.exit == 2 and 'gh exited 1' in result.reason and len(calls) == 2


def test_classic_403_is_unmeasured_without_reading_rulesets(monkeypatch):
    calls = install_replay(monkeypatch, 'gh', [
        {'exit': 1, 'stderr': 'gh: Must have admin rights to Repository. (HTTP 403)'}, {'stdout': '[[]]'}])
    assert adapter().protection('acme/widget', 'main').exit == 2 and len(calls) == 1


@pytest.mark.parametrize('stderr', ['gh: Not Found (HTTP 404)', 'gh: Branch not protected (HTTP 404)'])
def test_classic_404_reads_rulesets(monkeypatch, stderr):
    calls = install_replay(monkeypatch, 'gh', [{'exit': 1, 'stderr': stderr}, {'stdout': '[[]]'}])
    result = adapter().protection('acme/widget', 'main')
    assert result.exit == 0 and len(calls) == 2
    assert result.data == {
        'required_checks': [], 'strict': False, 'approvals': 0, 'dismiss_stale_reviews': False,
        'require_code_owner_reviews': False, 'require_last_push_approval': False,
        'enforce_admins': False, 'conversation_resolution': False, 'allow_force_pushes': True,
        'allow_deletions': True, 'merge_queue': False, 'classic': False}


def test_classic_404_takes_rules_fields(monkeypatch):
    rules = [{'type': 'required_status_checks', 'parameters': {
                 'strict_required_status_checks_policy': False,
                 'required_status_checks': [{'context': 'Security'}]}},
             {'type': 'pull_request', 'parameters': {
                 'required_approving_review_count': 1, 'dismiss_stale_reviews_on_push': False,
                 'require_code_owner_review': False, 'require_last_push_approval': False,
                 'required_review_thread_resolution': False}},
             {'type': 'non_fast_forward'}, {'type': 'deletion'}]
    install_replay(monkeypatch, 'gh', [{'exit': 1, 'stderr': 'gh: Not Found (HTTP 404)'},
                                       {'stdout': json.dumps([rules])}])
    data = adapter().protection('acme/widget', 'main').data
    assert data['required_checks'] == [{'name': 'Security', 'app_id': None}]
    assert data['approvals'] == 1 and data['classic'] is False
    assert data['allow_force_pushes'] is False and data['allow_deletions'] is False


HEAD = 'a' * 40
PR_URL = 'repos/acme/widget/pulls/7'
CHECKS_URL = f'repos/acme/widget/commits/{HEAD}/check-runs?per_page=100'
STATUSES_URL = f'repos/acme/widget/commits/{HEAD}/statuses?per_page=100'


def answer(endpoint, status, etag='', body='', exit=0, tag=None):
    argv = ['api', endpoint, '--include'] + (['-H', f'If-None-Match: {tag}'] if tag else [])
    headers = f'HTTP/2.0 {status}\r\nContent-Type: application/json\r\n' + (f'Etag: {etag}\r\n' if etag else '')
    return {'argv': argv + ['--hostname', 'github.com'], 'stdout': headers + '\r\n' + body, 'exit': exit}


FRESH = [answer(PR_URL, '200 OK', 'W/"p1"', json.dumps({'head': {'sha': HEAD}})),
         answer(CHECKS_URL, '200 OK', 'W/"c1"', '{"total_count": 0, "check_runs": []}'),
         answer(STATUSES_URL, '200 OK', '"s1"', '[]')]
TAGS = {'pr': 'W/"p1"', 'head': HEAD, 'checks': 'W/"c1"', 'statuses': '"s1"'}


def test_probe_reads_tags_then_answers_not_modified(monkeypatch):
    install_replay(monkeypatch, 'gh', FRESH)
    result = adapter().probe('acme/widget#7', {})
    assert (result.exit, result.data) == (0, {'modified': True, 'tags': TAGS})
    calls = install_replay(monkeypatch, 'gh', [
        answer(PR_URL, '304 Not Modified', 'W/"p1"', exit=1, tag='W/"p1"'),
        answer(CHECKS_URL, '304 Not Modified', exit=1, tag='W/"c1"'),
        answer(STATUSES_URL, '304 Not Modified', exit=1, tag='"s1"')])
    result = adapter().probe('acme/widget#7', TAGS)
    assert (result.exit, result.data) == (0, {'modified': False, 'tags': TAGS})
    assert len(calls) == 3


def test_probe_check_change_is_modified(monkeypatch):
    install_replay(monkeypatch, 'gh', [
        answer(PR_URL, '304 Not Modified', exit=1, tag='W/"p1"'),
        answer(CHECKS_URL, '200 OK', 'W/"c2"', '{"check_runs": []}', tag='W/"c1"'),
        answer(STATUSES_URL, '304 Not Modified', exit=1, tag='"s1"')])
    result = adapter().probe('acme/widget#7', TAGS)
    assert result.exit == 0 and result.data == {'modified': True, 'tags': {**TAGS, 'checks': 'W/"c2"'}}


@pytest.mark.parametrize('tags,steps', [
    ({'pr': 'W/"p1"'}, [answer(PR_URL, '304 Not Modified', exit=1, tag='W/"p1"')]),
    ({}, [{'stdout': 'HTTP/2.0 404 Not Found\r\n\r\nprivate body', 'exit': 1}]),
    ({}, [{'stdout': '', 'exit': 1}]),
    ({}, [answer(PR_URL, '200 OK', '', '{}')]),
    ('tags', []),
])
def test_probe_fails_closed(tags, steps, monkeypatch, capsys):
    install_replay(monkeypatch, 'gh', steps)
    result = adapter().probe('acme/widget#7', tags)
    assert result.exit == 2 and result.data is None
    assert 'private body' not in capsys.readouterr().err


@pytest.mark.parametrize('header', ['If-None-Match: "a"\nX: y', 'If-None-Match: a', 'X-Other: "a"'])
def test_conditional_header_is_allowlisted(header, monkeypatch):
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: pytest.fail('spawned'))
    with pytest.raises(ValueError, match='unsupported gh command'):
        adapter()._run(['api', 'repos/o/r/pulls/1', '--include', '-H', header], json_output=False)


def test_threads_carry_the_file_path(monkeypatch):
    case = deepcopy(next(c for c in CASES if c['operation'] == 'threads'))
    step = case['steps'][1]
    value = json.loads(step['stdout'])
    nodes = value['data']['repository']['pullRequest']['reviewThreads']['nodes']
    nodes.append({**nodes[0], 'id': 'THREAD_2', 'path': 'cli/x.py'})
    step['stdout'] = json.dumps(value)
    install_replay(monkeypatch, 'gh', case['steps'])
    result = adapter().threads('acme/widget#7')
    assert [thread['path'] for thread in result.data['threads']] == [None, 'cli/x.py']


@pytest.mark.parametrize('branch', ['-x', '', None])
def test_default_branch_refuses_an_unusable_name(branch, monkeypatch):
    install_replay(monkeypatch, 'gh', [{'stdout': json.dumps({'default_branch': branch})}])
    assert adapter().default_branch('acme/widget').exit == 2


def test_stderr_line_and_auth_hint(monkeypatch):
    install_replay(monkeypatch, 'gh', [{'exit': 1, 'stderr':
                                        'To get started with GitHub CLI, please run:  gh auth login'}])
    result = adapter().pr('acme/widget#7')
    assert result.exit == 2
    for text in ('gh exited 1', 'acme/widget', 'please run:  gh auth login', 'run gh auth login'):
        assert text in result.reason, text


def test_stderr_line_search_has_no_email(monkeypatch):
    install_replay(monkeypatch, 'gh', [{'exit': 1, 'stderr': 'HTTP 422: q=author-email:dev@example.test'}])
    result = adapter().author_login('acme/widget', 'dev@example.test')
    assert result.exit == 2 and 'gh exited 1' in result.reason and 'search' in result.reason
    assert 'example.test' not in result.reason
