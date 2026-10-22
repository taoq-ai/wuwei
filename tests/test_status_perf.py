"""A cold status reads each repository's PR evidence in parallel and says what it is reading (#1121)."""

import datetime
import json
import os
import threading
import time

import pytest

from conftest import HEAD, OLD, make_pr, write_plan
from test_evidence import attest
from wuwei import __main__ as cli, board, evidence, ws

DELAY = 0.05


def _slow(fake, monkeypatch):
    calls = []

    def slow(args, timeout=30):
        calls.append(args)
        time.sleep(DELAY)
        return fake(args, timeout)
    monkeypatch.setattr('wuwei.gh.run', slow)
    return calls


def _eighteen(root, fake):
    write_plan(root, [{'id': f'I-{n}', 'title': f'item {n}', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light',
                       'status': 'open'} for n in range(1, 19)])
    for n in range(1, 19):
        fake.prs[str(100 + n)] = make_pr(100 + n, body=f'WUWEI-Item: I-{n}')


def test_a_cold_board_reads_linked_prs_in_parallel_with_rows_in_plan_order(root, fake, monkeypatch):
    _eighteen(root, fake)
    calls = _slow(fake, monkeypatch)
    started = time.monotonic()
    rows = board.compute(root)
    elapsed = time.monotonic() - started
    assert [(r['item'], r['pr']) for r in rows] == [('team', None)] + [(f'I-{n}', f'acme/app#{100 + n}') for n in range(1, 19)]
    serial = len(calls) * DELAY  # every gh call one after another, as at efcd9e7
    assert elapsed < serial / 3, (elapsed, serial, len(calls))


def test_two_threads_writing_one_cache_key_never_share_a_temp_file(root):
    errors = []

    def write(tag):
        try:
            for n in range(200):
                ws.cache_put(root, 'spec-acme__app', {'by': tag, 'n': n})
        except Exception as exc:  # noqa: BLE001 - any failure fails the test
            errors.append(exc)
    threads = [threading.Thread(target=write, args=(tag,)) for tag in ('a', 'b')]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert json.loads((root / ws.DIR / 'cache' / 'spec-acme__app.json').read_text())['n'] == 199
    assert not list((root / ws.DIR / 'cache').glob('.*.tmp'))


def test_a_cold_status_names_each_repository_on_stderr_and_keeps_stdout(root, fake, monkeypatch, capsys):
    _eighteen(root, fake)
    monkeypatch.setattr(cli, '_root', lambda: root)
    assert cli.main(['status']) == 0
    cold = capsys.readouterr()
    assert cold.err.splitlines() == ['wuwei: reading acme/app: 18 open PRs']
    assert cold.out.splitlines() == ['Board (what each open item still lacks):', (
        '- team seats: orchestration: open PRs with no shepherd seat running; '
        'orchestration: gates owed with no gate seat running')] + [
        f'- I-{n} item {n} (acme/app#{100 + n}) [standard, last event 0h ago]: gates missing at head aaaaaaa: quality'
        for n in range(1, 19)]


def _pr_reads(calls):
    return sum(1 for args in calls if len(args) > 1 and args[1].startswith('repos/acme/app/pulls/') and args[1].count('/') == 4)


def test_a_warm_board_rereads_only_the_prs_that_changed(root, fake, monkeypatch):
    """One status on 197 open PRs spent ~387 REST calls, and every read paid it again (#1161)."""
    _eighteen(root, fake)
    for n, pr in fake.prs.items():
        pr['headRefOid'] = n * 8  # the fake reads a head's checks by its sha
    fake.prs['101']['statusCheckRollup'] = [{'name': 'test', 'status': 'IN_PROGRESS', 'conclusion': ''}]
    calls = _slow(fake, monkeypatch)
    board.compute(root)
    assert _pr_reads(calls) == 18
    calls.clear()
    fake.prs['102']['updatedAt'] = '2026-10-19T09:00:00Z'  # a review, a comment or a push moves it
    fake.prs['103']['headRefOid'] = 'c' * 40
    ws.cache_put(root, 'prs-acme__app', None)
    board.compute(root)
    assert _pr_reads(calls) == 3  # 101 waits on CI, 102 moved, 103 has a new head
    assert not [args for args in calls if '/pulls/104' in args[1] or 'number=104' in args]  # unchanged: no host read


def test_a_warm_board_reads_the_same_and_an_entry_expires_by_its_first_read(root, fake, monkeypatch):
    _eighteen(root, fake)
    calls = _slow(fake, monkeypatch)
    cold = board.compute(root)
    entry = root / ws.DIR / 'cache' / 'pr-acme__app-101.json'
    old = entry.stat().st_mtime - evidence.PR_TTL + 30
    os.utime(entry, (old, old))
    calls.clear()
    assert board.compute(root) == cold and _pr_reads(calls) == 0  # a hit never rewrites, so it never resets the clock
    assert entry.stat().st_mtime == old
    os.utime(entry, (old - 60, old - 60))
    board.compute(root)
    assert _pr_reads(calls) == 1


def test_a_board_reads_one_page_of_merged_prs_however_many_merged(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light',
                       'status': 'open', 'added': '2026-01-01'}])
    now = ws.now().isoformat(timespec='seconds')
    for n in range(1, 251):
        fake.prs[str(n)] = {**make_pr(n, state='MERGED', body=''), 'headRefName': f'other-{n}', 'mergedAt': now, 'updatedAt': now}
    board.compute(root)
    fake.calls.clear()
    board.compute(root)
    assert len([args for args in fake.calls if 'state=closed' in args[1]]) == 1


def test_a_cold_board_reads_the_error_budget_once_and_at_most_a_hundred_deploy_statuses(root, fake, monkeypatch):
    """Eight threads each read the budget, so 100 production deploys cost 800 status reads (#1177)."""
    _eighteen(root, fake)
    at = (ws.now() - datetime.timedelta(days=1)).isoformat(timespec='seconds')
    fake.deployments = [{'id': n, 'environment': 'production', 'created_at': at} for n in range(150)]
    fake.statuses = {str(n): ['success'] for n in range(150)}
    calls = _slow(fake, monkeypatch)
    board.compute(root)
    assert sum('/statuses' in args[1] for args in calls) == 100
    assert sum('/deployments?' in args[1] for args in calls) == 2


def _hosted(calls):
    return [args for args in calls if 'state=closed' not in ' '.join(args)]  # the merged list is read fresh by design


@pytest.mark.parametrize('ci', ['COMPLETED', 'IN_PROGRESS'])
def test_a_warm_board_rereads_no_compare_and_no_spec_artifact(root, fake, monkeypatch, ci):
    """Verdicts at an older head cost a compare each per read, and a PR with CI running re-read its spec (#1161)."""
    write_plan(root, [{'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'standard', 'status': 'open'}])
    fake.paths.add('.specify')
    fake.files.update({'specs/001-x/spec.md': '# spec', 'specs/001-x/plan.md': '# plan', 'specs/001-x/tasks.md': '- [x] done'})
    fake.prs['42'] = make_pr(files=('specs/001-x/spec.md', 'src/app.py', 'tests/test_app.py'))
    fake.prs['42']['statusCheckRollup'][0]['status'] = ci
    fake.ancestors.add((OLD, HEAD))
    fake.deltas[(OLD, HEAD)] = [{'path': 'README.md', 'additions': 1, 'deletions': 0}]
    for gate in ('arch', 'quality', 'security'):
        attest(root, gate, head=OLD)
    calls = _slow(fake, monkeypatch)
    cold = board.compute(root)
    assert sum('/compare/' in args[1] for args in calls) == 1  # three ancestry checks and the delta share one read
    calls.clear()
    assert board.compute(root) == cold
    warm = _hosted(calls)
    assert not [args for args in warm if '/compare/' in args[1] or '/contents/' in args[1]], warm
    assert ci != 'COMPLETED' or warm == []  # CI running re-reads the PR, never what its head fixes


def test_reading_the_open_list_prunes_pr_entries_older_than_a_day(root, fake, monkeypatch):
    _eighteen(root, fake)
    cache = root / ws.DIR / 'cache'
    for name in ('pr-acme__app-9', 'cmp-acme__app-' + OLD + '-' + HEAD, 'budget-other__repo'):
        ws.cache_put(root, name, {})
        os.utime(cache / f'{name}.json', (time.time() - 86400 - 60,) * 2)
    ws.cache_put(root, 'pr-acme__app-8', {})  # fresh entries of the pruned kinds stay
    ws.cache_put(root, f'cmp-acme__app-{HEAD}-{OLD}', {})
    board.compute(root)
    assert not (cache / 'pr-acme__app-9.json').exists() and not (cache / f'cmp-acme__app-{OLD}-{HEAD}.json').exists()
    assert all((cache / f'{name}.json').exists() for name in ('budget-other__repo', 'pr-acme__app-8', f'cmp-acme__app-{HEAD}-{OLD}'))


def _spec_pr(root, fake):
    write_plan(root, [{'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'standard', 'status': 'open'}])
    fake.paths.add('.specify')
    fake.files.update({'specs/001-x/spec.md': '# spec', 'specs/001-x/tasks.md': '- [x] done'})
    fake.prs['42'] = make_pr(files=('specs/001-x/spec.md', 'src/app.py', 'tests/test_app.py'))


def _spec_texts(root):
    return [g['text'] for g in evidence.gaps(root, 'acme/app', 42) if 'specs/' in g['text']]


def test_a_spec_read_through_a_host_error_is_read_again(root, fake):
    """A host error reads as missing, so a missing result is never kept (#1161)."""
    _spec_pr(root, fake)
    assert _spec_texts(root) == ['specs/001-x/plan.md missing: run the spec engine step that writes it']
    fake.files['specs/001-x/plan.md'] = '# plan'  # the host answers again, at the same head
    assert _spec_texts(root) == []


def test_a_push_reads_the_spec_at_the_new_head(root, fake):
    _spec_pr(root, fake)
    fake.files['specs/001-x/plan.md'] = '# plan'
    assert _spec_texts(root) == []
    fake.files['specs/001-x/tasks.md'] = '- [ ] undone'
    fake.prs['42']['headRefOid'] = 'f' * 40
    assert _spec_texts(root) == ['specs/001-x/tasks.md has 1 unchecked item']


def test_a_compare_naming_a_branch_is_never_kept(root, fake):
    for _ in range(2):
        evidence.compare(root, 'acme/app', 'main', HEAD)
    assert sum('/compare/' in call[1] for call in fake.calls if call[0] == 'api') == 2
    assert not list((root / ws.DIR / 'cache').glob('cmp-*'))
