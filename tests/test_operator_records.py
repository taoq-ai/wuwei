"""Issue 209 acceptance: every record the operator reads tells the same true story."""

import json

from wuwei import plan, state, workspace
from wuwei.__main__ import main
from test_intraday_intake import candidate


def section(text, heading):
    return text.split(heading + '\n')[1].split('\n\n')[0].rstrip('\n')


def test_merged_item_and_answered_decision_read_the_same_everywhere(tmp_path, monkeypatch, capsys):
    root = tmp_path
    (root / '.wuwei/memory').mkdir(parents=True)
    (root / '.wuwei/memory/goals.md').write_text(
        '# Goals\n## G-1\noutcome: Ship\nmeasure: shipped\n'
        'target: 1\ndate: 2026-10-30\npriority: 1\n')
    (root / '.wuwei/config.toml').write_text(
        '[adapters]\ntts = "none"\ncalendar = "none"\ncode_host = "none"\n')
    monkeypatch.setenv('WUWEI_WORKSPACE', str(root))
    monkeypatch.setenv('WUWEI_NOW', '2026-09-29T10:00:00+02:00')
    monkeypatch.chdir(root)
    plan.propose({'goals': ['G-1'], 'cap': 2,
                  'seat_policy': {'builder': {'runtime': 'claude', 'model': 'sonnet'}},
                  'envelope': {'start': '09:00', 'end': '17:00', 'net_build_hours': 5},
                  'sweep': {'manual': 'measured: none'},
                  'candidates': [candidate('DIVIDE-1')]}, root)
    plan.approve(['DIVIDE-1'], root, goals_confirmed=True)
    for args in (('lead', 'DISCOVERY', 'lead-1'), ('steward', 'day', 'steward-1')):
        assert main(['brief', *args, '--body', 'body']) == 0
    for phase in ('implement', 'gate', 'raised'):
        assert main(['state', 'transition', 'DIVIDE-1', phase]) == 0
    state._write_state(lambda data: data['items']['DIVIDE-1'].update(pr='org/repo#1'),
                       root, reserved=False)
    assert main(['state', 'transition', 'DIVIDE-1', 'merged']) == 0
    (workspace.day_dir(root) / 'decisions').mkdir(exist_ok=True)
    (workspace.day_dir(root) / 'decisions/D-1.md').write_text('Question: Ship now?\nOutcome: defer\n')
    for kind, payload in (
            ('build.started', {'item': 'DIVIDE-1'}), ('build.checked', {'item': 'DIVIDE-1'}),
            ('verdict.rejected', {'item': 'DIVIDE-1'}),
            ('tracker.call', {'item': 'DIVIDE-1', 'action': 'claim', 'exit': 2,
                              'reason': 'tracker adapter is none'}),
            ('draft.created', {'id': 'draft-1', 'channel': 'code_host'}),
            ('draft.sent', {'id': 'draft-1', 'exit': 0}),
            ('merge.policy_blocked', {'pr': 'org/repo#1', 'exit': 1}),
            ('pr.action', {'pr': 'org/repo#1', 'tier': 'silent', 'state': 'merged'})):
        state.append_event(kind, payload, root)
    capsys.readouterr()

    assert main(['report']) == 0
    report = capsys.readouterr().out
    assert section(report, '## Merged') == '- DIVIDE-1 (org/repo#1)'
    assert '- D-1: defer' in section(report, '## Decisions answered')
    assert section(report, '## Open at close') == section(report, '## Carry') == 'none'

    assert main(['status', '--line']) == 0
    line = capsys.readouterr().out
    assert 'pages 0 · nudges 0' in line and '1 shipped' in line

    assert main(['brief', 'pack']) == 0
    pack = (root / capsys.readouterr().out.strip()).read_text()
    assert section(pack, '## Headline').strip() == 'DIVIDE-1: merged (org/repo#1)'
    assert section(pack, '## Decided').strip() == 'D-1: defer'

    assert main(['nudges', '--json']) == 0
    assert json.loads(capsys.readouterr().out) == []
    assert set(state.read_state(root)['items']) == {'DIVIDE-1'}
    assert not any('DISCOVERY' in text for text in (report, line, pack))
