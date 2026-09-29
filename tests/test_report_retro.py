"""Owner report, evidence retro and promoted charter history."""

import json
import subprocess
from types import SimpleNamespace

from wuwei import registry, state, workspace
from wuwei.__main__ import main
from wuwei.guards.stop import check as stop_check


def test_retro_compiles_role_evidence_and_cycle(tmp_path, monkeypatch):
    root = tmp_path
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    monkeypatch.chdir(root)
    state._write_state(lambda data: data.update(items={'A': {'phase': 'merged', 'status': 'done'}}),
                       root, reserved=False)
    day = workspace.day_dir(root)
    (day / 'retro').mkdir()
    (day / 'decisions').mkdir()
    (day / 'decisions/gate-a.md').write_text('Verdict: PASS\nChange: Check review timing\n')
    evidence = day / 'retro/role.json'
    evidence.write_text(json.dumps({'agent_id': 'builder-1', 'agent_type': 'builder',
        'fields': {'Blocked': 'none', 'Gap': 'Review lag', 'Change': 'Check review timing'},
        'missing': [], 'invalid': []}))
    state.append_event('retro.captured', {'agent_id': 'builder-1', 'agent_type': 'builder',
        'fields': {'Blocked': 'none', 'Gap': 'Review lag', 'Change': 'Check review timing'},
        'missing': [], 'invalid': [], 'evidence': evidence.relative_to(root).as_posix()}, root)
    from wuwei import retro
    path = retro.compile(root)
    text = path.read_text()
    assert '| builder |' in text and 'Review lag' in text
    assert '| A | merged | done |' in text
    assert '| gate-a.md | PASS |' in text
    assert '## Applied\nnone' in text and '.wuwei/charters/builder.md' in text
    proposals = list((day / 'proposals').glob('*.json'))
    assert len(proposals) == 1
    assert json.loads(proposals[0].read_text())['evidence'] == evidence.relative_to(root).as_posix()


def test_hard_rule_change_is_decision_only(tmp_path, monkeypatch):
    root = tmp_path
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    day = workspace.day_dir(root)
    (day / 'retro').mkdir(parents=True)
    evidence = day / 'retro/role.json'
    fields = {'Blocked': 'none', 'Gap': 'unsafe path',
              'Change': 'Hard rule: refuse all shell commands'}
    record = {'agent_id': 'security-1', 'agent_type': 'sentinel-security',
              'fields': fields, 'missing': [], 'invalid': []}
    evidence.write_text(json.dumps(record))
    state.append_event('retro.captured', {**record,
        'evidence': evidence.relative_to(root).as_posix()}, root)
    from wuwei import retro
    retro.compile(root)
    assert not list((day / 'proposals').glob('*.json'))
    decisions = list((day / 'decisions').glob('D-*.md'))
    assert len(decisions) == 1
    from wuwei.decision import lint
    assert lint(decisions[0].read_text())[0] == 0


def test_report_sections_and_baseline(tmp_path, monkeypatch, capsys):
    root = tmp_path
    (root / '.wuwei/memory/notes').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    (root / '.wuwei/memory/notes/baseline.md').write_text(
        'Escaped-defect-rate: 0.2\nReview-rework: 1.4\n'
        'Owner-intervention: 32 minutes\nLead-time: 3 days\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    monkeypatch.chdir(root)
    state._write_state(lambda data: data.update(items={
        'open': {'phase': 'implement', 'status': 'running'},
        'park': {'phase': 'parked', 'resume_phase': 'implement', 'status': 'blocked',
                 'decision': 'D-1'}}), root, reserved=False)
    day = workspace.day_dir(root)
    (day / 'decisions').mkdir()
    (day / 'decisions/D-1.md').write_text('Question: Defer?\nOutcome: pending\n')
    (day / 'decisions/D-2.md').write_text('Question: Ship?\nOutcome: Accepted\n')
    assert main(['report']) == 0
    text = capsys.readouterr().out
    assert all(section in text for section in ('## Outcome', '## Open at close',
        '## Parked', '## Decisions answered', '## Carry'))
    assert all(value in text for value in ('0.2', '1.4', '32 minutes', '3 days', 'unmeasured'))
    assert 'open' in text and 'park' in text and 'D-1' in text
    assert 'D-2: Accepted' in text
    assert 'decisions/D-1.md' in text


def test_promotion_changelog_and_real_stop(tmp_path, monkeypatch):
    root = tmp_path
    base = root / '.wuwei'
    (base / 'memory').mkdir(parents=True)
    (base / 'charters').mkdir()
    (base / 'memory/spine.md').write_text('Spine\n')
    (base / 'config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    monkeypatch.setenv('GIT_AUTHOR_DATE', '2026-09-29T12:00:00Z')
    monkeypatch.setenv('GIT_COMMITTER_DATE', '2026-09-29T12:00:00Z')
    vcs = registry.load('vcs', workspace.load_config(root))
    assert vcs.workspace_init(base).exit == 0
    state._write_state(lambda data: data.update(planner_session_id='planner', close_requested=True),
                       root, reserved=False)
    day = workspace.day_dir(root)
    (day / 'retro').mkdir()
    (day / 'decisions').mkdir()
    evidence = day / 'retro/role.json'
    evidence.write_text(json.dumps({'agent_id': 'builder-1', 'agent_type': 'builder',
        'fields': {'Blocked': 'none', 'Gap': 'none', 'Change': 'Check tests'},
        'missing': [], 'invalid': []}))
    state.append_event('retro.captured', {'agent_id': 'builder-1', 'agent_type': 'builder',
        'fields': {'Blocked': 'none', 'Gap': 'none', 'Change': 'Check tests'},
        'missing': [], 'invalid': [], 'evidence': evidence.relative_to(root).as_posix()}, root)
    from wuwei import closing, promotion, retro
    retro.compile(root)
    assert closing.retro(root)[0] != 0
    assert promotion.promote(root)[0]['status'] == 'landed'
    from wuwei.commands import agents
    plugin_charter = (agents.ROOT / 'charters/builder.md').read_text()
    promoted_charter = (base / 'charters/builder.md').read_text()
    assert promoted_charter.startswith(plugin_charter)
    assert promoted_charter.endswith('- Check tests\n')
    assert agents._charter(agents.ROOT, 'builder', base / 'charters') == promoted_charter
    retro.compile(root)
    assert closing.retro(root) == (0, '')
    show = subprocess.run(['git', '-C', str(base), 'show', '-s', '--format=%B'],
                          capture_output=True, text=True, check=True).stdout
    assert 'Promoted-by: wuwei' in show
    assert '- 2026-09-29 ' in (base / 'memory/CHANGELOG.md').read_text()
    monkeypatch.setattr('wuwei.closing.obligations.evaluate', lambda root: {'exit': 0})
    from wuwei import pr_actions
    monkeypatch.setattr(pr_actions, 'check', lambda root, closing=False, rows=None: (0, ''))
    assert stop_check({'cwd': str(root), 'session_id': 'planner',
                       'stop_hook_active': False}) == (0, '')


def test_report_rejects_malformed_baseline(tmp_path, monkeypatch, capsys):
    root = tmp_path
    (root / '.wuwei/memory/notes').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    (root / '.wuwei/memory/notes/baseline.md').write_text('Escaped-defect-rate: bogus\n')
    monkeypatch.chdir(root)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    state._write_state(lambda data: None, root, reserved=False)
    assert main(['report']) == 2
    assert 'baseline' in capsys.readouterr().err


def test_report_requires_day_state(tmp_path, monkeypatch, capsys):
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    assert main(['report']) == 2
    assert 'state missing' in capsys.readouterr().err


def test_report_and_retro_outside_workspace_are_clean(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.chdir(tmp_path)
    assert main(['report']) == 0
    assert main(['retro']) == 0
