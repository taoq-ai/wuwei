"""Outcome measurements use local evidence and never disclose transcript prose."""

import json
from pathlib import Path

import pytest

from wuwei import metrics, state, workspace


@pytest.fixture
def root(tmp_path, monkeypatch):
    root = tmp_path / 'workspace'
    (root / '.wuwei/memory/notes').mkdir(parents=True)
    (root / 'repo').mkdir()
    (root / '.wuwei/config.toml').write_text('''
[[repos]]
name = "example/project"
path = "repo"
default_branch = "main"
merge_deploys = false
[metrics]
transcripts = "transcripts"
''')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-30T12:00:00Z')
    return root


def turn(at, cwd, content='private sentinel text', **extra):
    return {'type': 'user', 'timestamp': at, 'cwd': str(cwd),
            'message': {'role': 'user', 'content': content}, **extra}


def test_baseline_missing_and_populated(root):
    value = metrics.collect(root)
    assert value['baseline']['escaped_defects'] == 'unmeasured'
    baseline = root / '.wuwei/memory/notes/baseline.md'
    baseline.write_text('---\ntype: reference\n---\nEscaped-defect-rate: 0.25\n'
                        'Review-rework: 1.5\nOwner-intervention: 90\nLead-time: 48\n')
    value = metrics.collect(root)
    assert value['baseline'] == {'escaped_defects': '0.25', 'review_rework': '1.5',
                                  'owner_intervention': '90', 'lead_time': '48'}


def test_blank_template_baseline_is_unmeasured(root, capsys):
    from wuwei.__main__ import main

    template = Path(__file__).resolve().parents[1] / 'templates/workspace/memory/notes/baseline.md'
    (root / '.wuwei/memory/notes/baseline.md').write_bytes(template.read_bytes())
    assert main(['metrics']) == 0
    assert json.loads(capsys.readouterr().out)['baseline'] == {
        'escaped_defects': 'unmeasured', 'review_rework': 'unmeasured',
        'owner_intervention': 'unmeasured', 'lead_time': 'unmeasured'}


def test_escaped_defect_baseline_uses_merge_grammar(root):
    baseline = root / '.wuwei/memory/notes/baseline.md'
    baseline.write_text('Escaped-defect-rate: 1e-1\n')
    with pytest.raises(ValueError, match='baseline'):
        metrics.collect(root)


def test_transcripts_merge_overlap_and_keep_text_private(root, capsys):
    paths = root / 'transcripts'
    paths.mkdir()
    rows = [turn('2026-09-28T09:00:00Z', root / 'repo'),
            turn('2026-09-28T09:08:00Z', root / 'repo'),
            turn('2026-09-28T09:12:00Z', root / 'repo', isSidechain=True),
            turn('2026-09-28T09:30:00Z', root / 'repo', isMeta=True),
            turn('2026-09-28T09:40:00Z', root / 'repo', content='<system-reminder>private sentinel text')]
    (paths / 'a.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    (paths / 'b.jsonl').write_text(json.dumps(turn('2026-09-28T09:04:00Z', root / 'repo')) + '\n')
    value = metrics.collect(root)
    assert value['owner_intervention']['median_minutes'] == 13
    assert value['owner_intervention']['sensitivity_minutes'] == {'5': 10.5, '15': 15.5}
    print(json.dumps(value))
    captured = capsys.readouterr()
    assert 'private sentinel text' not in captured.out + captured.err
    for path in (root / '.wuwei').rglob('*'):
        if path.is_file() and path.suffix in ('.json', '.jsonl', '.md'):
            assert 'private sentinel text' not in path.read_text()


def test_transcript_outside_workspace_and_tool_results_excluded(root):
    paths = root / 'transcripts'
    paths.mkdir()
    rows = [turn('2026-09-28T09:00:00Z', root.parent / 'other'),
            turn('2026-09-28T10:00:00Z', root / 'repo', content=[{'type': 'tool_result', 'content': 'private sentinel text'}])]
    (paths / 'a.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    assert metrics.collect(root)['owner_intervention'] == 'unmeasured'


def test_no_tracker_is_unmeasured(root):
    assert metrics.collect(root)['lead_time'] == 'unmeasured'


def test_escaped_defects_only_full_window(root, monkeypatch):
    monkeypatch.setenv('WUWEI_NOW', '2026-10-20T12:00:00Z')
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text() + '\n[adapters]\ncode_host = "none"\n')
    state._write_state(lambda data: data.update(merges={
        'example/project#1': {'status': 'merged', 'merged_at': '2026-09-29T10:00:00Z',
                              'outcome': {'escaped': True, 'reverts': [
                                  {'sha': 'a', 'at': '2026-09-30T10:00:00Z'},
                                  {'sha': 'late', 'at': '2026-10-16T10:00:00Z'}], 'fixes': ['b']}},
        'example/project#2': {'status': 'merged', 'merged_at': '2026-10-15T10:00:00Z',
                              'outcome': {'escaped': False, 'reverts': [], 'fixes': []}},
    }), root, reserved=False)
    assert metrics.collect(root)['escaped_defects'] == {
        'rate': 1.0, 'prs': 1, 'raw_count': 2, 'reverts': 1, 'fixes': 1}


def test_review_rework_counts_human_threads_followed_by_commit(root, monkeypatch):
    from wuwei.registry import Result
    from wuwei import registry

    state._write_state(lambda data: data.update(raised_prs=['example/project#1']), root, reserved=False)

    class Host:
        def pr(self, ref, root=None):
            return Result(0, {'merged': True, 'merged_at': '2026-09-29T11:00:00Z',
                              'created_at': '2026-09-28T10:00:00Z', 'author': 'owner'})

        def threads(self, ref, root=None):
            return Result(0, {'threads': [
                {'id': 'a', 'comments': [{'author': 'reviewer', 'is_bot': False,
                                         'created_at': '2026-09-28T11:00:00Z'}]},
                {'id': 'b', 'comments': [{'author': 'bot', 'is_bot': True,
                                         'created_at': '2026-09-28T11:00:00Z'}]}]})

        def commits(self, ref, root=None):
            return Result(0, [{'at': '2026-09-28T12:00:00Z'}])

    monkeypatch.setattr(registry, 'load', lambda kind, config: Host())
    assert metrics.collect(root)['review_rework'] == {'mean_per_pr': 1, 'median_per_pr': 1,
        'p90_per_pr': 1, 'share_with_rework': 1}


def test_tracker_lead_time_and_secondary_durations(root, monkeypatch):
    from wuwei.registry import Result
    from wuwei import registry

    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text() + '\n[adapters]\ntracker = "linear"\n')
    state._write_state(lambda data: data.update(items={'ISSUE-1': {'pr': 'example/project#1'}}),
                       root, reserved=False)

    class Host:
        def pr(self, ref, root=None):
            return Result(0, {'merged': True, 'merged_at': '2026-09-29T10:00:00Z',
                              'created_at': '2026-09-28T10:00:00Z', 'author': 'owner'})

        def threads(self, ref, root=None):
            return Result(0, {'threads': []})

        def commits(self, ref, root=None):
            return Result(0, [])

    class Tracker:
        def history(self, item, root=None):
            return Result(0, [{'createdAt': '2026-09-28T11:00:00Z', 'toState': None},
                              {'createdAt': '2026-09-28T12:00:00Z',
                               'toState': {'name': 'In Progress'}}])

        def created(self, item, root=None):
            return Result(0, '2026-09-27T10:00:00Z')

    monkeypatch.setattr(registry, 'load', lambda kind, config: Tracker() if kind == 'tracker' else Host())
    assert metrics.collect(root)['lead_time'] == {
        'median_hours': 22, 'p75_hours': 22, 'p90_hours': 22,
        'creation_to_merge_hours': 48, 'pr_open_to_merge_hours': 24}


def test_invalid_transcript_fails_closed_without_disclosing_text(root, capsys):
    from wuwei.__main__ import main

    paths = root / 'transcripts'
    paths.mkdir()
    (paths / 'a.jsonl').write_text('{"message":"private sentinel text"\n')
    assert main(['metrics']) == 2
    captured = capsys.readouterr()
    assert 'transcript' in captured.err
    assert 'private sentinel text' not in captured.out + captured.err
    day = workspace.day_dir(root)
    assert not (day / 'events.jsonl').exists()
    assert not (day / 'state.json').exists()


def test_no_tracker_with_item_stays_unmeasured(root):
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text() + '\n[adapters]\ncode_host = "none"\n')
    state._write_state(lambda data: data.update(items={'ISSUE-1': {'pr': 'example/project#1'}}),
                       root, reserved=False)
    assert metrics.collect(root)['lead_time'] == 'unmeasured'


def test_report_shows_measured_outcome_beside_workspace_baseline(root, monkeypatch):
    from wuwei import report

    monkeypatch.setenv('WUWEI_NOW', '2026-10-20T12:00:00Z')
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text() + '\n[adapters]\ncode_host = "none"\n')
    (root / '.wuwei/memory/notes/baseline.md').write_text('Escaped-defect-rate: 0.25\n')
    state._write_state(lambda data: data.update(merges={'example/project#1': {
        'status': 'merged', 'merged_at': '2026-09-29T10:00:00Z',
        'outcome': {'escaped': True, 'reverts': [], 'fixes': ['f']}}}), root, reserved=False)
    text = report.build(root)
    assert "'rate': 1.0" in text
    assert 'baseline: 0.25' in text


def test_code_host_commit_adapter_normalizes_timestamps(monkeypatch):
    from adapters.code_host import github

    monkeypatch.setattr(github, '_pages', lambda endpoint: [
        {'sha': 'a' * 40, 'commit': {'committer': {'date': '2026-09-28T12:00:00Z'}}}])
    result = github.commits('example/project#1')
    assert result.exit == 0
    assert result.data == [{'sha': 'a' * 40, 'at': '2026-09-28T12:00:00Z'}]


def test_tracker_created_adapter_normalizes_timestamp(monkeypatch):
    from adapters.tracker import linear

    monkeypatch.setattr(linear, '_query', lambda query, variables: {
        'issue': {'createdAt': '2026-09-27T10:00:00Z'}})
    result = linear.created('ISSUE-1')
    assert result.exit == 0 and result.data == '2026-09-27T10:00:00Z'


def test_missing_code_host_does_not_bias_defect_denominator(root, monkeypatch):
    monkeypatch.setenv('WUWEI_NOW', '2026-10-20T12:00:00Z')
    config = root / '.wuwei/config.toml'
    config.write_text(config.read_text() + '\n[adapters]\ncode_host = "none"\n')
    state._write_state(lambda data: data.update(
        raised_prs=['example/project#2'],
        merges={'example/project#1': {'status': 'merged',
            'merged_at': '2026-09-29T10:00:00Z',
            'outcome': {'escaped': False, 'reverts': [], 'fixes': []}}}), root, reserved=False)
    assert metrics.collect(root)['escaped_defects'] == 'unmeasured'
