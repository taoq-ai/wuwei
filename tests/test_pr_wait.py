"""#887: wuwei pr wait blocks until a raised or claimed PR changes in a way wuwei next acts on."""

from datetime import timedelta

import pytest

from fakes.host import Fake as ProcessHost

from fakes import records
from wuwei import derive, registry, workspace
from wuwei.__main__ import main
from wuwei.registry import Result

NOW = '2026-10-12T10:00:00+00:00'
SHA = 'a' * 40
LIMIT = ('github.pulls: could not run: GitHub rate limit until 10:30:00 UTC (0 of 5000 graphql calls '
         'left); retry after it')


class Listing:
    """A code host whose one listing call answers the rows a test sets, and counts the calls."""

    def __init__(self):
        self.calls, self.rows, self.failure = [], {1: {}, 2: {}}, None

    def pulls(self, repo, root=None):
        self.calls.append(repo)
        if self.failure:
            return Result(2, None, self.failure)
        return Result(0, [{'number': number, 'state': 'open', 'head': SHA, 'checks': 'pending',
                           'draft': False, 'mergeable': 'mergeable', 'labels': [], 'activity_at': None, **row}
                          for number, row in self.rows.items()])


@pytest.fixture
def day(tmp_path, monkeypatch):
    """Two claimed PRs in one repository, the day approved, nothing for next to do."""
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    monkeypatch.delenv('WUWEI_SEAT_ROLE', raising=False)
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text(
        '[[repos]]\nname = "example/project"\npath = "project"\ndefault_branch = "main"\n'
        '[pr]\npoll_seconds = 60\n')
    records.write(tmp_path, {
        'gate_approved': True, 'approved_items': ['A', 'B'], 'planner_session_id': 'S', 'cap': 1,
        'claimed_prs': ['example/project#1', 'example/project#2'],
        'items': {'A': {'phase': 'raised', 'status': 'running', 'pr': 'example/project#1'},
                  'B': {'phase': 'raised', 'status': 'running', 'pr': 'example/project#2'}}})
    (workspace.day_dir(tmp_path) / 'plan.md').write_text('# Plan\n')
    host = Listing()
    monkeypatch.setattr(registry, 'load', lambda kind, config: ProcessHost() if kind == 'host' else host)
    return tmp_path, host


def clock(monkeypatch, change=None):
    """A sleep that moves WUWEI_NOW on; change runs once, after the first sleep (a reviewer acts)."""
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        monkeypatch.setenv('WUWEI_NOW', (workspace.now() + timedelta(seconds=seconds)).isoformat())
        if change and len(slept) == 1:
            change()
    monkeypatch.setattr('time.sleep', sleep)
    return slept


def test_a_new_review_thread_on_one_of_two_claimed_prs_wakes_it_within_one_poll(day, monkeypatch, capsys):
    root, host = day
    slept = clock(monkeypatch, lambda: host.rows[2].update(activity_at='2026-10-12T10:00:30Z'))
    assert main(['pr', 'wait', '--timeout', '600']) == 1
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1 and lines[0].startswith('B shepherd example/project#2: '), lines
    assert slept == [60]  # one poll
    assert host.calls == ['example/project'] * 2  # one listing call a tick for both PRs


def test_a_tick_inside_the_poll_interval_reads_nothing_and_the_timeout_prints_nothing(day, monkeypatch, capsys):
    root, host = day
    derive.refresh(root, workspace.load_config(root))  # wuwei next read the listing just now
    host.calls.clear()
    slept = clock(monkeypatch)
    assert main(['pr', 'wait', '--timeout', '50']) == 0
    assert capsys.readouterr().out == ''
    assert host.calls == [] and slept == [50]


def test_a_change_between_next_and_the_wait_is_reported(day, monkeypatch, capsys):
    # The baseline is what next saw; the first tick's own read is compared with it.
    root, host = day
    monkeypatch.setenv('WUWEI_NOW', '2026-10-12T09:58:00+00:00')
    derive.refresh(root, workspace.load_config(root))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    host.rows[1].update(checks='red')
    clock(monkeypatch)
    assert main(['pr', 'wait', '--timeout', '600']) == 1
    assert capsys.readouterr().out.startswith('A fix example/project#1: ')


def test_a_rate_limit_holds_the_next_read_until_its_reset(day, monkeypatch, capsys):
    # #899: the refusal names its reset; the wait sleeps past it, never one poll at a time.
    root, host = day
    host.failure = LIMIT
    slept = clock(monkeypatch, lambda: setattr(host, 'failure', None))
    assert main(['pr', 'wait', '--timeout', '1900']) == 0
    assert slept[0] == 1801 and len(host.calls) >= 2
    assert 'rate limit until 10:30:00 UTC' in capsys.readouterr().err


def test_a_merge_on_the_host_wakes_it(day, monkeypatch, capsys):
    # F5: a merge adds no launch when no tracker is set; the PR's own state change wakes it.
    root, host = day
    clock(monkeypatch, lambda: host.rows[1].update(state='merged'))
    assert main(['pr', 'wait', '--timeout', '600']) == 1
    assert capsys.readouterr().out.splitlines() == ['A merged example/project#1: PR example/project#1 is merged']


def test_nothing_to_wait_on_exits_at_once(day, monkeypatch, capsys):
    root, _ = day
    records.write(root, {'claimed_prs': []})
    slept = clock(monkeypatch)
    assert main(['pr', 'wait']) == 0
    assert slept == [] and capsys.readouterr().out == ''
