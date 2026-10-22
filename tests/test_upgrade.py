"""A 0.34 workspace upgrades in place: config shape, goals, open items with their PRs, verdicts."""

import json

from conftest import HEAD, OLD, make_pr
from wuwei import evidence, plan, setup, upgrade, ws

CONFIG_034 = '''cap = 0
profile = "strict"
[[repos]]
name = "acme/app"
path = "repos/app"
default_branch = "main"
identity = {name = "Builder", email = "b@example.test"}
[prioritisation]
framework = "wsjf"
[guards]
enforce = true
[merge]
owner_paths = ["infra/**"]
never_auto_paths = [".github/**"]
[telemetry]
mode = "off"
'''


def workspace_034(tmp_path):
    base = tmp_path / ws.DIR
    (base / 'days' / '2026-10-14' / 'decisions').mkdir(parents=True)
    (base / 'days' / '2026-10-15').mkdir(parents=True)
    (base / 'config.toml').write_text(CONFIG_034)
    (base / 'days' / '2026-10-15' / 'goals.md').write_text('## G-1\noutcome: ship rate limits\n')
    (base / 'days' / '2026-10-14' / 'state.json').write_text(json.dumps({'items': {
        'TIN-967': {'goal': 'G-1', 'repo': 'acme/app', 'tier': 'standard', 'phase': 'pr', 'status': 'active',
                    'pr': 'acme/app#42', 'approved_as': 'Rate limits for the login API; owner: "ship it"'},
        'TIN-1': {'goal': 'G-1', 'repo': 'acme/app', 'phase': 'merged', 'status': 'done'}}}))
    (base / 'days' / '2026-10-14' / 'decisions' / 'gate-tin-967-arch.md').write_text(f'Verdict: PASS\nHead: {OLD}\n')
    (base / 'days' / '2026-10-14' / 'decisions' / 'gate-tin-967-quality-delta.md').write_text(f'Verdict: FIX\nHead: {OLD[:12]}\n')
    (base / 'days' / '2026-10-15' / 'lead.json').write_text(json.dumps({'candidates': [
        {'id': 'TIN-990', 'scope': 'Retry policy for the importer', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light',
         'score': {'value': 8, 'time_criticality': 5, 'risk_reduction': 3, 'job_size': 2}}]}))
    return tmp_path


def test_a_034_config_reads_in_its_old_shape(tmp_path):
    root = workspace_034(tmp_path)
    config = ws.config(root)
    assert config['repos'] == ['acme/app'] and config['prioritisation'] == 'wsjf'
    assert config['owner_paths'] == ['infra/**', '.github/**'] and config['telemetry'] is False
    assert ws.retired(root) == ['cap', 'guards', 'merge', 'profile', 'prioritisation (0.34 shape)',
                                'repos (0.34 shape)', 'telemetry (0.34 shape)']


def test_init_upgrades_a_034_workspace_and_says_what_it_moved(tmp_path, monkeypatch):
    root = workspace_034(tmp_path)
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: '')
    lines = '\n'.join(setup.init(root))
    assert 'retired: cap, guards, merge, profile' in lines and (root / ws.DIR / 'config.0x.toml').is_file()
    assert set(ws.config(root)) == set(ws.DEFAULTS) and 'guards' not in (root / ws.DIR / 'config.toml').read_text()
    assert 'G-1' in (root / ws.DIR / 'goals.md').read_text()
    items = {item['id']: item for item in plan.items(root)}
    assert set(items) == {'TIN-967', 'TIN-990'}
    assert items['TIN-967']['prs'] == ['acme/app#42'] and items['TIN-967']['title'] == 'Rate limits for the login API'
    assert items['TIN-990']['score'] == 8.0
    attests = [row['data'] for row in ws.rows(root, 'attest')]
    assert [(a['gate'], a['verdict'], a['item']) for a in attests] == [('arch', 'PASS', 'TIN-967'), ('quality', 'FIX', 'TIN-967')]
    assert 'imported 2 open items' in lines and 'imported 2 verdicts' in lines
    again = '\n'.join(setup.init(root))
    assert len(plan.items(root)) == 2 and len(ws.rows(root, 'attest')) == 2 and 'imported' not in again


def test_an_imported_pass_needs_only_a_delta_gate(tmp_path, fake, monkeypatch):
    root = workspace_034(tmp_path)
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: '')
    setup.init(root)
    pr = make_pr(body='adopted in 0.34')
    pr['headRefName'] = 'feature/limits'
    fake.prs['42'] = pr
    fake.ancestors.add((OLD, pr['headRefOid']))
    fake.ancestors.add((OLD[:12], pr['headRefOid']))
    texts = [g['text'] for g in evidence.gaps(root, 'acme/app', 42)]
    assert texts == ['gates missing at head aaaaaaa: quality']


def test_doctor_runs_on_a_034_workspace_and_points_at_the_upgrade(tmp_path, fake):
    root = workspace_034(tmp_path)
    rows = {name: (status, detail) for name, status, detail in setup.doctor(root)}
    assert rows['repos'] == ('ok', 'acme/app')
    assert rows['retired config'][0] == 'warn' and 'wuwei init' in rows['retired config'][1]


def test_close_report_status_and_doctor_run_on_a_workspace_not_yet_upgraded(tmp_path, fake):
    from wuwei import board, report
    (tmp_path / ws.DIR).mkdir()
    (tmp_path / ws.DIR / 'config.toml').write_text(CONFIG_034)
    fake.prs['42'] = make_pr()
    assert report.close(tmp_path).is_file()
    assert 'acme/app' in report.day(tmp_path)
    board.text(board.compute(tmp_path), tmp_path)
    assert ('repos', 'ok', 'acme/app') in setup.doctor(tmp_path)


def test_the_034_review_channel_becomes_a_standards_line(tmp_path):
    (tmp_path / ws.DIR).mkdir()
    (tmp_path / ws.DIR / 'config.toml').write_text(CONFIG_034 + '[shepherd]\nreview_channel = "#eng-reviews"\n')
    upgrade.run(tmp_path)
    upgrade.run(tmp_path)
    assert (tmp_path / ws.DIR / 'standards.md').read_text().count('Review requests: #eng-reviews') == 1


def test_init_imports_no_day_decision_into_a_workspace_that_already_has_a_ledger(root, fake, monkeypatch):
    """Security gate on #1244: a seat wrote days/<date>/decisions/gate-quality-<item>.md, ran wuwei init, and got a PASS."""
    monkeypatch.setattr(setup.guards, 'origin', lambda cwd: '')
    plan.save(root, [{'id': 'I-1', 'title': 'change', 'goal': 'G-1', 'repo': 'acme/app', 'tier': 'light', 'status': 'open',
                      'score': 3, 'prs': ['acme/app#42']}])
    ws.record(root, 'seat.started', {'role': 'builder', 'agent': 'b1'})
    fake.prs['42'] = make_pr()
    planted = root / ws.DIR / 'days' / '2026-10-22' / 'decisions' / 'gate-quality-I-1.md'
    planted.parent.mkdir(parents=True)
    planted.write_text(f'Verdict: PASS\nHead: {HEAD}\n')
    assert 'verdicts' not in '\n'.join(setup.init(root))
    assert not ws.rows(root, 'attest') and any('quality' in g['text'] for g in evidence.gaps(root, 'acme/app', 42))
