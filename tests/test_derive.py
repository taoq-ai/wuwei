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


def test_head_resolves_a_loose_ref(tmp_path):
    tree, common = worktree(tmp_path, 'ref: refs/heads/item')
    (common / 'refs/heads').mkdir(parents=True)
    (common / 'refs/heads/item').write_text(SHA + '\n')
    assert derive.head(tree) == SHA


def test_head_resolves_a_packed_ref(tmp_path):
    tree, common = worktree(tmp_path, 'ref: refs/heads/item')
    (common / 'packed-refs').write_text(f'# pack-refs with: peeled\n{OTHER} refs/heads/main\n{SHA} refs/heads/item\n')
    assert derive.head(tree) == SHA


def test_head_of_a_gone_worktree_is_none(tmp_path):
    tree, common = worktree(tmp_path, SHA)
    assert derive.head(tmp_path / 'missing') is None
    (common / 'worktrees/item/HEAD').unlink()
    assert derive.head(tree) is None


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
    assert derive.listing(workspace.day_dir(root)) == {'fetched_at': None, 'pulls': {}}
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
    assert derive.refresh(root, config) == 'gh exited 1'
    assert derive.listing(workspace.day_dir(root))['pulls'] == pulls
    assert not derive.stale(root, config, {'items': {'A': {'pr': 'example/project#1'}}})


def test_the_github_listing_maps_one_call(monkeypatch):
    import importlib
    github = importlib.import_module('adapters.code_host.github')
    node = {'number': 7, 'state': 'OPEN', 'isDraft': False, 'headRefOid': SHA, 'mergeable': 'CONFLICTING',
            'author': {'login': 'me'}, 'labels': {'nodes': [{'name': 'owner-merge'}]},
            'commits': {'nodes': [{'commit': {'statusCheckRollup': {'state': 'FAILURE'}}}]},
            'latestReviews': {'nodes': [{'author': {'login': 'me'}, 'submittedAt': '2026-10-11T09:00:00Z'}]},
            'comments': {'nodes': [{'author': {'login': 'you'}, 'createdAt': '2026-10-11T08:00:00Z'}]}}
    calls = []

    def run(args, payload=None, **kwargs):
        calls.append(args)
        return {'data': {'repository': {'pullRequests': {'nodes': [node]}}}}
    monkeypatch.setattr(github, '_run', run)
    result = github.pulls('example/project')
    assert len(calls) == 1 and result.exit == 0
    assert result.data == [{'number': 7, 'state': 'open', 'head': SHA, 'draft': False, 'checks': 'red',
                            'mergeable': 'conflicting', 'labels': ['owner-merge'],
                            'activity_at': '2026-10-11T08:00:00Z'}]


def raised(root):
    state._write_state(lambda data: data.update(
        gate_approved=True, approved_items=['A'], raised_prs=['example/project#1'],
        items={'A': {'phase': 'raised', 'status': 'running', 'pr': 'example/project#1'}}),
        root, reserved=False, kind='plan.approved')


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


def test_a_review_post_records_the_ping(root):
    raised(root)
    state.append_event('pr.review_posted', {'pr': 'example/project#1'}, root)
    assert derive.duties(root, workspace.load_config(root)) == []


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
