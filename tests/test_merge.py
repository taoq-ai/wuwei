"""Merge policy tables use ports in process, never real git or gh."""

from copy import deepcopy
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fakes.code_host import Fake
from wuwei import registry, state, workspace
from wuwei.registry import Result
from test_pr_guards import evidence

SHA = 'a' * 40
BASE = 'b' * 40
MERGED = 'c' * 40
REF = 'example/project#7'


def policy():
    return importlib.import_module('wuwei.merge')


def events(root):
    from wuwei.watch import records
    return records(workspace.day_dir(root) / 'events.jsonl')


@pytest.fixture
def case(tmp_path, monkeypatch):
    root = tmp_path / 'workspace'
    (root / 'repo').mkdir(parents=True)
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text('''
[environments]
production = "production"
[owner]
handles = ["owner"]
[[repos]]
name = "example/project"
path = "repo"
default_branch = "main"
merge_deploys = false
[repos.merge]
auto = true
''')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    directory = workspace.day_dir(root)
    (directory / 'decisions').mkdir(parents=True)
    for gate in ('arch', 'quality', 'security'):
        (directory / 'decisions' / f'gate-item-7-{gate}.md').write_text(evidence())
    flags = {key: False for key in state.ITEM_DEFAULTS['flags']}
    state._write_state(lambda d: d.update(items={'item-7': {'pr': REF, 'flags': flags}},
        raised_prs=[REF], gate_approved=True, approved_items=['item-7'],
        channel_posts=[{'pr': REF, 'status': 'posted', 'url': 'https://chat.test/thread/1',
                        'reviewers': ['reviewer']}]), root, reserved=False,
        kind='plan.approved', payload={'flags': {'item-7': flags}, 'approved_items': ['item-7']})
    host = Fake({
        'pr': Result(0, {'repo': 'example/project', 'number': 7, 'head': SHA,
            'base': 'main', 'base_sha': BASE, 'state': 'open', 'draft': False,
            'author': 'owner', 'mergeable': True, 'merge_state': 'clean',
            'updated_at': '2026-09-29T10:00:00Z', 'additions': 10, 'deletions': 0,
            'changed_files': 1, 'requested_reviewers': ['reviewer'], 'requested_teams': [],
            'merged': False, 'merged_at': None, 'merge_commit': None}),
        'files': Result(0, [{'path': 'src/a.py', 'previous_path': None, 'status': 'added',
            'additions': 10, 'deletions': 0, 'patch': '@@ -0,0 +1,10 @@\n' + '+line\n' * 10}]),
        'checks': Result(0, [{'name': 'tests', 'sha': SHA, 'app_id': 1,
                            'state': 'completed', 'conclusion': 'success'}]),
        'protection': Result(0, {'required_checks': [{'name': 'tests', 'app_id': 1}],
            'approvals': 1, 'strict': True, 'merge_queue': False,
            'require_code_owner_reviews': False, 'require_last_push_approval': False,
            'dismiss_stale_reviews': True, 'conversation_resolution': True,
            'enforce_admins': True, 'squash': True}),
        'reviews': Result(0, [{'id': 1, 'author': 'reviewer', 'is_bot': False, 'sha': SHA,
            'state': 'approved', 'body': '', 'submitted_at': '2026-09-29T10:00:00Z'}]),
        'threads': Result(0, {'comments': [], 'threads': []}),
        'merge': Result(0, {'accepted': True, 'sha': SHA}),
        'revert_pr': Result(0, {'number': 8, 'url': 'https://github.com/example/project/pull/8'}),
        'history': Result(0, {'files': [], 'commits': []}),
    })
    monkeypatch.setattr(registry, 'load', lambda kind, config: host)
    return root, host


def check(case):
    return policy().check(REF, root=case[0])


def config_change(root, old, new):
    path = root / '.wuwei/config.toml'
    path.write_text(path.read_text().replace(old, new))


def test_clean_has_head_bound_evidence(case):
    result = check(case)
    assert result.exit == 0, result
    assert result.data['head'] == SHA
    assert len(result.data['verdicts']) == 3
    assert result.data['approvals'] == ['reviewer']
    assert result.data['checks'][0]['sha'] == SHA
    assert not any(call[0] == 'merge' for call in case[1].calls)


def test_merge_uses_quality_delta_record(case):
    root, _ = case
    directory = workspace.day_dir(root) / 'decisions'
    records = {}
    for role in ('arch', 'quality', 'security'):
        path = directory / f'gate-item-7-{role}.md'
        path.write_text(evidence(BASE) if role != 'quality' else
            evidence(BASE, 'FIX') + '- P1 | cli/example.py:12 | fails when empty | blocks: yes\n')
        records[f'item-7:{role}:initial'] = {
            'item': 'item-7', 'role': role, 'round': 'initial',
            'verdict': 'FIX' if role == 'quality' else 'PASS', 'head': BASE,
            'file': str(path.relative_to(root)), 'blocks': role == 'quality', 'notes': []}
    delta = directory / 'gate-item-7-quality-delta.md'
    delta.write_text(evidence(SHA))
    records['item-7:quality:delta'] = {
        'item': 'item-7', 'role': 'quality', 'round': 'delta', 'verdict': 'PASS',
        'head': SHA, 'file': str(delta.relative_to(root)), 'blocks': False, 'notes': []}
    state._write_state(lambda data: data.update(gate_verdicts=records), root, reserved=False)
    result = check(case)
    assert result.exit == 0, result
    assert any(row['path'].endswith('quality-delta.md') for row in result.data['verdicts'])


@pytest.mark.parametrize('conclusion', ['skipped', 'neutral', 'failure', 'cancelled', 'timed_out', None])
def test_required_check_must_be_green(case, conclusion):
    case[1].results['checks'].data[0]['conclusion'] = conclusion
    result = check(case)
    assert result.exit == 1 and 'tests' in result.reason


@pytest.mark.parametrize('change,hint', [
    (('merge_deploys = false', ''), 'merge_deploys'),
    (('merge_deploys = false', 'merge_deploys = true'), 'merge_deploys'),
    (('auto = true', 'auto = false'), 'merge.auto'),
    (('auto = true', 'auto = true\nmax_changed_lines = 5'), 'lines'),
    (('auto = true', 'auto = true\nsoak_minutes = 180'), 'soak'),
    (('auto = true', 'auto = true\nquiet_hours = ["11:00-13:00"]'), 'quiet'),
])
def test_config_eligibility(case, change, hint):
    config_change(case[0], *change)
    if hint == 'soak': base_checks(case[1], 'success')
    result = check(case)
    assert result.exit == 1 and hint in result.reason, result


def base_checks(host, conclusion):
    """#668: checks at the base commit BASE; a Result stands for the adapter's answer."""
    original = host.checks
    def checks(ref, sha, root=None):
        if sha != BASE:
            return original(ref, sha, root)
        host.calls.append(('checks', (ref, sha), root))
        return conclusion if isinstance(conclusion, Result) else Result(0, [
            {'name': 'tests', 'sha': BASE, 'app_id': 1, 'state': 'completed', 'conclusion': conclusion}])
    host.checks = checks


def base_reads(host):
    return [call for call in host.calls if call[:2] == ('checks', (REF, BASE))]


WAIT = '2026-09-29T13:00:00+00:00'
GRANT = "run bin/wuwei merge example/project#7: it merges under the owner's grant, or asks the owner on a card"


def test_soak_skip_config(case):
    # #668: base_fix by default; never turns the skip off; nothing else loads.
    root = case[0]
    assert workspace.load_config(root)['repos'][0]['merge']['soak_skip'] == 'base_fix'
    config_change(root, 'auto = true', 'auto = true\nsoak_skip = "never"')
    assert workspace.load_config(root)['repos'][0]['merge']['soak_skip'] == 'never'
    config_change(root, '"never"', '"sometimes"')
    with pytest.raises(ValueError):
        workspace.load_config(root)


def test_fixes_base_names_checks_red_at_base_and_green_at_head():
    fixes = policy().fixes_base
    def rows(**conclusions):
        return [{'name': name, 'conclusion': value} for name, value in conclusions.items()]
    assert fixes(rows(lint='failure'), rows(lint='success')) == ['lint']
    assert fixes(rows(lint='error'), rows(lint='success')) == ['lint']
    for base in ('success', 'cancelled', 'timed_out', 'skipped', None):
        assert fixes(rows(lint=base), rows(lint='success')) == []
    for head in ('neutral', 'skipped'):
        assert fixes(rows(lint='failure'), rows(lint=head)) == []
    assert fixes(rows(lint='failure'), rows(tests='success')) == []
    assert fixes(rows(tests='failure', lint='failure'), rows(tests='success', lint='success')) == ['lint', 'tests']


def test_a_fix_to_a_broken_base_skips_the_soak(case):
    root, host = case
    config_change(root, 'auto = true', 'auto = true\nsoak_minutes = 180')
    base_checks(host, 'failure')
    result = check(case)
    assert result.exit == 0, result
    assert 'fixes the broken base' in result.data['soak'] and 'tests' in result.data['soak']
    assert BASE in result.data['soak']
    config_change(root, 'auto = true', 'auto = true\nsoak_skip = "never"')
    assert check(case).exit == 1


def test_a_held_soak_says_when_it_ends(case):
    root, host = case
    config_change(root, 'auto = true', 'auto = true\nsoak_minutes = 180')
    base_checks(host, 'success')
    result = check(case)
    assert (result.exit, result.reason) == (1, f'merge policy: waits: soak ends at {WAIT}; run bin/wuwei merge example/project#7 after it'), result
    assert result.data == {'next': f'run bin/wuwei merge {REF} after {WAIT}'}
    for text in (result.reason, result.data['next']):
        assert 'owner merges' not in text and 'ask the owner' not in text


def test_unreadable_base_checks_fail_closed(case):
    root, host = case
    config_change(root, 'auto = true', 'auto = true\nsoak_minutes = 180')
    base_checks(host, Result(2, None, 'offline'))
    assert check(case).exit == 2


def test_base_checks_are_read_only_when_the_soak_holds(case):
    root, host = case
    base_checks(host, 'failure')
    result = check(case)
    assert result.exit == 0 and result.data['soak'] is None and not base_reads(host), result
    config_change(root, 'auto = true', 'auto = true\nsoak_minutes = 180')
    assert policy().check(REF, root=root, granted=True).exit == 0
    assert not base_reads(host)


def test_an_owner_rule_says_the_owner_merges(case):
    config_change(case[0], 'auto = true', 'auto = false')
    result = check(case)
    assert (result.exit, result.reason) == (1, "merge policy: owner merges: merge.auto is off; run bin/wuwei merge example/project#7: it merges under the owner's grant, or asks the owner on a card"), result
    assert result.data == {'next': GRANT} and 'waits' not in result.reason


def test_cli_check_prints_the_next_step(case, monkeypatch, capsys):
    from wuwei.__main__ import main
    root, host = case
    monkeypatch.chdir(root / 'repo')
    config_change(root, 'auto = true', 'auto = true\nsoak_minutes = 180')
    base_checks(host, 'success')
    assert main(['merge', 'check', '7']) == 1
    assert capsys.readouterr().out.splitlines() == [
        f'merge policy: waits: soak ends at {WAIT}; run bin/wuwei merge example/project#7 after it', f'Next: run bin/wuwei merge {REF} after {WAIT}']
    config_change(root, 'auto = true', 'auto = false')
    assert main(['merge', 'check', '7']) == 1
    assert capsys.readouterr().out.splitlines() == ["merge policy: owner merges: merge.auto is off; run bin/wuwei merge example/project#7: it merges under the owner's grant, or asks the owner on a card", f'Next: {GRANT}']
    host.results['checks'].data[0]['conclusion'] = 'failure'
    assert main(['merge', '7']) == 1
    assert 'Next:' not in capsys.readouterr().out


@pytest.mark.parametrize('value,code', [(False, 1), ('yes', 2)])
def test_squash_must_be_allowed(case, value, code):
    # #524: WUWEI merges only with --squash, so a repository without it is the owner's merge.
    case[1].results['protection'].data['squash'] = value
    result = check(case)
    assert result.exit == code, result
    if code == 1:
        assert 'example/project does not allow squash merges into main' in result.reason
        assert 'host terminal' in result.reason


@pytest.mark.parametrize('field,value,hint', [
    ('merge_state', 'dirty', 'dirty'), ('merge_state', 'behind', 'behind'),
    ('merge_state', 'blocked', 'protection'), ('draft', True, 'draft'),
    ('state', 'closed', 'open'), ('mergeable', None, 'mergeability'),
    ('base', 'production', 'base'), ('changed_files', 2, 'files'),
    ('head', 'bad', 'head'),
])
def test_host_refusals(case, field, value, hint):
    case[1].results['pr'].data[field] = value
    result = check(case)
    assert result.exit in (1, 2) and hint in result.reason, result


@pytest.mark.parametrize('path', ['.github/workflows/test.yml', 'package.json',
    'pkg/package-lock.json', 'src/deploy/a.py', 'infra/main.tf', 'CODEOWNERS',
    'db/migrations/001.sql', 'schema.sql', 'requirements.txt', 'pyproject.toml'])
def test_never_auto_paths(case, path):
    case[1].results['files'].data[0]['path'] = path
    assert check(case).exit == 1


def test_rename_cannot_hide_protected_source(case):
    case[1].results['files'].data[0]['previous_path'] = 'infra/a.py'
    assert check(case).exit == 1


@pytest.mark.parametrize('operation', ['pr', 'files', 'checks', 'protection', 'reviews', 'threads'])
@pytest.mark.parametrize('result', [Result(2, None, 'offline'), Result(0, {'message': 'Denied',
    'documentation_url': 'url'})])
def test_unreadable_evidence_routes_to_owner(case, operation, result):
    case[1].results[operation] = result
    answer = check(case)
    assert answer.exit == 2 and 'owner' in answer.reason, answer
    assert not any(call[0] == 'merge' for call in case[1].calls)


@pytest.mark.parametrize('change,hint', [
    ('missing-check', 'tests'), ('pending-optional', 'optional'),
    ('missing-required', 'required'), ('wrong-app', 'tests'),
    ('stale-check', 'head'), ('author-approval', 'approvals'),
    ('bot-approval', 'approvals'), ('stale-approval', 'approvals'),
    ('changes-requested', 'changes requested'), ('visibility', 'channel-post'),
    ('reply', 'comment'), ('thread', 'thread'), ('risk', 'risk'),
    ('cycle', 'cycle'), ('unlinked', 'item'), ('gate', 'security'),
    ('forged-flags', 'risk'),
])
def test_policy_preconditions(case, change, hint):
    root, host = case
    if change == 'missing-check': host.results['checks'] = Result(0, [])
    elif change == 'pending-optional': host.results['checks'].data.append(
        {'name': 'optional', 'sha': SHA, 'state': 'in_progress', 'conclusion': None, 'app_id': 1})
    elif change == 'missing-required': host.results['protection'].data['required_checks'] = []
    elif change == 'wrong-app': host.results['checks'].data[0]['app_id'] = 2
    elif change == 'stale-check': host.results['checks'].data[0]['sha'] = BASE
    elif change == 'author-approval': host.results['reviews'].data[0]['author'] = 'owner'
    elif change == 'bot-approval': host.results['reviews'].data[0]['is_bot'] = True
    elif change == 'stale-approval': host.results['reviews'].data[0]['sha'] = BASE
    elif change == 'changes-requested': host.results['reviews'].data[0]['state'] = 'changes_requested'
    elif change == 'visibility':
        state._write_state(lambda d: d.update(channel_posts=[]), root, reserved=False)
        with (root / '.wuwei/config.toml').open('a') as f:
            f.write('\n[adapters]\nchat = "slack"\n')
    elif change == 'reply': host.results['threads'].data['comments'] = [
        {'id': 2, 'author': 'reviewer', 'is_bot': False, 'body': 'Please explain',
         'created_at': '2026-09-29T10:00:00Z'}]
    elif change == 'thread': host.results['threads'].data['threads'] = [
        {'id': 't1', 'resolved': False, 'outdated': False, 'comments': [
            {'id': 2, 'author': 'reviewer', 'is_bot': False, 'body': 'Please fix',
             'created_at': '2026-09-29T10:00:00Z'}]}]
    elif change == 'risk': state._write_state(lambda data: data['items']['item-7']['flags'].update(agent_surface=True), root, reserved=False)
    elif change == 'forged-flags': state.append_event('plan.approved', {
        'flags': {'item-7': {'trust_surface': True, 'boundary_relevant': False, 'agent_surface': False}},
        'approved_items': ['item-7']}, root)
    elif change == 'cycle':
        for _ in range(2): state.append_event('state.transition', {'item': 'item-7', 'phase': 'fix'}, root)
    elif change == 'unlinked': state._write_state(lambda data: data['items']['item-7'].update(pr='example/project#8'), root, reserved=False)
    elif change == 'gate': (workspace.day_dir(root) / 'decisions/gate-item-7-security.md').unlink()
    answer = check(case)
    assert answer.exit == (2 if change == 'stale-check' else 1) and hint in answer.reason, answer


def test_changed_head_during_reads_is_not_cleared(case, monkeypatch):
    root, host = case
    original = host.pr
    calls = 0
    def read(ref, root=None):
        nonlocal calls
        calls += 1
        result = original(ref, root)
        if calls > 1: result.data['head'] = BASE
        return result
    monkeypatch.setattr(host, 'pr', read)
    assert check(case).exit == 1


@pytest.mark.parametrize('score,head,findings,code', [(5, SHA, [], 0), (4, SHA, [], 1),
    (5, BASE, [], 1), (5, SHA, [{'blocking': True}], 1)])
def test_review_bot_score_and_same_summary_head(case, monkeypatch, score, head, findings, code):
    root, host = case
    config_change(root, 'auto = true', 'auto = true\nbot_login = "reviewer-bot"')
    with (root / '.wuwei/config.toml').open('a') as f:
        f.write('\n[adapters]\nreview_bot = "greptile"\n')
    host.results['threads'].data['comments'] = [{'id': 3, 'author': 'reviewer-bot',
        'is_bot': True, 'body': f'Confidence Score: {score}/5\nhttps://github.com/example/project/commit/{head}',
        'created_at': '2026-09-29T10:00:00Z'}]
    bot = SimpleNamespace(score=lambda *a, **k: Result(0, score),
                          open_findings=lambda *a, **k: Result(0, findings))
    monkeypatch.setattr(registry, 'load', lambda kind, config: bot if kind == 'review_bot' else host)
    assert check(case).exit == code


def test_merge_pins_head_and_writes_evidence_and_undo(case):
    root, host = case
    result = policy().execute(REF, root)
    assert result.exit == 0, result
    assert ('merge', (REF, SHA), root) in host.calls
    entry = state.read_state(root)['merges'][REF]
    assert entry['head'] == SHA and entry['status'] == 'accepted'
    assert entry['evidence']['approvals'] == ['reviewer']
    assert any(e['kind'] == 'merge.auto' for e in events(root))
    undo = [json.loads(line) for line in (workspace.day_dir(root) / 'undo.jsonl').read_text().splitlines()]
    assert undo[0]['payload']['pr'] == REF and undo[0]['payload']['operation'] == 'revert_pr'
    assert undo[0]['payload']['head'] == SHA


def test_push_between_check_and_merge_fails(case, monkeypatch):
    root, host = case
    def race(ref, head, root=None):
        assert head == SHA
        host.results['pr'].data['head'] = BASE
        return Result(2, None, 'head does not match')
    monkeypatch.setattr(host, 'merge', race)
    result = policy().execute(REF, root)
    assert result.exit == 2 and 'head' in result.reason
    assert state.read_state(root)['merges'][REF]['status'] == 'intent'
    assert not any(e['kind'] == 'merge.auto' for e in events(root))


def test_refused_merge_never_calls_mutation(case):
    root, host = case
    host.results['checks'].data[0]['conclusion'] = 'skipped'
    assert policy().execute(REF, root).exit == 1
    assert not any(c[0] == 'merge' for c in host.calls)
    assert events(root)[-1]['kind'] == 'merge.policy_blocked'


def test_cli_check_and_numeric_merge(case, monkeypatch, capsys):
    from wuwei.__main__ import main
    root, host = case
    monkeypatch.chdir(root / 'repo')
    assert main(['merge', 'check', '7']) == 0
    assert not any(c[0] == 'merge' for c in host.calls)
    assert main(['merge', '7']) == 0
    assert 'head' in capsys.readouterr().out


@pytest.mark.parametrize('key', ['merges', 'merge_breakers'])
def test_generic_state_cannot_forge_merge_evidence(case, key):
    with pytest.raises(state.StateError, match='reserved'):
        state.set_state(key, {}, case[0])


@pytest.mark.parametrize('kind', ['merge.auto', 'merge.intent', 'merge.breaker', 'base.red'])
def test_generic_event_cannot_forge_merge_evidence(case, kind):
    from argparse import Namespace
    from wuwei.commands.event import run
    assert run(Namespace(kind=kind, payload='{}')) == 1


@pytest.mark.parametrize('command,code', [
    ('gh pr merge 7', 1), ('env X=1 gh pr merge 7 --squash', 1),
    ('gh pr merge 7 --admin', 1), ('gh api repos/example/project/pulls/7/merge -X PUT', 1),
    ('gh pr merge $PR', 2), ('gh pr merge "', 2),
    ('python3 -m pytest -q', 0), ('for x in 1; do echo x; done', 0), ('export X=1', 0),
])
def test_guard_never_bypasses_dedicated_writer(case, command, code):
    from wuwei.guards.pr import check as guard
    root, host = case
    result = guard({'cwd': str(root / 'repo'), 'tool_input': {'command': command}})
    assert result[0] == code, result
    assert not any(c[0] == 'merge' for c in host.calls)


def test_guard_calls_shared_policy(case, monkeypatch):
    from wuwei.guards.pr import check as guard
    calls = []
    def fail(*args, **kwargs):
        calls.append((args, kwargs))
        return Result(2, None, 'offline')
    monkeypatch.setattr(policy(), 'check', fail)
    result = guard({'cwd': str(case[0] / 'repo'), 'tool_input': {'command': 'gh pr merge 7'}})
    assert result == (2, 'offline') and len(calls) == 1


def merged(case):
    root, host = case
    assert policy().execute(REF, root).exit == 0
    host.results['pr'].data.update(state='closed', merged=True, merge_commit=MERGED,
                                  merged_at='2026-09-29T12:00:00Z')
    host.results['checks'].data[0]['sha'] = MERGED
    host.results['history'].data['files'] = deepcopy(host.results['files'].data)
    return root, host


def test_merge_done_uses_item_from_merge_day(case, monkeypatch):
    root, _ = merged(case)
    from wuwei import dispatch
    calls = []
    monkeypatch.setattr(dispatch, 'tracker_call', lambda *args: calls.append(args))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T12:00:00Z')
    assert state.read_state(root)['items'] == {}
    assert policy().poll(root) == 0
    assert calls == [('item-7', 'done', root)]


def test_merge_without_linked_item_records_tracker_miss(case):
    root, _ = merged(case)
    state._write_state(lambda data: data['items']['item-7'].update(pr='example/project#8'),
                       root, reserved=False)
    assert policy().poll(root) == 0
    assert any(event['kind'] == 'tracker.call' and event['payload']['action'] == 'done'
               and event['payload']['exit'] == 2
               and event['payload']['reason'] == 'no item linked to merged PR'
               for event in events(root))


def test_red_base_check_reverts_pages_and_disables_across_days(case, monkeypatch):
    root, host = merged(case)
    from wuwei import dispatch
    tracker_calls = []
    monkeypatch.setattr(dispatch, 'tracker_call', lambda *args: tracker_calls.append(args))
    host.results['checks'].data[0]['conclusion'] = 'failure'
    result = policy().poll(root)
    assert result == 1
    assert tracker_calls == [('item-7', 'done', root)]
    assert ('checks', (REF, MERGED), root) in host.calls
    assert ('revert_pr', (REF,), root) in host.calls
    assert state.read_state(root)['merges'][REF]['revert_pr'].endswith('/8')
    from wuwei.signal import classify
    red = next(e for e in events(root) if e['kind'] == 'base.red')
    assert classify(red, {})[0] == 'page'
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T12:00:00Z')
    result = check(case)
    assert result.exit == 1 and 'breaker' in result.reason
    host.calls.clear()
    assert policy().poll(root) == 1
    assert not any(c[0] == 'revert_pr' for c in host.calls)


def test_failed_revert_still_disables_and_retries(case):
    root, host = merged(case)
    host.results['checks'].data[0]['conclusion'] = 'failure'
    host.results['revert_pr'] = Result(2, None, 'unavailable')
    assert policy().poll(root) == 2
    assert check(case).exit == 1
    host.results['revert_pr'] = Result(0, {'number': 8, 'url': 'https://github.com/example/project/pull/8'})
    assert policy().poll(root) == 1
    assert state.read_state(root)['merges'][REF]['revert_pr'].endswith('/8')


def test_watch_reconciles_accepted_mutation_after_timeout(case, monkeypatch):
    root, host = case
    host.results['merge'] = Result(2, None, 'timeout')
    assert policy().execute(REF, root).exit == 2
    host.results['pr'].data.update(state='closed', merged=True, merge_commit=MERGED,
                                  merged_at='2026-09-29T12:00:00Z')
    host.results['checks'].data[0]['sha'] = MERGED
    assert policy().poll(root) == 0
    assert state.read_state(root)['merges'][REF]['status'] == 'merged'
    assert (workspace.day_dir(root) / 'undo.jsonl').exists()


def test_missing_base_checks_are_unmeasured_and_keep_monitoring(case):
    root, host = merged(case)
    host.results['checks'] = Result(0, [])
    assert policy().poll(root) == 2
    assert state.read_state(root)['merges'][REF]['status'] == 'merged'


def test_watch_scheduler_runs_merge_poll(case, monkeypatch):
    from wuwei import watch
    root, host = case
    calls = []
    monkeypatch.setattr(policy(), 'poll', lambda r: calls.append(r) or 1)
    monkeypatch.setattr(watch, 'poll', lambda r: 0)
    monkeypatch.setattr(watch, 'sweep', lambda *a, **k: 0)
    assert watch.tick(root) == 1
    assert calls == [root]


def test_daily_cap_counts_pending_intents(case):
    root, host = case
    config_change(root, 'auto = true', 'auto = true\nmax_per_day = 1')
    state._write_state(lambda d: d.update(merges={'example/project#6': {
        'head': SHA, 'status': 'intent', 'at': workspace.now().isoformat()}}), root, reserved=False)
    result = check(case)
    assert result.exit == 1 and 'cap' in result.reason


def test_completed_windows_only_and_baseline_comparison(case, monkeypatch):
    root, host = merged(case)
    assert policy().poll(root) == 0
    host.results['history'].data['commits'] = [{'sha': 'd' * 40, 'at': '2026-10-01T12:00:00Z',
        'message': 'fix: regression', 'files': [{'path': 'src/a.py', 'previous_path': None,
        'status': 'modified', 'additions': 1, 'deletions': 1, 'patch': '@@ -2 +2 @@\n-line\n+fixed'}]}]
    directory = root / '.wuwei/memory/notes'
    directory.mkdir(parents=True)
    (directory / 'baseline.md').write_text('---\ntype: reference\n---\nEscaped-defect-rate: 0.1\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-10-02T12:00:00Z')
    assert policy().poll(root) == 0  # Too young for a rate denominator.
    monkeypatch.setenv('WUWEI_NOW', '2026-10-14T12:00:00Z')
    assert policy().poll(root) == 1
    assert 'defect rate' in state.read_state(root)['merge_breakers']['example/project']['reason']


@pytest.mark.parametrize('now', ['2026-10-27T12:00:00Z', '2026-11-28T12:00:00Z'])
def test_expired_monitor_stops_host_reads_and_clears_old_errors(case, monkeypatch, now):
    root, host = merged(case)
    directory = workspace.day_dir(root)
    host.results['history'] = Result(2, None, 'nonlinear base history')
    assert policy().poll(root) == 2
    monkeypatch.setenv('WUWEI_NOW', now)
    host.calls.clear()
    assert policy().poll(root) == 0
    assert host.calls == []
    assert 'monitor_error' not in state.read_state(directory=directory)['merges'][REF]
    result = policy().check('example/project#8', root)
    assert 'post-merge observations' not in result.reason


def test_outcome_measured_once_at_fourteen_days_but_later_reverts_still_trip(case, monkeypatch):
    root, host = merged(case)
    directory = workspace.day_dir(root)
    notes = root / '.wuwei/memory/notes'
    notes.mkdir(parents=True)
    (notes / 'baseline.md').write_text('Escaped-defect-rate: 1\n')
    measured = []
    original = policy().outcome
    def measure(*args):
        measured.append(True)
        return original(*args)
    monkeypatch.setattr(policy(), 'outcome', measure)
    monkeypatch.setenv('WUWEI_NOW', '2026-10-13T11:59:59Z')
    assert policy().poll(root) == 0
    assert measured == []
    assert ('history', ('example/project', MERGED, 'main', False), root) in host.calls
    monkeypatch.setenv('WUWEI_NOW', '2026-10-13T12:00:00Z')
    assert policy().poll(root) == 0
    assert measured == [True]
    cached = state.read_state(directory=directory)['merges'][REF]['outcome']
    assert cached['escaped'] is False
    assert ('history', ('example/project', MERGED, 'main', True), root) in host.calls
    monkeypatch.setenv('WUWEI_NOW', '2026-10-26T12:00:00Z')
    host.results['history'].data['files'] = None
    host.results['history'].data['commits'] = [{'sha': 'd' * 40,
        'at': '2026-10-26T12:00:00Z', 'message': f'This reverts commit {MERGED}.'}]
    host.calls.clear()
    assert policy().poll(root) == 1
    assert measured == [True]
    assert state.read_state(directory=directory)['merges'][REF]['outcome'] == cached
    assert ('history', ('example/project', MERGED, 'main', False), root) in host.calls
    assert 'reverted' in state.read_state(root)['merge_breakers']['example/project']['reason']


def test_mature_outcomes_without_baseline_are_unmeasured(case, monkeypatch):
    root, host = merged(case)
    assert policy().poll(root) == 0
    monkeypatch.setenv('WUWEI_NOW', '2026-10-14T12:00:00Z')
    assert policy().poll(root) == 2


def test_revert_in_base_history_trips_immediately(case):
    root, host = merged(case)
    host.results['history'].data['commits'] = [{'sha': 'd' * 40, 'at': '2026-09-29T12:00:00Z',
        'message': f'Revert change\n\nThis reverts commit {MERGED}.', 'files': []}]
    assert policy().poll(root) == 1
    assert 'revert' in state.read_state(root)['merge_breakers']['example/project']['reason']


@pytest.mark.parametrize('path', [None, '', '../src/a.py'])
def test_malformed_primary_path_fails_closed(case, path):
    case[1].results['files'].data[0]['path'] = path
    assert check(case).exit == 2


def test_required_app_cannot_be_spoofed_by_latest_status(case):
    case[1].results['checks'].data.append({'name': 'tests', 'sha': SHA,
        'state': 'completed', 'conclusion': 'failure', 'app_id': 2})
    assert check(case).exit == 1


def test_fail_before_external_merge_if_undo_cannot_be_written(case, monkeypatch):
    root, host = case
    monkeypatch.setattr(policy(), 'undo', lambda *a: (_ for _ in ()).throw(OSError('disk full')))
    assert policy().execute(REF, root).exit == 2
    assert not any(c[0] == 'merge' for c in host.calls)


def test_concurrent_merges_only_one_mutation(case, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    root, host = case
    entered, release = Event(), Event()
    def merge(ref, head, root=None):
        host.calls.append(('merge', (ref, head), root))
        entered.set()
        assert release.wait(5)
        return Result(0, {'accepted': True, 'sha': head})
    monkeypatch.setattr(host, 'merge', merge)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(policy().execute, REF, root)
        assert entered.wait(5)
        second = pool.submit(policy().execute, REF, root)
        release.set()
        assert first.result().exit == 0
        assert second.result().exit == 1
    assert sum(c[0] == 'merge' for c in host.calls) == 1


def test_owner_reset_allows_next_policy_evaluation(case):
    root, host = case
    policy().trip(root, 'example/project', workspace.load_config(root)['repos'][0]['merge'], 'test')
    assert check(case).exit == 1
    config_change(root, 'auto = true', 'auto = true\nreset_epoch = 1')
    assert check(case).exit == 0


def test_same_line_fixes_follow_intervening_insertions():
    entry = {'merged_at': '2026-09-01T12:00:00Z', 'merge_commit': MERGED,
        'evidence': {'files': [{'path': 'a.py', 'patch': '@@ -0,0 +1,2 @@\n+one\n+two',
                              'additions': 2, 'deletions': 0}]}}
    config = {'fix_pattern': r'\bfix\b'}
    def commit(patch, add, delete, message='refactor'):
        return {'sha': SHA, 'at': '2026-09-02T12:00:00Z', 'message': message, 'files': [
            {'path': 'a.py', 'previous_path': None, 'patch': patch,
             'additions': add, 'deletions': delete}]}
    history = [commit('@@ -0,0 +1 @@\n+heading', 1, 0),
               commit('@@ -3 +3 @@\n-two\n+correct', 1, 1, 'fix bug')]
    assert policy().outcome(entry, history, config)['escaped'] is True
    history[-1] = commit('@@ -4 +4 @@\n-unrelated\n+other', 1, 1, 'fix bug')
    assert policy().outcome(entry, history, config)['escaped'] is False


def test_patch_context_does_not_count_as_changed_line():
    file = {'patch': '@@ -1,3 +1,3 @@\n context\n-old\n+new\n context',
            'additions': 1, 'deletions': 1}
    assert policy().edits(file) == [[2, 1, 2, 1]]


def test_truncated_patch_is_unmeasured():
    with pytest.raises(ValueError, match='patch'):
        policy().edits({'patch': '@@ -1,3 +1,3 @@\n-a\n+b', 'additions': 1, 'deletions': 1})


def test_owner_reset_is_not_undone_by_old_red_entry(case):
    root, host = merged(case)
    host.results['checks'].data[0]['conclusion'] = 'failure'
    assert policy().poll(root) == 1
    config_change(root, 'auto = true', 'auto = true\nreset_epoch = 1')
    assert policy().poll(root) == 1
    _, breakers = policy().journals(root)
    assert breakers['example/project']['epoch'] == 0


def test_new_red_pr_pages_even_when_repo_already_disabled(case):
    root, host = merged(case)
    policy().trip(root, 'example/project', workspace.load_config(root)['repos'][0]['merge'],
                  'previous regression', ref='example/project#6')
    host.results['checks'].data[0]['conclusion'] = 'failure'
    assert policy().poll(root) == 1
    assert any(e['kind'] == 'base.red' and e['payload']['pr'] == REF for e in events(root))


def test_pending_base_check_cannot_become_clean_mature_metric(case, monkeypatch):
    root, host = merged(case)
    directory = root / '.wuwei/memory/notes'
    directory.mkdir(parents=True)
    (directory / 'baseline.md').write_text('Escaped-defect-rate: 0.1\n')
    host.results['checks'].data[0].update(state='in_progress', conclusion=None)
    assert policy().poll(root) == 0
    monkeypatch.setenv('WUWEI_NOW', '2026-10-14T12:00:00Z')
    assert policy().poll(root) == 2
    assert not any(e['kind'] == 'merge.metric' for e in events(root))


def test_transitions_cannot_erase_cycle_budget(case):
    root, host = case
    for phase in ('implement', 'gate', 'fix', 'delta', 'fix'):
        state.transition('item-7', phase, root)
    result = check(case)
    assert result.exit == 1 and 'cycle' in result.reason


def test_mature_missing_required_base_check_is_unmeasured(case, monkeypatch):
    root, host = merged(case)
    host.results['checks'].data[0]['name'] = 'unrelated'
    directory = root / '.wuwei/memory/notes'
    directory.mkdir(parents=True)
    (directory / 'baseline.md').write_text('Escaped-defect-rate: 0.1\n')
    monkeypatch.setenv('WUWEI_NOW', '2026-10-14T12:00:00Z')
    assert policy().poll(root) == 2
    assert not any(e['kind'] == 'merge.metric' for e in events(root))


def test_outcome_uses_actual_merge_patch_and_fresh_base_branch(case):
    root, host = merged(case)
    host.results['history'] = Result(0, {'files': [{'path': 'src/a.py', 'previous_path': None,
        'additions': 1, 'deletions': 1, 'patch': '@@ -100 +100 @@\n-old\n+new'}],
        'commits': [{'sha': 'd' * 40, 'at': '2026-09-29T12:00:00Z', 'message': 'fix bug',
            'files': [{'path': 'src/a.py', 'previous_path': None, 'additions': 1,
                      'deletions': 1, 'patch': '@@ -100 +100 @@\n-new\n+fixed'}]}]})
    assert policy().poll(root) == 0
    assert ('history', ('example/project', MERGED, 'main', False), root) in host.calls


def test_undo_file_is_protected(case):
    from wuwei.guards.protect_state import check_file
    path = workspace.day_dir(case[0]) / 'undo.jsonl'
    payload = {'cwd': str(case[0]), 'tool_name': 'Write',
               'tool_input': {'file_path': str(path), 'content': '{}'}}
    assert check_file(payload)[0] == 1


def test_insertions_preserve_original_line_tracking():
    entry = {'merged_at': '2026-09-01T12:00:00Z', 'merge_commit': MERGED,
        'evidence': {'files': [{'path': 'a.py', 'patch': '@@ -0,0 +1 @@\n+one',
                              'additions': 1, 'deletions': 0}]}}
    def change(patch, additions, deletions, message):
        return {'sha': SHA, 'at': '2026-09-02T12:00:00Z', 'message': message,
                'files': [{'path': 'a.py', 'previous_path': None, 'patch': patch,
                           'additions': additions, 'deletions': deletions}]}
    history = [change('@@ -0,0 +1 @@\n+heading', 1, 0, 'refactor'),
               change('@@ -2 +2 @@\n-one\n+fixed', 1, 1, 'fix bug')]
    assert policy().outcome(entry, history, {'fix_pattern': 'fix'})['escaped'] is True


def test_unreadable_post_merge_measurement_blocks_next_merge(case):
    root, host = merged(case)
    host.results['checks'] = Result(2, None, 'offline')
    assert policy().poll(root) == 2
    # A new PR must not bypass an unmeasured post-merge breaker input.
    result = policy().check('example/project#8', root)
    assert result.exit == 2 and 'post-merge' in result.reason


def test_skipped_check_is_named_even_when_host_marks_branch_blocked(case):
    case[1].results['pr'].data['merge_state'] = 'blocked'
    case[1].results['checks'].data[0]['conclusion'] = 'skipped'
    result = check(case)
    assert result.exit == 1 and 'tests' in result.reason


@pytest.mark.parametrize('path', ['ci/check.sh', '.buildkite/pipeline.yml',
                                  'setup.py', 'infrastructure/stack.py'])
def test_default_never_auto_covers_ci_and_infrastructure(case, path):
    case[1].results['files'].data[0]['path'] = path
    assert check(case).exit == 1


def test_evidence_does_not_copy_source_patch_to_state_or_events(case):
    root, host = case
    host.results['files'].data[0]['patch'] = 'private-source-marker'
    result = policy().execute(REF, root)
    assert result.exit == 0
    assert 'private-source-marker' not in json.dumps(result.data)
    assert 'private-source-marker' not in (workspace.day_dir(root) / 'events.jsonl').read_text()
    assert 'private-source-marker' not in (workspace.day_dir(root) / 'state.json').read_text()


def test_owner_disabling_config_during_reads_vetoes_merge(case, monkeypatch):
    root, host = case
    original = host.pr
    def read_pr(ref, root=None):
        config_change(root, 'auto = true', 'auto = false')
        return original(ref, root)
    monkeypatch.setattr(host, 'pr', read_pr)
    assert policy().execute(REF, root).exit == 1
    assert not any(c[0] == 'merge' for c in host.calls)


def test_protected_stacked_base_is_eligible(case):
    case[1].results['pr'].data['base'] = 'parent-feature'
    assert check(case).exit == 0


@pytest.mark.parametrize('checks', [Result(0, [{'name': 'tests', 'sha': MERGED, 'app_id': 1,
    'state': 'in_progress', 'conclusion': None}]), Result(0, []), Result(2, None, 'offline')])
def test_revert_is_detected_even_with_incomplete_base_checks(case, checks):
    root, host = merged(case)
    host.results['checks'] = checks
    host.results['history'].data['files'][0]['patch'] = None
    host.results['history'].data['commits'] = [{'sha': 'd' * 40,
        'at': '2026-09-29T12:00:00Z', 'message': f'This reverts commit {MERGED}.', 'files': []}]
    assert policy().poll(root) in (1, 2)
    assert 'reverted' in state.read_state(root)['merge_breakers']['example/project']['reason']


def test_generic_note_writer_cannot_forge_owner_baseline(case):
    from argparse import Namespace
    from wuwei.commands.note import run_add
    root, _ = case
    directory = root / '.wuwei/memory/notes'
    directory.mkdir(parents=True)
    assert run_add(Namespace(slug='baseline', type='reference', summary='Baseline',
                             alias=[], body='Escaped-defect-rate: 1')) == 1
    assert not (directory / 'baseline.md').exists()


@pytest.mark.parametrize('action', ['patch', 'archive', 'fold'])
def test_generic_promotion_cannot_change_owner_baseline(case, action):
    from wuwei.promotion import _apply
    root, _ = case
    directory = root / '.wuwei/memory/notes'
    directory.mkdir(parents=True)
    target = directory / 'baseline.md'
    original = ('---\ntype: reference\nsummary: Baseline\naliases: []\nstatus: active\n'
                'created: 2026-01-01\n---\nEscaped-defect-rate: 0.1\n')
    target.write_text(original)
    proof = '.wuwei/memory/notes/proof.md'
    (root / proof).write_text('Observation')
    with pytest.raises(ValueError, match='owner'):
        _apply(root, {'target': '.wuwei/memory/notes/baseline.md', 'action': action,
                     'reason': 'Improve', 'evidence': proof, 'old_text': '0.1', 'text': '1',
                     'survivor': proof})
    assert target.read_text() == original


def test_matched_checks_every_path_suffix():
    merge = importlib.import_module('wuwei.merge')
    assert merge.matched('cli/wuwei/guards/pr.py', ['guards/*']) == 'guards/*'
    assert merge.matched('uv.lock', ['*.lock']) == '*.lock'
    assert merge.matched('docs/guide.md', ['guards/*', '*.lock']) is None


def test_light_item_merge_evidence_lists_quality_only(case):
    root, _ = case
    directory = workspace.day_dir(root) / 'decisions'
    for role in ('arch', 'security'):
        (directory / f'gate-item-7-{role}.md').unlink()
    path = directory / 'gate-item-7-quality.md'
    record = {'item': 'item-7', 'role': 'quality', 'round': 'initial', 'verdict': 'PASS',
              'head': SHA, 'file': str(path.relative_to(root)), 'blocks': False, 'notes': []}
    light = {'tier': 'light', 'computed': 'light', 'reasons': [], 'roles': ['quality']}

    def update(data):
        data['gate_verdicts']['item-7:quality:initial'] = record
        data['items']['item-7']['gates'] = light
    state._write_state(update, root, reserved=False)
    result = check(case)
    assert result.exit == 0, result
    assert [row['path'] for row in result.data['verdicts']] == [record['file']]


def test_shepherd_seat_never_merges(case, monkeypatch, capsys):
    from wuwei.__main__ import main
    root, host = case
    monkeypatch.setenv('WUWEI_SEAT_ROLE', 'shepherd')
    before = len(events(root))
    result = policy().execute(REF, root)
    assert result.exit == 1 and result.reason.startswith('merge refused: a shepherd seat never merges')
    assert len(events(root)) == before
    monkeypatch.chdir(root / 'repo')
    assert main(['merge', '7']) == 1
    assert not any(c[0] == 'merge' for c in host.calls)
    monkeypatch.delenv('WUWEI_SEAT_ROLE')
    assert policy().execute(REF, root).exit == 0


def test_revert_opens_the_revert_pr_once(case):
    # #557: the merge watch and wuwei undo share one revert call.
    root, host = merged(case)
    directory = workspace.day_dir(root)
    entry = state.read_state(root)['merges'][REF]
    url = 'https://github.com/example/project/pull/8'
    assert policy().revert(root, directory, REF, entry, host) == url
    assert entry['revert_pr'] == url and state.read_state(root)['merges'][REF]['revert_pr'] == url
    assert [e['kind'] for e in events(root)][-1] == 'merge.revert'
    host.calls.clear()
    assert policy().revert(root, directory, REF, entry, host) == url and not host.calls


def auto_only(root, host, name):
    """#524: make the PR fail one auto-merge eligibility or pacing rule, and nothing else."""
    if name == 'auto': config_change(root, 'auto = true', 'auto = false')
    elif name == 'breaker': policy().trip(root, 'example/project', workspace.load_config(root)['repos'][0]['merge'], 'test')
    elif name == 'cap':
        config_change(root, 'auto = true', 'auto = true\nmax_per_day = 1')
        state._write_state(lambda d: d.update(merges={'example/project#6': {
            'head': SHA, 'status': 'intent', 'at': workspace.now().isoformat()}}), root, reserved=False)
    elif name == 'quiet': config_change(root, 'auto = true', 'auto = true\nquiet_hours = ["11:00-13:00"]')
    elif name == 'plan': state._write_state(lambda d: d.update(approved_items=[]), root, reserved=False)
    elif name == 'risk': state._write_state(lambda d: d['items']['item-7']['flags'].update(agent_surface=True), root, reserved=False)
    elif name == 'cycle':
        for _ in range(2): state.append_event('state.transition', {'item': 'item-7', 'phase': 'fix'}, root)
    elif name == 'size': config_change(root, 'auto = true', 'auto = true\nmax_changed_lines = 5')
    elif name == 'path': host.results['files'].data[0]['path'] = '.github/workflows/test.yml'
    elif name == 'soak':
        config_change(root, 'auto = true', 'auto = true\nsoak_minutes = 180')
        base_checks(host, 'success')


@pytest.mark.parametrize('name,hint', [
    ('auto', 'merge.auto'), ('breaker', 'breaker'), ('cap', 'cap'), ('quiet', 'quiet'),
    ('plan', 'approved plan'), ('risk', 'risk'), ('cycle', 'cycle'), ('size', 'lines'),
    ('path', 'never-auto'), ('soak', 'soak')])
def test_grant_lifts_only_auto_eligibility_and_pacing(case, name, hint):
    auto_only(*case, name)
    result = check(case)
    assert result.exit == 1 and hint in result.reason, result
    granted = policy().check(REF, root=case[0], granted=True)
    assert granted.exit == 0 and granted.data['head'] == SHA, granted


@pytest.mark.parametrize('change,hint', [
    ('gates', 'pre-PR gates not passed at current HEAD'), ('red', 'required check tests is not green'),
    ('approval', 'required human approvals missing at head'), ('changes', 'outstanding changes requested'),
    ('thread', 'thread:t1'), ('deploys', 'merge_deploys'), ('environment', 'ineligible base branch'),
    ('draft', 'PR is a draft'), ('squash', 'does not allow squash')])
def test_grant_never_lifts_a_precondition(case, change, hint):
    root, host = case
    config_change(root, 'auto = true', 'auto = false')
    if change == 'gates':
        for gate in ('arch', 'quality', 'security'):
            (workspace.day_dir(root) / 'decisions' / f'gate-item-7-{gate}.md').write_text(evidence(BASE))
    elif change == 'red': host.results['checks'].data[0]['conclusion'] = 'failure'
    elif change == 'approval': host.results['reviews'].data[0]['sha'] = BASE
    elif change == 'changes': host.results['reviews'].data[0]['state'] = 'changes_requested'
    elif change == 'thread': host.results['threads'].data['threads'] = [
        {'id': 't1', 'resolved': False, 'outdated': False, 'comments': [
            {'id': 2, 'author': 'reviewer', 'is_bot': False, 'body': 'Please fix',
             'created_at': '2026-09-29T10:00:00Z'}]}]
    elif change == 'deploys': config_change(root, 'merge_deploys = false', 'merge_deploys = true')
    elif change == 'environment': host.results['pr'].data['base'] = 'production'
    elif change == 'draft': host.results['pr'].data['draft'] = True
    elif change == 'squash': host.results['protection'].data['squash'] = False
    result = policy().check(REF, root=root, granted=True)
    assert result.exit == 1 and hint in result.reason, result
    assert result.reason.endswith('; no grant lifts this; run bin/wuwei pr act example/project#7 once it holds')
    assert 'ask the owner;' not in result.reason and 'the owner merges' not in result.reason


@pytest.fixture
def owner(monkeypatch):
    """#524: the owner answers a merge card (the #478 decide path)."""
    from fakes.integrity import seed
    from wuwei import integrity
    from wuwei.commands import decision
    monkeypatch.setattr(integrity, '_host_confirm', lambda *args, **kwargs: True)

    def answer(root, option, identifier='D-1'):
        seed(root)
        return decision.owner_outcome(SimpleNamespace(id=identifier, option=option), root=root)
    return answer


def merged_calls(host):
    return [call[1] for call in host.calls if call[0] == 'merge']


def cards(root):
    return sorted(path.name for path in (workspace.day_dir(root) / 'decisions').glob('D-*.md'))


def granted_case(case, posture=None, tier=None):
    root, host = case
    config_change(root, 'auto = true', 'auto = false')
    with (root / '.wuwei/config.toml').open('a') as stream:
        if posture:
            stream.write(f'\n[security]\nposture = "{posture}"\n')
        if tier:
            stream.write(f'\n[merge]\ndefault_tier = "{tier}"\n')
    return root, host


@pytest.mark.parametrize('posture', ['guarded', 'observe'])
def test_merge_asks_on_a_card_then_runs_under_today(case, owner, posture):
    root, host = granted_case(case, posture)
    result = policy().execute(REF, root)
    assert result.exit == 1 and result.reason.endswith('the owner decides: bin/wuwei decision show D-1 --widget'), result
    assert 'ask the owner' not in result.reason and not merged_calls(host)
    row = state.read_state(root)['grants']['D-1']
    assert (row['action'], row['target'], row['answered']) == ('merge', 'repo:example/project', None)
    assert policy().execute(REF, root).exit == 1 and cards(root) == ['D-1.md']
    assert owner(root, 'Allow today') == (0, 'today')
    result = policy().execute(REF, root)
    assert result.exit == 0, result
    assert merged_calls(host) == [(REF, SHA)]
    kinds = [row['kind'] for row in events(root) if row['kind'] in ('grant.used', 'merge.intent', 'merge.auto')]
    assert kinds == ['grant.used', 'merge.intent', 'merge.auto']
    used = next(row['payload'] for row in events(root) if row['kind'] == 'grant.used')
    assert (used['action'], used['scope'], used['target'], used['decision']) == (
        'merge', 'today', 'repo:example/project', 'D-1')


def test_merge_allow_once_is_spent(case, owner):
    root, host = granted_case(case)
    policy().execute(REF, root)
    owner(root, 'Allow once')
    assert policy().execute(REF, root).exit == 0
    assert state.read_state(root)['grants']['D-1']['spent'] is True
    # The next ready PR on the repository asks again.
    state._write_state(lambda d: d.update(merges={}), root, reserved=False)
    result = policy().execute(REF, root)
    assert result.exit == 1 and 'decision show D-2' in result.reason and len(merged_calls(host)) == 1


@pytest.mark.parametrize('target,code', [('pr:example/project#7', 0), ('pr:example/project#8', 1)])
def test_planned_pr_card_answered_today(case, target, code):
    root, host = granted_case(case)
    state._write_state(lambda d: d.setdefault('grants', {}).update({'D-9': {
        'action': 'merge', 'target': target, 'rule': 'planned', 'command': None, 'item': 'item-7',
        'goal': 'G-1', 'seat': None, 'planned': True, 'answered': 'today', 'spent': False}}),
        root, reserved=False)
    assert policy().execute(REF, root).exit == code
    assert len(merged_calls(host)) == (1 - code)
    if code == 0:
        used = next(row['payload'] for row in events(root) if row['kind'] == 'grant.used')
        assert (used['decision'], used['target']) == ('D-9', target)


def standing_merge(root):
    with (root / '.wuwei/config.toml').open('a') as stream:
        stream.write('\n[grants]\nstanding = [{action = "merge", target = "repo:example/*", scope = "always", '
                     'decision = "D-3", date = "2026-09-28"}]\n')


def test_standing_merge_line_under_guarded(case):
    root, host = granted_case(case)
    standing_merge(root)
    assert policy().execute(REF, root).exit == 0 and merged_calls(host) == [(REF, SHA)]
    used = next(row['payload'] for row in events(root) if row['kind'] == 'grant.used')
    assert used['scope'] == 'always'


def test_kept_merge_card(case, owner):
    root, host = granted_case(case)
    policy().execute(REF, root)
    owner(root, 'Keep owner-only')
    result = policy().execute(REF, root)
    assert result.exit == 1 and 'the owner kept it owner-only (D-1)' in result.reason and not merged_calls(host)


COMMAND = f'gh pr merge https://github.com/example/project/pull/7 --squash --match-head-commit {SHA}'


@pytest.mark.parametrize('standing', [False, True])
def test_strict_without_grant_names_the_owner_command(case, standing):
    root, host = granted_case(case, 'strict')
    if standing:
        standing_merge(root)
    result = policy().execute(REF, root)
    assert result.exit == 1 and 'merge.default_tier = owner_only' in result.reason and COMMAND in result.reason
    assert cards(root) == []
    assert not merged_calls(host)


def test_strict_ask_tier_offers_no_always(case, owner):
    root, host = granted_case(case, 'strict', 'ask')
    assert 'decision show D-1' in policy().execute(REF, root).reason
    text = (workspace.day_dir(root) / 'decisions/D-1.md').read_text()
    assert 'Allow today' in text and 'Always allow' not in text


def test_strict_honours_a_recorded_answer(case, owner):
    root, host = granted_case(case, 'strict', 'ask')
    policy().execute(REF, root)
    config_change(root, 'default_tier = "ask"', 'default_tier = "owner_only"')
    owner(root, 'Allow today')
    assert policy().execute(REF, root).exit == 0


def test_moved_head_merges_under_no_grant(case, owner):
    root, host = granted_case(case)
    policy().execute(REF, root)
    owner(root, 'Allow today')
    for gate in ('arch', 'quality', 'security'):
        (workspace.day_dir(root) / 'decisions' / f'gate-item-7-{gate}.md').write_text(evidence(BASE))
    result = policy().execute(REF, root)
    assert result.exit == 1 and 'pre-PR gates not passed at current HEAD' in result.reason
    assert 'no grant lifts this; run bin/wuwei pr act example/project#7' in result.reason
    assert 'ask the owner' not in result.reason
    assert not merged_calls(host) and not any(row['kind'] == 'grant.used' for row in events(root))
    assert cards(root) == ['D-1.md']


def test_unmeasured_auto_policy_never_reaches_the_grant(case, owner):
    root, host = granted_case(case)
    policy().execute(REF, root)
    owner(root, 'Allow today')
    host.results['checks'] = Result(2, None, 'offline')
    assert policy().execute(REF, root).exit == 2
    assert not merged_calls(host) and not any(row['kind'] == 'grant.used' for row in events(root))


def test_shepherd_seat_never_merges_under_a_grant(case, owner, monkeypatch):
    root, host = granted_case(case)
    standing_merge(root)
    monkeypatch.setenv('WUWEI_SEAT_ROLE', 'shepherd')
    assert policy().execute(REF, root).exit == 1 and not merged_calls(host)


@pytest.mark.parametrize('posture', ['guarded', 'observe'])
def test_merge_default_today_runs_without_a_card(case, posture):
    # #530: the autonomous answer's merge default; the 4.6 preconditions still hold.
    root, host = granted_case(case, posture, 'today')
    result = policy().execute(REF, root)
    assert result.exit == 0, result
    assert merged_calls(host) == [(REF, SHA)] and not (workspace.day_dir(root) / 'decisions' / 'D-1.md').exists()
    assert not [row for row in events(root) if row['kind'] == 'grant.asked']
    used = [row['payload'] for row in events(root) if row['kind'] == 'grant.used']
    assert [(row['decision'], row['scope'], row['target']) for row in used] == [
        ('merge.default_tier', 'today', 'repo:example/project')]


def test_merge_default_today_never_deploys(case):
    root, host = granted_case(case, 'observe', 'today')
    config_change(root, 'merge_deploys = false', 'merge_deploys = true')
    result = policy().execute(REF, root)
    assert result.exit == 1 and 'merge_deploys' in result.reason and not merged_calls(host)


def test_missing_risk_evidence_names_the_plan_add_that_records_it(case):
    # #615: an item admitted by plan add before the fix had no flags; plan add now records them.
    from wuwei import plan
    root = case[0]
    path = workspace.day_dir(root) / 'events.jsonl'
    mode = path.stat().st_mode
    path.chmod(mode | 0o200)  # the log is read-only; only the test rewrites it
    path.write_text(''.join(line + '\n' for line in path.read_text().splitlines()
                            if json.loads(line)['kind'] != 'plan.approved'))
    path.chmod(mode)
    answer = check(case)
    assert answer.exit == 2 and 'run bin/wuwei plan add item-7 ' in answer.reason, answer
    assert plan.add('item-7', root)['action'] == 'risk recorded'
    assert check(case).exit == 0


@pytest.mark.parametrize('setting,path,previous,code,hint', [
    ('size_exclude = ["results/*.json"]\n', 'results/run.json', None, 0, ''),
    ('', 'results/run.txt', None, 1, 'diff exceeds max changed lines'),
    ('size_exclude = ["*.lock"]\n', 'deps/big.lock', None, 1, 'never-auto path'),
    ('size_exclude = ["results/*.txt"]\n', 'src/run.txt', 'results/run.txt', 1, 'diff exceeds max changed lines'),
])
def test_size_exclude_counts_only_the_files_it_does_not_match(case, setting, path, previous, code, hint):
    # #615: a generated data file does not count toward max_changed_lines; never-auto still applies.
    root, host = case
    config_change(root, 'auto = true\n', 'auto = true\n' + setting)
    host.results['files'].data.append({'path': path, 'previous_path': previous,
        'status': 'renamed' if previous else 'added', 'additions': 1000, 'deletions': 0, 'patch': ''})
    host.results['pr'].data.update(additions=1010, changed_files=2)
    answer = check(case)
    assert answer.exit == code and hint in answer.reason, answer


def flag_item(root, record):
    state._write_state(lambda d: d['items']['item-7'].update(owner_merge=record), root, reserved=False)


HOLD = {'value': True, 'by': 'owner', 'at': '2026-09-29T11:00:00+00:00'}
OWNER_LINE = ('owner merges: owner_merge set by owner on 2026-09-29; '
              'clear it with bin/wuwei plan set item-7 owner_merge=false')


@pytest.mark.parametrize('item,hold', [
    ({}, None), ({'owner_merge': dict(HOLD, value=False)}, None),
    ({'owner_merge': HOLD}, ('owner', '2026-09-29'))])
def test_owner_hold_reads_the_item_record(item, hold):
    assert policy().owner_hold(item) == hold


@pytest.mark.parametrize('record', ['yes', dict(HOLD, value='true'),
                                    {'value': True, 'at': HOLD['at']}, dict(HOLD, at=None)])
def test_malformed_owner_hold_is_damaged(record):
    with pytest.raises(ValueError, match='invalid owner_merge record; a WUWEI record'):
        policy().owner_hold({'owner_merge': record})


def test_owner_merge_refuses_before_every_other_rule(case):
    root, host = case
    flag_item(root, HOLD)
    result = check(case)
    assert result.exit == 1 and OWNER_LINE in result.reason, result
    config_change(root, 'auto = true', 'auto = false')
    result = check(case)
    assert result.exit == 1 and OWNER_LINE in result.reason, result
    assert policy().execute(REF, root).exit == 1
    assert not any(c[0] == 'merge' for c in host.calls)
    assert events(root)[-1]['kind'] == 'merge.policy_blocked'
    assert OWNER_LINE in events(root)[-1]['payload']['reason']
    flag_item(root, 'yes')
    assert check(case).exit == 2


def test_plan_set_owner_merge_labels_the_linked_pr(case, monkeypatch):
    # #678: the label is the PR's record; the state is written first, so a failure keeps the hold.
    from wuwei import plan
    root, host = case
    monkeypatch.delenv('WUWEI_SESSION_ID', raising=False)
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    host.results['label'] = Result(0, {'labels': ['owner-merge']})
    assert plan.set_owner_merge('item-7', 'true', root) == 'item-7: owner_merge true'
    host.results['label'] = Result(0, {'labels': []})
    plan.set_owner_merge('item-7', 'false', root)
    assert [c[1] for c in host.calls if c[0] == 'label'] == [
        (REF, 'owner-merge', True), (REF, 'owner-merge', False)]
    host.results['label'] = Result(2, None, 'offline')
    with pytest.raises(OSError, match='rerun bin/wuwei plan set item-7 owner_merge=true'):
        plan.set_owner_merge('item-7', 'true', root)
    assert state.read_state(root)['items']['item-7']['owner_merge']['value'] is True
    assert check(case).exit == 1


def row(path, additions=10, deletions=0, previous=None):
    return {'path': path, 'previous_path': previous, 'additions': additions, 'deletions': deletions}


def uncounted(root, files):
    return policy().uncounted(root, workspace.load_config(root)['repos'][0], files)


@pytest.mark.parametrize('setting,file,kind', [
    ('', row('pilot/manifest.json', 4800), 'data'),
    ('', row('small/config.json', 10), None),
    ('', row('small/config.json', 200), None),
    ('', row('small/config.json', 201), 'data'),
    ('', row('study/results/x.parquet', None, None), 'data'),
    ('', row('uv.lock'), 'generated'),
    ('', row('web/package-lock.json'), 'generated'),
    ('[repos.merge]\nsize_exclude = ["results/*.txt"]\n', row('results/a.txt', 1000), 'generated'),
    ('[repos.gates]\ndata_paths = ["corpus/runs/"]\n', row('corpus/runs/a/b.log', 3000), 'data'),
    ('', row('corpus/runs/a/b.log', 3000), None),
    ('', row('src/run.txt', 4800, previous='pilot/manifest.json'), None),
    ('', row('src/app.py', 4800), None),
])
def test_uncounted_names_generated_and_data_files(case, setting, file, kind):
    # #657: what never counts toward the tier or max_changed_lines.
    root, _ = case
    config_change(root, 'auto = true\n', 'auto = true\n' + setting.replace('[repos.merge]\n', ''))
    assert uncounted(root, [file]) == ({file['path']: kind} if kind else {})


@pytest.mark.parametrize('attributes,extra,kind', [
    ('dist/* linguist-generated\n', [], 'generated'),
    ('# generated\n/dist/* linguist-generated=true\n', [], 'generated'),
    ('**/dist/* linguist-generated\n', [], 'generated'),
    ('dist/* -linguist-generated\n', [], None),
    ('dist/* linguist-generated=false\n', [], None),
    ('dist/* linguist-generated\n', [row('.gitattributes', 1)], None),
])
def test_uncounted_reads_linguist_generated_from_the_checkout(case, attributes, extra, kind):
    root, _ = case
    (root / 'repo/.gitattributes').write_text(attributes)
    assert uncounted(root, [row('dist/app.js', 4800), *extra]).get('dist/app.js') == kind


def test_uncounted_fails_closed_on_unreadable_gitattributes(case):
    root, _ = case
    (root / 'repo/.gitattributes').mkdir()
    with pytest.raises(OSError):
        uncounted(root, [row('src/app.py')])


@pytest.mark.parametrize('source,code,hint', [
    (190, 0, ''),
    (590, 1, 'diff exceeds max changed lines: 600 count over 400 (4800 generated or data excluded)'),
])
def test_size_cap_skips_generated_and_data_lines(case, source, code, hint):
    root, host = case
    host.results['files'].data.extend([row('src/b.py', source), row('pilot/manifest.json', 4800)])
    host.results['pr'].data.update(additions=10 + source + 4800, changed_files=3)
    answer = check(case)
    assert answer.exit == code and hint in answer.reason, answer


def test_size_cap_unreadable_gitattributes_is_unmeasured(case):
    root, _ = case
    (root / 'repo/.gitattributes').mkdir()
    assert check(case).exit == 2
