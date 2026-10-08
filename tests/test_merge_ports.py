"""Offline transport evidence needed by the merge policy."""

from copy import deepcopy
import json

import pytest

from fakes.replay import install_replay, recordings
from test_code_host import adapter

SHA = 'a' * 40


def protection_case():
    return deepcopy(next(c for c in recordings('code_host') if c['operation'] == 'protection'))


def rules_step(rules):
    return {'argv': ['api', 'repos/acme/widget/rules/branches/release%2Fnext?per_page=100',
                     '-H', 'Cache-Control: no-cache', '--paginate', '--slurp',
                     '--hostname', 'github.com'], 'stdout': json.dumps([rules])}


@pytest.mark.parametrize('source', [{'integration_id': 12}, {'integration_id': None}, {}])
def test_rulesets_union_checks_and_reviews(monkeypatch, source):
    case = protection_case()
    case['steps'] = case['steps'][:1] + [rules_step([
        {'type': 'required_status_checks', 'parameters': {
            'strict_required_status_checks_policy': True,
            'required_status_checks': [{'context': 'Security', **source}]}},
        {'type': 'pull_request', 'parameters': {
            'required_approving_review_count': 3, 'dismiss_stale_reviews_on_push': True,
            'require_code_owner_review': True, 'require_last_push_approval': True,
            'required_review_thread_resolution': True}},
        {'type': 'merge_queue'},
    ])] + case['steps'][2:]
    install_replay(monkeypatch, 'gh', case['steps'])
    result = adapter().protection(*case['args'])
    assert result.exit == 0, result
    assert {'name': 'Security', 'app_id': source.get('integration_id')} in result.data['required_checks']
    assert result.data['approvals'] == 3
    assert result.data['merge_queue'] is True
    assert result.data['require_code_owner_reviews'] is True


@pytest.mark.parametrize('body', ['{}', '[{}]', '[{"message":"Denied","documentation_url":"url"}]'])
def test_unreadable_ruleset_is_not_clean(monkeypatch, body):
    case = protection_case()
    install_replay(monkeypatch, 'gh', case['steps'][:1] + [{'stdout': body}])
    assert adapter().protection(*case['args']).exit == 2


def test_files_include_rename_source_and_patch(monkeypatch):
    install_replay(monkeypatch, 'gh', [{'stdout': json.dumps([[{
        'filename': 'src/a.py', 'previous_filename': 'infra/a.py',
        'status': 'renamed', 'additions': 1, 'deletions': 1,
        'patch': '@@ -1 +1 @@\n-old\n+new'}]])}])
    result = adapter().files('acme/widget#7')
    assert result.exit == 0, result
    assert result.data[0]['previous_path'] == 'infra/a.py'


def test_pr_carries_actual_merge_commit(monkeypatch):
    case = deepcopy(next(c for c in recordings('code_host') if c['operation'] == 'pr'))
    body = json.loads(case['steps'][0]['stdout'])
    body.update(merged=True, merged_at='2026-09-28T12:00:00Z', merge_commit_sha='b' * 40)
    case['steps'][0]['stdout'] = json.dumps(body)
    install_replay(monkeypatch, 'gh', case['steps'])
    result = adapter().pr(*case['args'])
    assert result.data['merge_commit'] == 'b' * 40
    assert result.data['merged_at'] == '2026-09-28T12:00:00Z'


def commit(sha, parent, message='merge change'):
    return {'sha': sha, 'parents': [{'sha': parent}],
        'commit': {'message': message, 'committer': {'date': '2026-09-29T12:00:00Z'}},
        'files': [{'filename': 'src/a.py', 'status': 'modified', 'additions': 1,
                   'deletions': 1, 'patch': '@@ -1 +1 @@\n-old\n+new'}]}


def history_prefix():
    return [{'argv': ['api', 'repos/acme/widget/branches/main', '-H', 'Cache-Control: no-cache',
                       '--hostname', 'github.com'],
             'stdout': json.dumps({'commit': {'sha': 'b' * 40}})},
            {'stdout': json.dumps([commit(SHA, 'e' * 40)])}]


def test_history_requires_complete_linear_base_history(monkeypatch):
    install_replay(monkeypatch, 'gh', history_prefix() + [{'stdout': json.dumps({
        'status': 'ahead', 'total_commits': 1, 'commits': [{'sha': 'b' * 40}]
    })}, {'stdout': json.dumps([commit('b' * 40, SHA, 'fix: regression')])}])
    result = adapter().history('acme/widget', SHA, 'main')
    assert result.exit == 0, result
    assert result.data['commits'][0]['message'] == 'fix: regression'
    assert result.data['files'][0]['patch'].startswith('@@ -1 +1 @@')


@pytest.mark.parametrize('response', [
    {'status': 'ahead', 'total_commits': 2, 'commits': [{'sha': 'b' * 40}]},
    {'status': 'diverged', 'total_commits': 0, 'commits': []},
    {'message': 'Denied', 'documentation_url': 'url'},
])
def test_history_never_counts_partial_data_as_zero(monkeypatch, response):
    install_replay(monkeypatch, 'gh', history_prefix() + [{'stdout': json.dumps(response)}])
    assert adapter().history('acme/widget', SHA, 'main').exit == 2


def test_history_without_patches_uses_compare_messages_only(monkeypatch):
    reverted = commit('b' * 40, SHA, f'This reverts commit {SHA}.')
    reverted.pop('files')
    # A merge commit does not prevent reading revert messages.
    reverted['parents'].append({'sha': 'd' * 40})
    calls = install_replay(monkeypatch, 'gh', history_prefix()[:1] + [{
        'argv': ['api', f'repos/acme/widget/compare/{SHA}...{"b" * 40}',
                 '-H', 'Cache-Control: no-cache', '--hostname', 'github.com'],
        'stdout': json.dumps({'status': 'ahead', 'total_commits': 1, 'commits': [reverted]})}])
    result = adapter().history('acme/widget', SHA, 'main', patches=False)
    assert result.exit == 0, result
    assert result.data['commits'] == [{'sha': 'b' * 40, 'at': '2026-09-29T12:00:00Z',
                                      'message': f'This reverts commit {SHA}.'}]
    assert len(calls) == 2


@pytest.mark.parametrize('rule,key', [('non_fast_forward', 'allow_force_pushes'),
                                      ('deletion', 'allow_deletions')])
def test_rulesets_block_force_pushes_and_deletions(monkeypatch, rule, key):
    case = protection_case()
    body = json.loads(case['steps'][0]['stdout'])
    body['allow_force_pushes'] = body['allow_deletions'] = {'enabled': True}
    case['steps'][0]['stdout'] = json.dumps(body)
    case['steps'] = case['steps'][:1] + [rules_step([{'type': rule}])] + case['steps'][2:]
    install_replay(monkeypatch, 'gh', case['steps'])
    result = adapter().protection(*case['args'])
    assert result.exit == 0, result
    assert result.data[key] is False
    assert result.data[({'allow_force_pushes', 'allow_deletions'} - {key}).pop()] is True
