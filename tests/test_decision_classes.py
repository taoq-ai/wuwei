"""#530 part A: decision classes (MIT CISR) and who decides under autonomy.mode."""

import json
from types import SimpleNamespace

import pytest

from test_decision import VALID, LENS_BLOCK, SUPERVISED, save, events

TIE = (('| 10 | 8 | 2 |', '| 10 | 5 | 5 |'), ('| 2 | 3 | 5 |', '| 2 | 5 | 5 |'))
LEAD = (('| 10 | 8 | 2 |', '| 10 | 6 | 5 |'),)  # A 66, B 60: margin 0.05
EDGE = (('| 10 | 8 | 2 |', '| 10 | 8 | 5 |'), ('| 2 | 3 | 5 |', '| 2 | 3 | 6 |'))  # margin 0.2
BELOW = (('| 10 | 8 | 2 |', '| 10 | 8 | 6 |'), ('| 2 | 3 | 5 |', '| 2 | 3 | 2 |'))  # margin 0.18


def record(cls='design', door='two-way', radius='own branch', confidence='high', wants=(),
           by='seat'):
    text = (VALID.replace('Class: design', 'Class: ' + cls)
            .replace('Reversibility: two-way', 'Reversibility: ' + door)
            .replace('Blast radius: own branch', 'Blast radius: ' + radius)
            .replace('Confidence: high', 'Confidence: ' + confidence)
            .replace('Decided-by: seat', 'Decided-by: ' + by))
    if cls != 'design':
        text = text.replace(LENS_BLOCK, '')
    for old, new in wants:
        text = text.replace(old, new)
    return text


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.delenv('WUWEI_WORKSPACE', raising=False)
    monkeypatch.setenv('WUWEI_NOW', '2026-09-28T12:00:00+00:00')
    root = tmp_path / 'workspace'
    (root / '.wuwei').mkdir(parents=True)
    (root / '.wuwei/config.toml').write_text('')
    monkeypatch.chdir(root)
    return root


def route(root, capsys, ident='D-3'):
    from wuwei.__main__ import main
    code = main(['decision', 'route', ident])
    return code, capsys.readouterr().out.strip()


def test_autonomy_mode_key(ws):
    from wuwei import workspace
    assert workspace.load_config(ws)['autonomy']['mode'] == 'autonomous'
    (ws / '.wuwei/config.toml').write_text(SUPERVISED)
    assert workspace.load_config(ws)['autonomy']['mode'] == 'supervised'
    (ws / '.wuwei/config.toml').write_text('[autonomy]\nmode = "sometimes"\n')
    with pytest.raises(workspace.ConfigError):
        workspace.load_config(ws)


@pytest.mark.parametrize('wants,expected', [((), 56 / 120), (TIE, 0.0), (EDGE, 0.2)])
def test_margin(wants, expected):
    from wuwei import decision
    fields, scores = decision.evaluate(record(wants=wants))
    assert decision.margin(fields, scores) == pytest.approx(expected)


@pytest.mark.parametrize('kwargs,expected', [
    (dict(cls='retry', door='one-way', confidence='low', wants=TIE), 'Strategic'),
    (dict(cls='approach', door='unsure', radius='repository'), 'Routine'),
    (dict(cls='park', confidence='low'), 'Routine'),
    (dict(cls='accept-residual', door='unsure', wants=TIE), 'Routine'),
    (dict(cls='accept-residual', door='one-way'), 'Consequential'),
    ({}, 'Routine'),
    (dict(radius='Own branch and PR.'), 'Routine'),
    (dict(radius='own PR'), 'Routine'),
    (dict(radius='item DIV-1'), 'Routine'),
    (dict(radius='day'), 'Routine'),
    (dict(wants=EDGE), 'Routine'),
    (dict(radius='repository'), 'Consequential'),
    (dict(radius='outside'), 'Consequential'),
    (dict(radius='scope agreed with others'), 'Consequential'),
    (dict(door='one-way'), 'Consequential'),
    (dict(door='unsure'), 'Consequential'),
    (dict(confidence='low'), 'Exploratory'),
    (dict(wants=BELOW), 'Exploratory'),
    (dict(radius='item DIV-1', wants=TIE), 'Exploratory'),
    (dict(door='one-way', confidence='low'), 'Strategic'),
    (dict(radius='repository', wants=LEAD), 'Strategic'),
])
def test_cisr(kwargs, expected):
    from wuwei import decision
    assert decision.cisr(*decision.evaluate(record(**kwargs))) == expected


@pytest.mark.parametrize('text', [
    VALID.replace('Recommendation: A\n', ''), VALID.replace('Recommendation: A', 'Recommendation: '),
    VALID.replace('Reasoning: Correctness decided it. A risky fix would flip it to B.\n', '')],
    ids=['missing', 'blank', 'no-reasoning'])
def test_lint_needs_recommendation_and_reasoning(text):
    from wuwei import decision
    code, message = decision.lint(text)
    assert code == 1 and 'add the recommendation and the reasoning' in message


def test_lint_names_the_class_and_accepts_mandate():
    from wuwei import decision
    assert decision.lint(VALID) == (0, 'OK: A (86), Routine')
    assert decision.lint(VALID.replace('Decided-by: seat', 'Decided-by: mandate')) == (0, 'OK: A (86), Routine')
    assert decision.lint(record(door='one-way', confidence='low')) == (0, 'OK: A (86), Strategic')


@pytest.mark.parametrize('cls', ['retry', 'approach', 'park'])
def test_routine_is_taken_under_mandate(ws, capsys, cls):
    from wuwei import state
    path = save(ws, record(cls=cls, door='unsure', radius='item DIV-1'))
    assert route(ws, capsys) == (0, 'mandate')
    data = state.read_state(ws)
    outcome = data['decision_outcomes']['D-3']
    assert outcome['decided_by'] == 'mandate' and outcome['cisr'] == 'Routine' and outcome['option'] == 'A'
    kinds = [row['kind'] for row in events(ws)]
    assert kinds.count('decision.decided') == 1 and 'decision.routed' not in kinds
    payload = next(row['payload'] for row in events(ws) if row['kind'] == 'decision.decided')
    assert payload['decided_by'] == 'mandate' and payload['cisr'] == 'Routine'
    assert not data.get('decision_routes')
    text = path.read_text()
    assert 'Decided-by: mandate' in text and 'Outcome: A' in text
    from wuwei.__main__ import main
    assert main(['decision', 'show', 'D-3', '--widget']) == 0
    assert json.loads(capsys.readouterr().out) == []


@pytest.mark.parametrize('kwargs,expected,kind', [
    (dict(door='one-way'), 'owner', 'Consequential'),
    (dict(door='unsure'), 'owner', 'Consequential'),
    (dict(radius='outside'), 'mandate', 'Consequential'),
    (dict(cls='approach', door='one-way', radius='outside, client email', confidence='low', wants=TIE),
     'owner', 'Strategic'),
    (dict(by='owner', radius='outside'), 'owner', 'Consequential'),
    (dict(radius='item DIV-1', wants=LEAD), 'mandate', 'Exploratory'),
    (dict(radius='item DIV-1', wants=TIE), 'owner', 'Exploratory'),
    (dict(wants=TIE), 'seat', 'Exploratory'),
    (dict(door='one-way', confidence='low'), 'owner', 'Strategic'),
])
def test_who_decides_follows_the_class(ws, capsys, kwargs, expected, kind):
    from wuwei import state
    save(ws, record(**kwargs))
    assert route(ws, capsys) == (0, expected)
    data = state.read_state(ws)
    if expected == 'owner':
        assert data['decision_routes']['D-3']['cisr'] == kind
        assert not data.get('decision_outcomes')
        assert next(row for row in events(ws) if row['kind'] == 'decision.routed')['payload']['cisr'] == kind
    else:
        assert data['decision_outcomes']['D-3']['decided_by'] == expected
        assert data['decision_outcomes']['D-3']['cisr'] == kind


@pytest.mark.parametrize('cls', ['retry', 'approach', 'park'])
def test_supervised_keeps_the_cards(ws, capsys, cls):
    from wuwei import state
    (ws / '.wuwei/config.toml').write_text(SUPERVISED)
    save(ws, record(cls=cls, radius='item DIV-1'))
    assert route(ws, capsys) == (0, 'owner')
    data = state.read_state(ws)
    assert data['decision_routes']['D-3']['cisr'] == 'Routine'
    assert not data.get('decision_outcomes')


def test_supervised_seat_route_carries_the_class(ws, capsys):
    from wuwei import state
    (ws / '.wuwei/config.toml').write_text(SUPERVISED)
    save(ws)
    assert route(ws, capsys) == (0, 'seat')
    outcome = state.read_state(ws)['decision_outcomes']['D-3']
    assert outcome['decided_by'] == 'seat' and outcome['cisr'] == 'Routine'


def test_a_repeat_route_writes_nothing(ws, capsys):
    path = save(ws, record(door='one-way', confidence='low'))
    assert route(ws, capsys) == (0, 'owner')
    path.write_text(VALID)
    before = len(events(ws))
    assert route(ws, capsys) == (0, 'owner')
    assert len(events(ws)) == before
    save(ws, record(cls='retry'), name='D-4.md')
    assert route(ws, capsys, 'D-4') == (0, 'mandate')
    before = len(events(ws))
    assert route(ws, capsys, 'D-4') == (0, 'mandate')
    assert len(events(ws)) == before


def test_owner_reverses_a_mandate_decision(ws, capsys, monkeypatch):
    from wuwei import state
    from wuwei.commands.decision import owner_outcome
    save(ws, record(cls='retry', door='unsure'))
    assert route(ws, capsys) == (0, 'mandate')
    monkeypatch.setattr('wuwei.integrity._host_confirm', lambda value, **kwargs: True)
    assert owner_outcome(SimpleNamespace(id='D-3', option='B'), root=ws) == (0, 'B')
    assert events(ws)[-1]['kind'] == 'decision.reversed'
    assert state.read_state(ws)['decision_outcomes']['D-3']['decided_by'] == 'owner'


SCANNER = """Question: How should this critical tool sequence be investigated?
Class: other
Context: Affected reserved items parked where active.
Chain: Read -> Bash
Session digest: abc
Options:
| Option | Title | Rationale | Consequence |
| --- | --- | --- | --- |
| investigate | Investigate the session | Resolves the potential exposure while affected work stays paused. | The session is reviewed and any exposure contained. |
| defer | Defer investigation | Keeps work paused but leaves the exposure unresolved. | Affected work stays paused until someone investigates. |
Musts:
| Criterion | investigate | defer |
| --- | --- | --- |
| Keep affected work paused | pass | pass |
Wants:
| Criterion | Weight | investigate | defer |
| --- | --- | --- | --- |
| Resolve potential exposure | 10 | 10 | 0 |
Recommendation: investigate
Reasoning: Resolving the potential exposure decided it; nothing safer would flip it.
Confidence: high
Reversibility: unsure
Blast radius: workspace security
Pre-mortem: Further activity could expose data.
Revisit: Before resuming affected work.
Decided-by: owner
Outcome: pending
"""


def test_a_security_finding_still_asks_the_owner(ws, capsys):
    # Review F1: a record the CLI wrote for the owner is never taken under the mandate.
    from wuwei import state
    from wuwei.__main__ import main
    path = save(ws, SCANNER)
    assert route(ws, capsys) == (0, 'owner')
    data = state.read_state(ws)
    assert 'D-3' in data['decision_routes'] and not data.get('decision_outcomes')
    assert 'Decided-by: owner' in path.read_text() and 'Outcome: pending' in path.read_text()
    assert main(['decision', 'show', 'D-3', '--widget']) == 0
    assert json.loads(capsys.readouterr().out) != []


def test_a_mandate_park_keeps_its_disposition(ws, capsys):
    # Review F2: the Outcome line holding a disposition survives, and next drops the item.
    from wuwei import state
    from wuwei.commands.next import approved
    path = save(ws, record(cls='park', radius='item DIV-1').replace('Outcome: pending', 'Outcome: parked DIV-1'))
    assert route(ws, capsys) == (0, 'mandate')
    assert 'Outcome: parked DIV-1' in path.read_text() and 'Decided-by: mandate' in path.read_text()
    data = state.read_state(ws)
    assert data['decision_outcomes']['D-3']['item_disposition'] == 'parked DIV-1'
    assert approved({**data, 'approved_items': ['DIV-1'], 'items': {'DIV-1': {}}}) == []
