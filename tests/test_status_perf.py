"""A cold status reads each repository's PR evidence in parallel and says what it is reading (#1121)."""

import json
import os
import threading
import time

from conftest import make_pr, write_plan
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
    assert [(r['item'], r['pr']) for r in rows] == [(f'I-{n}', f'acme/app#{100 + n}') for n in range(1, 19)]
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
    assert cold.out.splitlines() == ['Board (what each open item still lacks):'] + [
        f'- I-{n} item {n} (acme/app#{100 + n}): gates missing at head aaaaaaa: quality' for n in range(1, 19)]


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
