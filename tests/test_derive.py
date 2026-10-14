"""The derived next's world readers and duty records (#844)."""

import json

import pytest

from wuwei import derive, state, workspace
from wuwei.registry import Result

SHA, OTHER = 'a' * 40, 'b' * 40


def worktree(tmp_path, head):
    """A linked worktree: its .git pointer, git's per-worktree registry and the common dir."""
    common = tmp_path / 'repo/.git'
    registry = common / 'worktrees/item'
    registry.mkdir(parents=True)
    (registry / 'HEAD').write_text(head + '\n')
    (registry / 'commondir').write_text('../..\n')
    tree = tmp_path / 'item'
    tree.mkdir()
    (tree / '.git').write_text(f'gitdir: {registry}\n')
    return tree, common


def test_head_reads_a_detached_head(tmp_path):
    tree, _ = worktree(tmp_path, SHA)
    assert derive.head(tree) == SHA


def _case_head_resolves_a_loose_ref(tmp_path):
    tree, common = worktree(tmp_path, 'ref: refs/heads/item')
    (common / 'refs/heads').mkdir(parents=True)
    (common / 'refs/heads/item').write_text(SHA + '\n')
    assert derive.head(tree) == SHA


def _case_head_resolves_a_packed_ref(tmp_path):
    tree, common = worktree(tmp_path, 'ref: refs/heads/item')
    (common / 'packed-refs').write_text(f'# pack-refs with: peeled\n{OTHER} refs/heads/main\n{SHA} refs/heads/item\n')
    assert derive.head(tree) == SHA


@pytest.mark.parametrize("scenario_fn", [
    _case_head_resolves_a_loose_ref,
    _case_head_resolves_a_packed_ref,
])
def test_head_resolves_cases_31(tmp_path, scenario_fn):
    scenario_fn(tmp_path)


def test_head_of_a_gone_worktree_is_none(tmp_path):
    tree, common = worktree(tmp_path, SHA)
    assert derive.head(tmp_path / 'missing') is None
    (common / 'worktrees/item/HEAD').unlink()
    assert derive.head(tree) is None


def _case_existing_start_detects_a_recorded_external_worktree(root):
    state._write_state(lambda data: None, root)
    repo = root / 'project'
    (repo / '.git').mkdir(parents=True)
    (repo / '.git/HEAD').write_text(SHA + '\n')
    tree = root.parent / (root.name + '-external')
    (tree / '.git').mkdir(parents=True)
    (tree / '.git/HEAD').write_text(OTHER + '\n')
    found = {'pulls': {}, 'repos': {'example/project': {'at': '2026-10-11T10:00:00+00:00'}}}
    data = {'seats': {}, 'builds': {}}
    row = {'worktree': str(tree)}
    state.append_event('worktree.created', {'item': 'ITEM', 'worktree': str(tree),
                                            'start': SHA}, root)

    evidence = derive.existing_start(root, workspace.load_config(root), data, 'ITEM', row, found)
    assert evidence['state'] == 'blocked' and str(tree) in evidence['why']


def _case_existing_start_skips_a_pr_row_after_its_repository_read_failed(root):
    state._write_state(lambda data: None, root)
    found = {'pulls': {'example/project#7': {'state': 'open', 'branch': 'item'}},
             'repos': {'example/project': {'failed': 'host unavailable'}}}

    evidence = derive.existing_start(root, workspace.load_config(root), {'seats': {}, 'builds': {}},
                                     'ITEM', {}, found)
    assert evidence is None


def _case_existing_start_matches_branch_suffix_and_registered_worktree(root):
    state._write_state(lambda data: None, root)
    repo = root / 'project'
    common = repo / '.git'
    registry = common / 'worktrees' / 'index-timeout-analyzer'
    registry.mkdir(parents=True)
    tree = repo / '.claude/worktrees/index-timeout-analyzer'
    tree.mkdir(parents=True)
    (tree / '.git').write_text(f'gitdir: {registry}\n')
    (registry / 'gitdir').write_text(str(tree / '.git') + '\n')
    (registry / 'HEAD').write_text(OTHER + '\n')
    state.append_event('worktree.created', {'item': 'INDEX-TIMEOUT-ANALYZER',
                                            'worktree': str(tree), 'start': SHA}, root)
    config = workspace.load_config(root)
    found = {'pulls': {'example/project#3174': {'state': 'open',
              'branch': 'leone/index-timeout-analyzer', 'head_repo': 'example/project'}}, 'repos': {}}
    data = {'seats': {}, 'builds': {}}
    evidence = derive.existing_start(root, config, data, 'INDEX-TIMEOUT-ANALYZER', {}, found)
    assert evidence['state'] == 'review' and '3174' in evidence['why']
    assert evidence['worktree'] == str(tree)
    assert derive.existing_start(root, config, data, 'INDEX-TIMEOUT-ANALYZER', {},
                                 {'pulls': {}, 'repos': {}})['state'] == 'blocked'
    assert derive.existing_start(root, config, data, 'INDEX-TIMEOUT-ANALYZER-2', {},
                                 {'pulls': {}, 'repos': {}}) is None


def _case_existing_start_skips_commit_for_own_brief_or_build(root):
    state._write_state(lambda data: None, root)
    repo = root / 'project'
    (repo / '.git').mkdir(parents=True)
    tree = root / 'worktrees/ITEM'
    (tree / '.git').mkdir(parents=True)
    (tree / '.git/HEAD').write_text(OTHER + '\n')
    state.append_event('worktree.created', {'item': 'ITEM', 'worktree': str(tree),
                                            'start': SHA}, root)
    found = {'pulls': {}, 'repos': {}}
    for data in ({'seats': {}, 'builds': {'ITEM': {'status': 'running'}}},
                 {'seats': {}, 'builds': {}}):
        if not data['builds']:
            state.append_event('brief written', {'item': 'ITEM', 'role': 'builder'}, root)
        assert derive.existing_start(root, workspace.load_config(root), data, 'ITEM',
                                     {'worktree': str(tree)}, found) is None


@pytest.mark.parametrize('scenario', [
    'unresolved_repo', 'explicit_item', 'bad_proposal', 'spec_and_reviewer',
])
def test_existing_start_tracks_only_matching_adhoc_work(root, monkeypatch, scenario):
    state._write_state(lambda data: None, root)
    config = workspace.load_config(root)
    found = {'pulls': {}, 'repos': {}}
    if scenario == 'unresolved_repo':
        config['repos'] = [{'name': 'one', 'path': 'one'}, {'name': 'two', 'path': 'two'}]
        data = {'seats': {'adhoc-1': {'role': 'adhoc', 'item': 'ITEM', 'label': 'builder'}}, 'builds': {}}
    elif scenario == 'explicit_item':
        state.append_event('seat adhoc', {'role': 'builder', 'item': 'ITEM',
                                          'prompt': 'Item: ITEM.'}, root)
        data = {'seats': {}, 'builds': {}}
    elif scenario == 'bad_proposal':
        from wuwei import dispatch
        monkeypatch.setattr(dispatch, 'candidate',
                            lambda *args: (_ for _ in ()).throw(AttributeError('bad')))
        data = {'seats': {'adhoc-1': {'role': 'adhoc', 'label': 'builder', 'item': 'ITEM'}}, 'builds': {}}
    else:
        data = {'seats': {'adhoc-1': {'role': 'adhoc', 'label': 'spec', 'item': 'ITEM'}}, 'builds': {}}
    assert derive.existing_start(root, config, data, 'ITEM', {}, found)['state'] == 'wait'
    if scenario in ('unresolved_repo', 'explicit_item'):
        assert derive.existing_start(root, config, data, 'ITEM-2', {}, found) is None
    elif scenario == 'bad_proposal':
        monkeypatch.setattr(dispatch, 'candidate', lambda *args: [1])
        assert derive.existing_start(root, config, data, 'ITEM', {}, found)['state'] == 'wait'
    else:
        data['seats']['adhoc-1']['label'] = 'reviewer'
        assert derive.existing_start(root, config, data, 'ITEM', {}, found) is None
        state.append_event('seat adhoc', {'role': 'spec', 'prompt': 'Item ITEM.'}, root)
        assert derive.existing_start(root, config, {'seats': {}, 'builds': {}},
                                     'ITEM', {}, found)['state'] == 'wait'


def _case_carried_worktree_uses_its_creation_reflog_before_origin(root):
    state._write_state(lambda data: None, root)
    tree, common = worktree(root, 'ref: refs/heads/item')
    (common / 'refs/heads').mkdir(parents=True)
    (common / 'refs/heads/item').write_text(SHA + '\n')
    (common / 'refs/remotes/origin').mkdir(parents=True)
    (common / 'refs/remotes/origin/main').write_text(OTHER + '\n')
    logs = common / 'worktrees/item/logs'
    logs.mkdir()
    (logs / 'HEAD').write_text(f"{'0' * 40} {SHA} Builder <b@example.test> 1 +0000\tcheckout\n")
    (common / 'worktrees/item/gitdir').write_text(str(tree / '.git') + '\n')
    config = workspace.load_config(root)
    config['repos'][0]['path'] = 'repo'
    assert derive.existing_start(root, config, {'seats': {}, 'builds': {}}, 'item', {},
                                 {'pulls': {}, 'repos': {}}) is None


def test_existing_start_expands_home_in_repo_path(root, monkeypatch):
    state._write_state(lambda data: None, root)
    home = root / 'home'
    home.mkdir()
    monkeypatch.setenv('HOME', str(home))
    tree, common = worktree(home, OTHER)
    (common / 'worktrees/item/gitdir').write_text(str(tree / '.git') + '\n')
    (common / 'refs/remotes/origin').mkdir(parents=True)
    (common / 'refs/remotes/origin/main').write_text(SHA + '\n')
    config = workspace.load_config(root)
    config['repos'][0]['path'] = '~/repo'
    found = derive.existing_start(root, config, {'seats': {}, 'builds': {}}, 'item', {},
                                  {'pulls': {}, 'repos': {}})
    assert found['state'] == 'blocked' and found['worktree'] == str(tree)


def test_offers_reads_events_once_for_multiple_planned_items(root, monkeypatch):
    from wuwei import brief
    state._write_state(lambda data: data.update(
        approved_items=['A', 'B'], gate_approved=True, cap=2,
        items={'A': {'phase': 'planned', 'status': 'queued'},
               'B': {'phase': 'planned', 'status': 'queued'}}), root)
    calls = []
    original = brief.events
    def counted(value):
        calls.append(value)
        return original(value)
    monkeypatch.setattr(brief, 'events', counted)
    derive.offers(state.read_state(root), root, workspace.load_config(root))
    assert len(calls) == 1


def test_planned_items_do_not_schedule_periodic_pr_listing(root):
    state._write_state(lambda data: None, root)
    data = {'approved_items': ['ITEM'], 'items': {'ITEM': {'phase': 'planned'}}}
    assert derive.stale(root, workspace.load_config(root), data) == []


def test_a_pass_counts_at_head_or_through_a_recorded_fix_round():
    row = {'fix_heads': [[SHA, OTHER]]}
    assert derive.at_head({}, SHA[:12], SHA)
    assert not derive.at_head({}, SHA[:12], OTHER)  # #669: moved some other way
    assert derive.at_head(row, SHA[:12], OTHER)  # design 5.3: the fix round made it
    assert derive.at_head({}, SHA[:12], None)  # an unread HEAD judges nothing


@pytest.fixture
def root(tmp_path, monkeypatch):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "example/project"\npath = "project"\ndefault_branch = "main"\n'
        '[adapters]\ncode_host = "github"\n[shepherd]\nreview_channel = "C0REVIEW"\n'
        '[outbound]\nowner_channel = "dm"\n[duties]\non = ["ping", "summary"]\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', '2026-10-11T10:00:00+00:00')
    return tmp_path


class Host:
    def __init__(self, result):
        self.result = result

    def pulls(self, repo, root=None):
        return self.result


def test_listing_absent_is_empty_and_stale_once_an_item_has_a_pr(root):
    data = {'items': {'A': {'pr': 'example/project#1'}}}
    assert derive.listing(workspace.day_dir(root)) == {'fetched_at': None, 'pulls': {}, 'repos': {}}
    assert derive.stale(root, workspace.load_config(root), data)
    assert not derive.stale(root, workspace.load_config(root), {'items': {'A': {}}})


def test_refresh_writes_the_listing_and_a_failed_call_keeps_it(root, monkeypatch):
    from wuwei import registry
    config = workspace.load_config(root)
    row = {'number': 1, 'state': 'open', 'head': SHA, 'checks': 'green', 'labels': []}
    monkeypatch.setattr(registry, 'load', lambda kind, config: Host(Result(0, [row])))
    assert derive.refresh(root, config) is None
    pulls = derive.listing(workspace.day_dir(root))['pulls']
    assert pulls['example/project#1']['checks'] == 'green'
    monkeypatch.setattr(registry, 'load', lambda kind, config: Host(Result(2, None, 'gh exited 1')))
    assert derive.refresh(root, config) == 'example/project: gh exited 1'
    assert derive.listing(workspace.day_dir(root))['pulls'] == pulls
    assert not derive.stale(root, config, {'items': {'A': {'pr': 'example/project#1'}}})


REPOS = ('example/one', 'example/two', 'example/three')


class Counted:
    """#907: a code host whose listing of example/two fails (#900: an HTTP 502); counts calls."""
    def __init__(self):
        self.calls = []

    def pulls(self, repo, root=None):
        self.calls.append(repo)
        if repo == 'example/two':
            return Result(2, None, 'gh: HTTP 502')
        return Result(0, [{'number': 1, 'state': 'open', 'head': SHA, 'checks': 'green', 'labels': []}])


def three(root, monkeypatch):
    from wuwei import registry
    (root / '.wuwei/config.toml').write_text(''.join(
        f'[[repos]]\nname = "{name}"\npath = "{name[8:]}"\ndefault_branch = "main"\n' for name in REPOS))
    host = Counted()
    monkeypatch.setattr(registry, 'load', lambda kind, config: host)
    return workspace.load_config(root), host


def test_each_repository_refreshes_alone_and_a_failed_one_keeps_its_retry_time(root, monkeypatch):
    # #907: a failed repository no longer makes the whole listing stale: the others stay read,
    # nothing is called again inside pr.poll_seconds, and the failed one retries after it.
    config, host = three(root, monkeypatch)
    data = {'items': {'A': {'pr': 'example/one#1'}}}
    assert derive.stale(root, config, data)
    assert derive.refresh(root, config, derive.stale(root, config, data)) == 'example/two: gh: HTTP 502'
    assert host.calls == list(REPOS)
    found = derive.listing(workspace.day_dir(root))
    assert sorted(found['pulls']) == ['example/one#1', 'example/three#1']
    assert found['repos']['example/two'] == {'at': '2026-10-11T10:00:00+00:00', 'failed': 'gh: HTTP 502'}
    assert not derive.stale(root, config, data)  # inside pr.poll_seconds: no call at all
    monkeypatch.setenv('WUWEI_NOW', '2026-10-11T10:02:00+00:00')
    assert derive.stale(root, config, data) == list(REPOS)
    host.calls.clear()
    assert derive.refresh(root, config, derive.stale(root, config, data))
    assert host.calls == list(REPOS)
    config['repos'] = [repo for repo in config['repos'] if repo['name'] != 'example/three']
    assert derive.refresh(root, config, []) is None  # a repository out of config leaves the listing
    found = derive.listing(workspace.day_dir(root))
    assert sorted(found['pulls']) == ['example/one#1'] and sorted(found['repos']) == ['example/one', 'example/two']


def test_a_failed_repository_leaves_its_pr_rows_unmeasured_and_the_others_usable(root, monkeypatch):
    # #900: a stale listing never decides: the PR of the failed repository gets no merge, gate or
    # fix step, and its row names the repository and when next reads it again.
    config, host = three(root, monkeypatch)
    state._write_state(lambda data: data.update(
        gate_approved=True, approved_items=['A', 'B'], raised_prs=['example/one#1', 'example/two#1'],
        items={'A': {'phase': 'raised', 'status': 'running', 'pr': 'example/one#1'},
               'B': {'phase': 'raised', 'status': 'running', 'pr': 'example/two#1'}}),
        root, kind='plan.approved')
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({'fetched_at': None, 'pulls': [
        {'ref': 'example/two#1', 'state': 'open', 'checks': 'red', 'labels': []}]}))
    derive.refresh(root, config)
    found = derive.offers(state.read_state(root), root, config)
    assert [(row['kind'], row['item']) for row in found['launches']] == [('merge', 'A')]
    assert found['decision'] is None
    row, = [row for row in found['rows'] if row['item'] == 'B']
    assert row['state'] == 'unmeasured'
    assert 'example/two' in row['why'] and 'gh: HTTP 502' in row['why'] and '2026-10-11T10:02:00+00:00' in row['why']


@pytest.mark.parametrize('viewer,activity', [
    ('me', '2026-10-11T09:30:00Z'),  # a raised PR: the author is the viewer, left out
    ('wuwei-owner', '2026-10-11T09:00:00Z')])  # D2: a claimed PR: the teammate author's follow-up counts
def test_the_github_listing_maps_one_call(monkeypatch, viewer, activity):
    import importlib
    github = importlib.import_module('adapters.code_host.github')
    node = {'number': 7, 'state': 'OPEN', 'isDraft': False, 'headRefOid': SHA, 'headRefName': 'review-7',
            'headRepository': {'nameWithOwner': 'example/project'}, 'mergeable': 'CONFLICTING',
            'author': {'login': 'me'}, 'labels': {'nodes': [{'name': 'owner-merge'}]},
            'commits': {'nodes': [{'commit': {'statusCheckRollup': {'state': 'FAILURE'}}}]},
            'latestReviews': {'nodes': [{'author': {'login': 'me'}, 'submittedAt': '2026-10-11T09:00:00Z'}]},
            'comments': {'nodes': [{'author': {'login': 'you'}, 'createdAt': '2026-10-11T08:00:00Z'},
                                   {'author': {'login': 'wuwei-owner'}, 'createdAt': '2026-10-11T09:30:00Z'}]}}
    calls = []

    def run(args, payload=None, **kwargs):  # #906 F3: the viewer's own replies are not activity
        calls.append(args)
        return {'data': {'viewer': {'login': viewer}, 'repository': {'pullRequests': {'nodes': [node]}}}}
    monkeypatch.setattr(github, '_run', run)
    result = github.pulls('example/project')
    assert len(calls) == 1 and result.exit == 0
    assert result.data == [{'number': 7, 'state': 'open', 'head': SHA, 'branch': 'review-7',
                            'head_repo': 'example/project', 'draft': False, 'checks': 'red',
                            'mergeable': 'conflicting', 'labels': ['owner-merge'],
                            'activity_at': activity}]


def raised(root):
    state._write_state(lambda data: data.update(
        gate_approved=True, approved_items=['A'], raised_prs=['example/project#1'],
        items={'A': {'phase': 'raised', 'status': 'running', 'pr': 'example/project#1'}}),
        root, kind='plan.approved')


def test_the_duty_command_records_a_due_duty_and_refuses_any_other(root, capsys):
    from wuwei.__main__ import main
    raised(root)
    assert [row['duty'] for row in derive.duties(root, workspace.load_config(root))] == ['ping']
    assert main(['duty', 'A', 'shepherd', '--evidence', 'x']) == 1
    assert main(['duty', 'B', 'ping', '--evidence', 'x']) == 1
    assert main(['duty', 'A', 'ping', '--evidence', 'https://chat.example/p1']) == 0
    assert derive.duties(root, workspace.load_config(root)) == []
    (workspace.day_dir(root) / 'report.md').write_text('# Report\n')
    assert [(row['item'], row['duty']) for row in derive.duties(root, workspace.load_config(root))] == [
        ('day', 'summary')]


def test_completed_review_item_has_no_pr_duties(root):
    raised(root)
    state._write_state(lambda data: data['items']['A'].update(kind='review', status='done'), root)
    assert derive.duties(root, workspace.load_config(root)) == []


def test_a_review_post_records_the_ping(root):
    raised(root)
    state.append_event('pr.review_posted', {'pr': 'example/project#1'}, root)
    assert derive.duties(root, workspace.load_config(root)) == []


@pytest.mark.parametrize('pr_state', ['open', 'closed', 'merged'])
def test_ping_duty_ends_with_pr(root, pr_state):
    raised(root)
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({
        'fetched_at': None, 'pulls': [{'ref': 'example/project#1', 'state': pr_state}]}))
    ping = [row for row in derive.duties(root, workspace.load_config(root))
            if row['duty'] == 'ping']
    assert len(ping) == (1 if pr_state == 'open' else 0)


def test_carried_ping_ends_when_current_listing_closes_pr(root, monkeypatch):
    raised(root)
    monkeypatch.setenv('WUWEI_NOW', '2026-10-12T10:00:00+00:00')
    today = workspace.day_dir(root)
    today.mkdir(parents=True)
    (today / 'prs.json').write_text(json.dumps({'fetched_at': None, 'pulls': [
        {'ref': 'example/project#1', 'state': 'closed'}]}))
    assert not [row for row in derive.duties(root, workspace.load_config(root))
                if row['duty'] == 'ping']


def test_offers_write_nothing(root):
    raised(root)
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({'fetched_at': None, 'pulls': [
        {'ref': 'example/project#1', 'state': 'open', 'checks': 'green', 'labels': []}]}))
    before = sorted((path.name, path.stat().st_size) for path in workspace.day_dir(root).iterdir())
    found = derive.offers(state.read_state(root), root, workspace.load_config(root))
    assert [(row['kind'], row['item']) for row in found['launches']] == [('merge', 'A')]
    assert sorted((path.name, path.stat().st_size) for path in workspace.day_dir(root).iterdir()) == before


def test_the_listing_is_stale_after_wuwei_raises_or_merges(root):
    config = workspace.load_config(root)
    data = {'items': {'A': {'pr': 'example/project#1'}}}
    (workspace.day_dir(root)).mkdir(parents=True)
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({
        'fetched_at': '2026-10-11T10:00:00+00:00', 'pulls': []}))
    assert not derive.stale(root, config, data)
    state.append_event('merge.completed', {'pr': 'example/project#1'}, root)
    assert derive.stale(root, config, data)


def test_shepherd_is_due_on_activity_newer_than_its_record_across_offsets(root, monkeypatch):
    # G2: times compare as instants, east and west of UTC; G5: newer activity makes it due.
    (root / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "example/project"\npath = "project"\ndefault_branch = "main"\n'
        '[adapters]\ncode_host = "github"\n')
    raised(root)
    monkeypatch.setenv('WUWEI_NOW', '2026-10-11T11:00:00+02:00')  # 09:00 UTC
    state.append_event('duty.done', {'item': 'A', 'duty': 'shepherd'}, root)
    for activity, due in (('2026-10-11T09:30:00Z', True), ('2026-10-11T08:30:00Z', False),
                          ('2026-10-11T04:30:00-05:00', True)):
        (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({'fetched_at': None, 'pulls': [
            {'ref': 'example/project#1', 'state': 'open', 'checks': 'pending', 'activity_at': activity}]}))
        duties = [row['duty'] for row in derive.duties(root, workspace.load_config(root))]
        assert ('shepherd' in duties) is due, activity


def test_a_pr_without_ci_is_none_and_merges_like_green(root, monkeypatch):
    # G3: a null checks rollup is 'none', never pending forever.
    import importlib
    github = importlib.import_module('adapters.code_host.github')
    node = {'number': 7, 'state': 'OPEN', 'isDraft': False, 'headRefOid': SHA, 'mergeable': 'MERGEABLE',
            'author': {'login': 'me'}, 'labels': {'nodes': []},
            'commits': {'nodes': [{'commit': {'statusCheckRollup': None}}]},
            'latestReviews': {'nodes': []}, 'comments': {'nodes': []}}
    monkeypatch.setattr(github, '_run', lambda *args, **kwargs: {'data': {'repository': {'pullRequests': {
        'nodes': [node]}}}})
    assert github.pulls('example/project').data[0]['checks'] == 'none'
    raised(root)
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({'fetched_at': None, 'pulls': [
        {'ref': 'example/project#1', 'state': 'open', 'checks': 'none', 'labels': []}]}))
    found = derive.offers(state.read_state(root), root, workspace.load_config(root))
    assert [(row['kind'], row['item']) for row in found['launches']] == [('merge', 'A')]


def test_a_skipped_duty_is_recorded_listed_and_clears_the_duty(root, capsys):
    # G5, G6: wuwei duty --skipped records duty.skipped; the report lists it.
    from wuwei import tracker, watch
    from wuwei.__main__ import main
    raised(root)
    assert main(['duty', 'A', 'ping', '--skipped', 'the review channel is archived']) == 0
    assert derive.duties(root, workspace.load_config(root)) == []
    rows = watch.records(workspace.day_dir(root) / 'events.jsonl')
    assert [(row['item'], row['duty']) for row in tracker.skipped_duties(rows)] == [('A', 'ping')]


def test_duties_follow_the_configured_channels(root):
    # G7: a duty is due only while its channel is configured; duties.on only turns one off.
    path = root / '.wuwei/config.toml'
    base = '[[repos]]\nname = "example/project"\npath = "project"\ndefault_branch = "main"\n'
    path.write_text(base)
    raised(root)
    (workspace.day_dir(root) / 'report.md').write_text('# Report\n')
    assert derive.duties(root, workspace.load_config(root)) == []  # no review channel, report in session
    path.write_text(base + '[adapters]\ncode_host = "none"\n[shepherd]\nreview_channel = "C0REVIEW"\n'
                    '[outbound]\nowner_channel = "dm"\n')
    assert [row['duty'] for row in derive.duties(root, workspace.load_config(root))] == ['ping', 'summary']
    path.write_text(path.read_text() + '[duties]\non = ["summary"]\n')
    assert [row['duty'] for row in derive.duties(root, workspace.load_config(root))] == ['summary']


def claimed(root, build=None):
    """#879: a claimed PR whose item has a worktree, and its fix-round build when given."""
    state._write_state(lambda data: data.update(
        gate_approved=True, approved_items=['A'], claimed_prs=['example/project#1'],
        items={'A': {'phase': 'raised', 'status': 'running', 'pr': 'example/project#1',
                     'worktree': 'worktrees/A'}}, **({'builds': {'A': build}} if build else {})),
        root, kind='plan.approved')


def offered(root, **pull):
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({'fetched_at': None, 'pulls': [
        {'ref': 'example/project#1', 'state': 'open', 'checks': 'pending', 'labels': [], **pull}]}))
    data = state.read_state(root)
    launches = derive.offers(data, root, workspace.load_config(root))['launches']
    return [(row['kind'], row['command'], derive.seated(data, row)) for row in launches]


ACT = 'wuwei pr act example/project#1'


@pytest.mark.parametrize('pull,build,expected', [
    ({'mergeable': 'conflicting'}, None, [('fix', ACT, True)]),
    ({'checks': 'red'}, None, [('fix', ACT, True)]),
    ({'checks': 'red'}, {'status': 'done'}, [('fix', ACT, True)]),
])
def test_a_claimed_pr_with_a_worktree_is_a_fix_round_step(root, pull, build, expected):
    # #879: the launch set resolves the step into the builder (a round opens in implement).
    claimed(root, build)
    assert offered(root, **pull) == expected


SHEPHERDED = ('[[repos]]\nname = "example/project"\npath = "project"\ndefault_branch = "main"\n'
              '[adapters]\ncode_host = "github"\n')


@pytest.mark.parametrize('setup', [raised, claimed])
def test_due_review_activity_is_one_shepherd_launch_per_activity_revision(root, setup):
    # #906: the duty is a seated launch (brief, then seat), never a record the planner writes;
    # once the revision's seat is registered the PR waits, and newer activity launches again.
    (root / '.wuwei/config.toml').write_text(SHEPHERDED)
    setup(root)
    first, later = '2026-10-11T09:30:00Z', '2026-10-11T04:45:00-05:00'
    pull = {'activity_at': first, 'head': SHA}
    assert offered(root, **pull) == [('shepherd', ACT, True)]
    name = derive.shepherd_seat('A', pull)
    assert name == f'shepherd-A-20261011093000-{SHA[:7]}' and derive.revision(None) is None

    def seat(status):
        state._write_state(lambda data: data.setdefault('seats', {}).update({name: {
            'item': 'A', 'role': 'shepherd', 'status': status}}), root)
    seat('running')
    assert offered(root, **pull) == []
    assert offered(root, activity_at=later, head=SHA) == []  # F3: never a second seat beside a running one
    seat('stopped')
    assert offered(root, **pull) == []  # this revision ran
    assert offered(root, activity_at=first, head=OTHER) == [('shepherd', ACT, True)]  # F1: a pushed fix round
    assert offered(root, activity_at=later, head=SHA) == [('shepherd', ACT, True)]  # 09:45 UTC: a new one
    state.append_event('duty.done', {'item': 'A', 'duty': 'shepherd', 'as_of': '2026-10-11T09:50:00+00:00'}, root)
    assert offered(root, activity_at=later, head=SHA) == []  # answered: the PR waits on people


def test_a_shepherd_record_counts_from_the_read_it_rests_on(root):
    # #906: duty.done carries as_of, the time its PR read started; activity after it is due again
    # even though the record was written later.
    (root / '.wuwei/config.toml').write_text(SHEPHERDED)
    raised(root)
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({'fetched_at': None, 'pulls': [
        {'ref': 'example/project#1', 'state': 'open', 'checks': 'pending', 'activity_at': '2026-10-11T09:30:00Z'}]}))
    state.append_event('duty.done', {'item': 'A', 'duty': 'shepherd', 'as_of': '2026-10-11T09:00:00+00:00'}, root)
    [row] = [row for row in derive.duties(root, workspace.load_config(root)) if row['duty'] == 'shepherd']
    assert row['record'] == 'wuwei pr act example/project#1'


def test_the_shepherd_duty_takes_no_evidence_text(root, capsys):
    # #906: completion comes from the obligation ledger (pr act), never from a link; a skip stays.
    from wuwei.__main__ import main
    (root / '.wuwei/config.toml').write_text(SHEPHERDED)
    raised(root)
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({'fetched_at': None, 'pulls': [
        {'ref': 'example/project#1', 'state': 'open', 'checks': 'pending', 'activity_at': '2026-10-11T09:30:00Z'}]}))
    capsys.readouterr()
    assert main(['duty', 'A', 'shepherd', '--evidence', 'https://example.test/x']) == 1
    assert 'bin/wuwei pr act example/project#1' in capsys.readouterr().err
    assert 'shepherd' in [row['duty'] for row in derive.duties(root, workspace.load_config(root))]
    assert main(['duty', 'A', 'shepherd', '--skipped', 'the reviewer left the company']) == 0
    assert 'shepherd' not in [row['duty'] for row in derive.duties(root, workspace.load_config(root))]


def test_a_raised_or_worktreeless_claimed_pr_keeps_its_pr_act_run(root):
    raised(root)
    assert offered(root, mergeable='conflicting') == [('pr', ACT, False)]
    claimed(root)
    state._write_state(lambda data: data['items']['A'].pop('worktree'), root)
    assert offered(root, mergeable='conflicting') == [('pr', ACT, False)]


def test_overlapping_refreshes_never_restore_a_failed_repositorys_old_rows(root, monkeypatch):
    # #907 review F2: next B reads example/one while next A reads example/two, fails and writes.
    # B merges into the listing as it is under the lock, so example/two stays failed.
    config, host = three(root, monkeypatch)
    derive.refresh(root, config, ['example/one', 'example/three'])
    reads = host.pulls

    def pulls(repo, root=None):
        if repo == 'example/one' and len(host.calls) == 2:
            derive.refresh(root, config, ['example/two'])  # A runs while B is on the network
        return reads(repo, root=root)
    monkeypatch.setattr(host, 'pulls', pulls)
    assert derive.refresh(root, config, ['example/one']) is None
    found = derive.listing(workspace.day_dir(root))
    assert found['repos']['example/two']['failed'] == 'gh: HTTP 502'
    assert sorted(found['pulls']) == ['example/one#1', 'example/three#1']


def test_a_released_owner_merge_is_not_a_hold(root):
    # #904: plan set owner_merge=false stores a record; only a true value holds the merge.
    raised(root)
    (workspace.day_dir(root) / 'prs.json').write_text(json.dumps({'fetched_at': None, 'pulls': [
        {'ref': 'example/project#1', 'state': 'open', 'checks': 'green', 'labels': []}]}))
    for value, launches, decision in ((False, [('merge', 'A')], None), (True, [], 'wuwei merge example/project#1')):
        state._write_state(lambda data: data['items']['A'].update(owner_merge={
            'value': value, 'by': 'owner', 'at': '2026-10-11T10:00:00+00:00'}), root)
        found = derive.offers(state.read_state(root), root, workspace.load_config(root))
        assert [(row['kind'], row['item']) for row in found['launches']] == launches
        assert (found['decision'] or {}).get('command') == decision


def test_red_checks_at_the_cap_after_the_owners_resume_are_a_fix_round(root):
    # #904: the owner's resume grants one round past the cap here too, until a round opens.
    claimed(root, {'status': 'done', 'fix_rounds': 2})
    assert offered(root, checks='red') == []
    state.append_event('plan.disposed', {'item': 'A', 'outcome': 'parked'}, root)
    state.append_event('plan.resumed', {'item': 'A'}, root)
    assert offered(root, checks='red') == [('fix', ACT, True)]
    state.append_event('build.fix_opened', {'item': 'A'}, root)
    assert offered(root, checks='red') == []


@pytest.mark.parametrize("scenario_fn", [
    _case_existing_start_detects_a_recorded_external_worktree,
    _case_existing_start_skips_a_pr_row_after_its_repository_read_failed,
    _case_existing_start_matches_branch_suffix_and_registered_worktree,
    _case_existing_start_skips_commit_for_own_brief_or_build,
    _case_carried_worktree_uses_its_creation_reflog_before_origin,
])
def test_existing_start_evidence_cases(root, scenario_fn):
    scenario_fn(root)
