"""A cold status reads each repository's PR evidence in parallel and says what it is reading (#1121)."""

import json
import threading
import time

from conftest import make_pr, write_plan
from wuwei import __main__ as cli, board, ws

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
