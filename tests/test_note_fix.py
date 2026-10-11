"""#646: a seat records a small fix it found with wuwei note --fix; wuwei next proposes it."""

import pytest

NOW = '2026-09-28T12:34:56+02:00'


@pytest.fixture
def day(tmp_path, monkeypatch):
    from wuwei import state
    monkeypatch.setenv('WUWEI_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('WUWEI_NOW', NOW)
    (tmp_path / '.wuwei').mkdir()
    (tmp_path / '.wuwei/config.toml').write_text('')
    state._write_state(lambda data: data['items'].update({'fix-a': {'phase': 'planned'}}),
                       tmp_path, reserved=False)
    return tmp_path


def findings(root):
    from wuwei import state
    return state.read_state(root).get('seat_findings', {})


def test_fix_records_a_finding(day, capsys):
    import json
    from wuwei import workspace
    from wuwei.__main__ import main
    assert main(['note', '--fix', 'Pin ruff in CI']) == 0
    assert capsys.readouterr().out.strip() == 'fix-pin-ruff-in-ci'
    assert findings(day) == {'fix-pin-ruff-in-ci': {
        'scope': 'Pin ruff in CI', 'evidence': 'seat finding', 'track': 'SLICE', 'at': NOW}}
    last = json.loads((workspace.day_dir(day) / 'events.jsonl').read_text().splitlines()[-1])
    assert last['kind'] == 'finding.noted'
    assert last['payload'].items() >= {'id': 'fix-pin-ruff-in-ci', 'title': 'Pin ruff in CI'}.items()
    assert main(['note', '--fix', 'Pin  ruff in CI']) == 1
    assert 'fix-pin-ruff-in-ci is already recorded' in capsys.readouterr().err


@pytest.mark.parametrize('title,reason', [
    ('', 'one line'), ('a\nb', 'one line'), ('x' * 121, '120'), ('!!! ???', 'letters or digits'),
    ('Fix /etc/hosts/x reader', 'absolute path'), ('A', 'fix-a is already recorded'),
])
def test_fix_refuses(day, capsys, title, reason):
    from wuwei.__main__ import main
    assert main(['note', '--fix', title]) == 1
    assert reason in capsys.readouterr().err
    assert findings(day) == {}


def test_note_needs_a_verb_or_fix(day, capsys):
    from wuwei.__main__ import main
    assert main(['note']) == 2
    assert '--fix "<title>"' in capsys.readouterr().err


def test_findings_are_reserved(day, capsys):
    from wuwei import state
    from wuwei.__main__ import main
    assert main(['event', 'finding.noted', '{}']) == 1
    assert 'finding.noted: reserved; written by wuwei note --fix' in capsys.readouterr().err
    with pytest.raises(state.StateError, match='reserved; written by wuwei note --fix'):
        state.set_state('seat_findings', '{}', day)
