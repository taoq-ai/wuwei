import datetime

import pytest

from conftest import make_pr, write_plan
from wuwei import evidence, report, ws


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


def merged(fake, number, title, at, created=None):
    pr = make_pr(number=number, state='MERGED', body='')
    pr.update(title=title, createdAt=created or at, mergedAt=at, updatedAt=at)
    fake.prs[str(number)] = pr


REVERTS = ['revert(infra/TIN-817): drop the issuer', 'revert: x', 'Revert "y"', 'fix: a revert-proof parser']


def test_dora_reads_the_code_host(root, fake):
    merged(fake, 2, 'Revert "feat: a"', '2026-10-02T02:00:00Z', '2026-10-02T00:00:00Z')
    merged(fake, 1, 'feat: a', '2026-10-01T10:00:00Z', '2026-10-01T00:00:00Z')
    fake.deployments = [{'created_at': '2026-10-03T00:00:00Z'}]
    table = report.dora(root, window=28, today='2026-10-15')
    assert table['acme/app'] == {'lead_time_hours': 6.0, 'deploys': 1, 'deploy_source': 'deployments',
                                 'change_failure_rate': 0.5, 'merged': 2, 'time_to_restore': 'unmeasured'}


def test_dora_counts_a_revert_by_its_first_word_in_any_case(root, fake):
    for number, title in enumerate(REVERTS, 1):
        merged(fake, number, title, '2026-10-01T00:00:00Z')
    table = report.dora(root, window=28, today='2026-10-15')['acme/app']
    assert (table['change_failure_rate'], table['merged']) == (0.75, 4)


@pytest.mark.parametrize('source', ['deployments', 'releases'])
def test_dora_counts_every_deploy_in_the_window_past_the_first_page(root, fake, source):
    rows = [{'created_at': f'2026-{day}T00:00:00Z', 'published_at': f'2026-{day}T00:00:00Z'}
            for day in ['10-10'] * 150 + ['09-01'] * 150]
    setattr(fake, source, rows)
    table = report.dora(root, window=28, today='2026-10-15')['acme/app']
    assert (table['deploys'], table['deploy_source'], table['time_to_restore']) == (150, source, 'unmeasured')
    assert len([args for args in fake.calls if f'/{source}?' in args[1]]) == 2  # the page that leaves the window is the last


def test_budget_and_dora_count_every_merge_in_the_window_and_stop_past_it(root, fake):
    inside, before = ((ws.now() - datetime.timedelta(days=days)).isoformat(timespec='seconds') for days in (1, 60))
    for number in range(1, 401):
        merged(fake, number, 'Revert "x"' if number % 50 == 0 else f'feat: {number}', inside if number <= 250 else before)
    reads = lambda: len([args for args in fake.calls if 'state=closed' in args[1]])  # noqa: E731
    table = report.dora(root, window=28, today=ws.today())['acme/app']
    assert (table['merged'], table['change_failure_rate'], reads()) == (250, 0.02, 3)
    fake.calls.clear()
    assert evidence.budget(root, 'acme/app') == {'cfr': 0.02, 'merged': 250, 'raised': False}
    assert reads() == 3  # the third page holds the first PR updated before the window


def test_the_report_learns_from_what_shipped(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light',
                       'status': 'open', 'score': 3}])
    now = ws.now().isoformat(timespec='seconds')
    for number, title in ((40, 'feat: login'), (41, 'Revert "feat: login"')):
        pr = make_pr(number=number, state='MERGED')
        pr.update(title=title, mergedAt=now)
        fake.prs[str(number)] = pr
    fake.prs['43'] = make_pr(number=43, body='a human fix')
    fake.prs['43']['headRefName'] = 'hotfix-cache'
    ws.record(root, 'attest', {'pr': 'acme/app#40', 'gate': 'quality', 'verdict': 'PASS', 'confidence': 'high'})
    ws.record(root, 'attest', {'pr': 'acme/app#40', 'gate': 'arch', 'verdict': 'FIX', 'confidence': 'low'})
    ws.record(root, 'seat.stopped', {'role': 'builder', 'tokens': 320})
    ws.record(root, 'ruling', {'kind': 'exception', 'pr': 'acme/app#42', 'head': 'aaaaaaa',
                               'gap': 'no test in the diff', 'approved': True})
    text = report.day(root)
    assert 'acme/app#40 reverted by #41; it passed: quality (high)' in text
    assert 'gate yield quality: 1 verdicts, 0 FIX' in text and 'gate yield arch: 1 verdicts, 1 FIX (100%)' in text
    assert 'builder 320' in text
    assert 'Unplanned: acme/app#43' in text
    assert 'acme/app: change failure rate 50% over 28 days' in text
    assert 'Sample for you this week: acme/app#4' in text
    assert 'acme/app#42 at aaaaaaa: no test in the diff' in text


def test_a_second_checkpoint_reports_what_changed_since_the_first(root, fake):
    report.close(root)
    ws.record(root, 'item.added', {'id': 'I-9'})
    ws.record(root, 'refused', {'tool': 'Bash', 'reason': 'force push refused'})
    text = report.day(root)
    assert '## Since the last checkpoint' in text
    assert 'item.added 1' in text and 'refused 1' in text


def test_the_report_lists_process_gaps_merged_past(root, fake):
    ws.record(root, 'merge.checked', {'pr': 'acme/app#42', 'process': ['specs/x/tasks.md has no checklist items']})
    assert 'acme/app#42 merged with process gaps: specs/x/tasks.md has no checklist items' in report.day(root)


def test_a_finding_written_after_the_merge_is_an_escape(root, fake):
    merged = make_pr(number=40, state='MERGED')
    import datetime
    merged['mergedAt'] = (ws.now() - datetime.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    fake.prs['40'] = merged
    ws.record(root, 'attest', {'pr': 'acme/app#40', 'gate': 'quality', 'verdict': 'PASS', 'head': 'a' * 40})
    ws.record(root, 'attest', {'pr': 'acme/app#40', 'gate': 'quality', 'verdict': 'FIX', 'head': 'a' * 40})
    assert 'merged before quality PASS' not in report.day(root)
    assert '- escaped (post-merge): acme/app#40 merged before quality FIX' in report.day(root)


def test_the_report_lists_the_goals_the_owner_ruled_met(root, fake):
    from wuwei import hook
    (root / ws.DIR / 'goals.md').write_text(''.join(f'## {g}\nOutcome: o\n\n' for g in ('G-1', 'G-2', 'G-4', 'G-5')))
    assert 'Met goals: none.' in report.day(root)
    for question, reply in (('owner review: acme/app#42 at aaaaaaa. Merge it?', 'Yes'), ('goal: G-2 met? 100 percent.', 'Yes'), ('goal: G-1 met? 40 percent.', 'No'),
                            ('goal: G-4 met? done.', 'Yes'), ('goal: G-4 met? reopened.', 'No'), ('goal: G-5 met? done.', 'Yes')):
        hook.handle(root, 'PostToolUse', {'session_id': 's1', 'tool_name': 'AskUserQuestion', 'cwd': str(root),
                                          'tool_input': {'questions': [{'question': question}]},
                                          'tool_response': {'answers': {question: reply}}})
    ws.record(root, 'ruling', {'kind': 'goal.other', 'goal': 'G-1', 'outcome': 'o', 'approved': True})  # another kind never counts
    assert 'Met goals: G-2, G-5.' in report.day(root)
