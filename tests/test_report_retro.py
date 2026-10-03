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
    assert '## Owner preferences\nnone\n' in text
    assert '"asks_per_item"' in text and '"unnecessary_asks"' in text
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
    (root / '.wuwei/config.toml').write_text('[owner.verbosity]\nreport = "standard"\n')
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
    # The retro checks git log for a commit on the pinned day; stamp the commit with that day too,
    # or the test depends on the wall clock.
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
    assert main(['report']) == 0  # #362: a state answer
    assert 'no day has started' in capsys.readouterr().out


def test_report_and_retro_outside_workspace_are_clean(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.chdir(tmp_path)
    assert main(['report']) == 0
    assert main(['retro']) == 0


def test_report_lists_merged_items(tmp_path, monkeypatch):
    root = tmp_path
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text('[adapters]\ncode_host = "none"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    state._write_state(lambda data: data.update(items={
        'A': {**state.ITEM_DEFAULTS, 'phase': 'merged', 'pr': 'org/repo#1'},
        'B': {**state.ITEM_DEFAULTS, 'phase': 'delta'}}), root, reserved=False)
    from wuwei import report
    text = report.build(root)
    merged = text.split('## Merged\n')[1].split('\n\n')[0]
    assert merged == '- A (org/repo#1)'
    for section in ('## Open at close\n', '## Carry\n'):
        body = text.split(section)[1].split('\n\n')[0]
        assert 'B' in body and 'A' not in body


def test_report_metrics_are_the_metrics_json(tmp_path, monkeypatch, capsys):
    root = tmp_path
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text('[owner.verbosity]\nreport = "standard"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    monkeypatch.chdir(root)
    state._write_state(lambda data: None, root, reserved=False)
    state.append_event('verdict.rejected', {'file': 'decisions/gate-a.md', 'reason': 'bad'}, root)
    assert main(['report']) == 0
    lines = capsys.readouterr().out.splitlines()
    measured = json.loads(lines[lines.index('## Process metrics') + 1])
    assert {'asks_per_item', 'unnecessary_asks'} <= set(measured)
    assert main(['metrics']) == 0
    assert measured == json.loads(capsys.readouterr().out)


def gates(monkeypatch, root, date, rows):
    """Record gate verdicts at UTC hours on one day: rows are (hour, verdict)."""
    for hour, verdict in rows:
        monkeypatch.setenv('WUWEI_NOW', f'{date}T{hour:02}:00:00+00:00')
        state.append_event('gate.received', {'item': 'A', 'verdict': verdict}, root)


def banded_day(monkeypatch, root):
    (root / '.wuwei').mkdir(exist_ok=True)
    (root / '.wuwei/config.toml').write_text('[owner]\ntimezone = "UTC"\n[owner.verbosity]\nreport = "standard"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T08:00:00+00:00')
    monkeypatch.chdir(root)
    state._write_state(lambda data: None, root, reserved=False)
    gates(monkeypatch, root, '2026-09-29', [(9, 'PASS'), (12, 'FIX')])
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T23:00:00+00:00')


def test_issue_acceptance_report_shows_quality_bands(tmp_path, monkeypatch, capsys):
    banded_day(monkeypatch, tmp_path)
    assert main(['report']) == 0
    text = capsys.readouterr().out
    assert '## Quality by band' in text and '| Hour |' in text and '| Session age |' in text
    assert '| midday | 1 | 1.00 |' in text and '| morning | 1 | 0.00 |' in text
    assert text.index('## Quality by band') < text.index('## Process metrics')


def captured(root):
    day = workspace.day_dir(root)
    (day / 'retro').mkdir(parents=True, exist_ok=True)
    fields = {'Blocked': 'none', 'Gap': 'Review lag', 'Change': 'none'}
    record = {'agent_id': 'builder-1', 'agent_type': 'builder', 'fields': fields,
              'missing': [], 'invalid': []}
    (day / 'retro/role.json').write_text(json.dumps(record))
    state.append_event('retro.captured', {**record, 'evidence': f'.wuwei/days/{day.name}/retro/role.json'}, root)


def test_issue_acceptance_retro_names_worst_band(tmp_path, monkeypatch):
    from wuwei import retro
    root = tmp_path
    banded_day(monkeypatch, root)
    gates(monkeypatch, root, '2026-09-27', [(19, 'FIX'), (19, 'FIX'), (9, 'PASS'), (12, 'PASS')])
    gates(monkeypatch, root, '2026-09-28', [(20, 'FIX'), (21, 'PASS'), (9, 'PASS'), (15, 'PASS')])
    gates(monkeypatch, root, '2026-09-29', [(15, 'PASS')])
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T23:00:00+00:00')
    captured(root)
    day = workspace.day_dir(root)
    path = retro.compile(root)
    text = path.read_text()
    assert '## Quality by band (last 7 days)' in text
    assert 'Worst hour band: evening (FIX rate 0.75; others at most 0.50)' in text
    assert 'Worst session age band: none' in text
    proposal = day / 'proposals/quality-hour-evening.json'
    record = json.loads(proposal.read_text())
    assert (record['target'], record['action']) == ('.wuwei/charters/planner.md', 'add')
    assert 'sessions.rotate_after' in record['text']
    assert record['evidence'] == path.relative_to(root).as_posix()
    assert '## Proposed\n- `.wuwei/charters/planner.md`' in text
    retro.compile(root)
    assert sorted(path.name for path in (day / 'proposals').iterdir()) == ['quality-hour-evening.json']
    proposal.unlink()
    earlier = root / '.wuwei/days/2026-09-27/proposals'
    earlier.mkdir()
    (earlier / 'quality-hour-evening.rejected').write_text('{}')
    retro.compile(root)
    assert not proposal.exists()


def test_retro_balanced_window_names_no_band(tmp_path, monkeypatch):
    from wuwei import retro
    root = tmp_path
    banded_day(monkeypatch, root)
    gates(monkeypatch, root, '2026-09-29', [(9, 'FIX'), (12, 'PASS'), (15, 'FIX'), (15, 'PASS'),
                                            (19, 'FIX'), (19, 'PASS')])
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T23:00:00+00:00')
    captured(root)
    text = retro.compile(root).read_text()
    assert 'Worst hour band: none' in text and 'Worst session age band: none' in text
    assert not list((workspace.day_dir(root) / 'proposals').glob('quality-*'))


def test_report_levels(tmp_path, monkeypatch):
    from wuwei import remote, report
    root = tmp_path
    (root / '.wuwei/memory/notes').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    state._write_state(lambda data: data.update(items={
        'A': {**state.ITEM_DEFAULTS, 'phase': 'merged'}}), root, reserved=False)
    day = workspace.day_dir(root)
    (day / 'decisions').mkdir()
    (day / 'decisions/D-2.md').write_text('Question: Ship?\nOutcome: Accepted\n')
    brief = report.build(root)
    sections = [line for line in brief.splitlines() if line.startswith('## ')]
    assert sections == ['## Changed', '## Merged', '## Open at close', '## Parked',
                        '## Decisions answered', '## Carry']
    assert brief.split('## Changed\n')[1].split('\n\n')[0] == 'none'
    (root / '.wuwei/memory/notes/baseline.md').write_text(
        'Escaped-defect-rate: 0.2\nReview-rework: 1.4\n'
        'Owner-intervention: 32 minutes\nLead-time: 3 days\n')
    changed = report.build(root).split('## Changed\n')[1].split('\n\n')[0].splitlines()
    assert len(changed) == 3 and changed[0].startswith('- Escaped defects: ')
    (root / '.wuwei/config.toml').write_text('[owner.verbosity]\nreport = "standard"\n')
    standard = report.build(root)
    assert '## Changed' not in standard and '## Outcome' in standard and '## Process metrics' in standard
    assert '- D-2: Accepted\n' in standard
    (root / '.wuwei/config.toml').write_text('[owner.verbosity]\nreport = "full"\n')
    full = report.build(root)
    assert full == standard.replace('- D-2: Accepted\n', '- D-2: Accepted (decisions/D-2.md)\n')
    (root / '.wuwei/config.toml').write_text(
        '[owner]\nname = "Robin Example"\n[control_plane]\nowner = "T1/U1"\n[adapters]\ncode_host = "none"\n')
    monkeypatch.setenv('SLACK_OWNER_DM_CHANNEL', 'D1')
    sent = []
    transport = SimpleNamespace(dm=lambda text, root=None: sent.append(text) or registry.Result(0, {}))
    event = {'id': 'D1/1.1', 'channel': 'D1', 'sender': 'T1/U1', 'text': 'report'}
    assert remote.handle(root, event, transport=transport) == 0
    assert sent == ['Report 2026-09-29: merged 1, open 0, parked 0, decisions answered 1.']


def test_report_shadow_section(tmp_path, monkeypatch):
    from wuwei import report
    root = tmp_path
    (root / '.wuwei').mkdir()
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T12:00:00Z')
    state._write_state(lambda data: data.update(items={}), root, reserved=False)
    before = report.build(root)
    assert '## Shadow' not in before
    state.append_event('hook.warning', {'reason': 'x', 'tool': 'Bash'}, root)
    assert report.build(root) == before
    state.append_event('guard.would_refuse', {'guard': 'pr', 'reason': 'r', 'target': 'gh pr merge 1',
                                              'session': 's', 'item': None}, root)
    for level in ('brief', 'full'):
        (root / '.wuwei/config.toml').write_text(f'[owner.verbosity]\nreport = "{level}"\n')
        assert '\n## Shadow\n- pr: 1 (gh pr merge: 1)\n' in report.build(root)

def finding(path, text):
    return f'- P2 | {path} | {text} fails when empty | blocks: no\nProbe: not run'


def test_retro_lists_findings_unique_to_each_model(tmp_path, monkeypatch):
    from wuwei import retro
    root = tmp_path
    banded_day(monkeypatch, root)
    captured(root)
    assert '## Second opinion' not in retro.compile(root).read_text()
    first = {'item': 'A', 'role': 'quality', 'round': 'initial', 'verdict': 'FIX',
             'findings': [finding('cli/a.py:1', 'parse'), finding('cli/b.py:2', 'only|first')],
             'usage': {'cost': 'unmeasured', 'model': 'opus', 'duration': 412.0}}
    second = {'item': 'A', 'role': 'quality@codex', 'round': 'initial', 'verdict': 'FIX',
              'runtime': 'codex', 'model': 'm1',
              'findings': [finding('CLI/a.py:1', 'parse again'), finding('cli/c.py:3', 'only second')],
              'usage': {'cost': 0.42, 'model': 'm1', 'duration': 380}}
    old = {'item': 'B', 'role': 'quality', 'round': 'initial', 'verdict': 'PASS'}
    other = {'item': 'B', 'role': 'quality@codex', 'round': 'initial', 'verdict': 'PASS',
             'runtime': 'codex', 'model': 'm1'}
    state._write_state(lambda data: data['gate_verdicts'].update({
        'A:quality:initial': first, 'A:quality@codex:initial': second,
        'B:quality:initial': old, 'B:quality@codex:initial': other}), root, reserved=False)
    text = retro.compile(root).read_text()
    section = text[text.index('## Second opinion'):]
    assert '| A | quality@codex m1 | - P2 / cli/c.py:3 / only second fails when empty / blocks: no |' in section
    assert '| A | quality | - P2 / cli/b.py:2 / only/first fails when empty / blocks: no |' in section
    assert 'cli/a.py:1' not in section
    assert '| B | quality@codex m1 | none |' in section and '| B | quality | none |' in section
    assert '| A | quality | opus | unmeasured | 412.0 |' in section
    assert '| A | quality@codex | m1 | 0.42 | 380 |' in section
    assert '| B | quality | unmeasured | unmeasured | unmeasured |' in section
