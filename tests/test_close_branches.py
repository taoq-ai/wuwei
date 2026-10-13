"""Day close: pushed branch evidence through the VCS boundary, and the close checks through
in-process ports (moved from test_stop.py with the Stop guard, #847)."""

import importlib
import io
import json
from datetime import timedelta
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from adapters.vcs import git
from fakes.host import Fake as ProcessHost
from fakes.code_host import Fake as Host
from fakes.replay import install_replay
from fakes.vcs import Fake as VCS
from wuwei import registry, state, watch, workspace
from wuwei.__main__ import main
from wuwei.registry import Result

REF = 'acme/widget#7'
DAY = '2026-09-28'
CHARTER = '.wuwei/charters/builder.md'
CHANGELOG = '.wuwei/memory/CHANGELOG.md'


def module(name):
    assert (Path(__file__).resolve().parents[1] / 'cli/wuwei' / (name + '.py')).exists(), name + ' missing'
    return importlib.import_module('wuwei.' + name.replace('/', '.'))


@pytest.fixture
def case(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/.git').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('[owner]\nhandles=["builder"]\n[spec]\nengine = "none"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', DAY + 'T12:00:00+00:00')
    state._write_state(lambda data: None, tmp_path)
    directory = workspace.day_dir(tmp_path)
    (directory / 'retro').mkdir()
    (directory / 'decisions').mkdir()
    (directory / 'retro' / (DAY + '.md')).write_text('## Applied\nnone\n## Proposed\nnone\n')
    from wuwei.guards.verdict import check_retro
    assert check_retro({'cwd': str(tmp_path), 'agent_id': 'planner-note', 'agent_type': 'planner',
                        'last_assistant_message': 'Blocked: none\nGap: none\nChange: none\n'})[0] == 0
    host, vcs = Host(), VCS()
    host.results['pr'].data['merged'] = False
    host.results['reviews'] = Result(0, [])
    host.results['threads'] = Result(0, {'comments': [], 'threads': []})
    host.results['checks'] = Result(0, [])
    vcs.results['changes_on'] = Result(0, ['charters/builder.md', 'memory/CHANGELOG.md'])
    (tmp_path / CHANGELOG).parent.mkdir(parents=True)
    (tmp_path / CHANGELOG).write_text('- (2026-09-01) Keep tests.\n')
    # HEAD contains the committed charter and changelog.
    vcs.results['read_tree'] = Result(0, {'charters/builder.md': '- (2026-09-01) Keep tests.\n',
        'memory/CHANGELOG.md': '- ' + DAY + ' builder changed\n- (2026-09-01) Keep tests.\n'})
    vcs.results['workspace_changes'] = Result(0, [])
    runtime = SimpleNamespace(dispatch=lambda *args, **kwargs: Result(0, {'agent_type': 'wuwei:steward'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config: {'host': ProcessHost(), 'code_host': host, 'vcs': vcs,
                                                               'runtime': runtime}[kind])
    return tmp_path, host, vcs


def capture(root, role='sentinel-arch', agent='sentinel-note'):
    from wuwei.guards.verdict import check_retro
    return check_retro({'cwd': str(root), 'agent_id': agent, 'agent_type': role,
                        'last_assistant_message': 'Blocked: none\nGap: none\nChange: none\n'})


def test_source_p7_shortfall_then_parity(case):
    root, _, _ = case
    (workspace.day_dir(root) / 'decisions/gate-a.md').write_text('Change: improve tests\n')
    closing = module('closing')
    code, reason = closing.retro(root)
    assert code == 1 and '1 verdict' in reason and '0 sentinel' in reason
    assert capture(root)[0] == 0
    assert closing.retro(root)[0] == 0


@pytest.mark.parametrize('change,expected,fragment', [
    ('clean', 0, ''), ('missing', 1, 'does not exist'),
    ('applied', 1, 'Applied'), ('proposed', 1, 'Proposed'),
    ('no_notes', 1, 'empty'), ('bad_notes', 2, 'unmeasured'),
    ('uncommitted', 1, 'no commit'), ('no_changelog', 1, 'dated'),
    ('uncommitted_changelog', 1, 'changelog'), ('landed', 0, ''),
    ('none_bypass', 1, 'no commit'), ('read_error', 2, 'unmeasured'),
    ('malformed_paths', 2, 'unmeasured'), ('empty_applied', 1, 'Applied'),
])
def test_retro_table(case, change, expected, fragment):
    root, _, vcs = case
    directory = workspace.day_dir(root)
    path = directory / 'retro' / (DAY + '.md')
    if change == 'missing':
        path.unlink()
    elif change in ('applied', 'proposed'):
        path.write_text(path.read_text().replace('## ' + change.title(), '## Absent'))
    elif change == 'empty_applied':
        path.write_text('## Applied\n\n## Proposed\nnone\n')
    elif change in ('no_notes', 'bad_notes'):
        event_path = directory / 'events.jsonl'
        event_path.chmod(0o644)
        event_path.write_text('' if change == 'no_notes' else '{broken\n')
    elif change != 'clean':
        path.write_text('## Applied\n' + ('none\n' if change == 'none_bypass' else '') +
                        '- `' + CHARTER + '`\n## Proposed\nnone\n')
        if change in ('uncommitted', 'none_bypass'):
            vcs.results['changes_on'] = Result(0, [])
        elif change == 'no_changelog':
            vcs.results['read_tree'].data['memory/CHANGELOG.md'] = '- 2026-09-27 prior change\n'
        elif change == 'uncommitted_changelog':
            vcs.results['changes_on'] = Result(0, ['charters/builder.md'])
        elif change == 'read_error':
            vcs.results['changes_on'] = Result(2, None, 'timeout')
        elif change == 'malformed_paths':
            vcs.results['changes_on'] = Result(0, {'error': 'no history'})
    code, reason = module('closing').retro(root)
    assert code == expected, reason
    assert fragment in reason


def test_duplicate_capture_cannot_hide_shortfall(case):
    root, _, _ = case
    for name in ('a', 'b'):
        (workspace.day_dir(root) / 'decisions' / ('gate-' + name + '.md')).write_text('**Change:** x\n')
    capture(root)
    capture(root)
    assert module('closing').retro(root)[0] == 1


def test_pending_charter_proposal_blocks_retro(case):
    root, _, _ = case
    directory = workspace.day_dir(root)
    (directory / 'proposals').mkdir()
    (directory / 'proposals/one.json').write_text(json.dumps({
        'target': CHARTER, 'action': 'add', 'text': '- Check tests.',
        'reason': 'gap', 'evidence': '.wuwei/days/' + DAY + '/retro/note.json'}))
    code, reason = module('closing').retro(root)
    assert code == 1 and 'promote' in reason


def test_landed_charter_omitted_from_retro_blocks(case):
    root, _, _ = case
    directory = workspace.day_dir(root)
    (directory / 'proposals').mkdir()
    (directory / 'proposals/one.landed').write_text(json.dumps({'target': CHARTER}))
    code, reason = module('closing').retro(root)
    assert code == 1 and 'Applied' in reason


def test_rejected_charter_proposal_without_landing_blocks(case):
    root, _, _ = case
    directory = workspace.day_dir(root)
    (directory / 'proposals').mkdir()
    (directory / 'proposals/one.rejected').write_text(json.dumps({'target': CHARTER}))
    code, reason = module('closing').retro(root)
    assert code == 1 and 'rejected' in reason


def test_close_without_amendments_needs_no_git_repository(case, monkeypatch):
    root, host, _ = case
    vcs = importlib.import_module('adapters.vcs.git')
    runtime = SimpleNamespace(dispatch=lambda *args, **kwargs: Result(0, {'agent_type': 'wuwei:steward'}))
    monkeypatch.setattr(registry, 'load', lambda kind, config: {'host': ProcessHost(), 'code_host': host, 'vcs': vcs,
                                                               'runtime': runtime}[kind])
    monkeypatch.chdir(root)
    assert not (root / '.git').exists()
    assert main(['close']) == 0


def own(root):
    state._write_state(lambda data: data.update(raised_prs=[REF]), root)
    state._write_state(lambda data: data.update(planner_session_id='planner'), root)


def advance(monkeypatch, seconds):
    monkeypatch.setenv('WUWEI_NOW', (workspace.now() + timedelta(seconds=seconds)).isoformat())


def action(case):
    root, host, _ = case
    host.results['pr'].data['mergeable'] = False
    from wuwei import pr_actions
    assert pr_actions.evaluate(root)[0] == 1


def disposition(case, kind='parked', body=None, author='builder'):
    root, host, _ = case
    host.results['threads'].data['comments'] = [{
        'id': 10, 'author': author, 'is_bot': False,
        'body': body or f'WUWEI {kind} {REF} {DAY}', 'created_at': DAY + 'T12:00:00Z'}]
    return module('pr_actions').record_disposition(root, REF, kind, 10)


@pytest.mark.parametrize('change', ['author', 'kind', 'day'])
def test_disposition_needs_the_owner_marker(case, change):
    root, _, _ = case
    own(root)
    body = {'kind': f'WUWEI carried {REF} {DAY}', 'day': f'WUWEI parked {REF} 2026-01-01'}.get(change)
    with pytest.raises(ValueError, match='owner-authored comment: WUWEI parked'):
        disposition(case, body=body, author='someone' if change == 'author' else 'builder')
    assert not state.read_state(root).get('pr_dispositions')


def test_disposition_accepts_a_marker_posted_before_the_upgrade(case):
    # Part 14: a marker with its D-n and fingerprint, posted before the upgrade, still verifies.
    root, _, _ = case
    own(root)
    assert disposition(case, body=f'WUWEI parked {REF} D-1 {DAY} ' + 'a' * 64) == 0
    assert state.read_state(root)['pr_dispositions'][REF] == {'kind': 'parked', 'comment_id': 10, 'day': DAY}
    assert not list((workspace.day_dir(root) / 'decisions').glob('D-*.md'))


@pytest.mark.parametrize('kind', ['parked', 'carried'])
@pytest.mark.parametrize('tool', ['comment', 'api', 'Write', 'Edit'])
def test_native_tools_cannot_produce_disposition_markers(case, monkeypatch, capsys, kind, tool):
    root, _, _ = case
    marker = f'WUWEI {kind} {REF} D-1 {DAY} ' + 'a' * 64
    if tool in ('comment', 'api'):
        command = (f"gh pr comment 7 -R acme/widget --body '{marker}'" if tool == 'comment'
                   else f"gh api repos/acme/widget/issues/7/comments -f body='{marker}'")
        name, inputs = 'Bash', {'command': command}
    else:
        name, inputs = tool, {'file_path': str(root / 'body.txt'),
                              'content' if tool == 'Write' else 'new_string': marker}
    monkeypatch.setattr(sys, 'stdin', io.StringIO(json.dumps({
        'cwd': str(root), 'session_id': 'planner', 'transcript_path': 'unused',
        'hook_event_name': 'PreToolUse', 'tool_name': name, 'tool_input': inputs})))
    assert main(['hook', 'PreToolUse']) == 2
    refusal = json.loads(capsys.readouterr().out)['hookSpecificOutput']
    assert refusal['permissionDecision'] == 'deny'
    assert 'owner disposition' in refusal['permissionDecisionReason']


@pytest.mark.parametrize('seconds,expected', [(1799, 0), (1800, 0), (1801, 1)])
def test_explicit_action_deadline(case, monkeypatch, seconds, expected):
    root, _, _ = case
    own(root)
    action(case)
    saved = state.read_state(root)['watch']
    assert 'actions' in saved, 'watch action producer missing'
    deadline = saved['actions'][REF]['deadline']
    advance(monkeypatch, seconds)
    module('pr_actions').evaluate(root)
    assert state.read_state(root)['watch']['actions'][REF]['deadline'] == deadline
    code, reason = module('pr_actions').check(root)
    assert code == expected, reason
    if expected:
        assert REF in reason and 'conflicted' in reason and 'rebase' in reason


def test_waiting_pr_without_action_blocks_only_the_close(case, monkeypatch):
    root, _, _ = case
    own(root)
    advance(monkeypatch, 1801)
    assert module('pr_actions').check(root) == (0, '')
    assert module('pr_actions').check(root, closing=True)[0] == 1


def test_watch_never_inherits_yesterdays_actions(case, monkeypatch):
    root, _, _ = case
    own(root)
    action(case)
    prior = watch.saved(root)['actions'][REF]['deadline']
    advance(monkeypatch, 86400)
    own(root)
    assert module('pr_actions').evaluate(root)[0] == 1
    assert watch.saved(root)['actions'][REF]['deadline'] > prior


@pytest.mark.parametrize('change,expected', [
    ('open', 1), ('closed', 1), ('merged', 0), ('parked', 0), ('carried', 0),
    ('missing_action', 1), ('failed_read', 2), ('malformed_action', 2),
])
def test_pr_close_table(case, change, expected):
    root, host, _ = case
    own(root)
    module('pr_actions').evaluate(root)
    if change in ('closed', 'merged'):
        host.results['pr'].data.update(state='closed', merged=change == 'merged')
    elif change in ('parked', 'carried'):
        assert disposition(case, change) == 0
    elif change == 'missing_action':
        state._write_state(lambda data: data['watch'].pop('actions', None), root)
    elif change == 'malformed_action':
        state._write_state(lambda data: data['watch'].update(actions=[]), root)
    elif change == 'failed_read':
        host.results['pr'] = Result(2, None, 'timeout')
    code, reason = module('pr_actions').check(root, closing=True)
    assert code == expected, reason


@pytest.mark.parametrize('change', ['author', 'bot', 'body', 'day', 'removed'])
def test_local_disposition_never_proves_owner_action(case, change):
    root, host, _ = case
    own(root)
    module('pr_actions').evaluate(root)
    assert disposition(case) == 0
    comment = host.results['threads'].data['comments'][0]
    if change == 'author':
        comment['author'] = 'seat'
    elif change == 'bot':
        comment['is_bot'] = True
    elif change == 'body':
        comment['body'] = 'I did not park it'
    elif change == 'day':
        comment['body'] = comment['body'].replace(DAY, '2026-09-27')
    else:
        host.results['threads'].data['comments'] = []
    code, reason = module('pr_actions').check(root, closing=True)
    assert code == 2, reason


def test_carried_does_not_waive_overdue_action(case, monkeypatch):
    root, _, _ = case
    own(root)
    action(case)
    module('pr_actions').evaluate(root)
    assert disposition(case, 'carried') == 0
    advance(monkeypatch, 1801)
    assert module('pr_actions').check(root)[0] == 1


def test_failed_poll_does_not_reset_deadline(case, monkeypatch):
    root, host, _ = case
    own(root)
    action(case)
    module('pr_actions').evaluate(root)
    assert 'actions' in state.read_state(root)['watch'], 'watch action producer missing'
    before = state.read_state(root)['watch']['actions']
    advance(monkeypatch, 1801)
    host.results['pr'] = Result(2, None, 'unavailable')
    assert module('pr_actions').evaluate(root)[0] == 2
    assert state.read_state(root)['watch']['actions'] == before


@pytest.mark.parametrize('change,expected', [
    ('clean', 0), ('owed_thread', 1), ('retro', 1), ('error', 2), ('malformed_state', 2),
])
def test_close_check_table(case, change, expected):
    # #847: what the Stop guard held at day close is closing.check, run by close.
    root, host, _ = case
    own(root)
    module('pr_actions').evaluate(root)
    if change in ('clean', 'retro'):
        host.results['pr'].data.update(state='closed', merged=True)
    if change == 'owed_thread':
        host.results['threads'].data['threads'] = [{'id': 'T17', 'resolved': False,
            'outdated': False, 'comments': [{'id': 3, 'author': 'reviewer', 'is_bot': False,
                'body': 'Please fix', 'created_at': DAY + 'T10:00:00Z'}]}]
    elif change == 'retro':
        (workspace.day_dir(root) / 'retro' / (DAY + '.md')).unlink()
    elif change == 'error':
        host.results['pr'] = Result(2, None, 'timeout')
    elif change == 'malformed_state':  # #844: records that fail their schema (a torn cache rebuilds)
        from fakes import records
        records.write(root, {'cap': 'bad'})
    code, reason = module('closing').check(root)
    assert code == expected, reason
    if change == 'owed_thread':
        assert REF in reason and 'thread:T17' in reason and 'triage review threads' in reason


@pytest.mark.parametrize('inspection', ['measured', 'none', 'ps', 'lsof'])
def test_close_command_retries(case, monkeypatch, capsys, inspection):
    root, host, _ = case
    if inspection != 'measured':
        from adapters.host import none
        process_host = none if inspection == 'none' else SimpleNamespace(processes=lambda **kw:
            Result(2, None, 'ps unavailable') if inspection == 'ps' else Result(0, {
                41001: {'pid': 41001, 'ppid': 1, 'command': 'worker', 'error': 'lsof unavailable'}}))
        load = registry.load
        monkeypatch.setattr(registry, 'load', lambda kind, config:
                            process_host if kind == 'host' else load(kind, config))
        if inspection == 'none':
            config = root / '.wuwei/config.toml'
            config.write_text(config.read_text() + '\n[adapters]\nhost="none"\n')
    own(root)
    module('pr_actions').evaluate(root)
    monkeypatch.chdir(root)
    assert module('commands/close')
    assert main(['close']) == 1
    assert state.read_state(root)['close_requested'] is True
    assert REF in capsys.readouterr().out
    host.results['pr'].data.update(state='closed', merged=True)
    assert main(['close']) == 0
    if inspection != 'measured':
        assert ('lsof unavailable' if inspection == 'lsof' else 'unmeasured') in capsys.readouterr().out
    assert any(row['kind'] == 'day.closed' for row in watch.records(workspace.day_dir(root) / 'events.jsonl'))


def test_close_outside_workspace(case, monkeypatch):
    root, _, _ = case
    monkeypatch.chdir(root.parent)
    assert module('commands/close')
    assert main(['close']) == 0
    assert 'close_requested' not in state.read_state(root)


def test_close_does_not_manufacture_empty_ownership(case, monkeypatch):
    root, _, _ = case
    monkeypatch.chdir(root)
    (workspace.day_dir(root) / 'state.json').unlink()
    assert main(['close']) == 0  # #362: a state answer, and still nothing written
    assert not (workspace.day_dir(root) / 'state.json').exists()


@pytest.mark.parametrize('kind', ['parked', 'carried'])
@pytest.mark.parametrize('profile', ['strict', 'standard'])
def test_agents_cannot_send_owner_disposition_markers(case, kind, profile):
    from wuwei import outward
    root, _, _ = case
    config = workspace.load_config(root)
    config['profile'] = profile
    config['outbound']['code_host_orgs'] = ['acme']
    code, reason = outward.check_call({'ref': REF, 'text':
        f'WUWEI {kind} {REF} D-1 {DAY} ' + 'a' * 64}, root, config, {'code_host'})
    assert (code, reason) == (1, 'owner disposition markers must be posted by the owner')


def approved(root, **item):
    state._write_state(lambda data: data.update(items={'A': item}, approved_items=['A']),
                       root)


def seat_disposition(root, kind='parked'):
    from wuwei import plan
    plan.dispose('A', kind, 'the reason', root)


@pytest.mark.parametrize('mode,expected', [
    ('open', 1), ('blocked', 1), ('phase_only', 1), ('done_only', 0),
    ('merged', 1), ('parked', 0), ('carried', 0),
])
def test_close_approved_item_table(case, monkeypatch, capsys, mode, expected):
    root, _, _ = case
    approved(root)
    if mode in ('blocked', 'phase_only', 'done_only', 'merged'):
        data = state.read_state(root)
        data['items']['A'].update(
            status='done' if mode == 'done_only' else 'blocked',
            phase={'phase_only': 'parked', 'merged': 'merged'}.get(mode, 'planned'))
        if mode == 'phase_only':
            data['items']['A']['resume_phase'] = 'planned'
        from fakes import records  # #844: the log holds the records
        records.write(root, {'items': data['items']})
    elif mode != 'open':
        seat_disposition(root, mode)
    monkeypatch.chdir(root)
    assert main(['close']) == expected
    if expected:
        assert 'A' in capsys.readouterr().out


@pytest.mark.parametrize('kind,phase,pr', [
    ('review', 'gate', REF), ('measure', 'gate', None),
    ('build', 'parked', None),
])
def test_done_non_build_item_does_not_hold_close(case, kind, phase, pr):
    root, _, _ = case
    approved(root, kind=kind, pr=pr)
    from fakes import records
    data = state.read_state(root)
    data['items']['A'].update(phase=phase, status='done')
    if phase == 'parked':
        data['items']['A']['resume_phase'] = 'planned'
    records.write(root, {'items': data['items']})
    assert module('closing').unresolved(root, []) == (0, '')


def test_unfinished_review_does_not_get_missing_pr_finding(case):
    root, _, vcs = case
    approved(root, kind='review', pr=REF, worktree='repo')
    from fakes import records
    data = state.read_state(root)
    data['items']['A'].update(phase='gate', status='running')
    records.write(root, {'items': data['items']})
    (root / 'repo').mkdir()
    vcs.results['branch'] = Result(0, {'name': 'review-branch'})
    vcs.results['pushed_branches'] = Result(0, ['review-branch'])
    code, reason = module('closing').unresolved(root, [])
    assert code == 1 and 'A is still open' in reason
    assert 'pushed branch' not in reason


@pytest.mark.parametrize('mode,expected', [
    ('unpushed', 0), ('pushed', 1), ('unlinked', 1), ('raised', 0), ('claimed', 0),
    ('read_error', 0), ('error_body', 0), ('branch_error', 0),
])
def test_close_pushed_branch_table(case, monkeypatch, mode, expected):
    root, host, vcs = case
    approved(root, worktree='repo')
    (root / 'repo').mkdir()
    seat_disposition(root)
    vcs.results['branch'] = Result(0, {'name': 'feature-A'})
    vcs.results['pushed_branches'] = Result(0, [] if mode == 'unpushed' else ['feature-A'])
    if mode in ('raised', 'claimed'):
        state._write_state(lambda data: (data['items']['A'].update(pr=REF),
            data[mode + '_prs'].append(REF)), root)
        host.results['pr'].data.update(state='closed', merged=True)
    elif mode == 'unlinked':
        state._write_state(lambda data: data['items']['A'].update(pr=REF), root)
    elif mode == 'read_error':
        vcs.results['pushed_branches'] = Result(2, reason='timeout')
    elif mode == 'error_body':
        vcs.results['pushed_branches'] = Result(0, {'error': 'unavailable'})
    elif mode == 'branch_error':
        vcs.results['branch'] = Result(2, reason='detached HEAD')
    code, reason = module('closing').check(root)
    assert code == expected, reason
    if mode in ('pushed', 'unlinked'):
        assert 'feature-A' in reason and 'A' in reason


def test_close_lists_all_offenders_despite_read_error(case, monkeypatch):
    root, _, vcs = case
    approved(root, worktree='repo')
    state._write_state(lambda data: (data['items'].update(B={}), data['approved_items'].append('B')),
                       root)
    vcs.results['branch'] = Result(2, reason='missing git')
    code, reason = module('closing').check(root)
    assert code == 2
    assert all(text in reason for text in ('A', 'B', 'missing git'))


@pytest.mark.parametrize('kind', ['parked', 'carried'])
def test_linked_verified_disposition_resolves_item_and_owner_decision(case, kind):
    root, _, _ = case
    own(root)
    approved(root, pr=REF)
    assert disposition(case, kind) == 0
    _, rows = module('pr_actions').evaluate(root)
    assert module('closing').unresolved(root, rows) == (0, '')


def test_build_park_counts_at_close(case):
    from wuwei.commands.build import _park
    root, _, _ = case
    approved(root)
    record = {'iteration': 3, 'status': 'check'}
    state._write_state(lambda data: data.update(builds={'A': record}), root)
    _park(root, 'A', dict(record), 'same fast-check failure repeated', record)
    assert state.read_state(root)['builds']['A']['status'] == 'parked'
    assert module('closing').check(root) == (0, '')


def test_merged_phase_requires_actual_merge_evidence(case):
    root, _, _ = case
    approved(root)
    for phase in ('implement', 'gate', 'raised', 'merged'):
        state.transition('A', phase, root=root)
    code, reason = module('closing').check(root)
    assert code == 1 and 'A' in reason


@pytest.mark.parametrize('kind', ['parked', 'carried'])
def test_merging_keeps_verified_owner_decision_resolved(case, kind):
    root, host, _ = case
    own(root)
    approved(root, pr=REF)
    assert disposition(case, kind) == 0
    host.results['pr'].data.update(state='closed', merged=True)
    assert module('closing').check(root) == (0, '')


def test_merged_item_can_close_after_worktree_cleanup(case):
    root, host, vcs = case
    own(root)
    approved(root, pr=REF, worktree='removed-tree')
    host.results['pr'].data.update(state='closed', merged=True)
    vcs.results['branch'] = Result(2, reason='worktree no longer exists')
    assert module('closing').check(root) == (0, '')


def records(root):
    return sorted(p.name for p in (workspace.day_dir(root) / 'decisions').glob('D-*.md'))


def last_event(root):
    return list(watch.records(workspace.day_dir(root) / 'events.jsonl'))[-1]


def _case_plan_carry_records_the_disposition(case, monkeypatch, capsys):
    root, _, _ = case
    approved(root)
    monkeypatch.chdir(root)
    assert main(['plan', 'carry', 'A']) == 0
    assert capsys.readouterr().out == 'carried A\n'
    data = state.read_state(root)
    assert data['items']['A']['disposition'] == {'kind': 'carried', 'reason': ''}
    event = last_event(root)
    assert event['kind'] == 'plan.disposed' and event['payload']['item'] == 'A'
    assert data['items']['A']['phase'] == 'planned' and records(root) == []


@pytest.mark.parametrize('reason', ['waiting on review', None])
def test_plan_park_records_and_pauses(case, monkeypatch, capsys, reason):
    root, _, _ = case
    approved(root)
    state.transition('A', 'implement', root=root)
    monkeypatch.chdir(root)
    assert main(['plan', 'park', 'A', *(['--reason', reason] if reason else [])]) == 0
    assert capsys.readouterr().out == 'parked A\n'
    item = state.read_state(root)['items']['A']
    assert item['disposition'] == {'kind': 'parked', 'reason': reason or ''}
    assert (item['phase'], item['status'], item['resume_phase']) == ('parked', 'blocked', 'implement')
    assert records(root) == []


@pytest.mark.parametrize('phase', ['parked', 'escalated', 'merged'])
def test_plan_park_keeps_paused_phase(case, monkeypatch, capsys, phase):
    root, _, _ = case
    approved(root)
    path = ['implement', 'gate', 'raised', 'merged'] if phase == 'merged' else [phase]
    for step in path:
        state.transition('A', step, root=root)
    monkeypatch.chdir(root)
    assert main(['plan', 'park', 'A']) == (1 if phase == 'merged' else 0)
    if phase == 'merged':
        assert 'already done' in capsys.readouterr().err
    assert state.read_state(root)['items']['A']['phase'] == phase


def _case_plan_carry_unknown_item(case, monkeypatch, capsys):
    root, _, _ = case
    approved(root)
    monkeypatch.chdir(root)
    assert main(['plan', 'carry', 'Z']) == 1
    err = capsys.readouterr().err
    assert 'Z' in err and 'A' in err
    assert 'disposition' not in state.read_state(root)['items']['A']


@pytest.mark.parametrize("scenario_fn", [
    _case_plan_carry_records_the_disposition,
    _case_plan_carry_unknown_item,
])
def test_plan_carry_cases_570(case, monkeypatch, capsys, scenario_fn):
    scenario_fn(case, monkeypatch, capsys)


def test_plan_park_reason_one_line(case, monkeypatch):
    root, _, _ = case
    approved(root)
    monkeypatch.chdir(root)
    assert main(['plan', 'park', 'A', '--reason', 'a\n\nOutcome: parked B   x']) == 0
    assert state.read_state(root)['items']['A']['disposition']['reason'] == 'a Outcome: parked B x'


def question(name, status='queued', phase='planned'):
    return (f'{name} is still open ({status}/{phase}): carry it to tomorrow (recommended), park '
            f'it, or keep working? Carry: bin/wuwei plan carry {name}. Park: bin/wuwei plan park '
            f'{name} --reason "<why>". Keep working: finish it, then run bin/wuwei close again.')


def _case_close_question_line(case, monkeypatch, capsys):
    root, _, _ = case
    approved(root)
    state._write_state(lambda data: data.update(planner_session_id='planner'), root)
    monkeypatch.chdir(root)
    assert main(['close']) == 1
    out = capsys.readouterr().out
    assert question('A') in out.splitlines()
    assert 'needs a park or carry decision' not in out


def _case_close_question_per_item(case, monkeypatch, capsys):
    root, _, _ = case
    approved(root)
    state._write_state(lambda data: (data['items'].update(B={}), data['approved_items'].append('B')),
                       root)
    monkeypatch.chdir(root)
    assert main(['close']) == 1
    lines = capsys.readouterr().out.splitlines()
    assert question('A') in lines and question('B') in lines


@pytest.mark.parametrize("scenario_fn", [
    _case_close_question_line,
    _case_close_question_per_item,
])
def test_close_question_cases_635(case, monkeypatch, capsys, scenario_fn):
    scenario_fn(case, monkeypatch, capsys)


def test_retro_line_names_skill(case, monkeypatch, capsys):
    root, _, _ = case
    (workspace.day_dir(root) / 'retro' / (DAY + '.md')).unlink()
    monkeypatch.chdir(root)
    assert main(['close', '--check', 'retro']) == 1
    assert capsys.readouterr().out == (f'OWED: retro/{DAY}.md does not exist; '
                                       'run /wuwei:wuwei-retro to write it\n')


def test_close_widget(case, monkeypatch, capsys):
    from wuwei import decision
    root, _, _ = case
    (workspace.day_dir(root) / 'plan.md').write_text('# Plan\n')
    approved(root)
    monkeypatch.chdir(root)
    assert main(['close', '--widget']) == 1
    widgets = json.loads(capsys.readouterr().out)
    assert len(widgets) == 1
    widget = widgets[0]
    assert widget['question'].startswith(decision.gate(root)) and 'A' in widget['question']
    assert widget['header'] == 'Open item' and widget['multiSelect'] is False
    assert [o['label'] for o in widget['options']] == ['carry', 'park', 'Skip']
    assert widget['options'][0]['description'].startswith('Recommended. ')
    assert widget['record'] == 'bin/wuwei plan <label> A'
    assert 'close_requested' not in state.read_state(root) or not state.read_state(root)['close_requested']
    events = workspace.day_dir(root) / 'events.jsonl'
    assert all(row['kind'] != 'steward.run' for row in watch.records(events))
    assert main(['plan', 'carry', 'A']) == 0
    capsys.readouterr()
    assert main(['close', '--widget']) == 0
    assert json.loads(capsys.readouterr().out) == []


def steward_runs(root):
    return [row['payload'] for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
            if row['kind'] == 'steward.run']


def _case_close_steward_waits_for_items(case, monkeypatch, capsys):
    root, _, _ = case
    approved(root)
    monkeypatch.chdir(root)
    assert main(['close']) == 1
    assert 'steward_launch' not in capsys.readouterr().out
    assert steward_runs(root) == [] and not list(root.rglob('steward-*.md'))
    assert state.read_state(root)['close_requested'] is True
    assert main(['plan', 'carry', 'A']) == 0
    capsys.readouterr()
    main(['close'])
    assert 'steward_launch' in capsys.readouterr().out
    assert [run['trigger'] for run in steward_runs(root)] == ['close']


def _case_close_steward_unmeasured(case, monkeypatch, capsys):
    root, _, _ = case
    approved(root, worktree=5)
    monkeypatch.chdir(root)
    assert main(['close']) == 2
    assert 'item A unmeasured' in capsys.readouterr().out
    assert steward_runs(root) == []


@pytest.mark.parametrize("scenario_fn", [
    _case_close_steward_waits_for_items,
    _case_close_steward_unmeasured,
])
def test_close_steward_cases_695(case, monkeypatch, capsys, scenario_fn):
    scenario_fn(case, monkeypatch, capsys)


def test_carry_closes_day(case, monkeypatch):
    root, _, _ = case
    approved(root)
    monkeypatch.chdir(root)
    assert [main(['close']), main(['plan', 'carry', 'A']), main(['close'])] == [1, 0, 0]


def merged_item(case):
    root, host, _ = case
    own(root)
    approved(root, pr=REF)
    for phase in ('implement', 'gate', 'raised', 'merged'):
        state.transition('A', phase, root=root)
    host.results['pr'].data.update(state='closed', merged=True, merged_at=DAY + 'T11:00:00Z')
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text() + '[adapters]\ntracker = "linear"\n')
    return root, module('pr_actions').evaluate(root)[1]


def test_close_waits_on_an_open_tracker_duty(case, monkeypatch, capsys):
    """#842: a due duty holds close; a done or skipped one does not; tracker none drops it."""
    from fakes.tracker import Fake
    from wuwei import tracker
    root, rows = merged_item(case)
    state._write_state(lambda data: data.update(tickets={'A': {'id': 'ENG-1', 'source': 'set'}}),
                       root)
    state.append_event('duty.due', {'item': 'A', 'duty': 'tracker.done', 'ticket': 'ENG-1',
                                    'command': 'wuwei tracker move A done'}, root)
    line = 'A: tracker.done not recorded: bin/wuwei tracker move A done'
    assert module('closing').unresolved(root, rows) == (1, line)
    config = root / '.wuwei/config.toml'
    linear = config.read_text()
    config.write_text(linear.replace('tracker = "linear"', 'tracker = "none"'))
    assert module('closing').unresolved(root, rows) == (0, '')
    config.write_text(linear)
    fake = Fake({'transition': Result(2, reason='LINEAR_API_KEY is missing')})
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, cfg: fake if kind == 'tracker' else load(kind, cfg))
    monkeypatch.chdir(root)
    assert main(['tracker', 'move', 'A', 'done']) == 2
    assert module('closing').unresolved(root, rows) == (0, '')  # skipped: the report lists it
    calls = []
    monkeypatch.setattr(tracker, 'log', lambda path: calls.append(path) or 0)
    monkeypatch.setattr(module('steward'), 'run', lambda *a, **k: None)  # metrics: own tests
    assert main(['close']) == 0
    assert calls == [root]


def test_close_never_names_a_missing_ticket(case):
    root, rows = merged_item(case)
    state._write_state(lambda data: data['items']['A'].update(tier='light'), root)
    assert module('closing').unresolved(root, rows) == (0, '')


def test_a_merge_seen_by_pr_state_records_the_done_duty_once(case, monkeypatch):
    """#842 F1: a PR merged on the host moves the item through pr_actions, which runs the done
    duty; a second run, as merge.monitor's, posts nothing again."""
    from fakes.tracker import Fake
    root, host, _ = case
    own(root)
    approved(root, pr=REF)
    for phase in ('implement', 'gate', 'raised'):
        state.transition('A', phase, root=root)
    state._write_state(lambda data: data.update(tickets={'A': {'id': 'ENG-1', 'source': 'set'}}),
                       root)
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text() + '[adapters]\ntracker = "linear"\n')
    fake = Fake({'transition': Result(0, {}), 'comment': Result(0, {'id': 'c-1'})})
    load = registry.load
    monkeypatch.setattr(registry, 'load', lambda kind, cfg: fake if kind == 'tracker' else load(kind, cfg))
    host.results['pr'].data.update(state='closed', merged=True, merged_at=DAY + 'T11:00:00Z')
    rows = module('pr_actions').evaluate(root)[1]
    assert state.read_state(root)['items']['A']['phase'] == 'merged'
    kinds = [row['kind'] for row in watch.records(workspace.day_dir(root) / 'events.jsonl')
             if row['kind'].startswith('duty.')]
    assert kinds == ['duty.due', 'duty.done']
    assert module('closing').unresolved(root, rows) == (0, '')
    module('dispatch').tracker_call('A', 'done', root)
    assert [call[0] for call in fake.calls] == ['transition', 'comment']


@pytest.mark.parametrize('output,expected,names', [
    ('', 0, []),
    ('refs/remotes/origin/feature-A\nrefs/remotes/backup/feature-A\n'
     'refs/remotes/origin/HEAD\nrefs/remotes/origin/topic/nested\n',
     0, ['feature-A', 'topic/nested']),
    ('error body\n', 2, None),
])
def test_pushed_branches(monkeypatch, tmp_path, output, expected, names):
    install_replay(monkeypatch, 'git', [{'argv': ['-C', str(tmp_path),
        'for-each-ref', '--format=%(refname)', 'refs/remotes/'], 'stdout': output}])
    result = git.pushed_branches(str(tmp_path))
    assert result.exit == expected
    assert result.data == names


@pytest.mark.parametrize('error', [FileNotFoundError(), subprocess.TimeoutExpired('git', 30)])
def test_pushed_branches_tool_failure(monkeypatch, tmp_path, error):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(git.subprocess, 'run', fail)
    result = git.pushed_branches(str(tmp_path))
    assert result.exit == 2 and 'could not run' in result.reason


@pytest.mark.parametrize('passing', [True, False])
def test_passing_close_records_the_day_without_a_digest(tmp_path, monkeypatch, passing):
    from argparse import Namespace
    from wuwei import closing, pr_actions, state, steward
    from wuwei.commands import close
    (tmp_path / '.wuwei/memory').mkdir(parents=True)
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-10-03T18:00:00+02:00')
    state._write_state(lambda data: None, tmp_path)
    monkeypatch.setattr(pr_actions, 'evaluate', lambda root: (0, []))
    monkeypatch.setattr(closing, 'unresolved', lambda *a, **k: (0, ''))
    monkeypatch.setattr(steward, 'run', lambda *a, **k: 0)
    monkeypatch.setattr(closing, 'check', lambda root: (0, '') if passing else (1, 'refused'))
    args = Namespace(check=None, widget=False)
    assert close.run(args) == (0 if passing else 1)
    assert not (tmp_path / '.wuwei/memory/digests').exists()  # #833: close writes no digest
    closed = [row for row in (tmp_path / '.wuwei/days/2026-10-03/events.jsonl').read_text().splitlines()
              if '"day.closed"' in row]
    assert len(closed) == int(passing)  # #551: next reads it to say the day is done


def test_close_check_runs_the_trace_sweep_and_no_obligations(tmp_path, monkeypatch):
    # #847: the watch is gone; close runs the trace sweep and reads duties, not obligations.
    from wuwei import closing, obligations, pr_actions, scanner, state
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-10-03T18:00:00+02:00')
    state._write_state(lambda data: None, tmp_path)
    monkeypatch.setattr(pr_actions, 'evaluate', lambda root: (0, []))
    monkeypatch.setattr(pr_actions, 'check', lambda *a, **k: (0, ''))
    monkeypatch.setattr(closing, 'unresolved', lambda *a, **k: (0, ''))
    monkeypatch.setattr(closing, 'retro', lambda root: (0, ''))
    calls = []
    monkeypatch.setattr(scanner, 'trace_sweep', lambda root, config: calls.append(root) or {})
    assert not hasattr(obligations, 'evaluate') and not hasattr(obligations, 'sweep')
    assert closing.check(tmp_path) == (0, '')
    assert calls == [tmp_path]
