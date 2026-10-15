from conftest import make_pr, write_plan
from wuwei import report, ws


def test_the_report_lists_the_day_and_what_slipped(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light',
                       'status': 'open', 'score': 3}])
    fake.prs['42'] = make_pr(files=('src/app.py',))
    merged = make_pr(number=40, state='MERGED')
    merged['mergedAt'] = ws.today() + 'T10:00:00Z'
    fake.prs['40'] = merged
    ws.record(root, 'refused', {'tool': 'Bash', 'reason': 'force push refused: history'})
    ws.record(root, 'prompt', {'questions': ['owner review: acme/app#41 at aaaaaaa'], 'answers': {}})
    text = report.day(root)
    assert '# WUWEI report' in text
    assert 'I-1' in text and 'no test in the diff' in text
    assert 'acme/app#40 merged without WUWEI reading its evidence' in text
    assert 'force push refused' in text
    assert 'Owner prompts: 1' in text
    assert 'Ledger: intact' in text


def test_close_is_a_checkpoint_the_next_pass_reopens(root, fake):
    path = report.close(root)
    assert path.is_file() and ws.rows(root, 'day.closed')
    assert report.close(root) == path


def test_dora_reads_the_code_host(root, fake, monkeypatch):
    rows = [{'number': 1, 'title': 'feat: a', 'createdAt': '2026-10-01T00:00:00Z', 'mergedAt': '2026-10-01T10:00:00Z'},
            {'number': 2, 'title': 'Revert "feat: a"', 'createdAt': '2026-10-02T00:00:00Z', 'mergedAt': '2026-10-02T02:00:00Z'}]
    monkeypatch.setattr(report.gh, 'merged_prs', lambda repo, since: rows)
    monkeypatch.setattr(report.gh, 'deployments', lambda repo: [{'created_at': '2026-10-03T00:00:00Z'}])
    table = report.dora(root, window=28, today='2026-10-15')
    assert table['acme/app'] == {'lead_time_hours': 6.0, 'deploys': 1, 'deploy_source': 'deployments',
                                 'change_failure_rate': 0.5, 'merged': 2, 'time_to_restore': 'unmeasured'}
