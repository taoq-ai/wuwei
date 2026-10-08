"""The DORA four keys (#586) read from cycles (#567), escaped defects (5.6) and the code host."""

from datetime import datetime, timedelta
import json

import pytest

from fakes.code_host import Fake
from test_telemetry import write_day
from wuwei import metrics, registry, report, workspace
from wuwei.__main__ import main
from wuwei.registry import Result

NOW = datetime.fromisoformat('2026-10-03T12:00:00+00:00')
SINCE = NOW - timedelta(days=28)
REPO = '[[repos]]\nname = "acme/widget"\npath = "repo"\ndefault_branch = "main"\n'


@pytest.fixture
def ws(tmp_path, monkeypatch, unread_deploys):
    monkeypatch.setattr(metrics, '_deploys', unread_deploys)
    (tmp_path / '.wuwei').mkdir()
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW.isoformat())
    return tmp_path


def config(root, host='none', repos=REPO):
    (root / '.wuwei/config.toml').write_text(
        f'[owner]\ntimezone = "UTC"\n\n[adapters]\ncode_host = "{host}"\n\n' + repos)
    return workspace.load_config(root)


def seed(root):
    """A, B, C merge on 2026-09-21 after 60, 120 and 300 minutes; a fix brief for C names B; D
    merged before the window."""
    write_day(root, '2026-09-01', [('09:00', 'plan.added', {'item': 'D'}),
                                   ('10:00', 'state.write', {'phase_changes': {'D': 'merged'}})],
              data={'items': {'D': {'phase': 'merged', 'gates': {'computed': 'light'}, 'pr': 'acme/widget#4'}}})
    (root / 'briefs').mkdir()
    (root / 'briefs/fix.md').write_text('Fix the regression B left in the parser.\n')
    write_day(root, '2026-09-21', [
        ('09:00', 'plan.approved', {'items': ['A', 'B', 'C']}),
        ('10:00', 'state.write', {'phase_changes': {'A': 'merged'}}),
        ('11:00', 'state.write', {'phase_changes': {'B': 'merged'}}),
        ('14:00', 'state.write', {'phase_changes': {'C': 'merged'}}),
        ('15:00', 'brief written', {'item': 'C', 'role': 'builder', 'name': 'fix', 'path': 'briefs/fix.md'}),
    ], data={'items': {
        'A': {'phase': 'merged', 'gates': {'computed': 'light'}, 'pr': 'acme/widget#1'},
        'B': {'phase': 'merged', 'gates': {'computed': 'light'}},
        'C': {'phase': 'merged', 'gates': {'computed': 'standard'}, 'pr': 'acme/widget#3'}}})


def host(monkeypatch, result):
    fake = Fake({'deployments': result})
    monkeypatch.setattr(registry, 'load', lambda kind, settings: fake)
    return fake


def deployed(source='deployments'):
    return Result(0, {'source': source, 'at': ['2026-09-01T00:00:00Z', '2026-09-21T12:00:00Z',
                                               '2026-09-21T15:00:00Z']})


def events(root):
    return [json.loads(line) for path in (root / '.wuwei/days').glob('*/events.jsonl')
            for line in path.read_text().splitlines()]


def test_local_keys_with_no_code_host(ws):
    seed(ws)
    rows = metrics.dora(ws, config(ws), SINCE, NOW)
    assert list(rows) == [key for key, _, _ in metrics.DORA]
    assert rows['lead_time_merge_hours'] == {'value': 2.0, 'source': 'cycle_minutes of 3 merged items (#567)'}
    assert rows['change_failure_rate'] == {
        'value': 1 / 3, 'source': '1 of 3 merged items named by a later fix brief (5.6)'}
    for key in ('lead_time_deploy_hours', 'deploys_per_week'):
        assert rows[key] == {'value': 'unmeasured', 'reason': 'code host adapter is none'}
    assert rows['time_to_restore_hours'] == {'value': 'unmeasured',
                                             'reason': 'no on-call incident signal yet (#415)'}
    assert not any(row['kind'] == 'adapter: none' for row in events(ws))


def test_no_item_merged_in_the_window(ws):
    seed(ws)
    rows = metrics.dora(ws, config(ws), NOW - timedelta(days=7), NOW)
    for key in ('lead_time_merge_hours', 'change_failure_rate'):
        assert rows[key] == {'value': 'unmeasured', 'reason': 'no item merged in the window'}


def test_deploy_keys_from_the_code_host(ws, monkeypatch):
    seed(ws)
    fake = host(monkeypatch, deployed())
    rows = metrics.dora(ws, config(ws, 'github'), SINCE, NOW)
    assert fake.calls == [('deployments', ('acme/widget', SINCE.isoformat()), ws)]
    assert rows['deploys_per_week'] == {'value': 0.5, 'source': '2 deployments in 28 days'}
    assert rows['lead_time_deploy_hours'] == {'value': 4.5, 'source': '2 merged items reached a deploy'}
    host(monkeypatch, deployed('releases'))
    assert metrics.dora(ws, config(ws, 'github'), SINCE, NOW)['deploys_per_week']['source'] == \
        '2 releases in 28 days'


@pytest.mark.parametrize('result,repos,reason', [
    (Result(0, {'source': None, 'at': []}), REPO, 'the code host reports no deployments or releases'),
    (Result(2, None, 'offline'), REPO, 'code host could not run: offline'),
    (deployed(), '', 'no repository configured'),
])
def test_deploy_keys_unmeasured(ws, monkeypatch, result, repos, reason):
    seed(ws)
    host(monkeypatch, result)
    rows = metrics.dora(ws, config(ws, 'github', repos), SINCE, NOW)
    for key in ('lead_time_deploy_hours', 'deploys_per_week'):
        assert rows[key]['value'] == 'unmeasured' and rows[key]['reason'] == reason
        assert rows[key].get('failed', False) == (result.exit == 2)
    assert rows['lead_time_merge_hours']['value'] == 2.0


def test_host_false_never_reads_the_code_host(ws, monkeypatch):
    seed(ws)
    fake = host(monkeypatch, deployed())
    rows = metrics.dora(ws, config(ws, 'github'), SINCE, NOW, host=False)
    assert fake.calls == []
    assert rows['deploys_per_week'] == {'value': 'unmeasured', 'reason': 'read when the week is final'}


def test_dora_lines_render_every_row(ws):
    seed(ws)
    lines = report.dora_lines(metrics.dora(ws, config(ws), SINCE, NOW))
    assert lines[:2] == ['| Key | Value | Source |', '| --- | --- | --- |']
    assert lines[2:] == [
        '| Lead time to merge | 2.0 hours | cycle_minutes of 3 merged items (#567) |',
        '| Lead time to deploy | unmeasured | code host adapter is none |',
        '| Deployment frequency | unmeasured | code host adapter is none |',
        '| Change failure rate | 0.33 | 1 of 3 merged items named by a later fix brief (5.6) |',
        '| Time to restore | unmeasured | no on-call incident signal yet (#415) |']


def test_dora_command(ws, capsys):
    seed(ws)
    config(ws)
    assert main(['dora']) == 0
    out = capsys.readouterr().out
    assert out.startswith('DORA, last 28 days (2026-09-05 to 2026-10-03)\n| Key | Value | Source |')
    assert '| Lead time to merge | 2.0 hours |' in out
    assert main(['dora', '--window', '7']) == 0
    assert '| Lead time to merge | unmeasured | no item merged in the window |' in capsys.readouterr().out
    assert main(['dora', '--window', '0']) == 2
    assert '--window must be a positive number of days' in capsys.readouterr().err


def test_dora_command_exits_2_when_the_code_host_failed(ws, monkeypatch, capsys):
    seed(ws)
    config(ws, 'github')
    host(monkeypatch, Result(2, None, 'offline'))
    assert main(['dora']) == 2
    captured = capsys.readouterr()
    assert '| Deployment frequency | unmeasured | code host could not run: offline |' in captured.out
    assert 'code host could not run: offline' in captured.err


def test_dora_command_without_a_workspace(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.chdir(tmp_path)
    assert main(['dora']) == 2
    captured = capsys.readouterr()
    assert 'wuwei dora:' in captured.err and '| Key |' not in captured.out


def test_week_digest_ends_metrics_with_the_table(ws):
    from datetime import date
    from wuwei import digest
    seed(ws)
    config(ws)
    text = digest.write(ws, date(2026, 9, 23), 'week').read_text()
    metrics_section = text.split('## Metrics\n')[1].split('\n\n')[0]
    assert metrics_section.endswith('| Time to restore | unmeasured | no on-call incident signal yet (#415) |')
    assert '| Lead time to merge | 2.0 hours | cycle_minutes of 3 merged items (#567) |' in metrics_section
    assert '| Key |' not in digest.write(ws, date(2026, 9, 23), 'month').read_text()
